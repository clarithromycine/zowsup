class DataException(Exception):
    
    def __init__(self,code,msg):        
        self.code = code
        self.msg = msg        

    def getCode(self):
        return self.code
    
    def getMsg(self):
        return self.msg