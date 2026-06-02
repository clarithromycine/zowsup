import json
from typing import Optional, Any, List, Dict, Union
import logging
logger = logging.getLogger(__name__)

class ResponseParser:
    def __init__(self) -> Any:
        self.meta = "*"
        
    def parse(self, text, pvars) -> Any:
        return text
    
    def getMeta(self) -> Any:
        return self.meta
    
    def getVars(self, pvars) -> Any:
        if type(pvars) is dict:
            return pvars
        if type(pvars) is list:
            
            out = {}
            
            for p in pvars:
                out[p] = p
                
            return out



class JSONResponseParser(ResponseParser):
    
    def __init__(self) -> Any:
        self.meta = "text/json"

    def parse(self, jsonData, pvars) -> Any:
        
        d = json.loads(jsonData)
        pvars = self.getVars(pvars)

        parsed = {}     
        
        for k,v in pvars.items():
            parsed[k] = self.query(d, v)

        return parsed
    
    def query(self, d, key) -> Any:
        keys = key.split('.', 1)
            
        currKey = keys[0]
        
        if(currKey in d):
            item = d[currKey]
            
            if len(keys) == 1:
                    return item
            
            if type(item) is dict:
                return self.query(item, keys[1])
            
            elif type(item) is list:
                output = []

                for i in item:
                    output.append(self.query(i, keys[1]))
                return output
            
            else:
                return None


        
