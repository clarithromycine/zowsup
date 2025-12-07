from zargo.wiretype.block import ArgoBlockWireType
from zargo.wiretype.scalar import ArgoScalarWireType


class ArgoDataDecoder() :

    def __init__(self,argoBlock,blockReader,argoHeader):
        self.argoBlock = argoBlock
        self.blockReader = blockReader
        self.argoHeader = argoHeader

    def decodeVarInt(self):
        return self.argoBlock.getBlockData(
            "Int", 
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoScalarWireType.VARINT),
                "Int",
                False
            )
        ).getData(
            self.blockReader
        )
              
    def decodeString(self):
        return self.argoBlock.getBlockData(
            "String", 
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoScalarWireType.STRING),
                "String",
                True
            )
        ).getData(
            self.blockReader
        )
    
    def decodeBoolean(self):
        return self.argoBlock.getBlockData(
            "Boolean", 
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN),
                "Boolean",
                False
            )
        ).getData(
            self.blockReader
        )       

    def decodeBytes(self):
        return self.argoBlock.getBlockData(
            "Bytes",
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoBlockWireType.BYTES),
                "Bytes",
                False
            )
        ).getData(
            self.blockReader
        )

    def decodeBlock(self,wt):

        wireType = wt.wireType
        
        if isinstance(wireType,ArgoScalarWireType):

            if wireType.type==ArgoScalarWireType.VARINT:
                return self.decodeVarInt()
 
            if wireType.type==ArgoScalarWireType.STRING:
                blockData = self.argoBlock.getBlockData(
                    wt.key ,
                    ArgoBlockWireType(
                        ArgoScalarWireType.getInstance(ArgoScalarWireType.STRING),
                        "String",
                        True
                    )
                )

                if blockData is None:
                    return None
                else:
                    return blockData.getData(
                        self.blockReader
                    )         

            if wireType.type==ArgoScalarWireType.BOOLEAN:
                return self.argoBlock.getBlockData(
                    "Boolean", 
                    ArgoBlockWireType(
                        ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN),
                        "Boolean",
                        False
                    )
                ).getData(
                        self.blockReader
                )  

            if wireType.type==ArgoScalarWireType.BYTES:
                return self.argoBlock.getBlockData(
                    wt.key,
                    ArgoBlockWireType(
                        ArgoScalarWireType.getInstance(ArgoScalarWireType.BYTES),
                        "Bytes",
                        False,
                    )
                ).getData(
                    self.blockReader
                )




