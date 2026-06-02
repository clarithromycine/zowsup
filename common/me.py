import os
import logging
from .utils import Utils
from typing import Any, Optional, Dict, List, Tuple


logger = logging.getLogger(__name__)

class ME:

    @staticmethod
    def parseFile(filePath) -> Any:
                  
        if os.path.exists(filePath) and os.path.getsize(filePath) > 0:
            with open(filePath, "rb") as f:               
                bs = f.read() 
            logger.debug(bs[0:93])    
            bs = bs[93:]        
            
            ccStart = 1            
            ccLen = (int(bs[ccStart])<<8)+int(bs[ccStart+1])            
            cc = bs[ccStart+2:ccStart+2+ccLen]            
            fnumstart = ccStart+2+ccLen+1
            fnumLen = (int(bs[fnumstart])<<8)+int(bs[fnumstart+1])
            fnum = bs[fnumstart+2:fnumstart+2+fnumLen]
            numstart = fnumstart+2+fnumLen+1
            numLen = (int(bs[numstart])<<8)+int(bs[numstart+1])
            num = bs[numstart+2:numstart+2+numLen]


            return {
                "cc": cc.decode(),
                "in": num.decode(),
                "num": fnum.decode(),
            }



    @staticmethod    
    def generateFile(filePath,num) -> Any:

        cc = Utils.getMobileCC(num)        
        _in = num[len(cc):]

        with open(filePath,"wb+") as f:
            f.write(b'\xac\xed\x00\x05sr\x00\x0fcom.whatsapp.Me\xe4\xe8\xad\xd1\xac\xe0e\xaa\x02\x00\x03L\x00\x02cct\x00\x12Ljava/lang/String;L\x00\tjabber_idq\x00~\x00\x01L\x00\x06numberq\x00~\x00\x01xp')                    
            ccLen = len(cc)
            f.write(b'\x74')
            f.write(ccLen.to_bytes(2, byteorder='big'))
            f.write(cc.encode())
            numLen = len(num)
            f.write(b'\x74')
            f.write(numLen.to_bytes(2, byteorder='big'))
            f.write(num.encode())
            inLen = len(_in)
            f.write(b'\x74')
            f.write(inLen.to_bytes(2, byteorder='big'))
            f.write(_in.encode())







    
