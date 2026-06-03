from typing import Any, Optional, Dict, List, Tuple, Union, Callable



class ArgoFieldWireType :

    def  __init__(self,type,name,omittable):
        self.name = name
        self.type = type
        self.omittable = omittable

    def __str__(self) -> Any:
        return "ArgoFieldWireType(name={}, type={}, omittable={})".format(self.name, self.type, self.omittable)
    




    