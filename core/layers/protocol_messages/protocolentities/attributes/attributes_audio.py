from .....layers.protocol_messages.protocolentities.attributes.attributes_downloadablemedia import \
    DownloadableMediaMessageAttributes
from typing import Optional, Any, List, Dict, Union

from .....common.tools import AudioTools
import os
import requests
from conf.constants import SysVar

class AudioAttributes:
    def __init__(self, downloadablemedia_attributes, seconds, ptt, streaming_sidecar=None) -> None:
        # type: (DownloadableMediaMessageAttributes, int, bool, bytes) -> None
        """
        :param seconds: duration of audio playback in seconds
        :param ptt: indicates whether this is a push-to-talk audio message
        :param streaming_sidecar
        """
        self._downloadablemedia_attributes = downloadablemedia_attributes
        self._seconds = seconds  # type: int
        self._ptt = ptt  # type: bool
        self._streaming_sidecar = streaming_sidecar  # type: bytes

    def __str__(self):
        attrs = []
        if self.seconds is not None:
            attrs.append(("seconds", self.seconds))
        if self.ptt is not None:
            attrs.append(("ptt", self.ptt))
        if self._streaming_sidecar is not None:
            attrs.append(("streaming_sidecar", "[binary data]"))
        attrs.append(("downloadable", self.downloadablemedia_attributes))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def downloadablemedia_attributes(self) -> Any:
        return self._downloadablemedia_attributes

    @downloadablemedia_attributes.setter
    def downloadablemedia_attributes(self, value: Any) -> None:
        self._downloadablemedia_attributes = value

    @property
    def seconds(self) -> Any:
        return self._seconds

    @seconds.setter
    def seconds(self, value: Any) -> None:
        self._seconds = value

    @property
    def ptt(self) -> Any:
        return self._ptt

    @ptt.setter
    def ptt(self, value: Any) -> None:
        self._ptt = value

    @property
    def streaming_sidecar(self) -> Any:
        return self._streaming_sidecar

    @streaming_sidecar.setter
    def streaming_sidecar(self, value: Any) -> None:
        self._streaming_sidecar = value


    @staticmethod
    def from_filepath(filepath,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        audioPropertis=None, ptt=False,streaming_sidecar=None):
        assert os.path.exists(filepath)
        audioPropertis = audioPropertis or AudioTools.getAudioProperties(filepath)
        seconds= audioPropertis if audioPropertis else None
        
        return AudioAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), seconds, ptt,streaming_sidecar
        )
    

    @staticmethod
    def from_url(url,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        audioPropertis=None, ptt=False,streaming_sidecar=None):

        down_res = requests.get(url=url)
        filename = url[url.rfind("/",0):]
        filepath = SysVar.DOWNLOAD_PATH+filename                
        with open(filepath,"wb") as file:
            file.write(down_res.content)       

        audioPropertis = audioPropertis or AudioTools.getAudioProperties(filepath)
        seconds= audioPropertis if audioPropertis else None
        
        return AudioAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), seconds, ptt,streaming_sidecar
        )