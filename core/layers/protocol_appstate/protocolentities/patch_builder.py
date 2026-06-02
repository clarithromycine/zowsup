
from common.utils import Utils
from typing import Optional, Any, List, Dict, Union
from .lthash import LTHash
import hmac
from ....layers.protocol_appstate.protocolentities.attributes import *
import hashlib
import copy

class PatchBuilder:


    '''
    浣跨敤涓夋澘鏂?

    PatchBuilder().addMutation().......addMutation.finish()

    '''


    def __init__(self,initState=None,mutationKeys=None,key=None) -> None:
        self.mutations = []
        self.state = copy.deepcopy(initState)

        self.generator = LTHash(self.state) 
        self.valueMacs = []
        self.key = key
        self.mutationKeys = mutationKeys
        self.syncdPatch = None
    
    def addMutation(self,actionData) -> Any:

        encrypted = Utils.encryptAndPrefix(actionData.encode().SerializeToString(),self.mutationKeys.encKey)
        
        indexMac = hmac.new(self.mutationKeys.indexKey, actionData.index, hashlib.sha256).digest()
        valueMac = Utils.generateMac(b"\x01",encrypted,self.key.key_id.key_id,self.mutationKeys.macKey)
        
        mutation = SyncdMutationAttribute(
                        operation=0,
                        record = SyncdRecordAttribute(
                            index = SyncdIndexAttribute(blob = indexMac),
                            value = SyncdValueAttribute(blob= encrypted+valueMac),
                            keyId =  SyncdKeyIdAttribute(id = self.key.key_id.key_id)
                        )
        )        
        self.mutations.append(mutation)            
        self.generator.mix(
            indexMac,
            valueMac,
            mutation.operation
        )    
        self.valueMacs.append(valueMac)   
        return self        

    def finish(self) -> Any:    
        self.state = self.generator.finish()
    
        snapshotMac = Utils.generateSnapshotMac(self.state.hash,self.state.version,self.state.type,self.mutationKeys.snapShotMacKey)

        patchMac = Utils.generatePatchMac(snapshotMac,self.valueMacs,self.state.version,self.state.type,self.mutationKeys.patchMacKey)

        syncdPatch = SyncdPatchAttribute(                        
            patchMac=patchMac,
            snapshotMac=snapshotMac,
            keyId=SyncdKeyIdAttribute(self.key.key_id.key_id),
            mutations=self.mutations
        )

        return self.state,syncdPatch
        
    def getState(self) -> Any:
        return self.state
    
    def getMutations(self) -> Any:
        return self.mutations
    
    def getSyncdPatch(self) -> Any:        
        return self.syncdPatch
    
    





        
