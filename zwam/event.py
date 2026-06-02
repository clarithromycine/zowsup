from typing import Any, Optional, Dict, List, Tuple, Union, Callable

class Event:    
    
    def __init__(self, tag: int = None):
        self.tag = tag if tag is not None else 0
        self.event_value = []
    
    def get_tag(self) -> int:
        return self.tag
    
    def get_event_value(self) -> list:
        return self.event_value
    
    def add_event_value(self, record) -> None:
        self.event_value.append(record)
    
    def set_tag(self, tag: int) -> None:
        self.tag = tag
    
    def __str__(self) -> str:
        string_builder = []
        string_builder.append("{ \nWamEvent: tag=")
        string_builder.append(str(self.tag))
        string_builder.append("\n")
        string_builder.append("Records: \n")
        
        for record in self.event_value:
            string_builder.append(str(record))
            string_builder.append("\n")
        
        string_builder.append("\n}")
        return "".join(string_builder)
