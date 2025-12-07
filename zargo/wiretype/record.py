


class ArgoRecordWireType :

    def  __init__(self,fields):
        self.fields = fields

    def __str__(self):        
        arr = []
        for key in self.fields:
            arr.append(key+"="+str(self.fields[key]))

        return "ArgoRecordWireType(fields=[%s])" % (', '.join(arr))
    

    

    

    
    
        


    