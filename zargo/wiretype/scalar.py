
class ArgoScalarWireType :

    BOOLEAN = "ArgoScalarWireType.Boolean"
    BYTES = "ArgoScalarWireType.Bytes"
    FLOAT64 = "ArgoScalarWireType.Float64"
    STRING = "ArgoScalarWireType.String"
    VARINT = "ArgoScalarWireType.Varint"
    DESC = "ArgoScalarWireType.Desc"

    scalarTypeMap = {}

    def __init__(self,type):
        self.type = type

    def __str__(self):
        return self.type
    
    @staticmethod
    def getInstance(type):
        if type not in ArgoScalarWireType.scalarTypeMap:
            obj = ArgoScalarWireType(type)
            ArgoScalarWireType.scalarTypeMap[type] = obj
        
        return ArgoScalarWireType.scalarTypeMap[type]
    
  
    



    