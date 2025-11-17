


import random
from .env_tools import EnvTools

class EnvSmbAndroid(object):
    def __init__(self,                
                 osVersion = "11.0.0",
                 deviceName = "Mi11 Pro 5G",
                 buildVersion = "R16AAWS001/release-keys",
                 manufacturer = "xiaomi",
                 deviceModelType = "SMBA 11.0.0",
                 isAxolotlEnable = True
        ):        
        self.platform = 10
        self.osName = "SMBA"     
        self.osVersion = osVersion
        self.deviceName = deviceName
        self.buildVersion = buildVersion
        self.manufacturer = manufacturer
        self.deviceModelType = deviceModelType
        self.isAxolotlEnable = isAxolotlEnable
        
        self.version = "2.25.32.75"
        self.md5Classes = "tscTjVmBD1zyO/7tYTYlKQ=="
        #self.key = "VROA1coOL6M5ywTDPnPB/6CwjpIl2UjqEbIDpuf4TtgbPMj9sEhhi3gqtaG1PM/Jy4VODs6UQE7SMLcqzf/XVQ=="   
        self.key = "wt9VMkXhC2ODULqh718Itr60VOm9tYtDWKmVD+48S96rbE9zYW0K0L+6Y82FKtRku9juFnml6nDUAMxHHf0c2A=="

    def __str__(self):
        return "%d-%s-%s" % (self.platform,self.osName,self.version)

    @staticmethod
    def randomEnv():
        MANUFACTURER = ["Huawei","Xiaomi","Samsung","Vivo","Google"]
        DEVICE_MODEL_TYPE = {
            "Huawei":[
                ["COL-AL00","HWCOL"],
                ["HRY-AL00","HWHRY-H"],
                ["HRY-AL00a","HWHRY-HF"],
                ["SCC-U21","hnSCC-Q"],
                ["SCL-AL00","hnSCL-Q"],
                ["HUAWEI LYO-L21","HWLYO-L6735"],
                ["NEM-L21","HNNEM-H"],
                ["KIW-L21","HNKIW-Q"],
                ["DLI-L22","HWDLI-Q"],
                ["BLN-L24","HWBLN-H"],
                ["PLK-AL10","HWPLK"],
                ["AUM-AL00","HWAUM-Q"],
                ["DUA-L22","HWDUA-M"],
                ["AUM-L41","HWAUM-Q"],
                ["LND-AL30","HWLND-Q"],
                ["DRA-LX5","HWDRA-MG"],
                ["DUA-AL00","HWDUA-M"],
                ["BND-L21","HWBND-H"],
                ["ATH-AL00","HWATH"],
                ["FRD-AL00","HWFRD"],
                ["PRA-LX1","HWPRA-H"],
                ["DUK-L09","HWDUK"],
                ["VEN-L22","HWVNS-H"],
                ["JAT-AL00","HWJAT-M"]            

            ],            
            "Xiaomi":[
                ["MI 5s","capricorn"],
                ["Mi 9 Lite","pyxis"],
                ["MI 9 SE","grus"],
                ["Mi 9T","davinci"],
                ["Mi 9T Pro","raphael"],               
                ["24053PY09C","chenfeng"],
                ["2405CPX3DC","ruyi"],
                ["M2011J18C","cetus"],
                ["22061218C","zizhan"],
                ["2308CPXD0C","babylon"],
                ["24072PX77C","goku"],
                ["21051182C","nabu"],
                ["22081281AC","dagu"],
                ["M2105K81AC","elish"],                                 
                ["Redmi Note 5","whyred"],
                ["Redmi Note 5A","ugg"],
                ["Redmi Note 5A","ugglite"],
                ["Redmi Note 8","ginkgo"],       
                ["MI CC9 Pro","tucana"],
                ["MI MAX","helium"],
                ["MI MAX","hydrogen"],
                ["MI MAX 2","oxygen"],
                ["MI MAX 3","nitrogen"],
                ["Mi MIX 2S","polaris"],
                ["MI NOTE LTE","virgo"],
                ["MI NOTE Pro","leo"]                   
            ],
            "Samsung":[
                ["GT-S6312","roy"],
                ["GT-S6313T","roydtv"],
                ["GT-S6310","royss"],
                ["GT-S6313T","royssdtv"],
                ["GT-S6310N","royssnfc"],
                ["SM-G130H","young23g"],
                ["SM-G130BT","young23gdtv"],
                ["SM-G130E","young2ds2g"],
                ["SM-G130HN","young2nfc3g"],
                ["SM-G130BU","young2ve3g"],
                ["SHV-E140K","SHV-E140K"],
                ["SHV-E140L","SHV-E140L"],
                ["SHV-E140S","SHV-E140S"],
                ["SHW-M305W","SHW-M305W"],
                ["SM-T555","gt510lte"],
                ["SM-T550","gt510wifi"],
                ["SM-T355C","gt58ltechn"],
                ["SM-P555M","gt5note10lte"],
                ["SM-P550","gt5note10wifi"],
                ["SM-P355M","gt5note8lte"],
                ["SM-P355C","gt5note8ltechn"],           
                ["SM-S9180","dm3q"],
                ["SM-S9160","dm2q"],
                ["SC-51E","SC-51E"],
                ["SCG25","SCG25"],
                ["SM-S9210","e1q"],
                ["SM-S921B","e1s"],
                ["SM-S7210","r12s"],
                ["SC-52E","SC-52E"]                     
            ],
            "Vivo":[
                ["V2025","2025"],
                ["V2025A","PD2024"],
                ["V2026","2026"],
                ["V2027","2027"],
                ["V2028","2028"],
                ["V2029","2027"],
                ["V2030","2030"],
                ["V2031","2036"],
                ["V2031A","PD2031"],
                ["V2031EA","PD2031EA"],
                ["V2031_21","2036"],
                ["V2032","2027"],
                ["V2033","2034"],
                ["V2034A","PD2034"],
                ["V2035","2036"],
                ["V2036A","PD2036"],         
                ["vivo V1","V1"],
                ["V1730EA","PD1730E"],
                ["V1731CA","PD1731C"],
                ["V1732A","PD1732"],
                ["V1809A","PD1809"],
                ["V1813BA","PD1813B"],
                ["V1813BT","PD1813D"],
                ["V1814A","PD1814"],
                ["V1816A","PD1816"],
                ["V1818A","PD1818"],
                ["V1818A","PD1818G"],
                ["V1818CA","PD1818E"],
                ["V1821A","PD1821"],
                ["V1824A","PD1824"],
                ["V1829A","PD1829"],
                ["V1836A","PD1836"],
                ["V1838A","PD1838"],
                ["V1901A","PD1901"],
                ["V1911A","PD1911"],
                ["V1913A","PD1913"],
                ["V1914A","PD1914"],
                ["V1916A","PD1916"]
            ],
            "Google":[
                ["Pixel 6 Pro","raven"],
                ["Pixel 6a","bluejay"],
                ["Pixel 7","panther"],
                ["Pixel 7 Pro","cheetah"],
                ["Pixel 7a","lynx"],
                ["Pixel 8","shiba"],
                ["Pixel 8 Pro","husky"],
                ["Pixel 8a","akita"],
                ["Pixel 9","tokay"],
                ["Pixel 9 Pro","caiman"],
                ["Pixel 9 Pro Fold","comet"],
                ["Pixel 9 Pro XL","komodo"]                
            ]
        }        
        
        VERSION = ["10.0.0","11.0.0","12.0.0","13.0.0","14.0.0"]

        osVersion = random.choice(VERSION)
        manufacturer = random.choice(MANUFACTURER)        
        obj = random.choice(DEVICE_MODEL_TYPE[manufacturer])           
        deviceModelType = obj[0]
        deviceName = obj[1]
        
        return EnvSmbAndroid(            
            osVersion=osVersion,
            manufacturer=manufacturer,
            deviceName=deviceName,
            deviceModelType=deviceModelType
        )

    def getToken(self,phoneNumber):
        return EnvTools.getAndroidToken(self,phoneNumber,self.key,self.md5Classes)
    
    def getUserAgent(self):
        return EnvTools.getAndroidUserAgent(self)    
    
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
    
    def getDeviceName2(self):
        return self.deviceName    
    
    def getOSVersion(self):
        return self.osVersion
    
    def getBuildVersion(self):
        return self.buildVersion
    
    def getOSName(self):
        return self.osName
    
    def getDeviceModelType(self):
        return self.deviceModelType