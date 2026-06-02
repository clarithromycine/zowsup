from ..iq import IqProtocolEntity
from typing import Optional, Any, List, Dict, Union
from .....common import YowConstants
from zargo.argo_message_decoder import ArgoMessageDecoder
import base64,json
from zargo.utils.jid import Jid

class BytesEncoder(json.JSONEncoder):
    def default(self, obj) -> Any:
        if isinstance(obj, bytes):
            if obj[0]==250 or obj[0]==247:
                return Jid.readJid(obj)
            else:
                return base64.b64encode(obj).decode('utf-8') 
        return json.JSONEncoder.default(self, obj)
    

class WmexResultIqProtocolEntity(IqProtocolEntity):

    idNameMap = {}

    '''

    <iq from="s.whatsapp.net" type="result" id="3979800857">
    <result>
        JSON-FORMATTED RESULT
    </result>
    </iq>  
    '''

    def __init__(self,_id,result_obj=None,result_type="json") -> None:
        super().__init__(_id = _id, _type = "result", _from = YowConstants.DOMAIN)
        self.result_obj = result_obj
        self.result_type = result_type
        

    def setResultObj(self, result_obj,result_type) -> Any:
        self.result_obj = result_obj
        self.result_type = result_type

    def __str__(self):
        out = super().__str__()
        out += "result_obj: %s\n" % (json.dumps(self.result_obj) if self.result_type=="json" else str(self.result_obj))
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = WmexResultIqProtocolEntity
        result = node.getChild("result")                
        if result is not None:      
            format = result.getAttributeValue("format")                    
            if format=="argo":               
                data = result.getData()                                                                         
                id = node.getAttributeValue("id")
                query_name =  WmexResultIqProtocolEntity.idNameMap.pop(id)                
                if query_name=="BizIntegrityQuery":
                    data= data.replace(b"\x01\x02\x02",b"\x01\x00\x02") #little temp patch to ignore some weird fields in integrity_tags formats
                if query_name is not None:
                    ArgoMessageDecoder.setSchemaFile("data/argo-wire-type-store.argo")
                    obj = ArgoMessageDecoder.decodeMessage(query_name,data)                    
                    res = json.dumps(obj,cls=BytesEncoder)                   
                                    
                    entity.setResultObj(json.loads(res),"json")
                else:
                    entity.setResultObj(data,"argo") 
            else:
                jsonstr = str(result.getData(),"utf-8")
                entity.setResultObj(json.loads(jsonstr),"json")
            return entity
        else:            
            return None
