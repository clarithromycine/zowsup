from .message_media_downloadable import DownloadableMediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_sticker import StickerAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class StickerDownloadableMediaMessageProtocolEntity(DownloadableMediaMessageProtocolEntity):
    def __init__(self, sticker_attrs, message_meta_attrs) -> None:
        # type: (StickerAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "sticker", MessageAttributes(sticker=sticker_attrs),  message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.sticker

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        return self.message_attributes.sticker.downloadablemedia_attributes

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
    def png_thumbnail(self) -> Any:
        return self.media_specific_attributes.png_thumbnail

    @png_thumbnail.setter
    def png_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.png_thumbnail = value

    @property
    def is_animated(self) -> Any:
        return self.media_specific_attributes.is_animated

    @is_animated.setter
    def is_animated(self, value: Any) -> None:
        self.media_specific_attributes.is_animated = value    

    @property
    def sticker_sent_ts(self) -> Any:
        return self.media_specific_attributes.sticker_sent_ts

    @sticker_sent_ts.setter
    def sticker_sent_ts(self, value: Any) -> None:
        self.media_specific_attributes.sticker_sent_ts = value          

    @property
    def is_avatar(self) -> Any:
        return self.media_specific_attributes.is_avatar

    @is_avatar.setter
    def is_avatar(self, value: Any) -> None:
        self.media_specific_attributes.is_avatar = value     

    @property
    def is_ai_sticker(self) -> Any:
        return self.media_specific_attributes.is_ai_sticker

    @is_ai_sticker.setter
    def is_ai_sticker(self, value: Any) -> None:
        self.media_specific_attributes.is_ai_sticker = value       

    @property
    def is_lottie(self) -> Any:
        return self.media_specific_attributes.is_lottie

    @is_lottie.setter
    def is_lottie(self, value: Any) -> None:
        self.media_specific_attributes.is_lottie = value                           



    


