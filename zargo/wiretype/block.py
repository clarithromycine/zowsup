from typing import Any, Optional, Dict, List, Tuple, Union, Callable



class ArgoBlockWireType :

    def  __init__(self,wireType,key,dedupe):
        self.wireType = wireType
        self.key = key
        self.dedupe = dedupe

    def __str__(self) -> Any:
        return "ArgoBlockWireType(of=%s, key=%s, dedupe=%s)" % (self.wireType,self.key,str(self.dedupe))
    

    

    
    
        


    