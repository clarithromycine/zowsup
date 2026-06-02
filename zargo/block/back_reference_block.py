from typing import Any, Optional, Dict, List, Tuple, Union, Callable

class BackReferenceBlock() :

    def __init__(self,index):
        self.index = index

    def __str__(self) -> Any:
        return "Backreference(index=%d)" % self.index

        
        

