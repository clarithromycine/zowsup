import sys,os
sys.path.append(os.getcwd())

import logging
from app.zowbot import ZowBot
from conf.constants import SysVar
from common.utils import Utils
from common.consolemain import ConsoleMain

from app.zowbot_values import ZowBotType
logger = logging.getLogger(__name__)

class RegWithScan(ConsoleMain):
    def run(self,params,options):
        self.commonOptionsProcess(options)   
        if "debug" in options:
            self.init_log(logging.DEBUG,"regwithscan.log")
        else:
            self.init_log(logging.INFO,"regwithscan.log")

        try:  
            wabot = ZowBot(bot_id=None,env=self.env,bot_type=ZowBotType.TYPE_REG_COMPANION_SCANQR)                      
            wabot.run()
        except KeyboardInterrupt:        
            print("error")
            
if __name__ == "__main__":

    SysVar.loadConfig()
    
    params,options = Utils.cmdLineParser(sys.argv) 
    RegWithScan().run(params,options)    

       

    

    

    
    

    


    

        
    




    



            
