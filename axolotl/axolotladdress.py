class AxolotlAddress:
    def __init__(self, name):
        self.name = name        

    def getName(self):
        return self.name

    def __str__(self):
        return f"{self.name}"

    def __eq__(self, other):
        if other is None:
            return False

        if other.__class__ != AxolotlAddress:
            return False

        return self.name == other.getName() 

    def __hash__(self):
        return hash(self.name)
