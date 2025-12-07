
from zargo.struct import *
from zargo.utils import *
from .argo_data_decoder import ArgoDataDecoder
from .argo_wire_type_decoder import ArgoWireTypeDecoder
from zargo.exception.data_exception import DataException
from zargo.wiretype import *

class NoInstance(type):
    def __call__(self,*args,**kwargs):
        raise TypeError('STATIC CALL ONLY')

class ArgoMessageDecoder(metaclass=NoInstance):

    _schemaStore = None
    _schemaFile = None
    
    @staticmethod
    def getArgoDataDecoder(data):
        reader = DataReader(data)
        b = reader.readByte()
        if b & 0x80 ==0:
            inlineEverything = Bitwise.isBitSet(b,0)
            selfDescribing = Bitwise.isBitSet(b,1)
            outOfBandFieldErrors = Bitwise.isBitSet(b,2)
            selfDescribingErrors = Bitwise.isBitSet(b,3)
            nullTerminatedStrings = Bitwise.isBitSet(b,4)
            noDeduplication = Bitwise.isBitSet(b,5)
            hasUserFlags = Bitwise.isBitSet(b,6)
            userFlags = None
            if hasUserFlags:
                userFlags = []
                userFlagBytes = []
                bitCount = 0
                while True:
                    nextByte = reader.readByte()
                    bitCount+=7
                    userFlagBytes.append(nextByte)
                    if nextByte & 0x01 == 0:
                        break            

                if len(userFlagBytes)>0:                                    
                    for byte in reversed(userFlagBytes):
                        for pos in range(1,8):
                            userFlags.append(Bitwise.isBitSet(byte,pos))
                
            header = ArgoHeader(inlineEverything,selfDescribing,outOfBandFieldErrors,selfDescribingErrors,nullTerminatedStrings,noDeduplication,hasUserFlags,userFlags)    
            argoBlock = ArgoBlock(header)

            if header.inlineEverything:
                inline = reader.readBytes(reader.getDataLength()-reader.getCurrentIndex())
                argoBlock.byteQueue.append(inline)
            else:
                blockData = reader.readBytes(reader.getDataLength()-reader.getCurrentIndex())
                
            blockReader = BlockReader(blockData)
            while True:
                length = blockReader.readLength()
                if length is None:
                    break
                bytes = blockReader.readBytes(length)                
                argoBlock.byteQueue.append(bytes)

            if not argoBlock.inlineEverything:
                return ArgoDataDecoder(argoBlock,BlockReader(argoBlock.byteQueue.pop()),header)
        return None
    
    @staticmethod
    def setSchemaFile(filepath):
        if ArgoMessageDecoder._schemaFile is None or ArgoMessageDecoder._schemaFile!=filepath:
            ArgoMessageDecoder._schemaFile = filepath
            ArgoMessageDecoder._schemaStore = None      #重新设置名称，那下次调用的时候就重新load

    #从argofile中读取信息
    @staticmethod
    def loadSchemaFile():

        if ArgoMessageDecoder._schemaFile is  None:
            raise DataException(-1,"SCHEMA FILE NOT SET")
                
        with open(ArgoMessageDecoder._schemaFile, 'rb') as f:
            data = f.read()

        dataDecoder = ArgoMessageDecoder.getArgoDataDecoder(data)
        wireTypeDecoder = ArgoWireTypeDecoder(dataDecoder)
        blockReader = dataDecoder.blockReader
        typeId = blockReader.readLength()

        if typeId==2:
            if ArgoMessageDecoder._schemaStore is None:
                ArgoMessageDecoder._schemaStore={}

            length = blockReader.readLength()
            for i in range(0,length):
                key = dataDecoder.decodeString()                
                value = wireTypeDecoder.decodeWireType()
                ArgoMessageDecoder._schemaStore[key] = value

    @staticmethod
    def decodeMessage(schemaEntry, msgBytes):
        
        if ArgoMessageDecoder._schemaStore is None:
            ArgoMessageDecoder.loadSchemaFile()

        if schemaEntry not in ArgoMessageDecoder._schemaStore:
            raise DataException(-1,"SCHEMA NAME ERROR")

        entryWireType = ArgoMessageDecoder._schemaStore[schemaEntry]
        dataDecoder = ArgoMessageDecoder.getArgoDataDecoder(msgBytes)
        

        jsonObject = ArgoMessageDecoder.decodeTypeData(entryWireType,dataDecoder)

        
    
        return jsonObject
        
    @staticmethod
    def decodeTypeData(wireType,dataDecoder):

        #python .\script\main.py 639750291982 misc.bizintegrity 8619874406144,8613431020620 --env smb_android

        obj = {}

        

        if isinstance(wireType,ArgoFieldWireType):
            return ArgoMessageDecoder.decodeTypeData(wireType.type,dataDecoder)
        
        if isinstance(wireType,ArgoRecordWireType):
            for key,value in wireType.fields.items():                             
                value = ArgoMessageDecoder.decodeTypeData(value,dataDecoder)                
                if value is not None:
                    obj[key] = value

                                
            return obj
        
        if isinstance(wireType, ArgoScalarWireType):
            length = dataDecoder.blockReader.tryReadLength()

            if length==None:
                return None
            
            if length==-2:                
                dataDecoder.blockReader.readLength()
                return None
            if wireType.type==ArgoScalarWireType.BOOLEAN:
                return dataDecoder.decodeBoolean()
            if wireType.type==ArgoScalarWireType.STRING:
                return dataDecoder.decodeString()
            if wireType.type==ArgoScalarWireType.VARINT:
                return dataDecoder.decodeVarInt()

        if isinstance(wireType, ArgoBlockWireType):
            length = dataDecoder.blockReader.tryReadLength()
            if length==None:
                return None            
            if length==-2:
                return None
            else:
                return dataDecoder.decodeBlock(wireType)
        
        if isinstance(wireType, ArgoArrayWireType):
            arr = []
            length = dataDecoder.blockReader.tryReadLength()
            if length==None:
                return None
            if length==-2:
                #length = dataDecoder.blockReader.readLength()
                return arr
            else:
                length = dataDecoder.blockReader.readLength()


            #length = dataDecoder.blockReader.readLength()

            for i in range(0,length):
                arr.append(ArgoMessageDecoder.decodeTypeData(wireType.type, dataDecoder))
            return arr
        
        if isinstance(wireType, ArgoNullableWireType):
            typeId = dataDecoder.blockReader.tryReadLength()

            if typeId in [-1,-2,-3,0] :
                dataDecoder.blockReader.readLength()

            if typeId==-1:
                return None #NullBlock
            elif typeId==-3:
                return "ERROR"
            elif typeId==-2:
                return None
            else:
                return ArgoMessageDecoder.decodeTypeData(wireType.inner,dataDecoder)
            
        return None           




