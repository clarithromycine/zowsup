from typing import Any, Optional, Dict, List, Tuple, Union, Callable



class ErrorWireType :

    def  __init__(self,inner):
        self.inner = inner

    def __str__(self) -> Any:
        return "ErrorWireType(inner=%s)" % (self.inner)
    




    