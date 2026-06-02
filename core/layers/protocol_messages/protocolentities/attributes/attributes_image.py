from .....common.tools import ImageTools
from .....layers.protocol_messages.protocolentities.attributes.attributes_downloadablemedia \
    import DownloadableMediaMessageAttributes
from typing import Optional, Any, List, Dict, Union
import os
import requests
from conf.constants import SysVar


class ImageAttributes:
    def __init__(self, downloadablemedia_attributes, width, height, caption=None, jpeg_thumbnail=None) -> None:
        self._downloadablemedia_attributes = downloadablemedia_attributes  # type: DownloadableMediaMessageAttributes
        self._width = width
        self._height = height
        self._caption = caption
        self._jpeg_thumbnail = jpeg_thumbnail        

    def __str__(self):
        attrs = []
        if self.width is not None:
            attrs.append(("width", self.width))
        if self.height is not None:
            attrs.append(("height", self.height))
        if self.caption is not None:
            attrs.append(("caption", self.caption))
        if self.jpeg_thumbnail is not None:
            attrs.append(("jpeg_thumbnail", "[binary data]"))
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
    def caption(self) -> Any:
        return self._caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self._caption = value if value else ''

    @property
    def jpeg_thumbnail(self) -> Any:
        return self._jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self._jpeg_thumbnail = value if value else b''

    @staticmethod
    def from_filepath(filepath,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        dimensions=None, caption=None, jpeg_thumbnail=None):
        assert os.path.exists(filepath)
        if not jpeg_thumbnail:
            jpeg_thumbnail = ImageTools.generatePreviewFromImage(filepath)
        dimensions = dimensions or ImageTools.getImageDimensions(filepath)
        width, height = dimensions if dimensions else (None, None)
        assert width and height, "Could not determine image dimensions, install pillow or pass dimensions"

        return ImageAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), width, height, caption, jpeg_thumbnail
        )

    @staticmethod
    def from_url(url,mediaType=None,resultRequestMediaConnIqProtocolEntity=None, 
        dimensions=None, caption=None, jpeg_thumbnail=None):

        #澶氫竴涓笅杞芥祦绋?
        down_res = requests.get(url=url)
        filepath = SysVar.DOWNLOAD_PATH+"image.jpg"
        with open(filepath,"wb") as file:
            file.write(down_res.content)             

        assert os.path.exists(filepath)
        if not jpeg_thumbnail:
            jpeg_thumbnail = ImageTools.generatePreviewFromImage(filepath)
        dimensions = dimensions or ImageTools.getImageDimensions(filepath)
        width, height = dimensions if dimensions else (None, None)
        assert width and height, "Could not determine image dimensions, install pillow or pass dimensions"

        return ImageAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity), width, height, caption, jpeg_thumbnail
        )        
