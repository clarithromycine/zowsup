import sys,os
sys.path.append(os.getcwd())
from common.consolemain import ConsoleMain
from core.config.manager import ConfigManager
import base64
from core.axolotl.factory import AxolotlManagerFactory
from conf.constants import SysVar,GlobalVar
from common.utils import Utils


class Export6(ConsoleMain):

    def run(self,params,options):

        if len(params)<1:
            print("NOT ENOUGH PARAMS")

        self.commonOptionsProcess(options)

        numarr = params[0].split(",")
        for number in numarr:
            config_manager = ConfigManager()
            config = config_manager.load(SysVar.ACCOUNT_PATH+number)
            kp = config.client_static_keypair
            pk1 = Utils.b64str(kp.public.data)
            sk1 = Utils.b64str(kp.private.data)
            db = AxolotlManagerFactory().get_manager(SysVar.ACCOUNT_PATH+number,number)
            pk2 = Utils.b64str(db.identity.publicKey.serialize()[1:])
            sk2 = Utils.b64str(db.identity.privateKey.serialize())
            sixth = Utils.b64str(config.phone.encode()+b"#"+config.id)
            
            print("{},{},{},{},{},{}".format(config.phone,pk1,sk1,pk2,sk2,sixth))

if __name__ == "__main__":
    
    SysVar.loadConfig()       
    params,options = Utils.cmdLineParser(sys.argv)
    Export6().run(params,options)    



    






