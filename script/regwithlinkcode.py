import sys,os
sys.path.append(os.getcwd())

import logging
from app.zowbot import ZowBot
from conf.constants import SysVar,GlobalVar
from common.utils import Utils
from common.consolemain import ConsoleMain

from app.zowbot_values import ZowBotType
logger = logging.getLogger(__name__)

class RegWithLinkCode(ConsoleMain):    

    def run(self,params,options):
        
        if len(params) == 0:
            print("a phone number must be specified")        
            sys.exit(1)
        else:
            botId = params[0]        

        if len(params) >1 :
            linkCode = params[1]
        else:
            linkCode = "AAAAAAAA"

        if "debug" in options:
            self.init_log(logging.DEBUG,botId+".log")
        else:
            self.init_log(logging.INFO,botId+".log")
            

        self.commonOptionsProcess(options)   
        try:  
            wabot = ZowBot(bot_id=None,env=self.env,bot_type=ZowBotType.TYPE_REG_COMPANION_LINKCODE  )            
            wabot.pairPhoneNumber = botId
            wabot.pairLinkCode = linkCode
            wabot.run()
        except KeyboardInterrupt:        
            print("error")
            
if __name__ == "__main__":

    GlobalVar.BOTTYPE = 2  # 注册模式    
    #随机一个设备
    SysVar.loadConfig()    

    params,options = Utils.cmdLineParser(sys.argv) 
    RegWithLinkCode().run(params,options)    
        
    

    


    

        
    




    



            
