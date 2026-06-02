import sys,os
sys.path.append(os.getcwd())

from core.profile.profile import YowProfile
import base64
from core.axolotl.factory import AxolotlManagerFactory
from conf.constants import SysVar
from core.config.v1.config import Config
from consonance.structs.keypair import KeyPair
from pathlib import Path
from core.config.transforms.dict_json import DictJsonTransform
from core.config.v1.serialize import ConfigSerialize
from common.utils import Utils
import logging
import names
from core.common.tools import WATools
from common.consolemain import ConsoleMain

logger = logging.getLogger(__name__)
    
class Import6(ConsoleMain):
    def run(self,params,options):
        Utils.init_log(logging.INFO,"import6.log")    

        self.commonOptionsProcess(options)
        
        if "env" not in options:
            logger.info("set default env to android")
            options["env"] = "android"
        
        regType,osType = Utils.getTypesByEnvName(options["env"])

        if len(params) == 0:
            print("data must be specified")        
            sys.exit(1)

        auto = ("auto" in options)


        
        data = params[0].split(",")

        client_static_keypair_str = base64.b64encode(base64.b64decode(data[2]) + base64.b64decode(data[1])).decode()
        kp = KeyPair.from_bytes(base64.b64decode(client_static_keypair_str))

        if len(data[5]) % 4 !=0:
            data[5] = data[5]+'=' * (4- len(data[5]) % 4)
        sixth = base64.b64decode(data[5])
        #pos = sixth.find('#'.encode())   
        id = sixth[-20:]

        config = Config(
            pushname=names.get_full_name()+"X",
            cc=Utils.getMobileCC(data[0]),
            mcc='000',
            mnc='000',
            phone=data[0],    
            sim_mcc='000',
            sim_mnc='000',
            client_static_keypair = kp,   
            fdid = WATools.generatePhoneId(self.env),
            expid= WATools.generateDeviceId(),
            id = id
        )    

        config.os_name = SysVar.OS_NAME_MAPPING.get(options["env"],"Android")

        account_dir = Path(SysVar.ACCOUNT_PATH+data[0])
        if not account_dir.exists():
            account_dir.mkdir()

        profile = YowProfile(SysVar.ACCOUNT_PATH+data[0])   
        profile.write_config(config)
        
        db = AxolotlManagerFactory().get_manager(SysVar.ACCOUNT_PATH+data[0],data[0])

        db._store.identityKeyStore.dbConn.execute("DELETE FROM prekeys")

        
                        
        q = "UPDATE identities SET public_key=? , private_key=? WHERE recipient_id=-1 AND recipient_type=0"
        c = db._store.identityKeyStore.dbConn.cursor()
        
        if len(base64.b64decode(data[3]))==32:
            pubKey = b'\x05'+base64.b64decode(data[3])
        else:
            #这里用于适配出带类型\x05的公钥，33个字节直接用
            logger.info("6 parts account may be wrong")
            pubKey = base64.b64decode(data[3])
        privKey = base64.b64decode(data[4])

        c.execute(q, (pubKey,privKey))
        db._store.identityKeyStore.dbConn.commit()        
        jsonstr = DictJsonTransform().transform(ConfigSerialize(config.__class__).serialize(config))
        publicKey = str(base64.b64encode(pubKey),'UTF-8')
        privateKey = str(base64.b64encode(privKey),'UTF-8')   
        logger.info("===PART1-REGKEYS===")
        logger.info(db.registration_id)
        logger.info(publicKey)  
        logger.info(privateKey)                  
        logger.info("===PART2-PROFILE===")
        logger.info(jsonstr)        

        
if __name__ == "__main__":    

    SysVar.loadConfig()   
    
    params,options = Utils.cmdLineParser(sys.argv)

    Import6().run(params,options)    

    
    
    

