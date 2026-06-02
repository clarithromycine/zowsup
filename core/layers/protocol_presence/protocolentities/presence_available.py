from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .presence import PresenceProtocolEntity
class AvailablePresenceProtocolEntity(PresenceProtocolEntity):
    '''
    [send]
    <presence type="available"></presence>
    
    [received]
    <presence from="self.jid">
    </presence>

    '''
    def __init__(self) -> None:
        super().__init__("available")