from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from ....layers.protocol_messages.protocolentities.protomessage import ProtomessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class ExtendedTextMessageProtocolEntity(ProtomessageProtocolEntity):
    def __init__(self, extended_text_attrs, message_meta_attrs) -> None:
        # type: (ExtendedTextAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "text", MessageAttributes(extended_text=extended_text_attrs), message_meta_attrs
        )

    @property
    def text(self) -> Any:
        return self.message_attributes.extended_text.text

    @text.setter
    def text(self, value: Any) -> None:
        self.message_attributes.extended_text.text = value

    @property
    def context_info(self) -> Any:
        return self.message_attributes.extended_text.context_info

    @context_info.setter
    def context_info(self, value: Any) -> None:
        self.message_attributes.extended_text.context_info = value
