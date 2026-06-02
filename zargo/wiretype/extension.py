from typing import Any, Optional, Dict, List, Tuple, Union, Callable



class ExtensionWireType :

    def  __init__(self,inner):
        self.inner = inner

    def __str__(self) -> Any:
        return "ExtensionWireType(inner=%s)" % (self.inner)
    




    