from typing import Any, Optional, Dict, List, Tuple, Union, Callable
class ParamsNotEnoughException(Exception):
    
    def __init__(self):        
        pass
    
    def getMsg(self) -> Any:
        return "Params not enough"