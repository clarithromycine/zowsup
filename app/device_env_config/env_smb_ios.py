import random
from .env_tools import EnvTools

class EnvSmbIos:


    DEVICE_NAME = ["iPhone_14_Pro_Max","iPhone_15_Pro_Max","iPhone_XS_Max","iPhone_13","iPhone_14","iPhone_15","iPhone_16","iPhone_16_Pro_Max","iPhone_17","iPhone_17_Pro_Max","iPhone_17_Pro"]
    OS_VERSION =  ["16.7.1","16.7.2","16.7.3","16.7.6","16.7.7","16.7.8","16.7.9","16.7.10","18.0.1","18.1.1","26.0","26.0.1","26.1","26.2"]  

    DEVICE_NAME_FOR_RUN = {
        "iPhone_14_Pro_Max":"iPhone 14 Pro Max",
        "iPhone_15_Pro_Max":"iPhone 15 Pro Max",
        "iPhone_XS_Max":"iPhone XS Max",
        "iPhone_13":"iPhone 13",
        "iPhone_14":"iPhone 14",
        "iPhone_15":"iPhone 15",
        "iPhone_16":"iPhone 16",
        "iPhone_16_Pro_Max":"iPhone 16 Pro Max",
        "iPhone_17":"iPhone 17",
        "iPhone_17_Pro_Max":"iPhone 17 Pro Max",
        "iPhone_17_Pro":"iPhone 17 Pro"

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
        "18.1.1":"22B91",
        "26.0"  :"23A341",
        "26.0.1":"23A355",
        "26.1"  :"23B85",
        "26.2"  :"23C55",

    }


    DEVICE_MODEL_TYPE_FOR_RUN = {
        "iPhone_14_Pro_Max":"iPhone15,3",
        "iPhone_15_Pro_Max":"iPhone16,2",
        "iPhone_XS_Max":"iPhone11,6",
        "iPhone_13":"iPhone13,2",
        "iPhone_14":"iPhone14,2",
        "iPhone_15":"iPhone15,2",
        "iPhone_16":"iPhone17,1",
        "iPhone_16_Pro_Max":"iPhone17,2",
        "iPhone_17":"iPhone18,3",
        "iPhone_17_Pro_Max":"iPhone18,2",
        "iPhone_17_Pro":"iPhone18,1"
    }   

    def __init__(self,                 
                 version = "2.26.13.74",                 
                 osVersion = "18.1.1",
                 manufacturer = "Apple",
                 deviceName = "iPhone_15_Pro_Max",                                                   
                 isAxolotlEnable = True
        ):        
        self.platform = 12
        self.osName = "SMB iOS"
        self.version = version        
        self.osVersion = osVersion
        self.deviceName = deviceName
        self.manufacturer = manufacturer        
        self.isAxolotlEnable = isAxolotlEnable

        self.buildVersion = None
        self.deviceModelType = None

        

    @staticmethod
    def randomEnv():
              
        osVersion = random.choice(EnvSmbIos.OS_VERSION)
        deviceName = random.choice(EnvSmbIos.DEVICE_NAME)       

        return EnvSmbIos(            
            osVersion=osVersion,            
            deviceName=deviceName,            
        )

    def getToken(self,phoneNumber):
        _TOKEN = "USUDuDYDeQhY4RF2fCSp5m3F6kJ1M2J8wS7bbNA2{version}{phone}"
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
    
    def getOSName(self):
        return self.osName
    
    def getOSVersion(self):
        return self.osVersion    
    
    def getDeviceName(self):
        return self.deviceName

    def getDeviceName2(self):        
        if self.deviceName in EnvSmbIos.DEVICE_NAME_FOR_RUN:
            return EnvSmbIos.DEVICE_NAME_FOR_RUN[self.deviceName]
        else:
            return "iPhone 15"
    
    def getBuildVersion(self):
        if self.osVersion in EnvSmbIos.BUILD_VERSION_FOR_RUN:
            return EnvSmbIos.BUILD_VERSION_FOR_RUN[self.osVersion]
        else:
            return "22B91"
    
    def getDeviceModelType(self):
        if self.deviceName in  EnvSmbIos.DEVICE_MODEL_TYPE_FOR_RUN:
            return EnvSmbIos.DEVICE_MODEL_TYPE_FOR_RUN[self.deviceName]
        else:
            return "iPhone15,2"