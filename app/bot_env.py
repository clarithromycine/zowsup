from .device_env_config import *
from .device_env import DeviceEnv
from .network_env import NetworkEnv

class BotEnv:
            
    def __init__(self,deviceEnv:DeviceEnv|None = None, networkEnv:NetworkEnv|None = None):

        if deviceEnv is None:
            deviceEnv = DeviceEnv("android")
        
        if networkEnv is None:
            networkEnv = NetworkEnv("direct")

        self.deviceEnv = deviceEnv
        self.networkEnv = networkEnv

    def setDeviceEnv(self,deviceEnv:DeviceEnv):
        self.deviceEnv = deviceEnv

    def setNetworkEnv(self,networkEnv:NetworkEnv):
        self.networkEnv = networkEnv

    




