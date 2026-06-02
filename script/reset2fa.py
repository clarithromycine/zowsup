import sys,os
sys.path.append(os.getcwd())

import logging,traceback
from core.registration import WAReset2FARequest
from core.config.manager import ConfigManager
from conf.constants import SysVar
from common.utils import Utils
from common.consolemain import ConsoleMain

logger = logging.getLogger(__name__)
class Reset2FA(ConsoleMain):

    def run(self,params,options):

        if "env" not in options:
            options["env"] = SysVar.DEFAULT_ENV
            logger.info("set default env to %s" % options["env"])
                
        number = params[0]
        wipe_token = params[1]
        self.commonOptionsProcess(options,waNum=number)       
        config_manager = ConfigManager()
        config = config_manager.load(SysVar.ACCOUNT_PATH+number)
        try:
            req = WAReset2FARequest(config,wipe_token,self.env)            
            result = req.send(preview=False)         
            print(result)   
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
    params,options = Utils.cmdLineParser(sys.argv)    
    Reset2FA().run(params,options)