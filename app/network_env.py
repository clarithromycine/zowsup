from common.utils import Utils
import random,logging
from common.country_code import CountryCodeParser

logger = logging.getLogger(__name__)
class NetworkEnv:

    TYPE_DIRECT = "direct"
    TYPE_PROXY  = "proxy"

    def __init__(self,type,host=None,port=None,username=None,password=None,proxyStr=None):        

        self.type = type    #"direct" or "proxy"
        self.rawProxyStr = None     
        self.proxyStr = None
        if type=="proxy":
            if proxyStr is None:                
                proxyStr = "%s:%d:%s:%s" % (host,port,username,password)
                
            self.updateProxyStr(proxyStr,proxyStr)

    def __str__(self):
        return f"NetworkType={self.type}, Proxy={self.proxyStr}"
            
    def updateProxyStr(self,proxyStr,rawProxyStr=None):
        if rawProxyStr:
            self.rawProxyStr=rawProxyStr
        self.proxyStr=proxyStr
        params = proxyStr.split(":")     
        if len(params)==4:
            self.type = "proxy"
            self.host = params[0]
            self.port = int(params[1])
            self.username = params[2]
            self.password = params[3]
        else:
            raise Exception("proxy string format error")            
        
    def updateProxyByWaNum(self,waNum):
        if self.type=="direct":
            return 
        
        lc = CountryCodeParser.parse(waNum)
                        
        if lc.lower()=="cn":
            lc = "us"                                    
        session_id = waNum[-8:]       
        proxyStr =  self.rawProxyStr
        if "[location]" in proxyStr:
            proxyStr = proxyStr.replace("[location]",lc.lower())
        if "[session_id]" in proxyStr:
            proxyStr = proxyStr.replace("[session_id]",session_id)

        logger.info("USING PROXY %s" % proxyStr)

        self.updateProxyStr(proxyStr)        
            

        



        
            
