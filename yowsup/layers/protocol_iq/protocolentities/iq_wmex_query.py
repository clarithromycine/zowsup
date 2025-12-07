from ....structs import  ProtocolTreeNode
from .iq import IqProtocolEntity
from ....common import YowConstants
import json
from  .iq_wmex_result import WmexResultIqProtocolEntity
class WmexQueryIqProtocolEntity(IqProtocolEntity):

    _queryIdMap = None

    '''
    <iq to="s.whatsapp.net" type="get" id="3979800857",xmlns="w:mex">
        <query query_id='xxxxxxxxxx'>
            JSON-FORMATTED RESULT
        </query>
    </iq>  
    '''

    def __init__(self,query_name=None,query_obj=None,_id=None):
        super(WmexQueryIqProtocolEntity, self).__init__("w:mex",_id = _id, _type = "get", to = YowConstants.DOMAIN)

        #首次使用时，加载列表
        if WmexQueryIqProtocolEntity._queryIdMap is None:
            WmexQueryIqProtocolEntity.loadDict()

        self.query_obj = query_obj
        self.query_name = query_name
        self.query_id = WmexQueryIqProtocolEntity._queryIdMap.get(self.query_name)


    @staticmethod
    def loadDict():
        with open("data/argo_dict.json", 'r', encoding='utf8') as f:            
            WmexQueryIqProtocolEntity._queryIdMap =json.loads(f.read())

    def __str__(self):
        out = super(WmexQueryIqProtocolEntity, self).__str__()
        out += "query_name: %s\n" % self.query_name
        out += "query_id: %s\n" % self.query_id
        out += "query_obj: %s\n" % json.dumps(self.query_obj)
        return out

    def toProtocolTreeNode(self):
        node = super(WmexQueryIqProtocolEntity, self).toProtocolTreeNode()     
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


        