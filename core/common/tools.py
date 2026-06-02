import os
from .constants import YowConstants
import codecs, sys
import logging
import tempfile
import base64
import hashlib
import os.path, mimetypes
import uuid
from consonance.structs.keypair import KeyPair
import re
from conf.constants import SysVar
from typing import Optional, Any, Tuple, List, Union

from .optionalmodules import PILOptionalModule, FFMpegOptionalModule

logger = logging.getLogger(__name__)

class Jid:
    @staticmethod
    def normalize(tos: str) -> str:
        #这里的参数修改为逗号分隔的号码, 用于支持多个收件人

        numbers: List[str] = tos.split(",")
        ret: List[str] = []
        for number in numbers:
            if '@' in number:
                ret.append(number)                
                continue
            
            if len(number)>=14:
                ret.append(f"{number}@{YowConstants.LID_SERVER}")
                continue

            ret.append(f"{number}@{YowConstants.WHATSAPP_SERVER}")

        #返回的也是处理过的逗号分隔账号信息
        return ','.join(ret)
        

class HexTools:
    decode_hex = codecs.getdecoder("hex_codec")
    @staticmethod
    def decodeHex(hexString: str) -> str:
        result = HexTools.decode_hex(hexString)[0]
        result = result.decode('latin-1')
        return result

class WATools:

    @staticmethod
    def fullJid(jid: str) -> str:
       jid = Jid.normalize(jid) 
       s = jid.split("@")[1]
       i,t,d = WATools.jidDecode(jid)
       return "%s.%d:%d@%s" % (i,t,d,s)
    
    @staticmethod
    def jidDecode(jid: str) -> List[Union[str, int]]:
        username = jid.split("@")[0]
        nps = re.split(':|\\.',username)
        recipientId = nps[0]

        if len(recipientId) < 15:
            recipientType = int(nps[1]) if len(nps)>=2 else 0
            deviceId = int(nps[2]) if len(nps)>=3 else 0
        else:
            recipientType = 1
            deviceId = int(nps[1]) if len(nps)>=2 else 0
        
        return [recipientId,recipientType,deviceId] 

    @staticmethod
    def generateIdentity() -> bytes:
        return os.urandom(20)

    @classmethod
    def generatePhoneId(cls, env: Any) -> str:
        """
        :return:
        :rtype: str
        """                
        if env.deviceEnv.getOSName() in ["iOS","SMB iOS"]:
            return str(cls.generateUUID()).upper()
        else:
            return str(cls.generateUUID())
    
    @classmethod
    def generateDeviceId(cls) -> bytes:
        """
        :return:
        :rtype: bytes
        """        
        return cls.generateUUID().bytes

    @classmethod
    def generateUUID(cls) -> uuid.UUID:
        """
        :return:
        :rtype: uuid.UUID
        """
        return uuid.uuid4()

    @classmethod
    def generateKeyPair(cls) -> KeyPair:
        """
        :return:
        :rtype: KeyPair
        """
        return KeyPair.generate()

    @staticmethod
    def getFileHashForUpload(filePath: str) -> str:
        sha1 = hashlib.sha256()
        f = open(filePath, 'rb')
        try:
            sha1.update(f.read())
        finally:
            f.close()
        b64Hash = base64.b64encode(sha1.digest())
        return b64Hash if type(b64Hash) is str else b64Hash.decode()

    @staticmethod
    def getDataHashForUpload(data: bytes) -> str:
        sha1 = hashlib.sha256()
        sha1.update(data)
        b64Hash = base64.b64encode(sha1.digest())
        return b64Hash if type(b64Hash) is str else b64Hash.decode()        

