from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq import IqProtocolEntity

'''

    [FIRST REQUEST]
    <iq to='s.whatsapp.net' xmlns='w:sync:app:state' type='set' id='020'>
        <sync data_namespace='3'>
            <collection name='critical_unblock_low' order='0' version='0' return_snapshot='true'/>
            <collection name='critical_block' order='1' version='0' return_snapshot='true'/>
        </sync>
    </iq>    

    [WITH PATCHES SYNC]
    <iq to='s.whatsapp.net' xmlns='w:sync:app:state' type='set' id='0d'>
        <sync data_namespace='3'>
            <collection name='critical_unblock_low' order='0'>
                <patch>
                    EtkBCAAS1AEKIgogq1KjkZ0di/MjsxXUWlhl3kX3QGdMpDDX7vlM7opusQ0SowEKoAGGa8or/ieTjIehj/fR1vsP/dMSTEP9SqeckQ4fDJPi2JrIk8ZdOCHzCP7v4iwfCTyEJyk2bVbeXq+vwumzbPTxoqpuc/wrqMGv91YepCHFvyABBV2mEcnHla3nGZb2BZs8FYWge9dz5J/edB4Mxeiv4nNgWiBGTOrMyJPW6FONvNl8UzaMHsoa8KWbQ5fRCI702IAW0i+t1j5t+4EAX1kvGggKBgAAAABoRSIgHAetpsGu+MQlxtXgu1ziyTrLj9SzYB0ACj4J6P79xJcqICDiRWvAbC/IDW/xy7Ve7uvE3WzauqQfa7Y/2rh+zxL0MggKBgAAAABoRUAA
                </patch>
            </collection>
            <collection name='critical_block' order='1'>
                <patch>
                    EpcBCAASkgEKIgog6ljOH0I5TnwqXIiRJKsnlDYWcQuFbKohxbjYU6I926QSYgpgDY23FQHEzkllChxoPp+rvHs/ijgOHFo43uVjyTMmX1vnXzBO9vGH6T/ZAg7EeQh8QV1t+utJldrMueqt20wzjLE7De2ODIhbwUFnzGTV5YGeD0GjvKsU1/nV2ZTgEw3CGggKBgAAAABoRRKnAQgAEqIBCiIKICsyUbZaTs/L4QCU5YK3Hcxl5rpJMzqrqV5qIV/SkmynEnIKcPQUhIZ2cqk5tDuyW9BkWO4pQu79WFKgRn588FkwTSmbgvmDhci0EsIP89L5Dd8bDJrxSRfl0Wkhr8gk7aGFlj7f6/LJVUAb3FjwniToUuIw12gakgnJyU/O7SctYtJ4QGblc0EXUGl3wcwdq3qss9MaCAoGAAAAAGhFIiA3UluNObBB/ToM1EMLH6eWtRThSZjQZhtZ6fu5xftRZSogvFA3mV2BbKu/tsEdiuTIQ4mG+LUK0lSECKYEYETlgvwyCAoGAAAAAGhFQAA=
                </patch>
            </collection>
        </sync>
    </iq>

'''

class AppSyncStateIqProtocolEntity(IqProtocolEntity):

    def __init__(self,  _id = None, dataNamespace="3", request = None,first=True,patches = None) -> None:
        super().__init__("w:sync:app:state" , _id = _id, _type = "set",to="s.whatsapp.net")        
        self.dataNamespace = dataNamespace        
        self.request = request
        self.first = first
        self.patches = patches
    
    def toProtocolTreeNode(self) -> Any:
        node = super().toProtocolTreeNode()

        syncnode = ProtocolTreeNode("sync",{"data_namespace":str(self.dataNamespace)})        
        if self.patches is not None:            
            for name,patch in self.patches.items():
                collectionNode = ProtocolTreeNode("collection",{"name":name,"order":"0" if name=="critical_unblock_low" else "1"})                
                if patch is not None:
                    patchNode = ProtocolTreeNode("patch",{},None,patch.SerializeToString())
                    collectionNode.addChild(patchNode)                
                syncnode.addChild(collectionNode)        

        else:            
            if self.request is not None:                                        
                for name,params in self.request.items():
                    attrs = {"name":name}
                    if params is not None:
                        attrs["order"] = "0" if name=="critical_unblock_low" else "1"
                        attrs["version"] = str(params["version"]) if params.get("version") is not None else "0" 
                        attrs["return_snapshot"] = "true" if params.get("return_snapshot",True) else "false"
                    collectionNode = ProtocolTreeNode("collection",attrs)                            
                    syncnode.addChild(collectionNode)                                

        node.addChild(syncnode)      
        return node    


class ResultAppSyncStateIqResponseProtocolEntity(IqProtocolEntity):

    def __init__(self,  dataNamespace="3", collections = None) -> None:
        super().__init__()        
        self.dataNamespace = dataNamespace        
        self.collections = collections if collections is not None else {}

    @staticmethod   
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ResultAppSyncStateIqResponseProtocolEntity        
        syncNode = node.getChild("sync")        
        collections = {}
        for collectionNode in syncNode.getAllChildren():            
            name = collectionNode.getAttributeValue("name")
            collections[name] = {"data":[]}

            type = collectionNode.getAttributeValue("type")

            if type == "error":
                errorNode = collectionNode.getChild("error")
                error = {
                    "code": errorNode.getAttributeValue("code"),
                    "text": errorNode.getAttributeValue("text")
                }
                collections[name]["error"] = error
                 
            patchesNode = collectionNode.getChild("patches")
            if patchesNode is not None:            
                for patchNode in patchesNode.getAllChildren():
                    patchData = patchNode.getData() if patchNode is not None else None
                    collections[name]["data"].append(patchData)            

        entity.collections = collections

        return entity