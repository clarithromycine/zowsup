import sys,os
sys.path.append(os.getcwd())

import logging
from core.registration import LogoutSendRequest
from core.config.manager import ConfigManager
from conf.constants import SysVar
from common.utils import Utils
from common.consolemain import ConsoleMain
import traceback

logger = logging.getLogger(__name__)
class LogoutSend(ConsoleMain):

    def run(self,params,options):
        number = params[0]        

        if "env" not in options:
            options["env"] = SysVar.DEFAULT_ENV
            logger.info("set default env to %s" % options["env"])
            
        self.commonOptionsProcess(options)       
           
        config_manager = ConfigManager()
        config = config_manager.load(SysVar.ACCOUNT_PATH+number)

        print(SysVar.ACCOUNT_PATH+number)


        try:
            req = LogoutSendRequest(config, self.env)            
            result = req.send(preview=False)         
            logger.info("LOGOUT REQUEST SENT")
            print(result)

            if result.get("status")=="fail":
                return {
                    "retcode":-1,
                    "result":result
                }
            else:            
                return {
                    "retcode":0,
                    "result":result
                }
        except:
            logger.error(traceback.format_exc())
            Utils.outputResult({
                "retcode":-1,            
                "msg":"exception",
                "details":traceback.format_exc()
            })    
            sys.exit(1)   
                          
if __name__ == "__main__":
    
    SysVar.loadConfig()
    Utils.init_log(logging.INFO) 
    args = sys.argv      
    params,options = Utils.cmdLineParser(sys.argv)    
    LogoutSend().run(params,options)