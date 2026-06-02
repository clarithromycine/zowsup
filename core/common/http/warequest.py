from .waresponseparser import ResponseParser


import sys
from typing import Optional, Any, List, Dict, Union
import logging
from axolotl.ecc.curve import Curve
from ...common.tools import WATools
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ...config.v1.config import Config
from ...profile.profile import YowProfile
import struct
import base64
import requests
import uuid

from requests.adapters import HTTPAdapter

import ssl

from common.utils import Utils
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from http import client as httplib
from urllib.parse import quote as urllib_quote
import random

logger = logging.getLogger(__name__)

#ORIGIN_CIPHERS = (
#    'AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA'
#)


ORIGIN_CIPHERS = "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:TLS_DHE_RSA_WITH_AES_256_GCM_SHA384:TLS_DHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_DHE_DSS_WITH_AES_256_GCM_SHA384:TLS_DHE_RSA_WITH_AES_128_GCM_SHA256:TLS_DHE_DSS_WITH_AES_128_GCM_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384:TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256:TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256:TLS_DHE_RSA_WITH_AES_256_CBC_SHA256:TLS_DHE_DSS_WITH_AES_256_CBC_SHA256:TLS_DHE_RSA_WITH_AES_128_CBC_SHA256:TLS_DHE_DSS_WITH_AES_128_CBC_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA:TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA:TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA:TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:TLS_DHE_RSA_WITH_AES_256_CBC_SHA:TLS_DHE_DSS_WITH_AES_256_CBC_SHA:TLS_DHE_RSA_WITH_AES_128_CBC_SHA:TLS_DHE_DSS_WITH_AES_128_CBC_SHA:TLS_RSA_WITH_AES_256_GCM_SHA384:TLS_RSA_WITH_AES_128_GCM_SHA256:TLS_RSA_WITH_AES_256_CBC_SHA256:TLS_RSA_WITH_AES_128_CBC_SHA256:TLS_RSA_WITH_AES_256_CBC_SHA:TLS_RSA_WITH_AES_128_CBC_SHA:TLS_EMPTY_RENEGOTIATION_INFO_SCSV"

IOS_CIPHERS = "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA:TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA:TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA:TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:TLS_RSA_WITH_AES_256_GCM_SHA384:TLS_RSA_WITH_AES_128_GCM_SHA256:TLS_RSA_WITH_AES_256_CBC_SHA:TLS_RSA_WITH_AES_128_CBC_SHA:TLS_ECDHE_ECDSA_WITH_3DES_EDE_CBC_SHA:TLS_ECDHE_RSA_WITH_3DES_EDE_CBC_SHA:TLS_RSA_WITH_3DES_EDE_CBC_SHA"

ANDROID_CIPHERS = "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256:TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384:TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256:TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA:TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA:TLS_RSA_WITH_AES_128_GCM_SHA256:TLS_RSA_WITH_AES_256_GCM_SHA384:TLS_RSA_WITH_AES_128_CBC_SHA:TLS_RSA_WITH_AES_256_CBC_SHA"



class SSLFactory:
    def __init__(self) -> None:
        self.ciphers = ANDROID_CIPHERS.split(":")

    def __call__(self) -> ssl.SSLContext:
        random.shuffle(self.ciphers)
        ciphers = ":".join(self.ciphers)
        ciphers = ciphers + ":!aNULL:!eNULL:!MD5"

        context = ssl.create_default_context()
        context.set_ciphers(ciphers)
        return context

sslgen = SSLFactory()

class TlsAdapter(HTTPAdapter):

    def __init__(self, *args, **kwargs) -> None:
        
        '''
        ciphers = ORIGIN_CIPHERS.split(':')        
        ss = int(len(ciphers)*random.randint(75,90)/100.0)
        sample_ciphers = random.sample(ciphers,ss)
        random.shuffle(sample_ciphers)                     
        self.CIPHERS = ':'.join(sample_ciphers) #+ ':!aNULL:!eNULL:!MD5'  
        '''      
        
        self.CIPHERS = IOS_CIPHERS
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs) -> Any:
        context = create_urllib3_context()
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)
    
    def proxy_manager_for(self, *args, **kwargs) -> Any:
        context = create_urllib3_context()
        kwargs['ssl_context'] = context
        
        return super().proxy_manager_for(*args, **kwargs)
    
