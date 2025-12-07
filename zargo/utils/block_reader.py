from zargo.block.back_reference_block import BackReferenceBlock
from zargo.block.length_block import LengthBlock
from .data_reader import DataReader

class BlockReader() :

    def __init__(self,data):
        self.dataReader = DataReader(data)
            
        
    def tryReadLength(self):
        old = self.dataReader.getCurrentIndex()        
        length = self.dataReader.readVarLength()
        self.dataReader.setCurrentIndex(old)
        return length
    
    def readLength(self):
        return self.dataReader.readVarLength()        
    
    def readBlock(self):
        value = self.dataReader.readVarLength()
        if value < -3:
            adjValue = (-value) -4
            if adjValue >= 0 and adjValue < 4294967295 :
                return BackReferenceBlock(adjValue)
        else:
            return LengthBlock(value)
        

    def readBytes(self,length):
        return self.dataReader.readBytes(length)
        
        

