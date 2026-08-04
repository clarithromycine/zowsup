from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....structs import ProtocolTreeNode
from .....common import YowConstants


'''
<iq xmlns='w:b' smax_id='143' to='s.whatsapp.net' type='get' id='05'/>

'''
'''
<iq from='s.whatsapp.net' type='result' id='05'>
    <limits messages_left='35' total_limit='35' is_heavy_sender='false'/>
    <timeframe start_ts_s='1782878400' end_ts_s='1785556799' reset_ts_s='1785556800'/>
</iq>

'''

class GetBroadcastLimitationProtocolEntity(IqProtocolEntity):
    def __init__(self) -> None:
        super().__init__("w:b", _type="get",to="s.whatsapp.net",smax_id="143")

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()        
        return node


'''
<iq from='s.whatsapp.net' type='result' id='05'>
    <limits messages_left='35' total_limit='35' is_heavy_sender='false'/>
    <timeframe start_ts_s='1782878400' end_ts_s='1785556799' reset_ts_s='1785556800'/>
</iq>

'''


class GetBroadcastLimitationResultProtocolEntity(IqProtocolEntity):

    def __init__(self,_id=None, messagesLeft=None, totalLimit=None, isHeavySender=None,
                 startTs=None, endTs=None, resetTs=None) -> None:
        super().__init__(_id = _id, _type = "result", to=YowConstants.DOMAIN)
        self.messagesLeft = messagesLeft
        self.totalLimit = totalLimit
        self.isHeavySender = isHeavySender
        self.startTs = startTs
        self.endTs = endTs
        self.resetTs = resetTs

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = GetBroadcastLimitationResultProtocolEntity

        limitsNode = node.getChild("limits")
        if limitsNode is not None:
            entity.messagesLeft = int(limitsNode.getAttributeValue("messages_left"))
            entity.totalLimit = int(limitsNode.getAttributeValue("total_limit"))
            entity.isHeavySender = (limitsNode.getAttributeValue("is_heavy_sender")=="true")
        else:
            entity.messagesLeft = None
            entity.totalLimit = None
            entity.isHeavySender = None

        timeframeNode = node.getChild("timeframe")
        if timeframeNode is not None:
            entity.startTs = int(timeframeNode.getAttributeValue("start_ts_s"))
            entity.endTs =int(timeframeNode.getAttributeValue("end_ts_s"))
            entity.resetTs = int(timeframeNode.getAttributeValue("reset_ts_s"))
        else:
            entity.startTs = None
            entity.endTs = None
            entity.resetTs = None

        return entity
