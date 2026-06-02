from typing import Any, Optional, Dict, List, Tuple, Union, Callable

class InlineBlock() :

    def __init__(self,header):
        self.header = header

    def __str__(self) -> Any:
        return "InlineBlock(header=%s)" % (self.header)

        
        

