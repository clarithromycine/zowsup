import os,sys

sys.path.append(os.getcwd())
from common.consolemain import ConsoleMain
import logging
from pathlib import Path
from app.zowbot import ZowBot
from script.interactivethread import InteractiveThread
from conf.constants import SysVar
from common.utils import Utils
from core.profile.profile import YowProfile
from app.device_env import DeviceEnv
from app.zowbot_values import ZowBotType


logger = logging.getLogger(__name__)

class Main(ConsoleMain):
                       
    def run(self,params,options):
        
        # If no account specified, allow interactive connection
        botId = params[0] if len(params) > 0 else None
        
        if botId:
            if "debug" in options:
                self.init_log(logging.DEBUG,botId+".log")
            else:
                self.init_log(logging.INFO,botId+".log")
        else:
            if "debug" in options:
                self.init_log(logging.DEBUG,"zowbot.log")
            else:
                self.init_log(logging.INFO,"zowbot.log")

        
        if "proxy" not in options:
            options["proxy"] = "DIRECT"

        if botId:
            lg,lc = Utils.getLGLC(Utils.getMobileCC(botId))
            logger.info("LG={}, LC={}".format(lg,lc))
        
        self.commonOptionsProcess(options)

        # Only check for account file if botId is provided
        if botId:
            config_file = Path(SysVar.ACCOUNT_PATH+botId+"/config.json")

            if not config_file.exists():
                logger.info("account not exist !!")
                return         
            
            self.commonOptionsProcess(options)

            info = None        
            if "env" not in options:           
                profile = YowProfile(SysVar.ACCOUNT_PATH+botId)
                if profile.config.os_name is not None:
                    self.env.deviceEnv = DeviceEnv(SysVar.ENV_NAME_MAPPING.get(profile.config.os_name, "android"))
                else:
                    pass  

            logger.info("ENV={}, BotId={}".format(self.env.deviceEnv.getOSName(), botId))                


 
        wabot = ZowBot(bot_id=botId,env=self.env,bot_type=ZowBotType.TYPE_RUN_SINGLETON)        
        

        if botId:
            logger.info(self.env.networkEnv)
            logger.info("Starting bot: {}".format(botId))
        
        
        # Always start InteractiveThread, it handles both account init and commands
        if len(params) <= 1 or botId is None:
            # Interactive mode: either no params, only account param, or no account
            logger.debug(f"Starting interactive mode - botId={botId}, params={params}")
            interactive_thread = InteractiveThread(wabot, self.env, self)
            logger.debug("InteractiveThread created, starting...")
            interactive_thread.run()
            logger.debug("InteractiveThread started, waiting for completion...")
            # Wait for the interactive thread to complete (user exits)
            # Use timeout loop to allow Ctrl+C to be responsive even during connection
            try:
                while interactive_thread.thread.is_alive():
                    interactive_thread.thread.join(timeout=0.1)
            except KeyboardInterrupt:
                logger.info("Main thread interrupted by user (Ctrl+C)")
                # Thread will clean up gracefully via its own KeyboardInterrupt handler
                interactive_thread.thread.join(timeout=5)
            logger.info("InteractiveThread completed, exiting.")
        else:
            # Command execution mode: account + command
            if params[1] in wabot.getCmdList():
                # New way: Pass command args to bot, execute in event loop
                wabot._cmd_args_for_exec = params[1:]
                wabot._cmd_options_for_exec = options
            else:
                logger.info("Unknown Command")
                return
        
            wabot.botLayer.setProp("USER_REQUEST_QUIT",False)
            wabot.botLayer.setProp("QUITTED",False)

            wabot.run()  # asyncio event loop runs in main thread
            
if __name__ == "__main__":
    
    SysVar.loadConfig()    
        
    if len(sys.argv) <= 1:
        # Allow running without arguments - will start interactive mode
        params = []
        options = {}
    else:
        params,options = Utils.cmdLineParser(sys.argv)

    Main().run(params,options)    
    




    






    


    
    

    

    

    

    
    

    


    

        
    




    



            

