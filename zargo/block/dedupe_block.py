from zargo.utils.data_reader import DataReader

class DedupeBlock() :

    def __init__(self,header,blockData):
        self.header = header
        self.blockData = blockData
        self.reader = DataReader(blockData)
        self.cache = []

    def __str__(self):
        return "LengthBlock(header=%s, data=%s)" % (self.header,self.blockData)

        
        

