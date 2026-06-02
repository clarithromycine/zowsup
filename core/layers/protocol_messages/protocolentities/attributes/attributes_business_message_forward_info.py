from typing import Any
class BusinessMessageForwardInfoAttributes:
    def __init__(self,
                 business_owner_jid=None,
                ) -> None:
    
        self._business_owner_jid = business_owner_jid

    @property
    def business_owner_jid(self) -> Any:
        return self._business_owner_jid

    @business_owner_jid.setter
    def business_owner_jid(self, value: Any) -> None:
        self._business_owner_jid = value       

