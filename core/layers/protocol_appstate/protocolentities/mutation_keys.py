from common.utils import Utils
from typing import Optional, Any, List, Dict, Union

class MutationKeys:
    
    def __init__(self,indexKey,encKey,macKey,snapShotMacKey,patchMacKey) -> None:
        self.indexKey = indexKey
        self.encKey = encKey
        self.macKey = macKey
        self.snapShotMacKey = snapShotMacKey
        self.patchMacKey = patchMacKey

    @staticmethod
    def createFromKey(key):

        #从一个key生成5个key，保证sync流程用到的key
        ba = Utils.extract_and_expand(
            key = key,
            info = b"WhatsApp Mutation Keys",
            output_length=160
        )

        return MutationKeys(
            indexKey = ba[0:32],
            encKey = ba[32:64],
            macKey = ba[64:96],
            snapShotMacKey= ba[96:128],        
            patchMacKey=  ba[128:]
        )





        
