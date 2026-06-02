import os
import re
import logging
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import unpad
import traceback
from typing import Any, Optional, Dict, List, Tuple


logger = logging.getLogger(__name__)

class RC2:

    SOMETOKEN = "A\004\035@\021\030V\u0091\002\u0090\u0088\u009F\u009ET(3{;ES"

    def do_something(s: str) -> Any:
        return ''.join(chr(ord(c) ^ 18) for c in s)

    def get_recovery_jid_from_jid(phone_number: str) -> Any:
        pattern = r"^([17]|2[07]|3[0123469]|4[013456789]|5[12345678]|6[0123456]|8[1246]|9[0123458]|\d{3})\d*?(\d{4,6})$"
        match = re.match(pattern, phone_number)
        if match:
            return match.group(1) + match.group(2)
        return ""

    def read_file(file_path) -> Any:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, "rb") as f:               
                bs = f.read() 
        return bs
    
    def write_file(file_path,buf) -> Any:
        with open(file_path, "wb+") as f:    
            f.write(b'\xac\xed\x00\x05\x75\x72\x00\x02\x5b\x42\xac\xf3\x17\xf8\x06\x08\x54\xe0\x02\x00\x00\x78\x70\x00\x00\x00\x2a')        #JavaByteArray header
            f.write(buf)
        return     

    def byte_to_hex(b: bytes) -> Any:
        return b.hex()

    @staticmethod
    def decrypted_token_from_bytes(payload_bytes,phoneNumber) -> Any:
        logger.debug(payload_bytes)
        header_bytes = b"\x00\x02"
        if len(payload_bytes) >= 42:                    
            file_header = payload_bytes[:2]
            if file_header == payload_bytes[0:2]:
                key_bytes = payload_bytes[2:6]                        
                iv_bytes = payload_bytes[6:22]                        
                password =  (RC2.do_something(RC2.SOMETOKEN) + RC2.get_recovery_jid_from_jid(phoneNumber)).encode("utf-8")                           
                s1 = PBKDF2(password, key_bytes, dkLen=16, count=16)
                cipher = AES.new(s1, AES.MODE_OFB, iv=iv_bytes)
                decrypted = cipher.decrypt(payload_bytes[22:])
                return decrypted
            else:
                raise Exception("payload header mismatch")
        else:
            raise ValueError(f"payload size mismatch")        


    def decrypt_token_from_rc2(filePath,phoneNumber) -> Any:
        try:
            file_bytes = RC2.read_file(filePath)                        
            if file_bytes is not None:                         
                return RC2.decrypted_token_from_bytes(file_bytes[-42:],phoneNumber)      
            return None
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
        
    def encrypt_token_to_rc2(filePath,phoneNumber, rc_bytes) -> Any:
        
        try:
            header_bytes = bytes([0, 2])            
            password =  (RC2.do_something(RC2.SOMETOKEN) + RC2.get_recovery_jid_from_jid(phoneNumber)).encode("utf-8")            
            key_bytes = os.urandom(4)
            iv_bytes =  os.urandom(16)
            s1 = PBKDF2(password, key_bytes, dkLen=16, count=16)
            cipher = AES.new(s1, AES.MODE_OFB, iv=iv_bytes)
            content_bytes = cipher.encrypt(rc_bytes)                                        
            RC2.write_file(filePath,header_bytes + key_bytes + iv_bytes + content_bytes)                
        except Exception as e:
            logger.error("rc2 generating error: %s", e, exc_info=True)