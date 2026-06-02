from .....common.tools import VideoTools
import os
from typing import Optional, Any, List, Dict, Union
from .....layers.protocol_messages.protocolentities.attributes.attributes_downloadablemedia \
    import DownloadableMediaMessageAttributes
import random
import requests
from conf.constants import SysVar
import uuid

class VideoAttributes:
    def __init__(self, downloadablemedia_attributes, width, height, seconds, caption,
                 gif_playback=None, jpeg_thumbnail=None, gif_attribution=None, streaming_sidecar=None) -> None:
        self._downloadablemedia_attributes = downloadablemedia_attributes
        self._width = width
        self._height = height
        self._seconds = seconds
        self._caption = caption
        self._gif_playback = gif_playback
        self._jpeg_thumbnail = jpeg_thumbnail
        self._gif_attribution = gif_attribution        
        self._streaming_sidecar = streaming_sidecar

    def __str__(self):
        attrs = []
        if self.width is not None:
            attrs.append(("width", self.width))
        if self.height is not None:
            attrs.append(("height", self.height))
        if self.seconds is not None:
            attrs.append(("seconds", self.seconds))
        if self.gif_playback is not None:
            attrs.append(("gif_playback", self.gif_playback))
        if self.jpeg_thumbnail is not None:
            attrs.append(("jpeg_thumbnail", "[binary data]"))
        if self.gif_attribution is not None:
            attrs.append(("gif_attribution", self.gif_attribution))
        if self.caption is not None:
            attrs.append(("caption", self.caption))
        if self.streaming_sidecar is not None:
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
    def width(self) -> Any:
        return self._width

    @width.setter
    def width(self, value: Any) -> None:
        self._width = value

    @property
    def height(self) -> Any:
        return self._height

    @height.setter
    def height(self, value: Any) -> None:
        self._height = value

    @property
    def seconds(self) -> Any:
        return self._seconds

    @seconds.setter
    def seconds(self, value: Any) -> None:
        self._seconds = value

    @property
    def gif_playback(self) -> Any:
        return self._gif_playback

    @gif_playback.setter
    def gif_playback(self, value: Any) -> None:
        self._gif_playback = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self._jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self._jpeg_thumbnail = value

    @property
    def gif_attribution(self) -> Any:
        return self._gif_attribution

    @gif_attribution.setter
    def gif_attribution(self, value: Any) -> None:
        self._gif_attribution = value

    @property
    def caption(self) -> Any:
        return self._caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self._caption = value

    @property
    def streaming_sidecar(self) -> Any:
        return self._streaming_sidecar

    @streaming_sidecar.setter
    def streaming_sidecar(self, value: Any) -> None:
        self._streaming_sidecar = value


    @staticmethod
    def from_filepath(filepath,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        videoPropertis=None, caption=None, jpeg_thumbnail=None):
        assert os.path.exists(filepath)
        if not jpeg_thumbnail:
            jpeg_thumbnail = VideoTools.generatePreviewFromVideo(filepath)
        videoPropertis = videoPropertis or VideoTools.getVideoProperties(filepath)

        width, height, bitRate, seconds, codec = videoPropertis if videoPropertis else (None, None,None,None)

        assert width and height, "Could not determine video properties, install VideoStream or pass videoPropertis by code"

        return VideoAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), width, height, seconds, caption, False, jpeg_thumbnail,gif_attribution=0
        )
    
    @staticmethod
    def from_url(url,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        videoPropertis=None, caption=None, jpeg_thumbnail=None):

        #澶氫竴涓笅杞芥祦绋?
        down_res = requests.get(url=url)
        filename = url[url.rfind("/",0):]
        filepath = SysVar.DOWNLOAD_PATH+filename                
        with open(filepath,"wb") as file:
            file.write(down_res.content)             

        assert os.path.exists(filepath)

        if not jpeg_thumbnail:
            jpeg_thumbnail = VideoTools.generatePreviewFromVideo(filepath)
        videoPropertis = videoPropertis or VideoTools.getVideoProperties(filepath)

        width, height, bitRate, seconds, codec = videoPropertis if videoPropertis else (None, None,None,None)

        assert width and height, "Could not determine video properties, install VideoStream or pass videoPropertis by code"

        return VideoAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), width, height, seconds, caption, False, jpeg_thumbnail,gif_attribution=0
        )
