from zargo.exception.data_exception import DataException

class DataReader() :

    def __init__(self,data):
        self.data = data
        self.currentIndex = 0

    
    def getCurrentIndex(self):
        return self.currentIndex
    
    def setCurrentIndex(self,index):
        self.currentIndex = index

    def getDataLength(self):
        return len(self.data)
    
    def readByte(self):
        b = self.data[self.currentIndex]
        self.currentIndex+=1
        return b
    
    def readBytes(self,length):

        if length<0 :
            raise DataException(-1,"LENGTH IS OUT OF BOUND")

        endIndex = self.currentIndex+length        
        if endIndex > len(self.data):
            raise DataException(-1,"NOT ENOUGH DATA")
        
        ba = self.data[self.currentIndex:endIndex]
        self.currentIndex = endIndex
        return ba

    def readVarLength(self):    
        value = 0
        shift = 0
        while True:
            try:
                b = self.readByte()
                tempValue = b & 0xFF

                # Check if the shift is valid
                if shift < 64:
                    value |= (tempValue & 0x7F) << shift
                    shift += 7
                    # If the most significant bit is not set, decoding is complete
                    if (tempValue & 0x80) == 0:
                        # Decode ZigZag encoding
                        decodedValue = (value >> 1) ^ -(value & 1)                        
                        return decodedValue
                else:
                    #/OVERFLOW IN VARLENGTH DECODING
                    return None                    
                
            except IndexError:
                #UNEXPECTED END OF DATA
                return None                
    