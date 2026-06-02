from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union

from .....layers.protocol_appstate.protocolentities.attributes import *

#这个就是patch内的内容

class SyncdPatchAttribute:
    def __init__(self,mutations,snapshotMac,patchMac,keyId, version=None,externalMutations=None,exitCode=None,deviceIndex=0,clientDebugData=None) -> None:
        self.version = version
        self.mutations = mutations
        self.externalMutations = externalMutations
        self.snapshotMac = snapshotMac
        self.patchMac = patchMac
        self.keyId = keyId
        self.exitCode = exitCode
        self.deviceIndex = deviceIndex
        self.clientDebugData = clientDebugData

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncdPatch()

        if self.version is not None:
            pb_obj.version.MergeFrom(self.version.encode())
        
        if self.mutations is not None:
            for item in self.mutations:
                pb_obj.mutations.append(item.encode())
        
        if self.externalMutations is not None:
            for item in self.externalMutations:
                pb_obj.externalMutions.append(item.encode())

        if self.snapshotMac is not None:
            pb_obj.snapshotMac = self.snapshotMac

        if self.patchMac is not None:
            pb_obj.patchMac = self.patchMac

        if self.keyId is not None:
            pb_obj.keyId.MergeFrom(self.keyId.encode())
        
        if self.exitCode is not None:
            pb_obj.exitCode.MergeFrom(self.exitCode.encode())

        if self.deviceIndex is not None:
            pb_obj.deviceIndex = self.deviceIndex

        if self.clientDebugData is not None:
            pb_obj.clientDebugData = self.clientDebugData

        return pb_obj
    
    @staticmethod
    def decodeFrom(pb_obj):

        version = SyncdVersionAttribute.decodeFrom(pb_obj.version) if pb_obj.HasField("version") else None
            
        mutations = []
        for item in pb_obj.mutations:
            mutations.append(SyncdMutationAttribute.decodeFrom(item))
        
        externalMutations = []
        for item in pb_obj.externalMutations:
            externalMutations.append(SyncdExternalBlobReferenceAttribute.decodeFrom(item))


        snapshotMac = pb_obj.snapshotMac if pb_obj.HasField("snapshotMac") else None

        patchMac = pb_obj.patchMac if pb_obj.HasField("patchMac") else None

        keyId = SyncdKeyIdAttribute.decodeFrom(pb_obj.keyId) if pb_obj.HasField("keyId") else None

        exitCode = SyncdExitCodeAttribute.decodeFrom(pb_obj.exitCode) if pb_obj.HasField("exitCode") else None

        deviceIndex = pb_obj.deviceIndex if pb_obj.HasField("deviceIndex") else None

        clientDebugData = pb_obj.clientDebugData if pb_obj.HasField("clientDebugData") else None

        return SyncdPatchAttribute(
            version=version,
            mutations=mutations,
            externalMutations=externalMutations,
            snapshotMac=snapshotMac,
            patchMac=patchMac,
            keyId=keyId,
            exitCode=exitCode,
            deviceIndex=deviceIndex,
            clientDebugData=clientDebugData
        )