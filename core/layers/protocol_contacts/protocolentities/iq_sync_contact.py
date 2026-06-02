from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ...protocol_iq.protocolentities import IqProtocolEntity
from .iq_sync import SyncIqProtocolEntity

class ContactGetSyncIqProtocolEntity(SyncIqProtocolEntity):

    MODE_FULL = "full"
    MODE_DELTA = "delta"
    MODE_QUERY = "query"

    CONTEXT_REGISTRATION = "registration"
    CONTEXT_INTERACTIVE = "interactive"
    CONTEXT_MESSAGE = "message"

    CONTEXTS = (CONTEXT_REGISTRATION, CONTEXT_INTERACTIVE,CONTEXT_MESSAGE)
    MODES = (MODE_FULL, MODE_DELTA,MODE_QUERY)


    '''
    <iq type="get" id="{{id}}" xmlns="usync">
        <usync mode="{{full | ?}}"
            context="{{registration | ?}}"
            sid="{{str((int(time.time()) + 11644477200) * 10000000)}}"
            index="{{0 | ?}}"
            last="{{true | false?}}"
        >
            <list>
                <user>
                    <contact>
                        +18500000000
                    </contact>
                </user>
                <user>
                    <contact>
                        +18500000000
                    </contact>
                </user>
            </list>

        </usync>
    </iq>
    '''

    def __init__(self, numbers, mode = MODE_FULL, context = CONTEXT_INTERACTIVE, sid = None, index = 0, last = True) -> None:
        super().__init__("get", sid = sid, index =  index, last = last)

        self.setGetSyncProps(numbers, mode, context)        

    def setGetSyncProps(self, numbers, mode, context) -> Any:
        assert type(numbers) is list, "numbers must be a list"
        assert mode in self.__class__.MODES, "mode must be in %s" % self.__class__.MODES
        assert context in self.__class__.CONTEXTS, "context must be in %s" % self.__class__.CONTEXTS

        self.numbers = numbers
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
        status=ProtocolTreeNode("status",{},None,None)
        query.addChild(status)
        contact=ProtocolTreeNode("contact",{},None,None)
        query.addChild(contact)        
        business=ProtocolTreeNode("business",{},None,None)

        vn=ProtocolTreeNode("verified_name",{},None,None)
        business.addChild(vn)
        query.addChild(business)     



        '''
        business=ProtocolTreeNode("business",{},None,None)
        vn=ProtocolTreeNode("verified_name",{},None,None)
        business.addChild(vn)
        pro=ProtocolTreeNode("profile",{"v":"116"},None,None)
        business.addChild(pro)
        query.addChild(business)
        '''

        list =ProtocolTreeNode("list",{},None,None)        
        for number in self.numbers:
            if not number.startswith("+"):
                number = "+"+number                                
            contact = ProtocolTreeNode("contact",{}, None,number.encode())
            user = ProtocolTreeNode("user",{},None,None)            
            user.addChild(contact)
            list.addChild(user)

        node = super().toProtocolTreeNode()
        syncNode = node.getChild("usync")
        syncNode.setAttribute("mode", self.mode)
        syncNode.setAttribute("context", self.context)
        syncNode.addChild(query)        
        syncNode.addChild(list)

        return node

    @staticmethod
    def fromProtocolTreeNode(node):
        syncNode         = node.getChild("usync")        
        userNodes        = syncNode.getAllChildren()
        numbers = []

        for userNode in userNodes:
            contact = userNode.getChild("contact")
            number = contact.data
            numbers.append(number)            
        
        entity.__class__ = ContactGetSyncIqProtocolEntity        
        entity = SyncIqProtocolEntity.fromProtocolTreeNode(node)

        entity.setGetSyncProps(numbers,
            syncNode.getAttributeValue("mode"),
            syncNode.getAttributeValue("context"),
            )

        return entity


class ContactResultSyncIqProtocolEntity(SyncIqProtocolEntity):
    '''
    <iq type="result" from="491632092557@s.whatsapp.net" id="1417046561-4">
        <usync index="0" wait="166952" last="true" version="1417046548593182" sid="1.30615237617e+17">
            <result>
                <lid/>
                <disappearing_mode />
                <devices />
                <business />
                <status />
                <contact version="1417046548593182"/>    
            </result?
            <list>
                <user jid=".....">
                    <contact type="in/out" />
                        +8618500000000
                    </contact>
                </user>
                <user jid=".....">
                    <contact type="in/out" />
                        +8618500000000
                    </contact>
                </user>
                <user jid=".....">
                    <contact type="in/out" />
                        +8618500000000
                    </contact>
                </user>
            </list>            
        </usync>
    </iq>
    '''

    def __init__(self,_id, sid, index, last, version, mode, result) -> None:
        super().__init__("result", _id, sid, index, last)
        self.setResultSyncProps(version, mode, result)

    def setResultSyncProps(self, version, mode, result) -> Any:
        self.result = result        
        self.version = version
        self.mode = mode

    def __str__(self):
        out  = super(SyncIqProtocolEntity, self).__str__()
        if self.wait is not None:
            out += "Wait: %s\n" % self.wait
        out += "Version: %s\n" % self.version
        out += "In Numbers: %s\n" % (",".join(self.inNumbers))
        out += "Out Numbers: %s\n" % (",".join(self.outNumbers))

        return out

    def toProtocolTreeNode(self) -> Any:

        users = []

        for number,jid in self.inNumbers.items():
            contact =ProtocolTreeNode("contact",{type:"in"},None,number)
            user = ProtocolTreeNode("user",{jid:jid},None,None)
            user.addChild(contact)
            users.append(user)            

        for number,jid in self.outNumbers.items():
            contact =ProtocolTreeNode("contact",{type:"out"},None,number)
            user = ProtocolTreeNode("user",{jid:jid},None,None)
            user.addChild(contact)
            users.append(user)   

        for number in self.invalidUsers:
            contact =ProtocolTreeNode("contact",{type:"invalid"},None,number)
            user = ProtocolTreeNode("user",{},None,None)
            user.addChild(contact)
            users.append(user)

        node = super().toProtocolTreeNode()
        syncNode = node.getChild("usync")
        syncNode.setAttribute("version", self.version)

        if self.wait is not None:
            syncNode.setAttribute("wait", str(self.wait))

        if len(users):
            syncNode.addChild(ProtocolTreeNode("list", children = users))

        return node

    @staticmethod
    def fromProtocolTreeNode(node):

        syncNode         = node.getChild("usync")
        resultNode       = syncNode.getChild("result")
        listNode         = syncNode.getChild("list")

        mode = syncNode.getAttributeValue("mode")
        
        # Handle missing contact node in result (server may not include it in all responses)
        version = None
        if resultNode is not None:
            contactNode = resultNode.getChild("contact")
            if contactNode is not None:
                version = contactNode.getAttributeValue("version")

        users = listNode.getAllChildren() if listNode else []

        result = {}

        for user in users:

            jid = user.getAttributeValue("jid")
            contact = user.getChild("contact")
            
            # Skip user if contact node is missing
            if contact is None:
                continue
                
            type = contact.getAttributeValue("type")

            lid = None
            lidNode = user.getChild("lid")
            if lidNode is not None:
                lid = lidNode.getAttributeValue("val")
            
            result[contact.data.decode().replace("+","")] = {
                "type":type,
                "jid":jid,
                "lid":lid,
                "business":user.getChild("business") is not None
            }
                                                                
        entity           = SyncIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ContactResultSyncIqProtocolEntity

        entity.setResultSyncProps(version,
            mode,
            result
        )

        return entity
