import sys,os
from pathlib import Path
from conf.constants import SysVar,GlobalVar
from conf.logging_config import setup_logging

import re
import json
import urllib
import random
import logging
import hashlib
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import hmac
from math import ceil
from Crypto.Util.Padding import pad,unpad
import struct
from app.device_env import DeviceEnv
from proto import wa_struct_pb2
from axolotl.ecc.curve import Curve
import zlib
from core.axolotl.factory import AxolotlManagerFactory
from axolotl.state.signedprekeyrecord import SignedPreKeyRecord
from core.config.manager import ConfigManager
import shutil
from proto import e2e_pb2

import base64,time
from typing import Any, Optional, Dict, List, Tuple



logger = logging.getLogger(__name__)

class ApiCmd:
    def __init__(self, cmd , desc, order = 0) -> None:
        self.cmd  = cmd
        self.desc = desc
        self.order = order
    def __call__(self, fn) -> Any:
        fn.cmd = self.cmd
        fn.desc = self.desc
        fn.order = self.order
        return fn   

class Utils:

    _OUTPUT = []
    
    VIOLATION_TYPE_MAP = {
        1: "UNKNOWN",
        2: "HATESPEECH",
        3: "SUICIDE_OR_SELFINJURY",
        4: "ADULT_SEXUAL_EXPLOITATION",
        5: "ADULT_SEXUAL_SOLICITATION",
        6: "BULLYING_AND_HARASSMENT",
        7: "CHILD_SEXUAL_EXPLOITATION",
        8: "COORDINATING_HARM_AND_PROMOTING_CRIME",
        9: "CYBERSECURITY",
        10: "DANGEROUS_INDIVIDUALS_AND_ORGS",
        11: "FRAUD_AND_DECEPTION",
        12: "GRAPHIC_VIOLENCE",
        13: "HARMFUL_HEALTH",
        14: "HATE",
        15: "HUMAN_EXPLOITATION",
        16: "INTELLECTUALPROPERTY_RIGHTS",
        17: "PLATFORM_POLICY",
        18: "PORN",
        19: "PRIVACY_VIOLATION",
        20: "REGULATED_GOODS",
        21: "SPAM",
        22: "SSI",
        23: "VIOLENCE_AND_INCITEMENT",
        24: "IP_TRADEMARK_REPORTED",
        25: "IP_COUNTERFEIT_REPORTED",
        26: "IP_COPYRIGHT_REPORTED",
        27: "IP_REPEAT_INFRINGEMENT_REPORTED"
    }

    @staticmethod
    def violationTypeName(violation_type) -> Any:
        return Utils.VIOLATION_TYPE_MAP.get(violation_type, "UNKNOWN")
    
    @staticmethod
    def getIdTypeByOsName(os_name: str) -> Any:
        """
        Map OS name to WhatsApp protocol entity ID type.
        
        Args:
            os_name: Device OS name (e.g., 'Android', 'iOS', 'SMBA', 'SMB iOS')
        
        Returns:
            ProtocolEntity.ID_TYPE_* constant
        
        Raises:
            ValueError: If OS name is not supported
        """
        from core.structs import ProtocolEntity
        
        os_type_map = {
            "Android": ProtocolEntity.ID_TYPE_ANDROID,
            "SMBA": ProtocolEntity.ID_TYPE_SMB_ANDROID,
            "iOS": ProtocolEntity.ID_TYPE_IOS,
            "SMB iOS": ProtocolEntity.ID_TYPE_SMB_IOS,
        }
        
        if os_name not in os_type_map:
            raise ValueError(f"Unsupported OS: {os_name}. Supported values: {list(os_type_map.keys())}")
        
        return os_type_map[os_name]

    #单项指令
    @staticmethod
    def outputResult(obj) -> Any:
        #被特殊字符包裹的结果
        Utils._OUTPUT.append(obj)  
        logger.info("@@@@@{\"result\":}@@@@@" % json.dumps(obj))

    @staticmethod
    def normalize_jid(jid_str: str) -> str:
        """
        Normalize JID/LID format by removing device ID and cleaning decimal points.
        
        Examples:
            248846345101511:2@lid -> 248846345101511@lid
            8619874406144.0:1@s.whatsapp.net -> 8619874406144@s.whatsapp.net
        
        Args:
            jid_str: JID/LID string in format <phone>:<device>@<domain>
        
        Returns:
            Normalized JID/LID in format <phone>@<domain>
        """
        if not jid_str:
            return jid_str
        
        # Split by @ to separate phone/id from domain
        if '@' not in jid_str:
            return jid_str
        
        parts = jid_str.split('@')
        phone_part = parts[0]
        domain_part = '@'.join(parts[1:])  # Handle multiple @ symbols
        
        # Remove device ID (after colon)
        if ':' in phone_part:
            phone_part = phone_part.split(':')[0]
        
        # Remove decimal part if phone is a float (e.g., 8619874406144.0 -> 8619874406144)
        if '.' in phone_part:
            phone_part = phone_part.split('.')[0]
        
        return f"{phone_part}@{domain_part}"

    @staticmethod
    def generateMultiDeviceParams(ref,companion_auth_pub,companion_identity_pub,adv_secret,profile) -> Any:

        p1 = wa_struct_pb2.ADVDeviceIdentity()
        p1.raw_id = random.randint(1500000000,1700000000)
        p1.key_index = profile.config.get_new_device_index()      #自动按照最大的index+1
        p1.timestamp = int(time.time())

        db = profile.axolotl_manager

        p2 = wa_struct_pb2.ADVSignedDeviceIdentity()
        p2.details = p1.SerializeToString()
        p2.account_signature_key = db.identity.publicKey.serialize()[1:]
        p2.account_signature = Curve.calculateSignature(db.identity.privateKey,b"\x06\x00"+p2.details+companion_identity_pub)

        p3 = wa_struct_pb2.ADVSignedDeviceIdentityHMAC()
        p3.details = p2.SerializeToString()
        p3.hmac = hmac.new(key=adv_secret, msg=p3.details, digestmod=hashlib.sha256).digest()

        q1 = wa_struct_pb2.ADVKeyIndexList()
        q1.raw_id = p1.raw_id
        q1.timestamp = p1.timestamp
        if profile.config.device_list:
            q1.valid_indexes.extend(profile.config.device_list)

        q2 = wa_struct_pb2.ADVSignedKeyIndexList()
        q2.details = q1.SerializeToString()
        q2.account_signature = Curve.calculateSignature(db.identity.privateKey,b"\x06\x02"+p2.details)

        return ref,companion_auth_pub,p3.SerializeToString(),q2.SerializeToString()    
    
    
    @staticmethod
    def generateMultiDeviceParamsFromQrCode(qr_str,profile) -> Any:

        qr_parts = qr_str.split(",")  #四个部份
        ref = qr_parts[0].encode()
        companion_auth_pub = base64.b64decode(qr_parts[1])
        companion_identity_pub = base64.b64decode(qr_parts[2])
        adv_secret = base64.b64decode(qr_parts[3])
        logger.debug(len(adv_secret))

        return Utils.generateMultiDeviceParams(ref,companion_auth_pub,companion_identity_pub,adv_secret,profile)    

    @staticmethod
    def link_code_encrypt(link_code_key,data) -> Any:
        try:
            salt = get_random_bytes(32)
            random_iv = get_random_bytes(16)
            key = hashlib.pbkdf2_hmac(
                hash_name='sha256',
                password=link_code_key.encode(),
                salt=salt,
                iterations=131072,
                dklen=32,
            )                      
            cipher = AES.new(key, AES.MODE_CTR,initial_value=random_iv,nonce=b'')            
            ciphered = cipher.encrypt(data)
            return salt + random_iv + ciphered
        except Exception as e:
            raise RuntimeError("Cannot encrypt") from e

    @staticmethod  
    def link_code_decrypt(link_code_key,encrypted_data) -> Any:
        try:
            salt = encrypted_data[:32]
            key = hashlib.pbkdf2_hmac(
                hash_name='sha256',
                password=link_code_key.encode(),
                salt=salt,
                iterations=131072,
                dklen=32,
            )          
            iv = encrypted_data[32:48]
            payload = encrypted_data[48:80]            
            cipher = AES.new(key, AES.MODE_CTR,initial_value=iv,nonce=b'')          
            return cipher.decrypt(payload)            
        except Exception as e:
            raise RuntimeError("Cannot decrypt") from e
            #pass    

    @staticmethod
    def compress(uncompressed: bytes) -> bytes:
        # 压缩数据
        compressor = zlib.compressobj()
        compressed_data = compressor.compress(uncompressed)
        compressed_data += compressor.flush()
        return compressed_data

    @staticmethod
    def decompress(compressed: bytes) -> bytes:
        # 解压缩数�?
        decompressor = zlib.decompressobj()
        decompressed_data = decompressor.decompress(compressed)
        decompressed_data += decompressor.flush()
        return decompressed_data          
    
    @staticmethod
    def extract_and_expand(key: bytes, info: bytes = b"", output_length: int = 32,salt=None) -> bytes:         
        return Utils.expand(hmac.new(salt if salt is not None else bytes(32) , key, hashlib.sha256).digest(), info, output_length)
    
    @staticmethod
    def expand(prk: bytes, info: bytes, output_size: int) -> bytes:
        HASH_OUTPUT_SIZE = 32  # SHA-256 produces a 32-byte output                
        iterations = ceil(output_size / HASH_OUTPUT_SIZE)
        mixin = b""
        results = bytearray()
        
        for index in range(1, iterations + 1):
            mac = hmac.new(prk, mixin, hashlib.sha256)
            if info:
                mac.update(info)
            mac.update(bytes([index]))
            step_result = mac.digest()
            step_size = min(output_size, len(step_result))
            results.extend(step_result[:step_size])
            mixin = step_result
            output_size -= step_size    
        return bytes(results)
    
    @staticmethod
    def decryptAndUnpad(buffer,key) -> Any:
        iv = buffer[:AES.block_size]
        ciphered = buffer[AES.block_size:]
        cipher = AES.new(key, AES.MODE_CBC,iv= iv)                
        unpadded = unpad(cipher.decrypt(ciphered),block_size=AES.block_size)
        #unpadded = cipher.decrypt(ciphered)
        return unpadded      
    
    @staticmethod
    def encryptAndPrefix(buffer,key) -> Any:
        iv = get_random_bytes(AES.block_size)              
        cipher = AES.new(key, AES.MODE_CBC,iv= iv)           
        buffer_padded = pad(buffer, AES.block_size)
        ciphered = cipher.encrypt(buffer_padded)    
        return iv+ciphered    
    
    @staticmethod
    def generateMac(opbyte,data,keyId,key) -> Any:
        keyData = opbyte+keyId
        last = struct.pack(">Q",len(keyData))                
        total = keyData+data+last        
        mac = hmac.new(key, total, hashlib.sha512).digest()                
        return mac[0:32]
    
    @staticmethod
    def generateSnapshotMac(ltHash,version,patchType,key) -> Any:
        total = ltHash+struct.pack(">Q", version)+patchType.encode()
        mac = hmac.new(key, total, hashlib.sha256).digest()
        return mac
    
    @staticmethod
    def generatePatchMac(snapShotMac,valueMacs,version,patchType,key) -> Any:
        total = snapShotMac
        for item in valueMacs:
            total+=item
        total+=struct.pack(">Q", version)+patchType.encode()
        mac = hmac.new(key, total, hashlib.sha256).digest()
        return mac        

    @staticmethod
    def assureDir(path) -> Any:
        try:    
            if not os.path.exists(path):
                os.makedirs(path)
        except:
            #有时候并发创建目录会出异常，直接忽略就好
            pass

    @staticmethod
    def getOption(options,name,default=None) -> Any:
        if name in options:
            return options[name]
        else:
            return default

    @staticmethod       
    def getTypesByEnvName(name) -> Any:
        #regType,osType
        if name == "smb_android":
            return 2,1
        if name == "smb_ios":
            return 2,2
        if name == "android":
            return 1,1
        if name== "ios":
            return 1,2
            
        return 0,0
    
    @staticmethod
    def cmdLineParser(args) -> Any:
        options = {}
        params = []
        if len(args)==1:
            return params,options 
        i = 1
        while i<len(args):
            if args[i].startswith("--"):                
                if i+1>=len(args) or args[i+1].startswith("--") :
                    options[args[i][2:]] = True
                    i+=1
                else:
                    options[args[i][2:]] = args[i+1]
                    i+=2
            else:
                params.append(args[i])
                i+=1
        return params,options

    @staticmethod
    def init_log(level,name=None) -> Any:

        if name is None:
            name = "default.log"
        
        # 支持两种输入方式：logging常数 或 字符串名
        if isinstance(level, str):
            # 字符串方式：直接使用
            level_name = level.upper()
        else:
            # logging常数方式：转换为字符串
            level_map = {
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO',
                logging.WARNING: 'WARNING',
                logging.ERROR: 'ERROR',
                logging.CRITICAL: 'CRITICAL'
            }
            level_name = level_map.get(level, 'INFO')
        
        # 使用新的统一日志系统：启用文件输出，文件名取自 name 参数
        setup_logging(level=level_name, enable_file=True, log_file_name=name)
        
        # 兼容性处理：为特定库设置日志级别为WARNING
        logging.getLogger('transitions').setLevel(logging.WARNING)
        logging.getLogger('dissononce').setLevel(logging.WARNING)
        logging.getLogger('push_receiver').setLevel(logging.WARNING)
      
    @staticmethod
    def genMccMncList() -> Any:

        td_re = re.compile('<td>(.*)</td>')
        
        with urllib.request.urlopen('http://mcc-mnc.com/') as f:
            html = f.read().decode('utf-8')

        tbody_start = False
        mcc_mnc_list = []

        i=0
        for line in html.split('\n'):        
            if '<tbody>' in line:
                tbody_start = True
                logger.info("start")
            elif '</tbody>' in line:
                break
            elif tbody_start:
                td_search = td_re.search(line)     

                if td_search is None:
                    continue       
                                        
                if i==0:
                    current_item = {}
                    current_item['mcc'] = td_search[1]
                    i+=1
                    continue
                if i==1:
                    current_item['mnc'] = td_search[1]
                    i+=1
                    continue
                if i==2:
                    current_item['iso'] = td_search[1]
                    i+=1
                    continue            
                if i==3:
                    current_item['country'] = td_search[1]
                    i+=1
                    continue            
                if i==4:
                    current_item['countryCode'] = td_search[1]
                    i+=1
                    continue            
                if i==5:
                    current_item['network'] = td_search[1]
                    mcc_mnc_list.append(current_item)
                    i=0
                    continue      
        with open("mcc_mnc.json", 'w', encoding='utf8') as f2:
            f2.write(json.dumps(mcc_mnc_list, indent=2))           
    
    @staticmethod
    def getMccMnc(countryCode) -> Any:
        return {
            "mnc":"000",
            "mcc":"000"
        }

        '''
        with open("mcc_mnc.json", 'r', encoding='utf8') as f:            
            list =json.loads(f.read())
        map = {}
        for item in list:
            if item["countryCode"] not in map:
                map[item["countryCode"]] = []
            map[item["countryCode"]].append({"mcc":item["mcc"],"mnc":item["mnc"],"iso":item["iso"],"network":item["network"].strip()})
        x = random.choice(map[countryCode])
        return x
        '''

    @staticmethod
    def getMobileCC(mobile) -> Any:
        with open("data/mcc_mnc.json", encoding='utf8') as f:            
            list =json.loads(f.read())
        map = {}
        for item in list:
            if item["countryCode"]!="":
                map[item["countryCode"]] = 1
        
        for k in map:
            if mobile.startswith(k):                                                
                return k

    @staticmethod
    def getLGLC(countryCode) -> Any:

        for item in GlobalVar.COUNTRYCODE:
            if item[1] == countryCode:
                return item[3],item[4]

        logger.info("LGLC not Found, set US as default")
        return "en","US"        

    @staticmethod
    def exit(code) -> Any:
        sys.exit(code)


    @staticmethod
    def fail_exit(msg) -> Any:
        Utils.outputResult({
            "retcode":-1,
            "msg":msg
        })
        Utils.exit(0)
        
    @staticmethod
    def success_exit() -> Any:
        Utils.outputResult({
            "retcode":0,
            "msg":"success"
        })
        Utils.exit(0)        
    
    @staticmethod
    def getDeviceEnvByInfo(info) -> Any:

        if info is not None and "regType" in info:
            if "osType" not in info:
                info["osType"]=2

            if info["regType"]==1:
                if info["osType"]==1:
                    return DeviceEnv("android",random=True)
                if info["osType"]==2:
                    return DeviceEnv("ios",random=True)                
            else:
                if info["osType"]==1:
                    return DeviceEnv("smb_android",random=True)
                if info["osType"]==2:
                    return DeviceEnv("smb_ios",random=True) 
                       
    @staticmethod           
    def profile2Channel(config,db) -> Any:

        kp = config.client_static_keypair
        pk1 = Utils.b64str(kp.public.data)
        sk1 = Utils.b64str(kp.private.data)        
        pk2 = Utils.b64str(db.identity.publicKey.serialize()[1:])
        sk2 = Utils.b64str(db.identity.privateKey.serialize())

        sixth = Utils.b64str(config.phone.encode()+b"#"+config.id)
        return f"{config.phone},{pk1},{sk1},{pk2},{sk2},{sixth}"
    
    @staticmethod
    def profile2Context(profilePath,userName=None) -> Any:

        if userName is None:
            userName = profilePath.split("/")[-1]

        config_manager = ConfigManager()
        config = config_manager.load(profilePath)
        db = AxolotlManagerFactory().get_manager(profilePath,userName)
        signedprekey = db.load_latest_signed_prekey(generate=True)
        return {
            "config": json.loads(str(config)),
            "db": {
                "regid":db.registration_id,                
                "pk2":Utils.b64str(db.identity.publicKey.serialize()[1:]),
                "sk2":Utils.b64str(db.identity.privateKey.serialize()),
                "spkid":signedprekey.getId(),        
                "spkts":signedprekey.getTimestamp(),
                "spkrecord":Utils.b64str(signedprekey.serialize())                
            }
        }
    @staticmethod
    def context2Profile(contextJson,profilePath,userName=None) -> Any:

        if os.path.exists(profilePath):
            shutil.rmtree(profilePath)

        Utils.assureDir(profilePath)    #没有就新�?
        #STEP1 FILE                                                
        file = open(profilePath+'/config.json','w+')    
        file.write(json.dumps(contextJson["config"]))
        file.close()      
        #STEP2 DB
        if userName is None:
            userName = profilePath.split("/")[-1]
        db = AxolotlManagerFactory().get_manager(profilePath,userName)
        db._store.identityKeyStore.dbConn.execute("CREATE TABLE IF NOT EXISTS identities (_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "recipient_id INTEGER,"
                    "recipient_type INTEGER NOT NULL DEFAULT 0, device_id INTEGER,"
                    "registration_id INTEGER, public_key BLOB, private_key BLOB,"
                    "next_prekey_id INTEGER, timestamp INTEGER);")     

        db._store.identityKeyStore.dbConn.execute("DELETE FROM prekeys")

        q = "UPDATE identities SET registration_id=? , public_key=? , private_key=? WHERE recipient_id=-1 AND recipient_type=0"
        c = db._store.identityKeyStore.dbConn.cursor()
        pubKey = b'\x05'+base64.b64decode(contextJson["db"]["pk2"])
        privKey = base64.b64decode(contextJson["db"]["sk2"])
        c.execute(q, (contextJson["db"]["regid"],                            
                        pubKey,
                        privKey))                
        db._store.identityKeyStore.dbConn.commit()        
        
        db._store.signedPreKeyStore.dbConn.execute("CREATE TABLE IF NOT EXISTS signed_prekeys (_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                       "prekey_id INTEGER UNIQUE, timestamp INTEGER, record BLOB);")   
        
        prekey_id = contextJson["db"]["spkid"]        
        record = SignedPreKeyRecord(serialized = base64.b64decode(contextJson["db"]["spkrecord"]))
        db._store.signedPreKeyStore.storeSignedPreKey(prekey_id,record) 
        db._store.signedPreKeyStore.dbConn.commit()

    @staticmethod
    def vnamePayload(name,privateKey) -> Any:
        
        payload = e2e_pb2.VerifiedNameCertificate()            
        details = e2e_pb2.VerifiedNameCertificate.Details()
        details.serial = random.randint(1000000000000000000,9999999999999999999)                   
        details.issuer = "smb:wa"        
        details.verifiedName = name
        payload.details.MergeFrom(details)                                                      
        payload.signature = Curve.calculateSignature(privateKey,payload.details.SerializeToString())

        return payload
    
    
    @staticmethod
    def b64str(data) -> str:
        return str(base64.b64encode(data),"UTF-8")
    





        
                

          

            
    
    
    


        
        




