import os,sys
sys.path.append(os.getcwd())
from unicodedata import name
from conf.constants import SysVar

from common.utils import Utils
from core.profile.profile import YowProfile
from app.device_env import DeviceEnv
from app.zowbot_values import ZowBotStatus

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)))

import logging
import threading
import json
import shlex
import inspect
import asyncio
import time
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.output import create_output
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class CommandCompleter(Completer):
    """
    Custom completer for bot commands with descriptions.
    - Provides command name completion (including dot-separated commands like misc.prekeycount)
    - Stops providing completions after space (parameter section)
    - Provides sorted command list with descriptions as meta info
    """
    
    def __init__(self, bot):
        """
        Args:
            bot: ZowBot instance with cmdList dict
        """
        self.bot = bot
    
    def get_completions(self, document: Document, complete_event):
        """
        Get completions for the current document.
        - Provide completions for command names (including dots like misc.prekeycount)
        - Stop providing completions after space (parameters section)
        """
        # Get the text before cursor
        text_before_cursor = document.text_before_cursor
        
        # Don't provide completions if there's a space (parameters section)
        if ' ' in text_before_cursor:
            return
        
        if not hasattr(self.bot, 'cmdList') or not self.bot.cmdList:
            return
        
        # Get all command names
        cmd_names = sorted(self.bot.cmdList.keys())
        
        # Find matching commands
        text_lower = text_before_cursor.lower()
        for cmd_name in cmd_names:
            if cmd_name.lower().startswith(text_lower):
                # Get metadata (description)
                cmd_obj = self.bot.cmdList[cmd_name]
                desc = getattr(cmd_obj, 'desc', '')
                
                yield Completion(
                    cmd_name,  # 完整的单词
                    start_position=-len(text_before_cursor),
                    display=cmd_name,
                    display_meta=desc
                )


