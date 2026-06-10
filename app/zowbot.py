# ============================================================================
# Standard Library Imports
# ============================================================================
import asyncio
import inspect
import json
import logging
import os
import sys
import threading
import time
import traceback
import uuid
from typing import Dict, List




# ============================================================================
# Third-Party Imports
# ============================================================================
import names
import socks
from axolotl.util.keyhelper import KeyHelper

# ============================================================================
# Protocol Buffer Imports
# ============================================================================
from proto import zowsup_pb2

# ============================================================================
# Local Imports - Core
# ============================================================================
from core.common.tools import Jid, WATools
from core.layers import YowLayerEvent
from core.layers.network import YowNetworkLayer
from core.profile.profile import YowProfile
from core.stacks import YowStackBuilder

# ============================================================================
# Local Imports - App
# ============================================================================
from app.bot_env import BotEnv
from app.device_env import DeviceEnv
from app.network_env import NetworkEnv
from app.param_not_enough_exception import ParamsNotEnoughException
from app.layer.zowbot_layer import ZowBotLayer
from app.zowbot_values import ZowBotStatus, ZowBotType
from common.utils import Utils

# ============================================================================
# Local Imports - Configuration
# ============================================================================
from conf.constants import SysVar

logger = logging.getLogger(__name__)

class BotCmd:
    def __init__(self, cmd , desc, order = 0):
        self.cmd  = cmd
        self.desc = desc
        self.order = order
    def __call__(self, fn):
        fn.cmd = self.cmd
        fn.desc = self.desc
        fn.order = self.order
        return fn   
        
