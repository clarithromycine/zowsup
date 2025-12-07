


class ArgoFieldWireType :

    def  __init__(self,type,name,omittable):
        self.name = name
        self.type = type
        self.omittable = omittable

    def __str__(self):
        return "ArgoFieldWireType(name=%s, type=%s, omittable=%s)" % (self.name,self.type,str(self.omittable))
    




    