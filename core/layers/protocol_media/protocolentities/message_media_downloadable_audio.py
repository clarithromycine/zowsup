from .message_media_downloadable import DownloadableMediaMessageProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....layers.protocol_messages.protocolentities.attributes.attributes_audio import AudioAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message_meta import MessageMetaAttributes
from ....layers.protocol_messages.protocolentities.attributes.attributes_message import MessageAttributes


class AudioDownloadableMediaMessageProtocolEntity(DownloadableMediaMessageProtocolEntity):
    def __init__(self, audio_attrs, message_meta_attrs) -> None:
        # type: (AudioAttributes, MessageMetaAttributes) -> None
        super().__init__(
            "audio", MessageAttributes(audio=audio_attrs), message_meta_attrs
        )

    @property
    def media_specific_attributes(self) -> Any:
        return self.message_attributes.audio

    @property
    def downloadablemedia_specific_attributes(self) -> Any:
        return self.message_attributes.audio.downloadablemedia_attributes

    @property
    def seconds(self) -> Any:
        return self.media_specific_attributes.seconds

    @seconds.setter
    def seconds(self, value: Any) -> None:
        """
        :type value: int
        """
        self.media_specific_attributes.seconds = value

    @property
    def ptt(self) -> Any:
        return self.media_specific_attributes.ptt

    @ptt.setter
    def ptt(self, value: Any) -> None:
        """
        :type value: bool
        """
        self.media_specific_attributes.ptt = value

    @property
    def streaming_sidecar(self) -> Any:
        return self.media_specific_attributes.streaming_sidecar

    @streaming_sidecar.setter
    def streaming_sidecar(self, value: Any) -> None:
        self.media_specific_attributes.streaming_sidecar = value
