from .message_media import MediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class DownloadableMediaMessageProtocolEntity(MediaMessageProtocolEntity):
    def __init__(self, media_type, message_attrs, message_meta_attrs) -> None:
        # type: (str, MessageAttributes, MessageMetaAttributes) -> None
        super().__init__(
            media_type, message_attrs, message_meta_attrs
        )

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        raise NotImplementedError()

    @property
    def url(self) -> Any:
        return self.downloadablemedia_specific_attributes.url

    @url.setter
    def url(self, value: Any) -> None:
        self.downloadablemedia_specific_attributes.url = value

    @property
    def mimetype(self) -> Any:
        return self.downloadablemedia_specific_attributes.mimetype

    @mimetype.setter
    def mimetype(self, value: Any) -> None:
        self.downloadablemedia_specific_attributes.mimetype = value

    @property
    def file_sha256(self) -> Any:
        return self.downloadablemedia_specific_attributes.file_sha256

    @file_sha256.setter
    def file_sha256(self, value: Any) -> None:
        self.downloadablemedia_specific_attributes.file_sha256 = value

    @property
    def file_length(self) -> Any:
        return self.downloadablemedia_specific_attributes.file_length

    @file_length.setter
    def file_length(self, value: Any) -> None:
        self.downloadablemedia_specific_attributes.file_length = value

    @property
    def media_key(self) -> Any:
        return self.downloadablemedia_specific_attributes.media_key

    @media_key.setter
    def media_key(self, value: Any) -> None:
        self.downloadablemedia_specific_attributes.media_key = value

