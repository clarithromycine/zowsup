from typing import Dict, Optional, Tuple
import os
import re
from typing import Any

try:
    from proto import wam_pb2    
    HAS_PB2 = True
except (ImportError, ModuleNotFoundError):    
    HAS_PB2 = False


class ProtoDescriptor:

    def __init__(self, mode: Optional[str] = None):
        self.messages: Dict[str, Dict[int, Tuple[str, Optional[str]]]] = {}
        self.mode = (mode or os.environ.get('PROTO_DESCRIPTOR_MODE', 'auto')).lower()
        self._load_proto_descriptors()

    def _load_proto_descriptors(self) -> None:
        if self.mode == 'pb2' or (self.mode == 'auto' and HAS_PB2):
            # try pb2 first
            try:
                self._load_from_pb2(wam_pb2.DESCRIPTOR.message_types_by_name)
                return
            except Exception:
                # fall through to text parser
                pass

        if self.mode == 'text' or self.mode == 'auto':
            self._load_from_proto_file()

    def _load_from_pb2(self, message_types: Dict[str, Any]) -> None:
        for message_name, descriptor in message_types.items():
            if message_name not in self.messages:
                self.messages[message_name] = {}

            # Iterate through fields in the message descriptor
            for field in descriptor.fields:
                field_number = field.number
                field_name = field.name

                # Determine if this is a message type
                message_type = None
                if getattr(field, 'message_type', None) is not None:
                    message_type = field.message_type.name

                # Store both name and type info
                self.messages[message_name][field_number] = (field_name, message_type)

    def _load_from_proto_file(self) -> None:
        proto_file = os.path.join(os.path.dirname(__file__),'../proto', 'wam.proto')
        if not os.path.exists(proto_file):
            print(f"Warning: Proto file not found at {proto_file}")
            return
                

        try:
            with open(proto_file, 'r', encoding='utf-8') as f:
                content = f.read()
            self._parse_proto(content)
        except Exception as e:
            print(f"Warning: Failed to parse proto file: {e}")

    def _parse_proto(self, content: str) -> None:
        # Split into message blocks with nested braces support
        message_pattern = r'message\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        matches = re.finditer(message_pattern, content, re.DOTALL)

        for match in matches:
            message_name = match.group(1)
            message_body = match.group(2)

            # Extract field definitions with type information
            # Matches: optional|repeated TYPE field_name = number;
            field_pattern = r'(?:optional|repeated)\s+(\w+)\s+(\w+)\s*=\s*(\d+)'
            field_matches = re.finditer(field_pattern, message_body)

            if message_name not in self.messages:
                self.messages[message_name] = {}

            for field_match in field_matches:
                field_type = field_match.group(1)
                field_name = field_match.group(2)
                field_number = int(field_match.group(3))

                # Determine if this is a message type (starts with capital letter)
                message_type = None
                if field_type and field_type[0].isupper() and field_type not in ['String']:
                    message_type = field_type

                # Store both name and type info
                self.messages[message_name][field_number] = (field_name, message_type)
    
    def get_field_name(self, message_name: str, field_number: int) -> Optional[str]:
        if message_name in self.messages:
            field_info = self.messages[message_name].get(field_number)
            if field_info:
                return field_info[0]
        return None

    def get_field_type(self, message_name: str, field_number: int) -> Optional[str]:
        if message_name in self.messages:
            field_info = self.messages[message_name].get(field_number)
            if field_info:
                return field_info[1]
        return None

    def get_all_fields(self, message_name: str) -> Dict[int, str]:
        if message_name in self.messages:
            return {k: v[0] for k, v in self.messages[message_name].items()}
        return {}

    def get_event_field_names(self) -> Dict[int, str]:
        return self.get_all_fields('WamEvent')

    def get_event_field_types(self) -> Dict[int, Optional[str]]:
        if 'WamEvent' in self.messages:
            return {k: v[1] for k, v in self.messages['WamEvent'].items()}
        return {}

    def get_record_field_names(self) -> Dict[int, str]:
        return self.get_all_fields('WamRecord')


# Global descriptor instances keyed by mode
_descriptor_instances: Dict[str, ProtoDescriptor] = {}


def get_descriptor(mode: Optional[str] = None) -> ProtoDescriptor:
    selected = (mode or os.environ.get('PROTO_DESCRIPTOR_MODE', 'auto')).lower()
    # Normalize
    if selected not in ('auto', 'pb2', 'text'):
        selected = 'auto'

    if selected not in _descriptor_instances:
        _descriptor_instances[selected] = ProtoDescriptor(mode=selected)

    return _descriptor_instances[selected]
