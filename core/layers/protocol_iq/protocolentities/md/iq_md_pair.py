from .....structs import  ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from ..iq import IqProtocolEntity
from .....common import YowConstants
class MultiDevicePairIqProtocolEntity(IqProtocolEntity):

    '''

    <iq from="s.whatsapp.net" type="set" id="624196698" xmlns="md">
    <pair-device>
        <ref>
        0x3240464a3055636333693365454c7650326f516b7469516a4b4c6e6241533868526e7a414b5a6c51435058384237664e2f304364684546437a2f69646e4f4a597a79546b54795955336b72786f7476773d3d
        </ref>
        <ref>
        0x324055796b37326d6e486f67306531544c4f4e7870316e585550336250323178783052654d452f527171724266633746794f65666b73576b4d504e47386c6c70516c53316b36786c2b555638505954773d3d
        </ref>
        <ref>
        0x32404154713841452b494e516b47635a664b52664756634e74556d6b5a796b42712f364c4d3462506a6b376a454f4c50365145514a424b6e3967786d32446a536867595a77644e6538524369567744413d3d
        </ref>
        <ref>
        0x324039517a414d614b704f57394333636431506a7957434e704c52346a416a3449636b6d6e31665047716c7a74514263713249654343485733396d4c646e50754350613033304d7151704f4c443678673d3d
        </ref>
        <ref>
        0x32405067774d3951614978724b2f674c4876575a495555454161464447477a346e764e6c4d6d72637249315a76624a5a67354e6475656c4c7936596e6643446b59483379545a79524f6365757a3843513d3d
        </ref>
        <ref>
        0x3240512b3570687a742f494f76336437444e7a762b53492f6c69324556423630614d6765456c647a674242306f325451424f4a4c71306f6c587131325a62426f514450596f35486e6b3954336d4971673d3d
        </ref>
    </pair-device>
    </iq>    
    '''

    def __init__(self,_id) -> None:
        super().__init__(_id = _id, _type = "set", _from = YowConstants.DOMAIN, xmlns="md")
        self.refs = []        

    def setRefs(self, refs) -> Any:
        self.refs = refs

    def __str__(self):
        out = super().__str__()
        out += "refs: %s\n" % self.refs
        return out

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = IqProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = MultiDevicePairIqProtocolEntity
        nodePairDevice = node.getChild("pair-device")        
        refs=[]
        for p in nodePairDevice.getAllChildren("ref"):
            refs.append(p.getData())
        entity.setRefs(refs)       
        return entity