class InteractiveThread:
    
    # Built-in commands available in interactive mode
    BUILTIN_COMMANDS = [
        ("help", "Show this help message"),
        ("exit", "Exit the interactive mode"),
        ("connect", "Connect to a WhatsApp account"),
        ("disconnect", "Disconnect the current account")
    ]

    def __init__(self, bot, env=None,  main_instance=None):                                
        self.bot = bot            
        self.env = env  # BotEnv instance for creating new bots        
        self.main_instance = main_instance  # Reference to Main instance for account operations
        self.thread = threading.Thread(target=self._run_thread_wrapper)
        self.thread.daemon = True
        self._history_file = Path.home() / ".zowbot_history"
        self._patch_context = None
        self._patched_stream_handlers = []
        self.logger = bot.logger if bot else logging.getLogger(__name__)
        self._already_disconnected = False  # Flag to prevent duplicate disconnect calls
        self._event_loop = None  # Event loop reference for signal handling

    def _iter_stream_handlers(self):
        """Yield all StreamHandlers from root and child loggers."""
        seen = set()

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and id(handler) not in seen:
                seen.add(id(handler))
                yield handler

        for logger_name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(logger_name)
            if logger_obj.handlers:
                for handler in logger_obj.handlers[:]:
                    if isinstance(handler, logging.StreamHandler) and id(handler) not in seen:
                        seen.add(id(handler))
                        yield handler

    def _setup_stdout_patch(self):
        """
        Setup stdout patching for stable prompt display during background output.
        This also reconfigures any existing StreamHandlers to use the patched stdout.
        Must be called AFTER patch_stdout context is entered to refresh handlers.
        """
        try:
            self.logger.debug("Setting up stdout patch...")
            # Keep original streams so we can restore them before exiting patch_stdout.
            self._patched_stream_handlers = []
            for handler in self._iter_stream_handlers():
                try:
                    stream = getattr(handler, "stream", None)
                    if stream is None:
                        continue
                    if stream == sys.__stdout__ or "stdout" in str(stream).lower():
                        self._patched_stream_handlers.append((handler, stream))
                        handler.setStream(sys.stdout)
                except (AttributeError, TypeError):
                    continue
            
            self.logger.debug(f"Patched {len(self._patched_stream_handlers)} stream handlers")
            return True
        except Exception as e:
            self.logger.warning(f"Failed to setup stdout patch: {e}")
            return False

    def _restore_stdout_patch(self):
        """Restore StreamHandlers changed by _setup_stdout_patch()."""
        for handler, original_stream in reversed(self._patched_stream_handlers):
            try:
                handler.setStream(original_stream)
            except Exception:
                continue
        self._patched_stream_handlers = []
    
    def _get_completer(self):
        """Get CommandCompleter - includes both dynamic and built-in commands"""
        # Create completer from available commands
        try:
            from app.zowbot_cmd import load_commands
            
            # Start with actual bot commands or create minimal bot
            if self.bot and self.bot.botId is not None:
                # Use actual bot if connected
                bot_for_completer = self.bot
            else:
                # Create a minimal bot-like object to load commands
                class MinimalBot:
                    pass
                
                bot_for_completer = MinimalBot()
                bot_for_completer.botId = None
                bot_for_completer.cmdList = {}
                bot_for_completer.cmdMetadata = {}
                load_commands(bot_for_completer)
            
            # Add built-in commands (which are not in cmdList)
            builtin_commands_dict = {
                cmd_name: type('obj', (object,), {'desc': description})()
                for cmd_name, description in self.BUILTIN_COMMANDS
            }
            
            # Ensure cmdList has built-in commands
            if not hasattr(bot_for_completer, 'cmdList'):
                bot_for_completer.cmdList = {}
            bot_for_completer.cmdList.update(builtin_commands_dict)
            
            return CommandCompleter(bot_for_completer)
        except Exception as e:
            self.logger.debug(f"Failed to create completer: {e}")
            return None

    def waitLogin(self):
        if self.bot is None:
            return False
        return self.bot.waitLogin()
    
    def _run_thread_wrapper(self):
        """Wrapper to run async event loop in thread context"""
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Set debug mode False to suppress RuntimeWarnings
        loop.set_debug(False)
        
        # Suppress concurrent.futures logger to avoid "Event loop is closed" errors from callbacks
        import logging
        cf_logger = logging.getLogger("concurrent.futures")
        cf_logger.setLevel(logging.CRITICAL)  # Only show critical errors, not ERROR logs
        
        # Store loop reference for signal handler
        self._event_loop = loop
        
        try:
            # Add signal handler for Ctrl+C to gracefully shutdown
            try:
                import signal
                if threading.current_thread() is threading.main_thread():
                    loop.add_signal_handler(
                        signal.SIGINT,
                        self._handle_interrupt,
                        loop
                    )
                    self.logger.debug("Signal handler registered for Ctrl+C")
                else:
                    # asyncio signal handlers are only valid on the main thread.
                    self.logger.debug("Skipping signal handler registration in non-main thread")
            except (NotImplementedError, ValueError, RuntimeError) as e:
                # Signal handlers may be unsupported on this platform/runtime.
                self.logger.debug(f"Signal handler not available: {e}")
            
            loop.run_until_complete(self._async_main())            
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user (Ctrl+C)")
        finally:
            # Cancel any remaining tasks to avoid "Task was destroyed" warnings
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Run loop briefly to process cancellations
                loop.run_until_complete(asyncio.sleep(0))
            except:
                pass
            finally:
                # Suppress RuntimeWarnings during loop close
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    loop.close()
                self._event_loop = None
    
    def _handle_interrupt(self, loop):
        """Handle SIGINT (Ctrl+C) signal - gracefully shutdown event loop"""
        self.logger.info("Received Ctrl+C signal, initiating shutdown...")
        # Stop the event loop
        loop.stop()
    
    async def _async_main(self):
        """Main async prompt loop - supports interactive account management"""
                                
        bot_task = None
        
        # If we have an initial bot, try to login
        if self.bot and self.bot.botId is not None:
            self.logger.info("Waiting BOT %s Login" % self.bot.botId)
            # Run bot in background task to handle its event loop
            bot_task = asyncio.ensure_future(self.bot._async_run())
            
            # Wait for login in the bot's event loop with timeout
            try:
                # Use wait_for with timeout to make the wait interruptible
                # Check status periodically (0.5s intervals) for 60 seconds max
                start_time = time.time()
                login_timeout = 60
                check_interval = 0.5
                
                while True:
                    elapsed = time.time() - start_time
                    if elapsed > login_timeout:
                        self.logger.info("BOT %s connection timeout" % self.bot.botId)
                        self.bot = None
                        break
                    
                    if self.bot.status == ZowBotStatus.STATUS_RUNNING:
                        self.logger.info("BOT %s ready." % self.bot.botId)
                        break
                    elif self.bot.status in (ZowBotStatus.STATUS_INITIAL, ZowBotStatus.STATUS_UNKNOWN):
                        # Use wait_for to make asyncio.sleep interruptible
                        try:
                            await asyncio.wait_for(asyncio.sleep(check_interval), timeout=check_interval + 0.1)
                        except asyncio.TimeoutError:
                            pass  # Expected - just continue the loop
                    elif self.bot.botLayer.detect40x:
                        self.logger.info("BOT %s login failed" % self.bot.botId)
                        self.bot = None
                        break
                    else:
                        break
                        
            except asyncio.CancelledError:
                self.logger.info("Login wait cancelled by user")
                self.bot = None
                raise
            except Exception as e:
                self.logger.info(f"BOT {self.bot.botId} login failed: {e}")
                self.bot = None
                self.bot = None
        else:
            self.logger.info("No initial account")
        
        # Create history file path
        history = FileHistory(str(self._history_file))
        
        # Create session with adaptive prompt
        try:
            output = create_output()
            self.logger.debug("Created output using create_output()")
        except Exception as e:
            self.logger.debug(f"create_output() failed ({type(e).__name__}), using None for auto-detection: {e}")
            output = None  # Let prompt_toolkit auto-detect
        
        # Apply patch_stdout globally for this thread context
        # Note: This may fail on non-standard consoles like PowerShell ISE
        patch_context = None
        use_patch_stdout = True
        try:
            patch_context = patch_stdout()
            patch_context.__enter__()
            self._patch_context = patch_context
            self.logger.debug("Successfully patched stdout")
        except Exception as e:
            self.logger.debug(f"patch_stdout() failed ({type(e).__name__}), continuing without patching: {e}")
            use_patch_stdout = False
            self._patch_context = None
        
        # After patching stdout (if successful), reconfigure logging handlers
        if use_patch_stdout:
            self._setup_stdout_patch()
                        
        # Determine which input method to use (PromptSession or standard input)
        # Try once to create a PromptSession; if it fails, use standard input
        use_prompt_session = False
        try:
            # Test if PromptSession can be created
            test_session = PromptSession(
                "test",
                history=history,
                complete_in_thread=False,
                output=output
            )
            use_prompt_session = True
            self.logger.debug("PromptSession available, will use it")
        except Exception as e:
            self.logger.debug(f"PromptSession not available ({type(e).__name__}), will use standard input: {e}")
            use_prompt_session = False
        
        try:
            while True:
                try:
                    # Get prompt text based on connection status
                    prompt_text = self._get_prompt()
                    
                    # Get input using the appropriate method
                    if use_prompt_session:
                        try:
                            # Get completer - will use generic one if no bot connected
                            completer = self._get_completer()
                            
                            session = PromptSession(
                                prompt_text,
                                completer=completer,
                                history=history,
                                complete_in_thread=False,
                                output=output
                            )
                            cmd = await session.prompt_async()
                        except Exception as e:
                            self.logger.debug(f"PromptSession failed, falling back to input: {e}")
                            use_prompt_session = False
                            cmd = await asyncio.get_event_loop().run_in_executor(None, input, prompt_text)
                    else:
                        # Use standard input
                        cmd = await asyncio.get_event_loop().run_in_executor(None, input, prompt_text)
                    
                    # Check for empty command first - if user just pressed Enter
                    if not cmd or not cmd.strip():
                        continue
                    
                    self.logger.debug(f"Received command: {cmd}")
                    cmd = "CMD " + cmd 
                    params, options = Utils.cmdLineParser(shlex.split(cmd))
                    
                except (EOFError, KeyboardInterrupt):
                    self.logger.info("CMD thread exception")   
                    self.logger.info("Exiting...")
                    await self._async_disconnect()
                    break
                except Exception as e:
                    self.logger.error(f"Error in prompt loop: {e}", exc_info=True)
                    # Try again without raising to continue the loop
                    continue

                if len(params) == 0:
                    continue

                if len(params) == 1 and params[0] == "exit":
                    await self._async_quit()
                    break

                if len(params) >= 1 and params[0] == "help":
                    await self._execute_help_command(params[1:] if len(params) > 1 else [], options)
                    continue

                # Handle account management commands 
                cmd_name = params[0]
                if cmd_name == "connect":
                    if cmd_name == "connect":
                        account_num = params[1] if len(params) > 1 else None
                    else:
                        account_num = params[2] if len(params) > 2 else None
                    
                    if not account_num:
                        self.logger.info("Usage: connect <phone_number> or account connect <phone_number>")
                        continue
                    
                    await self._async_connect_account(account_num, options)
                    continue
                
                if cmd_name == "disconnect":
                    await self._async_disconnect_account()
                    continue
                
                # Execute regular commands (require connected account)
                if self.bot and self.bot.botId is not None:
                    if len(params[0].strip()) > 0:
                        await self._execute_command(params[0], params[1:] if len(params) > 1 else [], options)
                else:
                    self.logger.info("No account connected. Use 'connect <phone_number>' to connect.")
                                                                   
        except asyncio.CancelledError:
            pass
        finally:            
            self.logger.debug("Interactive thread shutting down")
            
            # Gracefully disconnect bot before cleaning up task
            try:
                if self.bot and self.bot.botId is not None:
                    await self._async_disconnect()
            except Exception as e:
                self.logger.debug(f"Error during final disconnect: {e}")
            
            # Give bot_task time to complete gracefully
            if bot_task and not bot_task.done():
                try:
                    await asyncio.wait_for(bot_task, timeout=2)
                except asyncio.TimeoutError:
                    self.logger.debug("Bot task did not complete in time, cancelling...")
                    bot_task.cancel()
                    try:
                        await bot_task
                    except asyncio.CancelledError:
                        pass
                except Exception as e:
                    self.logger.debug(f"Error waiting for bot task: {e}")
            
            if self._patch_context:
                try:
                    self._restore_stdout_patch()
                    self._patch_context.__exit__(None, None, None)
                except Exception as e:
                    self.logger.error(f"Error cleaning up patch_stdout: {e}")
    
    def _get_prompt(self):
        """Get prompt text based on connection status"""
        if self.bot and self.bot.botId:
            return f"[{self.bot.botId}] CMD > "
        else:
            return "CMD > "
    
    async def _async_connect_account(self, account_num, options):
        """Connect to a WhatsApp account"""
        self.logger.info(f"Connecting to account: {account_num}")
        
        try:
            config_file = Path(SysVar.ACCOUNT_PATH + account_num + "/config.json")
            if not config_file.exists():
                self.logger.info(f"Account {account_num} does not exist locally")
                return     
            # Disconnect current bot if any and ensure cleanup
            if self.bot is not None:
                if self.bot.botId is not None:
                    await self._async_disconnect()
                    await asyncio.sleep(1)  # Give it time to disconnect
            
            # Ensure bot is None and reset disconnect flag for new account connection
            self.bot = None
            self._already_disconnected = False
            
            # Load profile to get environment settings
            profile = YowProfile(SysVar.ACCOUNT_PATH + account_num)
            if profile.config.os_name is not None:
                self.logger.info(f"Local Profile found - OS: {profile.config.os_name}")
                if self.env:
                    self.env.deviceEnv = DeviceEnv(SysVar.ENV_NAME_MAPPING.get(profile.config.os_name, "android"))
            
            # Create new bot for this account
            from app.zowbot import ZowBot
            from app.zowbot_values import ZowBotType
            
            self.bot = ZowBot(
                bot_id=account_num,
                env=self.env,
                bot_type=ZowBotType.TYPE_RUN_SINGLETON
            )
            
            
            self.logger.info(f"Waiting for account {account_num} to login...")
            
            # Run bot in background task to handle its event loop
            bot_task = asyncio.ensure_future(self.bot._async_run())
            
            try:
                # Check login status periodically (same as in _async_main)
                for attempt in range(60):  # 60 seconds = 120 * 0.5s waits
                    if self.bot.status == ZowBotStatus.STATUS_RUNNING:
                        self.logger.info(f"Account {account_num} ready.")
                        return
                    elif self.bot.status in (ZowBotStatus.STATUS_INITIAL, ZowBotStatus.STATUS_UNKNOWN):
                        await asyncio.sleep(0.5)
                    elif self.bot.botLayer.detect40x:
                        self.logger.info(f"Account {account_num} login failed")
                        # Clean up bot task on failure
                        if bot_task and not bot_task.done():
                            bot_task.cancel()
                            try:
                                await bot_task
                            except asyncio.CancelledError:
                                pass
                        self.bot = None
                        return
                    else:
                        break
                else:
                    # Timeout after 60 seconds
                    self.logger.info(f"Account {account_num} connection timeout")
                    # Clean up bot task on timeout
                    if bot_task and not bot_task.done():
                        bot_task.cancel()
                        try:
                            await bot_task
                        except asyncio.CancelledError:
                            pass
                    self.bot = None
                    return
            except Exception as e:
                self.logger.info(f"Account {account_num} login failed: {e}")
                # Clean up bot task on exception
                if bot_task and not bot_task.done():
                    bot_task.cancel()
                    try:
                        await bot_task
                    except asyncio.CancelledError:
                        pass
                self.bot = None
                
        except Exception as e:
            self.logger.error(f"Error connecting to account {account_num}: {e}", exc_info=True)
            self.bot = None
    
    async def _async_disconnect_account(self):
        """Disconnect current account"""
        if self.bot and self.bot.botId is not None:
            account = self.bot.botId
            self.logger.info(f"Disconnecting from account: {account}")
            await self._async_disconnect()
            self.logger.info(f"Disconnected from account: {account}")
            # Reset flag when switching accounts
            self._already_disconnected = False
        else:
            self.logger.info("No account currently connected")
    

    
    async def _execute_help_command(self, args, options):
        """Execute the help command - display built-in and dynamic commands"""
        import sys
        
                
        print("|   [command]                  |       [description]                                      |")
        print("|------------------------------|----------------------------------------------------------|")
        
        # Display built-in commands first
        for cmd_name, description in self.BUILTIN_COMMANDS:
            print("|  {}|\t{}|".format(cmd_name.ljust(28, ' '), description.ljust(50, ' ')))
        
        # Display dynamic commands        
        try:
            from app.zowbot import ZowBot
            ZowBot.printUsageStatic()
        except Exception as e:
            self.logger.error(f"Error executing help command: {e}", exc_info=True)
    
    async def _execute_command(self, cmd_name, args, options):
        """
        Execute a command asynchronously.
        
        Determines wait time based on command type and executes appropriately.
        """
        if not self.bot or not self.bot.botId:
            self.logger.info("Bot is not initialized for command execution")
            return
        
        waitTime = 0            

        if cmd_name == "init":                
            waitTime = 10                            
        elif cmd_name == "mdlink":
            waitTime = 60
        else:
            waitTime = 20

        if SysVar.CMD_WAIT is not None:                
            waitTime = SysVar.CMD_WAIT             
        
        try:
            # Get the command function from bot's command list
            fn = self.bot.cmdList.get(cmd_name)
            if fn is None:
                self.logger.info(f"Command {cmd_name} not found")
                return
            
            # Execute the command directly using await (since we're already in async context)
            # This avoids the threading issue with run_coroutine_threadsafe
            result = await asyncio.wait_for(fn(args, options), timeout=waitTime)            
            self.logger.info("Command {} complete, result={}".format(cmd_name, json.dumps(result)))

        except asyncio.TimeoutError:
            self.logger.info("Command {} error, info={{'code': -999, 'msg': 'async command timeout after {}s'}}".format(cmd_name, waitTime))
        except Exception as e:
            self.logger.error(f"Command {cmd_name} exception: {e}", exc_info=True)
    
    async def _async_disconnect(self):
        """Async disconnect wrapper - properly disconnect and allow event processing"""
        # Prevent duplicate disconnect calls
        if self._already_disconnected:            
            return        
        try:
            if self.bot and self.bot.botId is not None:
                bot_id = self.bot.botId
                self.logger.info(f"Disconnecting bot {bot_id}...")
                
                # Set USER_REQUEST_QUIT flag to signal graceful shutdown
                try:
                    if hasattr(self.bot, 'botLayer') and self.bot.botLayer:
                        self.bot.botLayer.setProp("USER_REQUEST_QUIT", True)
                except Exception as e:
                    self.logger.debug(f"Could not set USER_REQUEST_QUIT: {e}")
                
                # Call disconnect method - this should trigger LOGOUT event
                try:
                    disconnect_coro = self.bot.disconnect()
                    if inspect.iscoroutine(disconnect_coro):
                        await asyncio.wait_for(disconnect_coro, timeout=5)
                    else:
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, self.bot.disconnect),
                            timeout=5
                        )
                except asyncio.TimeoutError:
                    self.logger.warning(f"Disconnect timeout for {bot_id}")
                except Exception as e:
                    self.logger.debug(f"Disconnect error: {e}")
                
                # Give bot time to process LOGOUT event and send QUIT
                await asyncio.sleep(0.5)
                
                self.logger.info(f"Bot {bot_id} disconnected.")
                self._already_disconnected = True  # Mark as disconnected
                self.bot = None  # ✅ Clear bot reference to prevent duplicate disconnect
        except Exception as e:
            self.logger.error(f"Error in _async_disconnect: {e}")
            self.bot = None  # ✅ Clear even on error to prevent zombie references
    
    async def _async_quit(self):
        """Async quit wrapper"""
        try:
            if self.bot:
                await self._async_disconnect()
        except Exception as e:
            self.logger.error(f"Error quitting: {e}")

    def run(self):
        """Start the interactive thread"""
        self.thread.start()



