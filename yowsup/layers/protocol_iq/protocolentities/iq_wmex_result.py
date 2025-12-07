from ....structs import  ProtocolTreeNode
from .iq import IqProtocolEntity
from ....common import YowConstants
from proto import wa_struct_pb2
import json,base64
from zargo.utils.jid import Jid
from zargo.argo_message_decoder import ArgoMessageDecoder

class BytesEncoder(json.JSONEncoder):
    def default(self, obj):
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

    def __init__(self,_id,result_obj=None,result_type="json"):
        super(WmexResultIqProtocolEntity, self).__init__(_id = _id, _type = "result", _from = YowConstants.DOMAIN)
        self.result_obj = result_obj
        self.result_type = result_type

    def setResultObj(self, result_obj,result_type):
        self.result_obj = result_obj
        self.result_type = result_type

    def __str__(self):
        out = super(WmexResultIqProtocolEntity, self).__str__()
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
        