class StorageTools:
    NAME_CONFIG: str = "config.json"

    @staticmethod
    def constructPath(*path: str) -> str:
        path_str = os.path.join(*path)
        fullPath = os.path.join(SysVar.ACCOUNT_PATH, path_str)  #如果path不是绝对路径，那就增加ACCOUNT_PATH前缀
        if not os.path.exists(os.path.dirname(fullPath)):
            os.makedirs(os.path.dirname(fullPath))
        return fullPath

    @staticmethod
    def getStorageForProfile(profile_name: Union[str, int]) -> str:
        if type(profile_name) is not str:
            profile_name = str(profile_name)
        return StorageTools.constructPath(profile_name)

    @staticmethod
    def writeProfileData(profile_name: Union[str, int], name: str, val: Union[str, bytes]) -> None:
        logger.debug(f"writeProfileData(profile_name={profile_name}, name={name}, val=[omitted])")
        path = os.path.join(StorageTools.getStorageForProfile(profile_name), name)
        logger.debug("Writing %s" % path)

        with open(path, 'w' if type(val) is str else 'wb') as attrFile:
            attrFile.write(val)

    @staticmethod
    def readProfileData(profile_name: Union[str, int], name: str, default: Optional[bytes] = None) -> Optional[bytes]:
        logger.debug(f"readProfileData(profile_name={profile_name}, name={name})")
        path = StorageTools.getStorageForProfile(profile_name)
        dataFilePath = os.path.join(path, name)
        if os.path.isfile(dataFilePath):
            logger.debug("Reading %s" % dataFilePath)
            with open(dataFilePath, 'rb') as attrFile:
                return attrFile.read()
        else:
            logger.debug("%s does not exist" % dataFilePath)

        return default

    @classmethod
    def writeProfileConfig(cls, profile_name: Union[str, int], config: Union[str, bytes]) -> None:
        cls.writeProfileData(profile_name, cls.NAME_CONFIG, config)

    @classmethod
    def readProfileConfig(cls, profile_name: Union[str, int], config: Any) -> Optional[bytes]:
        return cls.readProfileData(profile_name, cls.NAME_CONFIG)


class ImageTools:
    @staticmethod
    def scaleImage(infile: str, outfile: str, imageFormat: str, width: int, height: int) -> bool:
        with PILOptionalModule() as imp:
            Image = imp("Image")
            im = Image.open(infile)
            #Convert P mode images
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((width, height))
            im.save(outfile, imageFormat)
            return True
        return False

    @staticmethod
    def getImageDimensions(imageFile: str) -> Tuple[int, int]:
        with PILOptionalModule() as imp:
            Image = imp("Image")
            im = Image.open(imageFile)
            return im.size

    @staticmethod
    def generatePreviewFromImage(image: str) -> Optional[bytes]:
        fd, path = tempfile.mkstemp()
        preview = None
        if ImageTools.scaleImage(image, path, "JPEG", YowConstants.PREVIEW_WIDTH, YowConstants.PREVIEW_HEIGHT):
            fileObj = os.fdopen(fd, "rb+")
            fileObj.seek(0)
            preview = fileObj.read()
            fileObj.close()
        os.remove(path)
        return preview

class MimeTools:
    MIME_FILE: str = os.path.join(os.path.dirname(__file__), 'mime.types')
    mimetypes.init() # Load default mime.types
    try:
        mimetypes.init([MIME_FILE]) # Append whatsapp mime.types
    except:
        logger.warning("Mime types supported can't be read. System mimes will be used. Cause: " + e.message)

    @staticmethod
    def getMIME(filepath: str) -> str:
        mimeType = mimetypes.guess_type(filepath)[0]
        if mimeType is None:
            raise Exception("Unsupported/unrecognized file type for: "+filepath)
        return mimeType


class AudioTools:
    @staticmethod
    def getAudioProperties(audioFile: str) -> int:
        with FFMpegOptionalModule() as imp:
            ffmpeg = imp()
            probe = ffmpeg.probe(audioFile)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            duration = int(float(audio_stream['duration']))
            return duration

class VideoTools:
    @staticmethod
    def getVideoProperties(videoFile: str) -> Tuple[int, int, int, int, str]:
        with FFMpegOptionalModule() as imp:
            ffmpeg = imp()            
            probe = ffmpeg.probe(videoFile)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            bitrate = int(video_stream['bit_rate'])
            duration = int(float(video_stream['duration']))
            codec_name = video_stream['codec_name']            
            return width, height, bitrate, duration, codec_name

    @staticmethod
    def generatePreviewFromVideo(videoFile: str) -> Optional[bytes]:
        with FFMpegOptionalModule() as imp:
            ffmpeg = imp()
            path = "/tmp/"+str(uuid.uuid4())+".jpg"
            ffmpeg.input(videoFile,ss=0).filter("scale",100,-1).output(path,vframes=1).run()                        
            preview = ImageTools.generatePreviewFromImage(path)
            os.remove(path)
            return preview

