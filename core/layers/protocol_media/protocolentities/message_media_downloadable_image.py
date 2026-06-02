from .message_media_downloadable import DownloadableMediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_image import ImageAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class ImageDownloadableMediaMessageProtocolEntity(DownloadableMediaMessageProtocolEntity):
    def __init__(self, image_attrs, message_meta_attrs) -> None:
        # type: (ImageAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "image", MessageAttributes(image=image_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.image

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        return self.message_attributes.image.downloadablemedia_attributes

    @property
    def width(self) -> Any:
        return self.media_specific_attributes.width

    @width.setter
    def width(self, value: Any) -> None:
        self.media_specific_attributes.width = value

    @property
    def height(self) -> Any:
        return self.media_specific_attributes.height

    @height.setter
    def height(self, value: Any) -> None:
        self.media_specific_attributes.height = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self.media_specific_attributes.jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.jpeg_thumbnail = value if value is not None else b""

    @property
    def caption(self) -> Any:
        return self.media_specific_attributes.caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self.media_specific_attributes.caption = value if value is not None else ""
