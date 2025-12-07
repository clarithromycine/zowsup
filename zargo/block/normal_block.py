from zargo.utils.data_reader import DataReader

class NormalBlock() :

    def __init__(self,header,blockData):
        self.header = header
        self.blockData = blockData
        self.reader = DataReader(blockData)        

    def __str__(self):
        return "NormalBlock(header=%s, data=%s)" % (self.header,self.blockData)

        
        

