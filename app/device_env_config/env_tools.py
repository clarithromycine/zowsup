import base64
import hashlib

class EnvTools:

    
    _USERAGENT_STRING_ANDROID = "WhatsApp/{WHATSAPP_VERSION} {OS_NAME}/{OS_VERSION} Device/{MANUFACTURER}-{DEVICE_MODEL_TYPE}"
    _USERAGENT_STRING_IOS = "WhatsApp/{WHATSAPP_VERSION} {OS_NAME}/{OS_VERSION} Device/{DEVICE_NAME}"        

    _SIGNATURE_ANDROID = "MIIDMjCCAvCgAwIBAgIETCU2pDALBgcqhkjOOAQDBQAwfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCkNhbGlmb3JuaWExFDASBgNV" \
        "BAcTC1NhbnRhIENsYXJhMRYwFAYDVQQKEw1XaGF0c0FwcCBJbmMuMRQwEgYDVQQLEwtFbmdpbmVlcmluZzEUMBIGA1UEAxMLQnJ" \
        "pYW4gQWN0b24wHhcNMTAwNjI1MjMwNzE2WhcNNDQwMjE1MjMwNzE2WjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKQ2FsaWZvcm5" \
        "pYTEUMBIGA1UEBxMLU2FudGEgQ2xhcmExFjAUBgNVBAoTDVdoYXRzQXBwIEluYy4xFDASBgNVBAsTC0VuZ2luZWVyaW5nMRQwEg" \
        "YDVQQDEwtCcmlhbiBBY3RvbjCCAbgwggEsBgcqhkjOOAQBMIIBHwKBgQD9f1OBHXUSKVLfSpwu7OTn9hG3UjzvRADDHj+AtlEm" \
        "aUVdQCJR+1k9jVj6v8X1ujD2y5tVbNeBO4AdNG/yZmC3a5lQpaSfn+gEexAiwk+7qdf+t8Yb+DtX58aophUPBPuD9tPFHsMCN" \
        "VQTWhaRMvZ1864rYdcq7/IiAxmd0UgBxwIVAJdgUI8VIwvMspK5gqLrhAvwWBz1AoGBAPfhoIXWmz3ey7yrXDa4V7l5lK+7+jr" \
        "qgvlXTAs9B4JnUVlXjrrUWU/mcQcQgYC0SRZxI+hMKBYTt88JMozIpuE8FnqLVHyNKOCjrh4rs6Z1kW6jfwv6ITVi8ftiegEkO" \
        "8yk8b6oUZCJqIPf4VrlnwaSi2ZegHtVJWQBTDv+z0kqA4GFAAKBgQDRGYtLgWh7zyRtQainJfCpiaUbzjJuhMgo4fVWZIvXHaS" \
        "HBU1t5w//S0lDK2hiqkj8KpMWGywVov9eZxZy37V26dEqr/c2m5qZ0E+ynSu7sqUD7kGx/zeIcGT0H+KAVgkGNQCo5Uc0koLRW" \
        "YHNtYoIvt5R3X6YZylbPftF/8ayWTALBgcqhkjOOAQDBQADLwAwLAIUAKYCp0d6z4QQdyN74JDfQ2WCyi8CFDUM4CaNB+ceVXd" \
        "KtOrNTQcc0e+t"

    @staticmethod
    def getAndroidToken(self,phoneNumber,KEY,MD5_CLASSES):
        sigDecoded = base64.b64decode(EnvTools._SIGNATURE_ANDROID)
        keyDecoded = bytearray(base64.b64decode(KEY))        
        clsDecoded = base64.b64decode(MD5_CLASSES)
        data = sigDecoded + clsDecoded + phoneNumber.encode()

        opad = bytearray()
        ipad = bytearray()
        for i in range(0, 64):
            opad.append(0x5C ^ keyDecoded[i])
            ipad.append(0x36 ^ keyDecoded[i])
        hash = hashlib.sha1()
        subHash = hashlib.sha1()
        try:
            subHash.update(ipad + data)
            hash.update(opad + subHash.digest())
        except TypeError:
            subHash.update(bytes(ipad + data))
            hash.update(bytes(opad + subHash.digest()))
        result = base64.b64encode(hash.digest())
        return result  


    @staticmethod
    def getIosToken(obj,phoneNumber,TOKEN):        
        version = hashlib.md5(obj.version.encode("utf-8")).hexdigest()
        result = hashlib.md5(TOKEN.format(version=version,phone = phoneNumber).encode('utf-8')).hexdigest()
        return result         
    
    @staticmethod
    def getAndroidUserAgent(obj):
        return EnvTools._USERAGENT_STRING_ANDROID.format(
            WHATSAPP_VERSION=obj.getVersion(),
            OS_NAME=obj.getOSName(),
            OS_VERSION=obj.getOSVersion(),
            MANUFACTURER=obj.getManufacturer(),
            DEVICE_MODEL_TYPE=obj.getDeviceModelType().replace(" ","_")            
        )    
    
    @staticmethod
    def getIosUserAgent(obj):
        return EnvTools._USERAGENT_STRING_IOS.format(
            WHATSAPP_VERSION=obj.getVersion(),                
            OS_NAME=obj.getOSName(),
            OS_VERSION=obj.getOSVersion(),                
            DEVICE_NAME=obj.getDeviceName()
        )               
