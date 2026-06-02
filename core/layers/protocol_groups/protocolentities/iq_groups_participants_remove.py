from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups_participants import ParticipantsGroupsIqProtocolEntity

class RemoveParticipantsIqProtocolEntity(ParticipantsGroupsIqProtocolEntity):
    '''
    <iq type="set" id="{{id}}" xmlns="w:g2", to="{{group_jid}}">
        <remove>
            <participant jid="{{jid}}"></participant>
            <participant jid="{{jid}}"></participant>
        </remove>
    </iq>
    '''
    
    def __init__(self, group_jid, participantList, _id = None) -> None:
        super().__init__(group_jid, participantList, "remove", _id = _id)
        
