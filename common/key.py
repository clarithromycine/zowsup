import base64
import os
from typing import Any, Optional, Dict, List, Tuple


class KEY:
    '''
    key算法
    cipherVersion 固定 \x00\x01
    keyVersion    固定 \x02
    serverSalt和cipherKey 可以通过 crypto create 获取 
    googleIdSalt是一个随机的16bytes
    hashedGoogleIdSalt 是googleIdSalt 的 sha256
    encryptionIv  固定为16位\x00
    '''

    @staticmethod
    def parseFile(filePath) -> Any:
        if os.path.exists(filePath) and os.path.getsize(filePath) > 0:
            
            with open(filePath,"rb") as f:
                fileBytes = f.read()
                fileBytes = fileBytes[-131:]
                ret = {
                    "cipherVersion": str(fileBytes[0])+str(fileBytes[1]),
                    "keyVersion":   str(fileBytes[2]),
                    "serverSalt":   base64.b64encode(fileBytes[3:3+32]).decode(),
                    "googleIdSalt": base64.b64encode(fileBytes[35:35+16]).decode(),
                    "hashedGoogleIdSalt":base64.b64encode(fileBytes[51:51+32]).decode(),
                    "encryptionIv":  base64.b64encode(fileBytes[83:83+16]).decode(),
                    "cipherKey":  base64.b64encode(fileBytes[99:99+32]).decode()
                }
                return ret
    
        return None

    @staticmethod
    def generateFile(filePath,tokenDict) -> Any:
        with open(filePath,"wb+") as f:
            f.write("\x00\x01")     #cipherVersion
            f.write("\x02")         #keyVersion
            f.write(base64.b64decode(tokenDict.get("serverSalt")))
            f.write(base64.b64decode(tokenDict.get("googleIdSalt")))
            f.write(base64.b64decode(tokenDict.get("hashedGoogleIdSalt")))
            f.write("\x00" * 16)    #encryptionIv
            f.write(base64.b64decode(tokenDict.get("cipherKey")))

