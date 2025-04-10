from .waresponseparser import ResponseParser

import logging
from axolotl.ecc.curve import Curve
from yowsup.common.tools import WATools
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from yowsup.config.v1.config import Config
from yowsup.profile.profile import YowProfile
import struct
import base64
import requests
import uuid

from urllib.parse import quote as urllib_quote

logger = logging.getLogger(__name__)

    
class WARequest(object):
    OK = 200
    ENC_PUBKEY = Curve.decodePoint(
        bytearray([
            5, 142, 140, 15, 116, 195, 235, 197, 215, 166, 134, 92, 108,
            60, 132, 56, 86, 176, 97, 33, 204, 232, 234, 119, 77, 34, 251,
            111, 18, 37, 18, 48, 45
        ])
    )
    


    def __init__(self, config_or_profile=None,env=None):
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
        lg,lc = Utils.getLGLC(config.cc)        
        self.addParam("lg", lg)
        self.addParam("lc", lc)

        self.addParam("authkey", self.b64encode(config.client_static_keypair.public.data))        

        self.addParam("e_regid", self.b64encode(struct.pack('>I', self._axolotlmanager.registration_id)))

        self.addParam("e_keytype", self.b64encode(b"\x05"))
        self.addParam("e_ident", self.b64encode(self._axolotlmanager.identity.publicKey.serialize()[1:]))

        signedprekey = self._axolotlmanager.load_latest_signed_prekey(generate=True)
        self.addParam("e_skey_id", self.b64encode(struct.pack('>I', signedprekey.getId())[1:]))
        self.addParam("e_skey_val", self.b64encode(signedprekey.getKeyPair().publicKey.serialize()[1:]))   
        self.addParam("e_skey_sig", self.b64encode(signedprekey.getSignature()))

        self.addParam("fdid", config.fdid)        
        self.addParam("expid", self.b64encode(config.expid))
                     
        self.addParam("rc", "0")
        if self._config.id:
            self.addParam("id", self._config.id)

        self.env = env

    def setParsableVariables(self, pvars):
        self.pvars = pvars

    def onResponse(self, name, value):
        if name == "status":
            self.status = value
        elif name == "result":
            self.result = value

    def addParamIf(self,name,value,condition):
        if condition:
            self.addParam(name,value)

    def addParam(self, name, value):
        self.params.append((name, value))

    def getParam(self, name):
        for i, val in enumerate(self.params):
            if name in val:
                return  self.params[i][1]
        return None

    def removeParam(self, name):
        for i, val in enumerate(self.params):
            if name in val:
                del self.params[i]

    def addHeaderField(self, name, value):
        self.headers[name] = value

    def clearParams(self):
        self.params = []

    def getUserAgent(self):
        return self.env.deviceEnv.getUserAgent()

    def send(self, parser=None, encrypt=True, preview=False,cert=None,proxy=None):
        
        logger.debug("send(parser=%s, encrypt=%s, preview=%s)" % (
            None if parser is None else "[omitted]",
            encrypt, preview
        ))
        if self.type == "POST":
            return self.sendPostRequest(parser)

        return self.sendGetRequest(parser, encrypt, preview=preview,cert=cert,proxy=proxy)

    def setParser(self, parser):
        if isinstance(parser, ResponseParser):
            self.parser = parser
        else:
            logger.error("Invalid parser")

    def getConnectionParameters(self):

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

    def encryptParams(self, params, key):

        keypair = Curve.generateKeyPair()
        encodedparams = self.urlencodeParams(params)
        cipher = AESGCM(Curve.calculateAgreement(key, keypair.privateKey))
        ciphertext = cipher.encrypt(b'\x00\x00\x00\x00' + struct.pack('>Q', 0), encodedparams.encode(), b'')
        payload = base64.b64encode(keypair.publicKey.serialize()[1:] + ciphertext)
        return [('ENC', payload)]

    def sendGetRequest(self, parser=None, encrypt_params=True, preview=False,cert=None,proxy=None):
                
        logger.debug("sendGetRequest(parser=%s, encrypt_params=%s, preview=%s)" % (
            None if parser is None else "[omitted]",
            encrypt_params, preview
        ))
        self.response = None

        if encrypt_params:
            logger.debug("Encrypting parameters")
            if logger.level <= logging.DEBUG:
                logger.debug("pre-encrypt (encoded) parameters = \n%s", (self.urlencodeParams(self.params)))
            params = self.encryptParams(self.params, self.ENC_PUBKEY)
        else:
            ## params will be logged right before sending
            params = self.params

        parser = parser or self.parser or ResponseParser()
                        
        headers = dict(
            list(
                {
                    "Accept":"text/json",
                    "WaMsysRequest":'1',                              
                    "request_token": str(uuid.uuid4()),                                                                                                        
                    "Content-Type": "application/x-www-form-urlencoded",                    
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "User-Agent": self.getUserAgent(),       
                }.items()
            ) + list(self.headers.items()))
                          
        host, port, path = self.getConnectionParameters()
        self.response = WARequest.sendRequest(host, port, path, headers, params, "GET", preview=preview,proxy=proxy)
        if preview:
            logger.info("Preview request, skip response handling and return None")
            return None
        if not self.response.status_code == WARequest.OK:
            logger.error("Request not success, status was %s" % self.response.status)
            return {}
        return self.response.json()

    def sendPostRequest(self, parser=None,proxy=None):
        self.response = None
        params = self.params  # [param.items()[0] for param in self.params];
        parser = parser or self.parser or ResponseParser()
        headers = dict(list({"User-Agent": self.getUserAgent(),
                             "Accept": parser.getMeta(),
                             "Content-Type": "application/x-www-form-urlencoded"
                             }.items()) + list(self.headers.items()))

        host, port, path = self.getConnectionParameters()
        self.response = WARequest.sendRequest(host, port, path, headers, params, "POST",proxy=proxy)

        if not self.response.status_code == WARequest.OK:
            logger.error("Request not success, status was %s" % self.response.status)
            return {}

        self.sent = True             
        return self.response.json()

    def b64encode(self, value):
        return base64.urlsafe_b64encode(value)#.replace(b'=', b'')

    @classmethod
    def urlencode(cls, value):
        if type(value) not in (str, bytes):
            value = str(value)

        out = ""
        for char in value:
            if type(char) is int:
                char = bytearray([char])
            quoted = urllib_quote(char, safe='')
            out += quoted if quoted[0] != '%' else quoted.lower()

        return out \
            .replace('-', '%2d') \
            .replace('_', '%5f') \
            .replace('~', '%7e')

    @classmethod
    def urlencodeParams(cls, params):
        merged = []
        for k, v in params:
            merged.append(
                "%s=%s" % (k, cls.urlencode(v))
            )
        return "&".join(merged)

    @classmethod
    def sendRequest(cls, host, port, path, headers, params, reqType="GET", preview=False,tls_adapter=None,proxy=None):        
        logger.debug("sendRequest(host=%s, port=%s, path=%s, headers=%s, params=%s, reqType=%s, preview=%s)" % (
            host, port, path, headers, params, reqType, preview
        ))
        params = cls.urlencodeParams(params)
        rawpath = path
        path = path + "?" + params if reqType == "GET" and params else path
        session = requests.Session()   

        if proxy is not None:
            logger.debug("PROXY REQUEST TO %s" % rawpath)
            proxies = {
                "http":  "socks5://%s:%s@%s:%d" % (proxy.username, proxy.password, proxy.host, proxy.port),
                "https":  "socks5://%s:%s@%s:%d" % (proxy.username, proxy.password, proxy.host, proxy.port)
            }               
            response = session.request(reqType,"https://%s:%d%s" % (host,port,path),headers=headers,proxies=proxies)            
        else:
            logger.debug("REQUEST TO %s" % rawpath)
            response = session.request(reqType,"https://%s:%d%s" % (host,port,path),headers=headers)
                
        return response
