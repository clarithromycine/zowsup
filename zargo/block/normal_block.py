from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from zargo.utils.data_reader import DataReader

class NormalBlock() :

    def __init__(self,header,blockData):
        self.header = header
        self.blockData = blockData
        self.reader = DataReader(blockData)        

    def __str__(self) -> Any:
        return "NormalBlock(header=%s, data=%s)" % (self.header,self.blockData)

        
        

