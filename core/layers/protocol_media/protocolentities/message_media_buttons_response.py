from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_buttons_response import ButtonsResponseAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes

'''
BUTTON , LIST AND TEMPLATE MESSAGE WAS DEPRECATED BECAUSE OF THE  SERVER FILTERS  UPDATED AT 2023.5.11
'''
class ButtonsResponseMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, buttons_response_attr, message_meta_attrs) -> None:
        # type: (ButtonsResponseAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "buttons_response", MessageAttributes(buttons_response=buttons_response_attr), message_meta_attrs
        )

    @property
    def selected_button_id(self) -> Any:
        return self.message_attributes.buttons_response.selected_button_id

    @selected_button_id.setter
    def selected_button_id(self, value: Any) -> None:
        self.message_attributes.buttons_response.selected_button_id = value

    @property
    def selected_display_text(self) -> Any:
        return self.message_attributes.buttons_response.selected_display_text

    @selected_display_text.setter
    def selected_display_text(self, value: Any) -> None:
        self.message_attributes.buttons_response.selected_display_text = value

    @property
    def type(self) -> Any:
        return self.message_attributes.buttons_response.type

    @type.setter
    def type(self, value: Any) -> None:
        self.message_attributes.buttons_response.type = value
