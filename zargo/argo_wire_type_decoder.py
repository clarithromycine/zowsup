
from zargo.wiretype import *
from zargo.exception.data_exception import DataException

class ArgoWireTypeDecoder() :

    def __init__(self,messageDecoder):
        self.messageDecoder = messageDecoder


    def getWireTypeById(self,typeId):
        if  typeId==-1:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.STRING)
        elif typeId==-2:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN)
        elif typeId==-3:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.VARINT)
        elif typeId==-4:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.FLOAT64)
        elif typeId==-5:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.BYTES)
        elif typeId==-6:
            return ArgoFixedWireType()
        elif typeId==-11:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.DESC)

        return None


    def decodeNestedWireType(self):
        nestedTypeId = self.messageDecoder.blockReader.readLength()
        nestedType = self.getWireTypeById(nestedTypeId)
        if nestedType is None:
            return None
        
        key = self.messageDecoder.decodeString()
        dedupe = self.messageDecoder.argoBlock.getBlockData(
            "Boolean",
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN),
                "Boolean",
                False
            )
        ).getData(self.messageDecoder.blockReader)

        return ArgoBlockWireType(nestedType,key,dedupe)
    
    def decodeRecordWireType(self):
        fields = {}
        length = self.messageDecoder.blockReader.readLength()
        for i in range(0,length):
            wireType = self.decode()
            fields[wireType.name]=wireType
        return ArgoRecordWireType(fields)

    def decode(self):
        name = self.messageDecoder.decodeString()
        wireType = self.decodeWireType()
        omittable = self.messageDecoder.argoBlock.getBlockData(
            "Boolean",
            ArgoBlockWireType(
                ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN),
                "Boolean",
                False
            )
        ).getData(self.messageDecoder.blockReader)
        return ArgoFieldWireType(wireType,name,omittable)

    def decodeWireType(self):
        typeId = self.messageDecoder.blockReader.readLength()
        

        if  typeId==-1:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.STRING)
        elif typeId==-2:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.BOOLEAN)
        elif typeId==-3:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.VARINT)
        elif typeId==-4:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.FLOAT64)
        elif typeId==-5:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.BYTES)
        elif typeId==-6:
            return ArgoFixedWireType()
        elif typeId==-7:
            return self.decodeNestedWireType()
        elif typeId==-8:
            return ArgoNullableWireType(inner = self.decodeWireType())
        elif typeId==-9:
            return ArgoArrayWireType(type = self.decodeWireType())
        elif typeId==-10:
            return self.decodeRecordWireType()
        elif typeId==-11:
            return ArgoScalarWireType.getInstance(ArgoScalarWireType.DESC) 
        elif typeId==-12:
            return ErrorWireType(DefaultWireType())
        elif typeId==-13:
            return PatchWireType(DefaultWireType())
        elif typeId==-15:
            return ExtensionWireType(DefaultWireType())
        

        raise DataException(-2,"WIRETYPE ERROR")
    

        
        
            

