from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_buttons_response import ButtonsResponseAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes

'''
BUTTON , LIST AND TEMPLATE MESSAGE WAS DEPRECATED BECAUSE OF THE  SERVER FILTERS  UPDATED AT 2023.5.11
'''
class ListMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, list_attr, message_meta_attrs) -> None:        
        super().__init__(
            "list", MessageAttributes(list=list_attr), message_meta_attrs
        )

    @property
    def title(self) -> Any:
        return self.message_attributes.list.title

    @title.setter
    def title(self, value: Any) -> None:
        self.message_attributes.list.title = value

    @property
    def description(self) -> Any:
        return self.message_attributes.list.description

    @description.setter
    def description(self, value: Any) -> None:
        self.message_attributes.list.description = value

    @property
    def text(self) -> Any:
        return self.message_attributes.list.text

    @text.setter
    def text(self, value: Any) -> None:
        self.message_attributes.list.text = value

    @property
    def footer(self) -> Any:
        return self.message_attributes.list.footer
        
    @footer.setter
    def footer(self, value: Any) -> None:
        self.message_attributes.list.footer = value        

    @property
    def list_content(self) -> Any:
        return self.message_attributes.list.list_content
        
    @list_content.setter
    def list_content(self, value: Any) -> None:
        self.message_attributes.list.list_content = value        
