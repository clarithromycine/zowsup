from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ...protocol_iq.protocolentities import IqProtocolEntity
from .iq_sync import SyncIqProtocolEntity

class DevicesGetSyncIqProtocolEntity(SyncIqProtocolEntity):

    MODE_QUERY = "query"
    CONTEXT_MESSAGE = "message"

    CONTEXTS = (CONTEXT_MESSAGE,)
    MODES = (MODE_QUERY,)


    '''
    <iq type="get" id="{{id}}" xmlns="usync">
        <usync mode="query" last="true" index="0" context="message"        
            sid="xxxxxxxxxxxx"                        
        >
            <query>
                <devices version="2" />
            </query>
            <list>
                <user jid="XXXXXXXXXSADASD" />
            </list>
        </usync>
    </iq>
    '''

    def __init__(self, jids, mode = MODE_QUERY, context = CONTEXT_MESSAGE, sid = None, index = 0, last = True) -> None:
        super().__init__("get", sid = sid, index =  index, last = last)
        self.setDevicesGetSyncProps(jids, mode, context)

    def setDevicesGetSyncProps(self, jids, mode, context) -> Any:
        assert type(jids) is list, "numbers must be a list"
        assert mode in self.__class__.MODES, "mode must be in %s" % self.__class__.MODES
        assert context in self.__class__.CONTEXTS, "context must be in %s" % self.__class__.CONTEXTS

        self.jids = jids
        self.mode = mode
        self.context = context

    def __str__(self):
        out  = super().__str__()
        out += "Mode: %s\n" % self.mode
        out += "Context: %s\n" % self.context
        out += "numbers: %s\n" % (",".join(self.numbers))
        return out

    def toProtocolTreeNode(self) -> Any:
        query=ProtocolTreeNode("query",{},None,None)
        lid = ProtocolTreeNode("lid",{},None,None)
        query.addChild(lid)        
        devices=ProtocolTreeNode("devices",{"version":"2"},None,None)
        query.addChild(devices)        

        users =ProtocolTreeNode("list",{},None,None)        
        for jid in self.jids:
            user = ProtocolTreeNode("user",{"jid":jid},None,None)                        
            users.addChild(user)
            
        node = super().toProtocolTreeNode()
        syncNode = node.getChild("usync")
        syncNode.setAttribute("mode", self.mode)
        syncNode.setAttribute("context", self.context)
        syncNode.addChild(query)
        syncNode.addChild(users)

        return node


class DevicesResultSyncIqProtocolEntity(SyncIqProtocolEntity):
    '''
    <iq from="6283824958305@s.whatsapp.net" type="result" id="2">
    <usync sid="133187990650000000" index="0" last="true" mode="query" context="message">
        <result>
        <devices />
        </result>
        <list>
        <user jid="6283869786338@s.whatsapp.net">
            <devices>
            <device-list>
                <device id="0" />
                <device id="26" key-index="1" />
                <device id="27" key-index="2" />
                <device id="28" key-index="3" />                                
            </device-list>
            <key-index-list ts="1674309687">
                0x0a1308f1f192f60210b7e0af9e06180222030001021240740ee81523f4179cabfc0cd91348926a020af129f230b20738ddc4382951111d8aefa565475089737133bf47a34b90d613ee609259a47da6813f5adba8430607
            </key-index-list>
            </devices>
        </user>
        </list>
    </usync>
    </iq>
    '''

    def __init__(self,_id, sid, index, last, devicesDict,pnJidMap) -> None:
        super().__init__("result", _id, sid, index, last)
        self.setDevicesResultSyncProps(devicesDict,pnJidMap)        

    def setDevicesResultSyncProps(self, devicesDict,pnJidMap) -> Any:
        self.devicesDict = devicesDict
        self.pnJidMap = pnJidMap

    def collectAllResultTargets(self) -> Any:
        targets = []
        for key in self.devicesDict:                        
            listIds = self.devicesDict[key]            
            targets=[]
            for deviceId in listIds:
                if deviceId!="0":
                    targets.append(f"{key}:{deviceId}@lid")
                else:
                    targets.append("%s@lid" % (key))

        return targets
    
    def getPnJid(self,id) -> Any:        
        return self.pnJidMap.get(id)

    def __str__(self):
        out  = super(SyncIqProtocolEntity, self).__str__()
        for key in self.devicesDict:
            listDevices = self.devicesDict[key]
            out += "User:{}, Devices: {}\n".format(key,",".join(listDevices))
        return out
    
    @staticmethod
    def fromProtocolTreeNode(node) :
        """
        Parse protocol tree node and create a DevicesResultSyncIqProtocolEntity.
        
        This factory method dynamically converts a SyncIqProtocolEntity to 
        DevicesResultSyncIqProtocolEntity after parsing device information.
        
        Args:
            node: ProtocolTreeNode to parse containing device sync result
            
        Returns:
            DevicesResultSyncIqProtocolEntity: Parsed entity with devices dictionary 
                                              and phone number to JID mapping
        """
        syncNode         = node.getChild("usync")        
        listNode         = syncNode.getChild("list")
        
        devicesDict = {}
        pnJidMap = {}

        users = listNode.getAllChildren() if listNode else []

        for user in users:
            jid = user.getAttributeValue("jid")            
            if jid.endswith("lid"):
                lid = jid
            else:
                lid = user.getChild("lid").getAttributeValue("val")

            id = lid.split("@")[0]

            if jid.endswith("s.whatsapp.net"):
                pnJidMap[lid] = jid

            deviceList = user.getChild("devices").getChild("device-list")
            devicesDict[id] = []
            devices = deviceList.getAllChildren() if deviceList else []
            for device in devices:
                deviceId = device.getAttributeValue("id")                
                devicesDict[id].append(deviceId)

        entity           = SyncIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = DevicesResultSyncIqProtocolEntity

        entity.setDevicesResultSyncProps(devicesDict,pnJidMap)

        return entity
