from .device_env_config import * 
from conf.constants import SysVar

class DeviceEnv:

    ENV_MAP = {
        "android":EnvAndroid,
        "ios":EnvIos,
        "smb_android":EnvSmbAndroid,
        "smb_ios":EnvSmbIos,
    }

    def __init__(self,name,random=False,envObj=None):

        if random or envObj is None:
            self.obj = DeviceEnv.ENV_MAP[name].randomEnv()
            
        else:
            self.obj = DeviceEnv.ENV_MAP[name](                
                osVersion=envObj["osVersion"],
                deviceName=envObj["deviceName"],
                buildVersion=envObj["buildVersion"],
                manufacturer=envObj["manufacturer"],
                deviceModelType=envObj["deviceModelType"]
            )     

    def setVersion(self,version:str):
        self.obj.setVersion(version)

    def setMd5Classes(self,md5Classes:str):
        self.obj.setMd5Classes(md5Classes)

    def setKey(self,key):
        self.obj.setKey(key)

    def setDeviceModelType(self,value:str):
        self.obj.setDeviceModelType(value)

    def setPlatform(self,value):
        self.obj.setPlatform(value)

    def setManufacturer(self,value:str):
        self.obj.setManufacturer(value)

    def setDeviceName(self,value:str):
        self.obj.setDeviceName(value)

    def setOSVersion(self,value:str):
        self.obj.setOSVersion(value)

    def setBuildVersion(self,value:str):
        self.obj.setBuildVersion(value)

    def setOSName(self,value:str):
        self.obj.setOSName(value)

    def getPlatform(self):
        return self.obj.getPlatform()
    
    def getVersion(self):
        return self.obj.getVersion()
    
    def getManufacturer(self):
        return self.obj.getManufacturer()
    
    def getDeviceName(self):
        return self.obj.getDeviceName()
    
    def getDeviceName2(self):
        return self.obj.getDeviceName2()    
    
    def getOSVersion(self):
        return self.obj.getOSVersion()
    
    def getBuildVersion(self):
        return self.obj.getBuildVersion()
    
    def getOSName(self):
        return self.obj.getOSName()
    
    def getToken(self,number):
        return self.obj.getToken(number)
    
    def getUserAgent(self):
        return self.obj.getUserAgent()
    
    def getDeviceModelType(self):
        return self.obj.getDeviceModelType()
    


            


    
