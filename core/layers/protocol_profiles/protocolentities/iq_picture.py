from ....layers.protocol_iq.protocolentities import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
class PictureIqProtocolEntity(IqProtocolEntity):
    '''
    When receiving a profile picture:
    <iq type="result" from="{{jid}}" id="{{id}}">
        <picture type="image" id="{{another_id}}">
        {{Binary bytes of the picture.}}
        </picture>
    </iq>
    '''
    XMLNS = "w:profile:picture"

    def __init__(self, to=None , _from = None, _id = None, type = "get",target=None) -> None:
        super().__init__(self.__class__.XMLNS, _id = _id, _type=type, to = to, _from = _from, target=target)