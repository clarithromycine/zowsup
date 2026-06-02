from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_contact import ContactAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class ContactMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, contact_attrs, message_meta_attrs) -> None:
        # type: (ContactAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "contact", MessageAttributes(contact=contact_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.contact

    @property
    def display_name(self) -> Any:
        return self.media_specific_attributes.display_name

    @display_name.setter
    def display_name(self, value: Any) -> None:
        self.media_specific_attributes.display_name = value

    @property
    def vcard(self) -> Any:
        return self.media_specific_attributes.vcard

    @vcard.setter
    def vcard(self, value: Any) -> None:
        self.media_specific_attributes.vcard = value
