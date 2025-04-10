# coding=UTF-8
import os,sys
sys.path.append(os.getcwd())
from common.consolemain import ConsoleMain
import logging
from pathlib import Path
from app.yowbot import YowBot
from script.cmdprocess import CmdProcess
from conf.constants import SysVar,GlobalVar
from common.utils import Utils
from yowsup.profile.profile import YowProfile
from app.device_env import DeviceEnv

logger = logging.getLogger(__name__)

class Main(ConsoleMain):

     
    def run(self,params,options):
        
        if len(params) == 0:
            print("a phone number must be specified")        
            sys.exit(1)
        else:
            botId = params[0]
        
        if "debug" in options:
            self.init_log(logging.DEBUG,botId+".log")
        else:
            self.init_log(logging.INFO,botId+".log")

        
        if "proxy" not in options:
            options["proxy"] = "DIRECT"

        lg,lc = Utils.getLGLC(Utils.getMobileCC(botId))
        logger.info("LG=%s, LC=%s" % (lg,lc))

        self.commonOptionsProcess(options)
                                      
        config_file = Path(SysVar.ACCOUNT_PATH+botId+"/config.json")
        if not config_file.exists():
            logger.info("account not exist !!")
            return 
        
        self.commonOptionsProcess(options)

        info = None        
        if "env" not in options:           

            profile = YowProfile(SysVar.ACCOUNT_PATH+botId)
            if profile.config.os_name is not None:
                logger.info("Local Profile found")
                tt = {
                    "Android":"android",
                    "SMBA":"smb_android",
                    "iOS":"ios",
                    "SMB iOS":"smb_ios"
                }
                self.env.deviceEnv = DeviceEnv(tt[profile.config.os_name])
            else:
                pass  

        logger.info("ENV=%s",self.env.deviceEnv.getOSName())                
        logger.info("BotId=%s" % botId)        
        logger.info("RegType=%s" % (info["regType"] if info is not None else "1")) 
        
        try:  
            wabot = YowBot(bot_id=botId,env=self.env,)
            wabot.manualStop = True
            logger.info(self.env.networkEnv)            
            
            if len(params) == 1:
                pass            
            else: 
                if params[1] in wabot.getCmdList():                      
                    CmdProcess(wabot,params[1:],options).run()    
                else:
                    logger.info("Unknown Command")                                          
            wabot.run()
        except KeyboardInterrupt:                
            wabot.disconnect()            
            
if __name__ == "__main__":
    
    GlobalVar.WANUMTYPE = 1     
    SysVar.loadConfig()       
        
    if len(sys.argv)<=1:
        print("USAGE:")
        print("\nmain.py [account-number] [command] [commandParams]\n")
        YowBot.printUsage()
        sys.exit(0)
    
    params,options = Utils.cmdLineParser(sys.argv)
    
    print(options)


    Main().run(params,options)    
    
    





    






    


    
    

    

    

    

    
    

    


    

        
    




    



            
