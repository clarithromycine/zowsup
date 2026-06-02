from ....structs import ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .iq_sync import SyncIqProtocolEntity
import base64
from proto import e2e_pb2


class ProfilesGetSyncIqProtocolEntity(SyncIqProtocolEntity):

    MODE_QUERY = "query"
    CONTEXT_MESSAGE = "message"
    CONTEXT_INTERACTIVE = "interactive"

    CONTEXTS = (CONTEXT_MESSAGE,CONTEXT_INTERACTIVE)
    MODES = (MODE_QUERY,)

    '''
    <iq type="get" id="{{id}}" xmlns="usync">
        <usync mode="query" last="true" index="0" context="message"        
            sid="xxxxxxxxxxxx"                        
        >
            <query>
                <picture type="preview" />
                <status />
            </query>
            <list>
                <user jid="XXXXXXXXXSADASD" />
            </list>
        </usync>
    </iq>
    '''

    def __init__(self, jids, mode = MODE_QUERY, context = CONTEXT_MESSAGE, catalogs=None,sid = None, index = 0, last = True) -> None:
        super().__init__("get", sid = sid, index =  index, last = last)
        self.setProfilesGetSyncProps(jids, mode, context,catalogs=catalogs)

    def setProfilesGetSyncProps(self, jids, mode, context,catalogs) -> Any:
        assert type(jids) is list, "numbers must be a list"
        assert mode in self.__class__.MODES, "mode must be in %s" % self.__class__.MODES
        assert context in self.__class__.CONTEXTS, "context must be in %s" % self.__class__.CONTEXTS

        self.jids = jids
        self.mode = mode
        self.context = context
        self.catalogs = catalogs

        if self.catalogs is None:
            self.catalogs = ["picture","status","name"]

    def __str__(self):
        out  = super().__str__()
        out += "Mode: %s\n" % self.mode
        out += "Context: %s\n" % self.context
        out += "numbers: %s\n" % (",".join(self.numbers))
        return out

    def toProtocolTreeNode(self) -> Any:
        query=ProtocolTreeNode("query",{},None,None)     

        if "picture" in self.catalogs:
            picture=ProtocolTreeNode("picture",{"type":"preview"},None,None)
            query.addChild(picture)   

        if "lid" in self.catalogs:
            lid = ProtocolTreeNode("lid",{},None,None)
            query.addChild(lid)

        if "status" in self.catalogs:
            status=ProtocolTreeNode("status",{},None,None)
            query.addChild(status)
        
        if "name" in self.catalogs:
            business=ProtocolTreeNode("business",{},None,None)
            vn=ProtocolTreeNode("verified_name",{},None,None)
            business.addChild(vn)
            query.addChild(business)     
            username= ProtocolTreeNode("username",{},None,None)
            query.addChild(username)
         
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
        #syncNode.addChild(ProtocolTreeNode("side_list",{},None,None))

        return node


class ProfilesResultSyncIqProtocolEntity(SyncIqProtocolEntity):
    '''
    <iq from="919274165362@s.whatsapp.net" type="result" id="AC4F6B1D9E53508784C901FBE3276AD2">
    <usync sid="133924064680000000" index="0" last="true" mode="query" context="message">
        <result>
        <picture />
        <status />
        <business />
        <list>
        <user jid="8619874406144@s.whatsapp.net">
            <picture direct_path="/v/t61.24694-24/473407959_865478262323247_6238804481703930115_n.jpg?stp=dst-jpg_s96x96_tt6&ccb=11-4&oh=01_Q5Aa1gGYbc36dRnRPmTtcu6g5-p0p_QloSC8DlYGmnDELmK9ZA&oe=683C497C&_nc_sid=5e03e0&_nc_cat=110" id="1741264218" />
            <business><verified_name verified_level='unknown' v='1'>ChoI4dDkoJLF4u5REgZzbWI6d2EiBmlzOTl6cxJAgXgRt9emyAQcPVyZxKxi54udBquV+nH++AABKXczT147+OI+VCwFvpmSxefkY1/iiOfxHyBk6sX7symOsySiDQ==</verified_name></business>            
            <status t="1744907497">
            0xe698afe4b8aae6b4bbe4baba
            </status>
        </user>
        <user jid="8618502065005@s.whatsapp.net">
            <status />
        </user>
        </list>
    </usync>
    </iq>
    '''

    def __init__(self,_id, sid, index, last, profilesDict) -> None:
        super().__init__("result", _id, sid, index, last)
        self.setProfilesResultSyncProps(profilesDict)

    def setProfilesResultSyncProps(self, profilesDict) -> Any:
        self.profilesDict = profilesDict

    
    def __str__(self):
        out  = super(SyncIqProtocolEntity, self).__str__()
        for key in self.profilesDict:
            out += "User:%s\n" % (key)
        return out
    
    @staticmethod
    def fromProtocolTreeNode(node):
        syncNode         = node.getChild("usync")
        resultNode       = syncNode.getChild("result")
        listNode         = syncNode.getChild("list")
        
        profilesDict = {}

        users = listNode.getAllChildren() if listNode else []

        for user in users:
            jid = user.getAttributeValue("jid")
            picture = user.getChild("picture")
            status = user.getChild("status")
            business = user.getChild("business")
            lid = user.getChild("lid")
            
            profilesDict[jid] = {}

            if business:
                vn = business.getChild("verified_name")
                if vn:
                    vnbytes = vn.getData()
                    payload = e2e_pb2.VerifiedNameCertificate()                                
                    payload.ParseFromString(vnbytes)                    
                    name = payload.details.verifiedName
                    profilesDict[jid]["serial"] = payload.details.serial
                    profilesDict[jid]["name"] = name
                    profilesDict[jid]["vname_cert"]=base64.b64encode(vnbytes).decode()
            if picture:
                profilesDict[jid]["picture"] = picture.getAttributeValue("direct_path")

            if status:
                try:                    
                    if status.getAttributeValue("t") is not None:                        
                        profilesDict[jid]["status"] = str(status.getData(),"utf-8")
                except:
                    pass

            if lid:
                profilesDict[jid]["lid"] = lid.getAttributeValue("val")
                                

        entity           = SyncIqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = ProfilesResultSyncIqProtocolEntity

        entity.setProfilesResultSyncProps(profilesDict)

        return entity
