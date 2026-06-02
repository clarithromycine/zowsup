from .message_media_downloadable import DownloadableMediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_video import VideoAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class VideoDownloadableMediaMessageProtocolEntity(DownloadableMediaMessageProtocolEntity):
    def __init__(self, video_attrs, message_meta_attrs) -> None:
        # type: (VideoAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "video", MessageAttributes(video=video_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.video

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        return self.message_attributes.video.downloadablemedia_attributes

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
    def seconds(self) -> Any:
        return self.media_specific_attributes.seconds

    @seconds.setter
    def seconds(self, value: Any) -> None:
        self.media_specific_attributes.seconds = value

    @property
    def gif_playback(self) -> Any:
        return self.media_specific_attributes.gif_playback

    @gif_playback.setter
    def gif_playback(self, value: Any) -> None:
        self.media_specific_attributes.gif_playback = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self.media_specific_attributes.jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self.media_specific_attributes.jpeg_thumbnail = value

    @property
    def caption(self) -> Any:
        return self.media_specific_attributes.caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self.media_specific_attributes.caption = value

    @property
    def gif_attribution(self) -> Any:
        return self.proto.gif_attribution

    @gif_attribution.setter
    def gif_attribution(self, value: Any) -> None:
        self.media_specific_attributes.gif_attributions = value

    @property
    def streaming_sidecar(self) -> Any:
        return self.media_specific_attributes.streaming_sidecar

    @streaming_sidecar.setter
    def streaming_sidecar(self, value: Any) -> None:
        self.media_specific_attributes.streaming_sidecar = value