class ZowBot: 
                    
    def __init__(self,bot_id,env,bot_type=ZowBotType.TYPE_RUN_SINGLETON,auto=False):     
        self.botId = bot_id          

        self.logger = logging.getLogger(("BOT-"+self.botId) if self.botId is not None else __name__)
                      
        stackBuilder = YowStackBuilder()
        self.botLayer = ZowBotLayer(self)        
        self.env = env if env is not None else BotEnv(deviceEnv=DeviceEnv("android"),networkEnv=NetworkEnv("direct"))

        self.auto = auto    #是否自动登录

        osName = self.env.deviceEnv.getOSName()
        
        self.idType = Utils.getIdTypeByOsName(osName)

        if self.botId is not None:   
            path = SysVar.TMP_ACCOUNT_PATH if bot_type==ZowBotType.TYPE_RUN_TEMP else SysVar.ACCOUNT_PATH 
            self.profile = YowProfile(path+self.botId)   
            self.env.networkEnv.updateProxyByWaNum(self.botId)            
            self.botLayer.db = self.profile.axolotl_manager  

        
            
        self._stack = stackBuilder\
            .pushDefaultLayers()\
            .push(self.botLayer)\
            .build()
                
        
        

        self._stack.setProp("env",self.env)        
        self._stack.setProp("ID_TYPE",self.idType)
        self.bot_type = bot_type              
              
        self.inloop = False                      
        self.pairPhoneNumber=None
        self.pairLinkCode=None
        self.cmdEventMap = {}
        self.status = ZowBotStatus.STATUS_INITIAL
        self.conflict = False
        self.quitIfConflict = False
        self.thread = None
        self.startts = time.time() 
        self.wa_old = None        

        self.callback = self.onCallback          
        self.upperCallback = None        
        self._exit_code = None  # For graceful exit from callback (None = no exit requested)

        self.lastOnlineTime = None        
        
        if self.bot_type==ZowBotType.TYPE_REG_COMPANION_SCANQR or self.bot_type==ZowBotType.TYPE_REG_COMPANION_LINKCODE:                        
            identity = KeyHelper.generateIdentityKeyPair()
            self._stack.setProp("reg_info",{
                "keypair":WATools.generateKeyPair(),
                "regid": KeyHelper.generateRegistrationId(False),
                "identity": identity,            
                "signedprekey": KeyHelper.generateSignedPreKey(identity,0)
            })
        
        self._stack.setProp("botType",self.bot_type)

        self.cmdList = {}
        self._command_queue = None  # Will be initialized in _async_run
        self._cmd_args_for_exec = None  # Command-line args for AsyncCommandExec
        self._cmd_options_for_exec = None  # Options for AsyncCommandExec
        if self.botId is not None:
            self._stack.setProfile(self.profile)
            # Auto-load commands from zowbot_cmd directory
            from app.zowbot_cmd import load_commands
            load_commands(self)       


    def runAsThread(self,daemon=False):
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = daemon              
        self.thread.start()      
     
    def onCallback(self,event=None,message=None,messageStatus=None,cmdResult=None,modeResult=None):


        if event is not None:            
            if event.get("detail") is not None:
                self.logger.info("Event {}, detail={}".format(zowsup_pb2.BotEvent.Event.Name(event["event"]),json.dumps(event["detail"])))                    
            else:
                self.logger.info("Event {}".format(zowsup_pb2.BotEvent.Event.Name(event["event"])))
            
                                
        if message is not None:            
            self.logger.info("Receive {} message \"{}\" from {} to {}".format(zowsup_pb2.MessageType.Name(message["type"]),message["text"],message["from"],message["to"]))              

        if messageStatus is not None:
            if messageStatus.get("errorCode") is not None:
                self.logger.info("Message(ID={}) status:{}-{} from {}".format(messageStatus["msgId"],zowsup_pb2.MessageStatus.Name(messageStatus["status"]),messageStatus["errorCode"],messageStatus["target"]))
            else:
                self.logger.info("Message(ID={}) status:{} from {}".format(messageStatus["msgId"],zowsup_pb2.MessageStatus.Name(messageStatus["status"]),messageStatus["target"]))

        
        if self.upperCallback is not None:
            try:
                loop = asyncio.get_running_loop()

                future = loop.run_in_executor(None, lambda: self.upperCallback(
                    event=event,message=message,messageStatus=messageStatus,
                    cmdResult=cmdResult,modeResult=modeResult,cbId=self.botId
                ))

                def _handle_callback_exception(f):
                    try:
                        result = f.result()
                        # Check if callback wants to exit (should_exit flag)
                        if isinstance(result, tuple) and len(result) >= 2:
                            should_exit, exit_code = result[0], result[1]
                            if should_exit:
                                self.logger.info(f"Callback requested exit with code {exit_code}")                                
                                self._exit_code = exit_code
                                self.disconnect()
                    except SystemExit as e:
                        # Expected when callback calls exit() �� log and exit gracefully
                        self.logger.info(f"Callback triggered SystemExit({e.code})")
                        exit_code = e.code if e.code is not None else 0
                        self._exit_code = exit_code
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}", exc_info=True)
                future.add_done_callback(_handle_callback_exception)
            except RuntimeError:                
                self.upperCallback(event=event,message=message,messageStatus=messageStatus,
                                   cmdResult=cmdResult,modeResult=modeResult,cbId=self.botId)

            
    def getCmdList(self):
        return self.cmdList

    def run(self):     
        
        if self.bot_type==ZowBotType.TYPE_REG_COMPANION_SCANQR or self.bot_type==ZowBotType.TYPE_REG_COMPANION_LINKCODE:
            self.logger.info("Pairing-Device Registration Start")
        else:
            self.logger.info("Login start")           

        try:
            exit_code = asyncio.run(self._async_run())
            # If callback requested exit with a specific code, exit with that code
            if exit_code is not None and exit_code != 0:
                sys.exit(exit_code)
        except KeyboardInterrupt:
            self.inloop = False

    async def _command_runner_loop(self):
        """
        Background task to execute commands from the async queue.
        Allows external threads to push commands via push_command() instead of direct calls.
        """
        if self._command_queue is None:
            return
            
        try:
            while True:
                try:
                    # Get command from queue with small timeout to allow shutdown
                    cmd_item = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                    if cmd_item is None:  # Sentinel value to stop
                        break
                    
                    cmd_name, args, options, future = cmd_item
                    try:
                        # Execute command through sendLayer
                        result, errMsg = self.callDirectCompat(cmd_name, args, options, timeout=20)
                        future.set_result((result, errMsg))
                    except Exception as e:
                        future.set_exception(e)
                        
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
        except Exception as e:
            self.logger.error(f"Command runner loop error: {e}", exc_info=True)

    async def _agent_command_queue_loop(self):
        """Poll file-based command queue and execute commands inside this running bot process."""
        if not self.botId:
            return
        try:
            from script.command_queue import dequeue_command_tasks, write_command_result
        except Exception as e:
            self.logger.debug(f"Command queue module not available: {e}")
            return

        while True:
            try:
                tasks = dequeue_command_tasks(self.botId)
                if not tasks:
                    await asyncio.sleep(0.5)
                    continue

                for task in tasks:
                    task_id = str(task.get("id", ""))
                    cmd_name = str(task.get("command", "")).strip()
                    args = task.get("args")
                    options = task.get("options")
                    args = list(args) if isinstance(args, list) else []
                    options = dict(options) if isinstance(options, dict) else {}

                    if not task_id:
                        continue

                    if cmd_name not in self.cmdList:
                        write_command_result(task_id, False, error=f"command not found: {cmd_name}")
                        continue

                    try:
                        fn = self.cmdList[cmd_name]
                        if inspect.iscoroutinefunction(fn):
                            result = await fn(args, options)
                            write_command_result(task_id, True, result=result)
                        else:
                            write_command_result(task_id, False, error=f"command is not async: {cmd_name}")
                    except ParamsNotEnoughException:
                        write_command_result(task_id, False, error="params not enough")
                    except Exception as e:
                        write_command_result(task_id, False, error=str(e))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.debug(f"Command queue poll error: {e}")
                await asyncio.sleep(1.0)

    def push_command(self, cmd_name, args, options, timeout=20):
        """
        Push a command to the async queue for execution.
        
        Args:
            cmd_name: Name of command to execute
            args: List of arguments
            options: Dict of options
            timeout: Timeout in seconds
            
        Returns:
            asyncio.Future that will contain (result, errMsg) when complete
        """
        if self._command_queue is None:
            raise RuntimeError("Command queue not initialized - bot not running")
            
        future = asyncio.Future()
        self._command_queue.put_nowait((cmd_name, args, options, future))
        return future

    async def _async_run(self):
        # Initialize command queue and start command runner task
        if self._command_queue is None:
            self._command_queue = asyncio.Queue()
        
        command_runner_task = asyncio.ensure_future(self._command_runner_loop())
        command_exec_task = None  # For command-line argument execution
        
        # If command-line arguments provided, create command execution task
        if self._cmd_args_for_exec:
            from app.async_command_exec import AsyncCommandExec
            command_exec = AsyncCommandExec(self, self._cmd_args_for_exec, self._cmd_options_for_exec or {})
            command_exec_task = asyncio.ensure_future(command_exec.run())

        command_queue_task = None
        if self.botId is not None:
            command_queue_task = asyncio.ensure_future(self._agent_command_queue_loop())
        
        try:
            while True:                     
                try :                                        
                    self.inloop = True                                  
                    await self._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))                                                  

                    if self._exit_code is not None:                        
                        break

                    # If command-line execution, use shorter timeout to check completion
                    if command_exec_task:
                        # Create a combined wait for either loop completion or command completion
                        loop_task = asyncio.ensure_future(self._stack.loop())
                        done, pending = await asyncio.wait(
                            [loop_task, command_exec_task],
                            return_when=asyncio.ALL_COMPLETED
                        )

                        # Cancel pending tasks
                        #for task in pending:
                        #    task.cancel()
                        self.logger.info("Command execution completed, exiting...")                                                                        

                    else:
                        await self._stack.loop()           #last few events to process
                                        
                    if self.botLayer.getProp("QUITTED") or self.botLayer.getProp("THREADQUIT"):                                 
                        break                                         
                except KeyboardInterrupt:                      
                    self.inloop = False                
                    await self._async_disconnect()       
                    break     
                except socks.SOCKS5Error:
                    self.logger.info("PROXY ERROR") 
                except OSError:
                    logger.info("OSError")
                    self.inloop = False 
                    await self._async_disconnect()              
                    break
        finally:
            # Clean up command runner task (only if event loop is still running)
            try:
                if not command_runner_task.done():
                    command_runner_task.cancel()
                    try:
                        await command_runner_task
                    except asyncio.CancelledError:
                        pass
                
                # Clean up command execution task
                if command_exec_task and not command_exec_task.done():
                    command_exec_task.cancel()
                    try:
                        await command_exec_task
                    except asyncio.CancelledError:
                        pass

                if command_queue_task and not command_queue_task.done():
                    command_queue_task.cancel()
                    try:
                        await command_queue_task
                    except asyncio.CancelledError:
                        pass
            except RuntimeError:
                # Event loop is closed, can't cancel tasks
                pass
            
            # Return exit code if callback requested exit, otherwise 0
            return self._exit_code if self._exit_code is not None else 0

    def wait_logged_in(self, timeout: float = 30.0) -> bool:
        """Block until the bot finishes login, or timeout expires.
        Thread-safe: callable from any thread.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.botLayer.loginEventComplete:
                return True
            time.sleep(0.2)
        return False

    def setUpperCallback(self,upperCallback):
        self.upperCallback = upperCallback            
               
    def getStatus(self):        
        return self.status        
    
    def getLastOnlineTime(self):
        return self.lastOnlineTime  
    
    def getBotType(self):
        return self.bot_type
    
    @staticmethod
    def printUsageStatic():
        """Static method to print usage without requiring a bot instance.
        Used at startup when no bot is initialized yet."""
        from app.zowbot_cmd import load_commands
        
        # Create a minimal bot-like object just to load commands
        class MinimalBot:
            pass
        
        bot = MinimalBot()
        bot.botId = None
        bot.cmdList = {}
        bot.cmdMetadata = {}
        
        try:
            load_commands(bot)
        except Exception as e:
            print(f"Error loading commands: {e}")
            return
        
        if not bot.cmdList:
            print("No commands available.")
            return
        
        sorted_cmds = sorted(bot.cmdList.keys())
                
        for cmd_name in sorted_cmds:
            if hasattr(bot, 'cmdMetadata') and cmd_name in bot.cmdMetadata:
                description = bot.cmdMetadata[cmd_name].get('description', '')
            else:
                cmd_func = bot.cmdList[cmd_name]
                description = getattr(cmd_func, 'desc', '')
            
            print("|  {}|\t{}|".format(cmd_name.ljust(28, ' '), description.ljust(50, ' ')))

    def disconnect(self):        
        """Disconnect the bot. Use quit() instead for external thread calls."""
        asyncio.run_coroutine_threadsafe(self._async_disconnect(), self.botLayer.getStack().getLoop())

    async def _async_disconnect(self):
        """Async version for use within the event loop."""
        self.status=ZowBotStatus.STATUS_STOPPING
        self.botLayer.setProp("USER_REQUEST_QUIT",True)
        if self.inloop:
            await self._stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
        else:
            await self.botLayer.onDisconnected(YowLayerEvent(YowNetworkLayer.EVENT_STATE_DISCONNECT))
      
    def quit(self):               
        """Public API to disconnect from external thread."""
        self.disconnect()

    def setMode(self,mode,upperCallback=None):
        self.botLayer.setProp(mode,True)  #HC_MODE,TRANSFER6_MODE
        self.upperCallback = upperCallback       

    def callDirectCompat(self, name, params, options, timeout=20):
        """
        Compatibility wrapper for calling both async and sync commands from threading context.
        
        For async commands: uses asyncio.run_coroutine_threadsafe to execute in event loop
        For sync commands: calls directly
        
        Returns: (result_dict, error_dict) tuple
        Designed for use in threading.Thread context (e.g., InteractiveThread).
        """
        try:
            fn = self.cmdList[name] if name in self.cmdList else None
            if fn is None:
                logger.info("command {} not found".format(name))
                return None, {"code": -2, "msg": "Command Not Found"}
            
            try:
                # Check if function is a coroutine function (async def)
                if inspect.iscoroutinefunction(fn):
                    # Execute async function in event loop from threading context
                    loop = self.botLayer.getStack().getLoop()
                    if loop is None:
                        return None, {"code": -5, "msg": "Event loop not available"}
                    
                    coro = fn(params, options)
                    future = asyncio.run_coroutine_threadsafe(coro, loop)
                    
                    try:
                        # Wait for result with timeout
                        result = future.result(timeout=timeout)
                        return result, None
                    except asyncio.TimeoutError:
                        return None, {"code": -999, "msg": f"async command timeout after {timeout}s"}
                    except Exception as e:
                        return None, {"code": -4, "msg": f"async command error: {str(e)}"}
                else:
                    return None, {"code": -3, "msg": "Command is not async"}
                
            except ParamsNotEnoughException:
                return None, {"code": -1, "msg": "Params Not Enough"}
        except:
            logger.info("command {} exception: {}".format(name, traceback.format_exc()))
            return None, {"code": -2, "msg": "exception"}            



    

        
    def setCmdError(self,cmdId,error):
        if cmdId in self.cmdEventMap: 
            obj = self.cmdEventMap[cmdId]
            obj["error"] = error         
            obj["event"].set()  

    def setCmdResult(self,cmdId,result):

        if cmdId in self.cmdEventMap:            
            obj = self.cmdEventMap[cmdId]
            obj["result"] = result
            if obj["event"]:
                if obj["event"]=="callback":
                    self.callback(cmdResult={
                        "botId": self.botId,
                        "cmdId":cmdId,
                        "result":result,
                        "timestamp":int(time.time())
                    })
                else:                                   
                    obj["event"].set()    
        else:
            e = asyncio.Event()
            e.set()            
            self.cmdEventMap[cmdId] = {"result":result,"event":e}          




if __name__ == "__main__":    
    
    SysVar.loadConfig()  

    # default-env  android,direct
    env = BotEnv(
        deviceEnv = DeviceEnv("android",random=True), 
        networkEnv = NetworkEnv(NetworkEnv.TYPE_DIRECT)
    )

    bot = ZowBot(bot_id="212719800440",env=env)

    bot.run()
    

    
        


                            

                            






