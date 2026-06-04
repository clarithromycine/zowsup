from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
from .iq_wmex_result import WmexResultIqProtocolEntity
import json
class WmexQueryIqProtocolEntity(IqProtocolEntity):

    _queryIdMap = None
        
    '''
    <iq to="s.whatsapp.net" type="get" id="3979800857",xmlns="w:mex">
        <trace>
            <flow_id>9952408304882625</flow_id>
        </trace>    
        <query query_id='xxxxxxxxxx'>
            JSON-FORMATTED 
        </query>
    </iq>  
    '''

    def __init__(self,query_name=None,query_obj=None,_id=None) -> None:
        super().__init__("w:mex",_id = _id, _type = "get", to = YowConstants.DOMAIN)

        #首次使用时，加载列表
        if WmexQueryIqProtocolEntity._queryIdMap is None:
            WmexQueryIqProtocolEntity.loadDict()

        self.query_obj = query_obj
        self.query_name = query_name
        self.query_id = WmexQueryIqProtocolEntity._queryIdMap.get(self.query_name)

    @staticmethod
    def loadDict():
        with open("data/mex_argo_dict.json", encoding='utf8') as f:            
            rawJson = json.loads(f.read())
            WmexQueryIqProtocolEntity._queryIdMap = {k: str(v["doc_id"]) for k, v in rawJson.items()}
            
    def __str__(self):
        out = super().__str__()
        out += "query_name: {}\n".format(self.query_name)
        out += "query_id: {}\n".format(self.query_id)
        out += "query_obj: {}\n".format(json.dumps(self.query_obj))
        return out

    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()     
        WmexResultIqProtocolEntity.idNameMap[node.getAttributeValue("id")] = self.query_name   
        query = ProtocolTreeNode("query",{"query_id":self.query_id})
        self.query_obj["queryId"]=self.query_id
        query.setData(json.dumps(self.query_obj).encode())
        flow_id = ProtocolTreeNode("flow_id")
        flow_id.setData(self.query_id.encode())
        trace = ProtocolTreeNode("trace")
        trace.addChild(flow_id)
        node.addChild(trace)
        node.addChild(query)             
        return node               


