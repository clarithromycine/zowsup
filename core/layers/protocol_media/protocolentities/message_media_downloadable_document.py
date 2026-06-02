from .message_media_downloadable import DownloadableMediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_document import DocumentAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class DocumentDownloadableMediaMessageProtocolEntity(DownloadableMediaMessageProtocolEntity):
    def __init__(self, document_attrs, message_meta_attrs) -> None:
        """
        :type document_attrs: DocumentAttributes
        :type message_meta_attrs: MessageMetaAttributes
        """
        super().__init__(
            "document", MessageAttributes(document=document_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.document

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        if self.message_attributes.document:
            return self.message_attributes.document.downloadablemedia_attributes
        return None

    @property
    def file_name(self) -> Any:
        return self.media_specific_attributes.file_name

    @file_name.setter
    def file_name(self, value: Any) -> None:
        self.media_specific_attributes.file_name = value

    @property
    def file_length(self) -> Any:
        return self.media_specific_attributes.file_length

    @file_length.setter
    def file_length(self, value: Any) -> None:
        self.media_specific_attributes.file_length = value

    @property
    def title(self) -> Any:
        return self.media_specific_attributes.title

    @title.setter
    def title(self, value: Any) -> None:
        self.media_specific_attributes.title = value

    @property
    def page_count(self) -> Any:
        return self.media_specific_attributes.page_count

    @page_count.setter
    def page_count(self, value: Any) -> None:
        self.media_specific_attributes.page_count = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self.media_specific_attributes.image_message.jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.image_message.jpeg_thumbnail = value


    @property
    def caption(self) -> Any:
        return self.media_specific_attributes.caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self.media_specific_attributes.caption = value        
