from .....layers.protocol_messages.protocolentities.attributes.attributes_media import MediaAttributes
from typing import Optional, Any, List, Dict, Union
from .....common.tools import MimeTools
import base64
import hashlib
import os
import random
import time
from .....layers.protocol_messages.mediacipher import MediaCipher
from .....common.tools import WATools
import requests
import base64


class DownloadableMediaMessageAttributes(MediaAttributes):

    MEDIA_PATH = {
        "image": '/mms/image',
        "video": '/mms/video',
        "document": '/mms/document',
        "audio": '/mms/audio',
        "sticker": '/mms/image',
        'thumbnail-link': '/mms/image',
        'product-catalog-image': '/product/image',
        'md-app-state': '/mms/md-app-state',
        'history-sync':'/mms/md-msg-hist'
    }
    def __init__(self, mimetype, file_length, file_sha256, media_key=None,  media_key_timestamp=None,file_enc_sha256=None, url = None,direct_path = None,context_info=None) -> None:
        super().__init__(context_info)
        self._mimetype = mimetype
        self._file_length = file_length
        self._file_sha256 = file_sha256        
        self._media_key = media_key
        self._media_key_timestamp = media_key_timestamp
        self._file_enc_sha256 = file_enc_sha256
        self._url = url
        self._direct_path = direct_path

    def __str__(self):
        return "[mimetype=%s, file_length=%d, file_sha256=%s, media_key=%s, media_key_timestamp=%s, file_enc_sha256=%s,url=%s, direct_path=%s]" % (
            self.mimetype, self.file_length, base64.b64encode(self.file_sha256) if self.file_sha256 else None,
            base64.b64encode(self.media_key) if self.media_key else None,
            str(self.media_key_timestamp),
            base64.b64encode(self.file_enc_sha256) if self.file_enc_sha256 else None,
            self.url,
            self.direct_path
        )

    @property
    def url(self) -> Any:
        return self._url

    @url.setter
    def url(self, value: Any) -> None:
        self._url = value

    @property
    def mimetype(self) -> Any:
        return self._mimetype

    @mimetype.setter
    def mimetype(self, value: Any) -> None:
        self._mimetype = value

    @property
    def file_length(self) -> Any:
        return self._file_length

    @file_length.setter
    def file_length(self, value: Any) -> None:
        self._file_length = value

    @property
    def file_sha256(self) -> Any:
        return self._file_sha256

    @file_sha256.setter
    def file_sha256(self, value: Any) -> None:
        self._file_sha256 = value

    @property
    def media_key(self) -> Any:
        return self._media_key

    @media_key.setter
    def media_key(self, value: Any) -> None:
        self._media_key = value

    @property
    def media_key_timestamp(self) -> Any:
        return self._media_key_timestamp

    @media_key_timestamp.setter
    def media_key_timestamp(self, value: Any) -> None:
        self._media_key_timestamp = value            

    @property
    def file_enc_sha256(self) -> Any:
        return self._file_enc_sha256

    @file_enc_sha256.setter
    def file_enc_sha256(self, value: Any) -> None:
        self._file_enc_sha256 = value      

    @property
    def direct_path(self) -> Any:
        return self._direct_path

    @direct_path.setter
    def direct_path(self, value: Any) -> None:
        self._direct_path = value


    @staticmethod
    def from_buffer(
        data,
        mediaType,
        resultRequestMediaConnIqProtocolEntity,
        context_info=None
    ):
        
        file_sha256 = hashlib.sha256(data).digest()

        #以下是和加密上传相关的字段
        if resultRequestMediaConnIqProtocolEntity is not None:

            alp = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'                
            media_key = ''.join(random.sample(alp, 32)).encode("GBK")            
            media_key_timestamp = int(time.time())

            if mediaType=="image":
                enc_data = MediaCipher().encrypt_image(data,media_key)

            if mediaType=="video":
                enc_data = MediaCipher().encrypt_video(data,media_key)

            if mediaType=="audio":
                enc_data = MediaCipher().encrypt_audio(data,media_key)

            if mediaType=="document":
                enc_data = MediaCipher().encrypt_document(data,media_key)

            if mediaType=="history-sync":
                enc_data = MediaCipher().encrypt_history_sync(data,media_key)

            file_enc_sha256 = hashlib.sha256(enc_data).digest()     

            b64Hash = WATools.getDataHashForUpload(enc_data)
            b64Hash = b64Hash.replace('+','-').replace('/','_').replace('=','')
            uploadHost = (resultRequestMediaConnIqProtocolEntity.getHosts()[0])
            url = "https://"+uploadHost+DownloadableMediaMessageAttributes.MEDIA_PATH[mediaType]+"/"+b64Hash+"?auth="+resultRequestMediaConnIqProtocolEntity.getAuth()+"&token="+b64Hash   
            upload_result = requests.request(
                method = "POST",
                url = url,            
                data=enc_data,
                headers={
                    "Content-Type":"application/octet-stream"
                }
            ).json()

            
            url = upload_result["url"]
            direct_path = upload_result["direct_path"]

        return DownloadableMediaMessageAttributes(
            None, len(data), file_sha256,media_key,media_key_timestamp,file_enc_sha256,url,direct_path,context_info
        )        
    
    @staticmethod
    def from_file(            
            filepath,
            mediaType,
            resultRequestMediaConnIqProtocolEntity,
            context_info=None            
    ):
        
        #文件本身的属性

        mimetype = MimeTools.getMIME(filepath) 
        file_length = os.path.getsize(filepath)

        with open(filepath, 'rb') as f:
            data = f.read()


        res =  DownloadableMediaMessageAttributes.from_buffer(data,mediaType,resultRequestMediaConnIqProtocolEntity,context_info)

        res.mimetype = mimetype
        res.file_length = file_length

        return res


