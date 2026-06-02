from .....layers.protocol_messages.protocolentities.attributes.attributes_downloadablemedia import \
    DownloadableMediaMessageAttributes
import os
from typing import Optional, Any, List, Dict, Union
import requests
from conf.constants import SysVar

class DocumentAttributes:
    def __init__(self, downloadablemedia_attributes, file_name, file_length, title=None, page_count=None, jpeg_thumbnail=None,caption=None) -> None:
        self._downloadablemedia_attributes = downloadablemedia_attributes
        self._file_name = file_name
        self._file_length = file_length
        self._title = title
        self._page_count = page_count
        self._jpeg_thumbnail = jpeg_thumbnail
        self._caption = caption

    def __str__(self):
        attrs = []
        if self.file_name is not None:
            attrs.append(("file_name", self.file_name))
        if self.file_length is not None:
            attrs.append(("file_length", self.file_length))
        if self.title is not None:
            attrs.append(("title", self.title))
        if self.page_count is not None:
            attrs.append(("page_count", self.page_count))
        if self.jpeg_thumbnail is not None:
            attrs.append(("jpeg_thumbnail", self.jpeg_thumbnail))
        if self.caption is not None:
            attrs.append(("caption", self.caption))

        attrs.append(("downloadable", self.downloadablemedia_attributes))

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def downloadablemedia_attributes(self) -> Any:
        return self._downloadablemedia_attributes

    @downloadablemedia_attributes.setter
    def downloadablemedia_attributes(self, value: Any) -> None:
        self._downloadablemedia_attributes = value

    @property
    def caption(self) -> Any:
        return self._caption

    @caption.setter
    def caption(self, value: Any) -> None:
        self._caption = value        

    @property
    def file_name(self) -> Any:
        return self._file_name

    @file_name.setter
    def file_name(self, value: Any) -> None:
        self._file_name = value

    @property
    def file_length(self) -> Any:
        return self._file_length

    @file_length.setter
    def file_length(self, value: Any) -> None:
        self._file_length = value

    @property
    def title(self) -> Any:
        return self._title

    @title.setter
    def title(self, value: Any) -> None:
        self._title = value

    @property
    def page_count(self) -> Any:
        return self._page_count

    @page_count.setter
    def page_count(self, value: Any) -> None:
        self._page_count = value

    @property
    def jpeg_thumbnail(self) -> Any:
        return self._jpeg_thumbnail

    @jpeg_thumbnail.setter
    def jpeg_thumbnail(self, value: Any) -> None:
        self._jpeg_thumbnail = value

    @staticmethod
    def from_filepath(filepath,fileName,mediaType,resultRequestMediaConnIqProtocolEntity):
        return DocumentAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity),
            os.path.basename(filepath) if fileName is None else fileName,
            os.path.getsize(filepath)
        )


    @staticmethod
    def from_url(url,fileName,mediaType,resultRequestMediaConnIqProtocolEntity):

        #澶氫竴涓笅杞芥祦绋?
        down_res = requests.get(url=url)
        filename = url[url.rfind("/",0):]
        filepath = SysVar.DOWNLOAD_PATH+filename
        with open(filepath,"wb") as file:
            file.write(down_res.content)             
            
        assert os.path.exists(filepath)

        return DocumentAttributes(
            DownloadableMediaMessageAttributes.from_file(filepath,mediaType,resultRequestMediaConnIqProtocolEntity),
            os.path.basename(filepath) if fileName is None else fileName,
            os.path.getsize(filepath)
        )