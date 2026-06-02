import sys,os
sys.path.append(os.getcwd())

from common.consolemain import ConsoleMain

import logging
from conf.constants import SysVar
from core.profile.profile import YowProfile
from core.registration import WACodeRequest,WARegOnBoardAbPropRequest
from core.config.v1.config import Config
from conf.constants import SysVar
from common.utils import Utils
import traceback
import names



logger = logging.getLogger(__name__)

class RequestCode(ConsoleMain):

    def run(self,params,options):    

        number = params[0]
        countryCode = Utils.getMobileCC(number)
        self.commonOptionsProcess(options)      
            
        codeType = params[1] if len(params) > 1 else "sms"        
        name = params[3]  if len(params) > 3 else names.get_full_name()

        env = self.env.deviceEnv                
   
        mccmnc = Utils.getMccMnc(countryCode)

        config = Config(
            cc=countryCode,
            mcc="000",
            mnc="000",
            phone=number,
            sim_mcc="000",
            sim_mnc="000",        
            pushname=name,
            os_name = env.getOSName(),
            os_version=env.getOSVersion(),
            manufacturer=env.getManufacturer(),
            device_name=env.getDeviceName(),
            device_model_type=env.getDeviceModelType()            
        )
                
        profile = YowProfile(number, config)

        self.env.networkEnv.updateProxyByWaNum(countryCode+number)

        try:            
            
            #regOnBoardReq1 = WARegOnBoardAbPropRequest("1","2155550000",config=config,env=self.env)
            #result = regOnBoardReq1.send(preview=False)                                       
            #ab_hash = result["ab_hash"]                        
            regOnBoardReq2 = WARegOnBoardAbPropRequest(countryCode,number[len(countryCode):],config=config,env=self.env)
            result = regOnBoardReq2.send(preview=False)                                                
            codeReq = WACodeRequest(codeType, config,env=self.env)    
            
            profile.write_config(config)                                                            
            result = codeReq.send(encrypt=True, preview=False)                   
            #profile.write_config(config)             
            if result["status"]!="sent":                                  
                Utils.outputResult({
                    "retcode":-1,            
                    "msg":result["reason"],                    
                    "details":result,             
                })                
            else:            
                #sent
                profile.write_config(config)                
                Utils.outputResult({
                    "retcode":0,
                    "msg":"ok",
                    "details":result,
                })                           
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
    RequestCode().run(params,options)