class WARequest:
    OK = 200
    ENC_PUBKEY = Curve.decodePoint(
        bytearray([
            5, 142, 140, 15, 116, 195, 235, 197, 215, 166, 134, 92, 108,
            60, 132, 56, 86, 176, 97, 33, 204, 232, 234, 119, 77, 34, 251,
            111, 18, 37, 18, 48, 45
        ])
    )

    TLS_ADAPTER = TlsAdapter(ssl.PROTOCOL_TLS|ssl.OP_NO_TLSv1_1)


    def __init__(self, config_or_profile=None,env=None) -> None:
        """
       :type method: str
       :param config_or_profile:
       :type config: yowsup.config.v1.config.Config | YowProfile
       """

        self.pvars = []
        self.port = 443
        self.type = "GET"
        self.parser = None
        self.params = []
        self.headers = {}
        

        self.sent = False
        self.response = None


        if config_or_profile is None:
            return 

        if isinstance(config_or_profile, Config):            
            profile = YowProfile(config_or_profile.phone, config_or_profile)
        else:
            assert isinstance(config_or_profile, YowProfile)
            profile = config_or_profile

        self._config = profile.config
        config = self._config
        self._p_in = str(config.phone)[len(str(config.cc)):]
        self._axolotlmanager = profile.axolotl_manager

        if config.expid is None:
            config.expid = WATools.generateDeviceId()

        if config.fdid is None:
            config.fdid = WATools.generatePhoneId(env)                      

        if config.client_static_keypair is None:
            config.client_static_keypair = WATools.generateKeyPair()

        self.addParam("cc", config.cc)
        self.addParam("in", self._p_in)

        #杩欓噷瑕佽窡闅忓畨鍗撶郴缁熺殑鍙傛暟锛屾墍浠ユ敼涓哄灞傚彲瑕嗙洊锛岃繖閲屽彧鏄粯璁ゅ€?
        #lg,lc = Utils.getLGLC(config.cc)        
        self.addParam("lg", "en")
        self.addParam("lc", "US")

        self.addParam("authkey", self.b64encode(config.client_static_keypair.public.data,padding=False))        

        self.addParam("e_regid", self.b64encode(struct.pack('>I', self._axolotlmanager.registration_id),padding=False))

        self.addParam("e_keytype", self.b64encode(b"\x05",padding=False))
        self.addParam("e_ident", self.b64encode(self._axolotlmanager.identity.publicKey.serialize()[1:],padding=False))

        signedprekey = self._axolotlmanager.load_latest_signed_prekey(generate=True)
        self.addParam("e_skey_id", self.b64encode(struct.pack('>I', signedprekey.getId())[1:],padding=False))
        self.addParam("e_skey_val", self.b64encode(signedprekey.getKeyPair().publicKey.serialize()[1:],padding=False))   
        self.addParam("e_skey_sig", self.b64encode(signedprekey.getSignature(),padding=False))

        self.addParam("fdid", config.fdid)        
        self.addParam("expid", self.b64encode(config.expid,padding=False))

        #self.addParam("fdid", "2cba8377-bd5e-442f-b136-b00342901770")        
        #
        #287c4658-d2e0-4fdc-a827-fe3baf4a9d6e
        #self.addParam("expid", "tHSdE9EBSaeTXJFxYHqERw")        

                     
        self.addParam("rc", "0")
        if self._config.id:
            self.addParam("id", self._config.id)

        self.env = env

    def setParsableVariables(self, pvars) -> Any:
        self.pvars = pvars

    def onResponse(self, name, value) -> Any:
        if name == "status":
            self.status = value
        elif name == "result":
            self.result = value

    def addAllParamsFromDict(self,dict) -> Any:
        for key,val in dict.items():
            self.addParam(key,val)


    def addParamIf(self,name,value,condition) -> Any:
        if condition:            
            self.addParam(name,value)

    def addParam(self, name, value) -> Any:
        self.removeParam(name)      #濡傛灉鏈夛紝灏卞厛鍒犻櫎
        self.params.append((name, value))

    def getParam(self, name) -> Any:
        for i, val in enumerate(self.params):
            if name in val:
                return  self.params[i][1]
        return None

    def removeParam(self, name) -> Any:
        for i, val in enumerate(self.params):
            if name in val:
                del self.params[i]

    def addHeaderField(self, name, value) -> Any:
        self.headers[name] = value

    def clearParams(self) -> Any:
        self.params = []

    def getUserAgent(self) -> Any:
        return self.env.deviceEnv.getUserAgent()

    def send(self, parser=None, encrypt=True, preview=False) -> Any:
        
        logger.debug("send(parser={}, encrypt={}, preview={})".format(
            None if parser is None else "[omitted]",
            encrypt, preview
        ))
        if self.type == "POST":
            return self.sendPostRequest(parser)

        return self.sendGetRequest(parser, encrypt, preview=preview)

    def setParser(self, parser) -> Any:
        if isinstance(parser, ResponseParser):
            self.parser = parser
        else:
            logger.error("Invalid parser")

    def getConnectionParameters(self) -> Any:

        if not self.url:
            return ":", self.port

        try:
            url = self.url.split("://", 1)
            url = url[0] if len(url) == 1 else url[1]

            host, path = url.split('/', 1)
        except ValueError:
            host = url
            path = ""

        path = "/" + path

        return host, self.port, path

    def encryptParams(self, params, key) -> Any:

        keypair = Curve.generateKeyPair()
        encodedparams = self.urlencodeParams(params)
        cipher = AESGCM(Curve.calculateAgreement(key, keypair.privateKey))
        ciphertext = cipher.encrypt(b'\x00\x00\x00\x00' + struct.pack('>Q', 0), encodedparams.encode(), b'')
        payload = base64.b64encode(keypair.publicKey.serialize()[1:] + ciphertext)

        return None,[('ENC', payload)]
        

    def sendGetRequest(self, parser=None, encrypt_params=True, preview=False) -> Any:
                
        logger.debug("sendGetRequest(parser={}, encrypt_params={}, preview={})".format(
            None if parser is None else "[omitted]",
            encrypt_params, preview
        ))
        self.response = None

        if encrypt_params:
            logger.debug("Encrypting parameters")
            if logger.level <= logging.DEBUG:
                logger.debug("pre-encrypt (encoded) parameters = \n%s", (self.urlencodeParams(self.params)))
            authorization,params = self.encryptParams(self.params, self.ENC_PUBKEY)            
        else:
            ## params will be logged right before sending
            authorization = None
            params = self.params

        parser = parser or self.parser or ResponseParser()
        
        fixedHeader = {                  
                    "WaMsysRequest":'1',                              
                    "request_token": str(uuid.uuid4()).upper(),                                                                                                                           
                    "Content-Type": "application/x-www-form-urlencoded",                    
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "User-Agent": self.getUserAgent(),                       
        }

        if authorization:            
            self.headers["Authorization"] = authorization
        
        headers = dict(
            list(fixedHeader.items()) + list(self.headers.items())
        )                        
        #print(headers)
        
                                                              
        host, port, path = self.getConnectionParameters()
        logger.info(path)
        self.response = WARequest.sendRequest(host, port, path, headers, params, "GET", preview=preview,env=self.env)
        if preview:
            logger.info("Preview request, skip response handling and return None")
            return None
        if not self.response.status_code == WARequest.OK:
            logger.error("Request not success, status was %s" % self.response.status)
            return {}
        return self.response.json()

    def sendPostRequest(self, parser=None) -> Any:
        self.response = None
        params = self.params  # [param.items()[0] for param in self.params];
        parser = parser or self.parser or ResponseParser()
        headers = dict(list({"User-Agent": self.getUserAgent(),
                             "Accept": parser.getMeta(),
                             "Content-Type": "application/x-www-form-urlencoded"
                             }.items()) + list(self.headers.items()))

        host, port, path = self.getConnectionParameters()
        self.response = WARequest.sendRequest(host, port, path, headers, params, "POST",env=self.env)

        if not self.response.status_code == WARequest.OK:
            logger.error("Request not success, status was %s" % self.response.status)
            return {}

        self.sent = True             
        return self.response.json()

    def b64encode(self, value,padding=True) -> Any:
        s =  base64.urlsafe_b64encode(value)
        if not padding:
            s = s.replace(b'=',b'')        
        return s        

    @classmethod
    def urlencode(cls, value) -> Any:
        if type(value) not in (str, bytes):
            value = str(value)

        out = ""
        for char in value:
            if type(char) is int:
                char = bytearray([char])
            quoted = urllib_quote(char, safe='')
            out += quoted if quoted[0] != '%' else quoted.upper()

        return out             

    @classmethod
    def urlencodeParams(cls, params) -> Any:
        merged = []
        for k, v in params:
            merged.append(
                "{}={}".format(k, cls.urlencode(v))
            )
        return "&".join(merged)

    @classmethod
    def sendRequest(cls, host, port, path, headers, params, reqType="GET", preview=False,env=None) -> Any:        
        logger.debug("sendRequest(host={}, port={}, path={}, headers={}, params={}, reqType={}, preview={})".format(
            host, port, path, headers, params, reqType, preview
        ))
        params = cls.urlencodeParams(params)
        rawpath = path
        path = path + "?" + params if reqType == "GET" and params else path

        if reqType=="POST":
            data = params
        else:
            data = None
                              
        session = requests.Session()   
        if WARequest.TLS_ADAPTER is not None:     
            session.mount("https://", WARequest.TLS_ADAPTER)
        if env.networkEnv is not None and env.networkEnv.type!="direct":
            proxy = env.networkEnv            
            logger.debug("PROXY REQUEST TO %s" % rawpath)
            proxies = {
                "http":  "socks5://%s:%s@%s:%d" % (proxy.username, proxy.password, proxy.host, proxy.port),
                "https":  "socks5://%s:%s@%s:%d" % (proxy.username, proxy.password, proxy.host, proxy.port)
            }               
            response = session.request(reqType,"https://%s:%d%s" % (host,port,path),headers=headers,proxies=proxies,data=data)            
        else:
            logger.debug("REQUEST TO %s" % rawpath)
            response = session.request(reqType,"https://%s:%d%s" % (host,port,path),headers=headers,data=data)
                
        return response
