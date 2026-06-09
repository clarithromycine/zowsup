from .device_env_config import *
from conf.constants import SysVar


class DeviceEnv:
    """Device environment proxy — delegates property access to the underlying env object.

    Usage:
        env = DeviceEnv("android")                # random device profile
        env = DeviceEnv("android", envObj={...})  # specific device profile

    All getter/setter calls (e.g. ``getOSName()``, ``setVersion()``) are
    automatically forwarded to ``self.obj`` via ``__getattr__``.
    """

    ENV_MAP = {
        "android": EnvAndroid,
        "ios": EnvIos,
        "smb_android": EnvSmbAndroid,
        "smb_ios": EnvSmbIos,
    }

    def __init__(self, name, random=False, envObj=None):
        if random or envObj is None:
            self.obj = DeviceEnv.ENV_MAP[name].randomEnv()
        else:
            self.obj = DeviceEnv.ENV_MAP[name](
                osVersion=envObj["osVersion"],
                deviceName=envObj["deviceName"],
                buildVersion=envObj["buildVersion"],
                manufacturer=envObj["manufacturer"],
                deviceModelType=envObj["deviceModelType"],
            )

    def __getattr__(self, name):
        """Auto-delegate any undefined attribute access to ``self.obj``.

        This eliminates 25+ manual pass-through methods like::

            def getOSName(self):       return self.obj.getOSName()
            def setVersion(self, v):   self.obj.setVersion(v)
            ...
        """
        return getattr(self.obj, name)

    def __repr__(self):
        return f"DeviceEnv(obj={self.obj!r})"
