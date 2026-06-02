from typing import Any, Optional, Dict, List, Tuple, Union, Callable
from ..useragent import UserAgentConfig


class SamsungS9PUserAgentConfig(UserAgentConfig):
    DEFAULT_LOCALE_LANG = 'zh'
    DEFAULT_LOCALE_COUNTRY = 'CN'
    DEFAULT_MCC = '460'
    DEFAULT_MNC = '000'
    OS_VERSION = "7.1.2"
    OS_BUILD_NUMBER = "N2G47H"
    MANUFACTURER = "HUAWEI"
    DEVICE = "aosp"
    DEVICE_BOARD = "WNXS-301"

    def __init__(self,
                 app_version,
                 phone_id,
                 mcc=None, mnc=None,
                 locale_lang=None,
                 locale_country=None) -> Any:
        super().__init__(
            platform=UserAgentConfig.PLATFORM_ANDROID,
            app_version=app_version,
            mcc=mcc or self.DEFAULT_MCC, mnc=mnc or self.DEFAULT_MNC,
            os_version=self.OS_VERSION,
            manufacturer=self.MANUFACTURER,
            device=self.DEVICE,
            os_build_number=self.OS_BUILD_NUMBER,
            phone_id=phone_id,
            locale_lang=locale_lang or self.DEFAULT_LOCALE_LANG,
            locale_country=locale_country or self.DEFAULT_LOCALE_COUNTRY
        )
