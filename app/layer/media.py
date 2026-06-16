"""MediaManager — media download, decryption, and attribute parsing."""

import logging
import mimetypes

import httpx
from core.layers.protocol_media.mediacipher import MediaCipher
from conf.constants import SysVar

logger = logging.getLogger(__name__)


class MediaManager:
    """Handles media file download and decryption."""

    def __init__(self, layer):
        """
        Args:
            layer: ZowBotLayer instance (for logger, props, etc.)
        """
        self.layer = layer

    async def download(self, params):
        """Download and decrypt a media file from WhatsApp servers."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.get(url=params["url"])
            enc_data = resp.content

        if enc_data is None:
            logger.error("Download failed")
            return None

        filename = params["filename"]
        ext = None

        match params["type"]:
            case "IMAGE":
                media_info = MediaCipher.INFO_IMAGE
            case "VIDEO":
                media_info = MediaCipher.INFO_VIDEO
            case "AUDIO":
                media_info = MediaCipher.INFO_AUDIO
            case "DOCUMENT":
                media_info = MediaCipher.INFO_DOCUMENT
            case "STICKER":
                media_info = MediaCipher.INFO_IMAGE
            case _:
                logger.error("Unsupported type")
                return None

        filedata = MediaCipher().decrypt(enc_data, params["media_key"], media_info)

        if filedata is None:
            logger.error("Decrypt failed")
            return None

        if params["mimetype"] == "application/was":
            ext = ".was"

        if ext is None:
            ext = mimetypes.guess_extension(params["mimetype"].split(";")[0])

        try:
            filename = SysVar.DOWNLOAD_PATH + filename + ext
            with open(filename, "wb") as f:
                f.write(filedata)

        except Exception as e:
            logger.error(e)
            return None

        return filename

    def parse_media_common_attributes(self, msg, media_specific_attributes):
        """Copy common media attributes from protocol entity to message dict."""
        if media_specific_attributes is not None:
            msg.url = media_specific_attributes.url
            msg.direct_path = media_specific_attributes.direct_path
            msg.file_enc_sha256 = media_specific_attributes.file_enc_sha256
            msg.media_key_timestamp = media_specific_attributes.media_key_timestamp
            msg.file_sha256 = media_specific_attributes.file_sha256
            msg.file_length = media_specific_attributes.file_length
            msg.mimetype = media_specific_attributes.mimetype
            msg.media_key = media_specific_attributes.media_key
