
from  zargo.exception.data_exception import DataException
from  zargo.wiretype.scalar import ArgoScalarWireType
from  zargo.block import *

class ArgoBlockData(object):
    
    def __init__(self,wireType,header,data):
        self.block = None
        self.wireType = wireType
        if not header.inlineEverything:
            if not wireType.wireType.type==ArgoScalarWireType.BOOLEAN:
                if wireType.dedupe and not header.hasUserFlags :
                    if data is not None:
                        self.block = DedupeBlock(header,data)
                        return
                    raise DataException(-2,"MISSING DATA")                                            
                elif data is not None:
                    self.block = NormalBlock(header,data)
                else:
                    raise DataException(-2,"MISSING DATA")                                            
                        
        if data is None:
            self.block = InlineBlock(header)            

    def getVarInt(self,reader):
        
        if self.wireType.wireType.type==ArgoScalarWireType.VARINT:
            if isinstance(self.block, NormalBlock):
                length = self.block.reader.readVarLength()
                return length

    def getBoolean(self,reader):        
        if self.wireType.wireType.type==ArgoScalarWireType.BOOLEAN:
            #value = reader.readLength()
            value = reader.tryReadLength()            
            if value==1:
                reader.readLength()
                return True
            elif value==0:
                reader.readLength()
                return False
            
            return False
            #raise DataException(-2,"BOOLEAN VALUE ERROR")
        
    def getBytes(self, reader):
        if self.wireType.wireType.type==ArgoScalarWireType.BYTES:
            if isinstance(self.block, DedupeBlock):
                block = reader.readBlock()
                if block is not None:
                    if isinstance(block, BackReferenceBlock):
                        index = block.index
                        cache = self.block.cache
                        if index < len(cache):
                            bytes = cache[int(index)]
                            return bytes
                        else:
                            raise DataException(-4,"INDEX ERROR")
                        
                    elif isinstance(block, LengthBlock):
                        length = block.length
                        bytes = self.block.reader.readBytes(length)
                        self.block.cache.append(bytes)
                        return bytes
                    
            elif isinstance(self.block, InlineBlock):
                    length = reader.readLength()
                    return  reader.readBytes(length)                                  

            elif isinstance(self.block, NormalBlock):
                    length = reader.readLength()
                    return self.block.reader.readBytes(length)

            else:
                raise NotImplementedError("Unsupported block type.")


    def getString(self, reader):
        
        if self.wireType.wireType.type==ArgoScalarWireType.STRING:
            if isinstance(self.block, DedupeBlock):
                block = reader.readBlock()
                if block is not None:
                    if isinstance(block, BackReferenceBlock):
                        index = block.index
                        cache = self.block.cache
                        if index < len(cache):
                            str_block = cache[int(index)]
                            if isinstance(str_block, str):
                                return str_block
                            else:
                                raise DataException(-3,"INVALID DATA")
                        else:
                            return ""
                            #raise DataException(-4,"INDEX ERROR")

                    elif isinstance(block, LengthBlock):
                        length = block.length                        
                        obj = self.block.reader.readBytes(length)
                        decoded_str = obj.decode('utf-8')  # Assuming UTF-8 encoding
                        self.block.cache.append(decoded_str)
                        return decoded_str
                    
            elif isinstance(self.block, InlineBlock):
                block = reader.readBlock()
                if block is not None:
                    return str(block)                                        

            elif isinstance(self.block, NormalBlock):
                block = reader.readBlock()
                if block is not None:
                    return str(block)

            else:
                raise NotImplementedError("Unsupported block type.")

        raise DataException(-5,"WIRETYPE ERROR")

    def getData(self,reader):

        if self.wireType.wireType.type==ArgoScalarWireType.STRING:
            return self.getString(reader)

        if self.wireType.wireType.type==ArgoScalarWireType.BYTES:
            return self.getBytes(reader)

        if self.wireType.wireType.type==ArgoScalarWireType.BOOLEAN:
            return self.getBoolean(reader)

        if self.wireType.wireType.type==ArgoScalarWireType.FLOAT64:
            return self.getFloat64(reader)
        
        if self.wireType.wireType.type==ArgoScalarWireType.VARINT:
            return self.getVarInt(reader)
        
        return None





    



