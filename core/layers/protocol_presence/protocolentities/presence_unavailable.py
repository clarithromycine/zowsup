from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .presence import PresenceProtocolEntity
class UnavailablePresenceProtocolEntity(PresenceProtocolEntity):
    '''
    <presence type="unavailable"></presence>
    response:
    <presence type="unavailable" from="self.jid">
    </presence>
    '''
    def __init__(self) -> None:
        super().__init__("unavailable")