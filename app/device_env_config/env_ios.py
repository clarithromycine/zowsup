
import random
from .env_tools import EnvTools

class EnvIos(object):

    DEVICE_NAME = ["iPhone_14_Pro_Max","iPhone_15_Pro_Max","iPhone_XS_Max","iPhone_13","iPhone_14","iPhone_15"]
    OS_VERSION =  ["16.7.1","16.7.2","16.7.3","16.7.6","16.7.7","16.7.8","16.7.9","16.7.10","18.0.1","18.1.1"]  



    DEVICE_NAME_FOR_RUN = {
        "iPhone_14_Pro_Max":"iPhone 14 Pro Max",
        "iPhone_15_Pro_Max":"iPhone 15 Pro Max",
        "iPhone_XS_Max":"iPhone XS Max",
        "iPhone_13":"iPhone 13",
        "iPhone_14":"iPhone 14",
        "iPhone_15":"iPhone 15"      
    }


    BUILD_VERSION_FOR_RUN = {
        "16.7.1":"20H30",
        "16.7.2":"20H115",
        "16.7.3":"20H232",
        "16.7.6":"20H320",
        "16.7.7":"20H330",
        "16.7.8":"20H343",
        "16.7.9":"20H348",
        "16.7.10":"20H350",
        "18.0.1":"22A3370",
        "18.1.1":"22B91"
    }


    DEVICE_MODEL_TYPE_FOR_RUN = {
        "iPhone_14_Pro_Max":"iPhone15,3",
        "iPhone_15_Pro_Max":"iPhone16,2",
        "iPhone_XS_Max":"iPhone11,6",
        "iPhone_13":"iPhone13,2",
        "iPhone_14":"iPhone14,2",
        "iPhone_15":"iPhone15,2"
    }  
  

    def __init__(self,                 
                 version = "2.25.5.74",          
                 osVersion = "17.2.1",
                 deviceName = "iPhone_15_Pro_Max",
                 manufacturer = "Apple",                 
                 isAxolotlEnable = True
        ):        
        self.platform = 1
        self.osName = "iOS"
        self.version = version        
        self.osVersion = osVersion
        self.deviceName = deviceName        
        self.manufacturer = manufacturer
        self.isAxolotlEnable = isAxolotlEnable

        self.buildVersion = None
        self.deviceModelType = None
        

    @staticmethod
    def randomEnv():
   
        
        osVersion = random.choice(EnvIos.OS_VERSION)
        deviceName = random.choice(EnvIos.DEVICE_NAME)       

        return EnvIos(            
            osVersion=osVersion,        
            deviceName=deviceName
        )

    def getToken(self,phoneNumber):
        _TOKEN = "0a1mLfGUIBVrMKF1RdvLI5lkRBvof6vn0fD2QRSM{version}{phone}"
        return EnvTools.getIosToken(self,phoneNumber,_TOKEN)

    def getUserAgent(self):
        return EnvTools.getIosUserAgent(self)        
    

    def setPlatform(self,value):
        self.platform=value

    def setVersion(self,value):
        self.version=value

    def setManufacturer(self,value):
        self.manufacturer=value

    def setDeviceName(self,value):
        self.deviceName=value

    def setOSVersion(self,value):
        self.osVersion=value

    def setBuildVersion(self,value):
        self.buildVersion=value

    def setOSName(self,value):
        self.osName=value

    def setDeviceModelType(self,value):
        self.deviceModelType=value

    def getPlatform(self):
        return self.platform
    
    def getVersion(self):
        return self.version
    
    def getManufacturer(self):
        return self.manufacturer
    
    def getDeviceName(self):
        return self.deviceName
    
    def getOSVersion(self):
        return self.osVersion
    

    def getOSName(self):
        return self.osName
        
    def getDeviceName2(self):        
        if self.deviceName in EnvIos.DEVICE_NAME_FOR_RUN:
            return EnvIos.DEVICE_NAME_FOR_RUN[self.deviceName]
        else:
            return "iPhone 15"
    
    def getBuildVersion(self):
        if self.osVersion in EnvIos.BUILD_VERSION_FOR_RUN:
            return EnvIos.BUILD_VERSION_FOR_RUN[self.osVersion]
        else:
            return "22B91"
    
    def getDeviceModelType(self):
        if self.deviceName in  EnvIos.DEVICE_MODEL_TYPE_FOR_RUN:
            return EnvIos.DEVICE_MODEL_TYPE_FOR_RUN[self.deviceName]
        else:
            return "iPhone15,2"    