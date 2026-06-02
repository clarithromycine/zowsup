
class Record:

    
    def __init__(self, channel: int, tag: int, value=None):

        self.channel = channel
        self.tag = tag
        self.value = value
    
    def __str__(self) -> str:

        string_builder = []
        string_builder.append("Record{\tchannel= ")
        string_builder.append(str(self.channel))
        string_builder.append("\ttag= ")
        string_builder.append(str(self.tag))
        string_builder.append(",\tvalue= ")
        string_builder.append(str(self.value))
        
        if self.value is not None:
            string_builder.append(": ")
            string_builder.append(type(self.value).__name__)
        
        return "".join(string_builder)
    
    def get_protobuf_value(self):

        if self.value is not None:
            if isinstance(self.value, str):
                return self.value
            elif isinstance(self.value, bytes):
                return int.from_bytes(self.value, byteorder='little')
            elif isinstance(self.value, int):
                return self.value
            elif isinstance(self.value, float):
                return int(self.value)
            else:
                return self.value
        
        return None
