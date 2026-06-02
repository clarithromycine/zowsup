from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_extendedtext import ExtendedTextAttributes
from .message_media import MediaMessageProtocolEntity
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class ExtendedTextMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, extended_text_attrs,  message_meta_attrs) -> None:
        # type: (ExtendedTextAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "url", MessageAttributes(extended_text=extended_text_attrs),  message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.extended_text

    @property
    def text(self) -> Any:
        return self.media_specific_attributes.text

    @text.setter
    def text(self, value: Any) -> None:
        self.media_specific_attributes.text = value

    @property
    def matched_text(self) -> Any:
        return self.media_specific_attributes.matched_text

    @matched_text.setter
    def matched_text(self, value: Any) -> None:
        self.media_specific_attributes.matched_text = value

    @property
    def canonical_url(self) -> Any:
        return self.media_specific_attributes.canonical_url

    @canonical_url.setter
    def canonical_url(self, value: Any) -> None:
        self.media_specific_attributes.canonical_url = value

    @property
    def description(self) -> Any:
        return self.media_specific_attributes.description

    @description.setter
    def description(self, value: Any) -> None:
        self.media_specific_attributes.description = value

    @property
    def title(self) -> Any:
        return self.media_specific_attributes.title

    @title.setter
    def title(self, value: Any) -> None:
        self.media_specific_attributes.title = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self.media_specific_attributes.jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.jpeg_thumbnail = value
