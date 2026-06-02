from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_groups_participants  import ParticipantsGroupsIqProtocolEntity

class DemoteParticipantsIqProtocolEntity(ParticipantsGroupsIqProtocolEntity):
    '''
    <iq type="set" id="{{id}}" xmlns="w:g2", to="{{group_jid}}">
        <demote>
            <participant jid="{{jid}}" />
            <participant jid="{{jid}}" />
        </demote>
    </iq>
    '''

    def __init__(self, group_jid, participantList, _id = None) -> None:
        super().__init__(group_jid, participantList, "demote", _id = _id)
    

