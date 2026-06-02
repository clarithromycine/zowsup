"""
w:stats encoding/decoding module
"""

import base64
import io
import logging
from typing import List, Optional

from .event import Event
from .record import Record
from .wam_output_stream import WAMOutputstream
from .proto_descriptor import get_descriptor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Wam:    
    
    @staticmethod
    def deserializer(stats: str) -> dict:
        # Store WAM events
        event = Event()
        
        try:
            # Decode base64 stats
            data = base64.b64decode(stats)
        except Exception as e:
            logger.error(f"Base64 decoding error: {e}")
            raise ValueError(f"Invalid base64 encoding: {e}")
        
        # Create BytesIO buffer from data (skip first 8 bytes)
        buffer = io.BytesIO(data[8:])
        
        # Store events
        event_list: List[Event] = []
        
        # Store default parameters
        record_list: List[Record] = []
        
        # Record builder (simplified dict)
        record_builder = {
            'fields': {},
            'events': []
        }

        record = None
        
        while True:
            if buffer.tell() >= len(buffer.getvalue()):
                break                
            try:                
                record = WAMOutputstream.byte_buffer_to_record(buffer)

                channel = record.channel
                
                if channel == 0:
                    # Base parameter, not event content
                    record_list.append(record)
                    continue
                elif channel == 1:
                    # New event marker
                    if event.get_event_value():
                        event_list.append(event)
                    event = Event(record.tag)
                    continue
                elif channel == 2:
                    # Event value
                    event.add_event_value(record)
                    continue
                else:
                    logger.error(f"Invalid WAM channel value: {channel}")
                    
            except Exception as e:
                logger.error(f"WAM log decoding error: {e}")
                break
                
        # Add last event if it has values
        if event.get_event_value():
            event_list.append(event)
                
        # Get proto descriptor for field name lookups
        descriptor = get_descriptor()
        record_field_names = descriptor.get_record_field_names()
        event_field_names = descriptor.get_event_field_names()
        event_field_types = descriptor.get_event_field_types()
        
        # Track unresolved event names
        unresolved_events = set()
        
        # Process base parameters
        for r in record_list:
            tag = r.tag
            value = r.get_protobuf_value()            
            if value is not None:
                # Get the field name from proto descriptor
                field_name = record_field_names.get(tag, f"field_{tag}")
                record_builder['fields'][field_name] = {
                    'tag': tag,
                    'value': value
                }
        
        # Process WAM events
        for e in event_list:
            tag = e.get_tag()
            event_name = event_field_names.get(tag, None)
            event_message_type = event_field_types.get(tag)
            
            # Track unresolved events
            if event_name is None:
                unresolved_events.add(tag)
                event_name = f"WamEvent_{tag}"
                # If we have a message type, use it; otherwise use the fallback
                if event_message_type:
                    event_name = event_message_type
            
            event_data = {
                'tag': tag,
                'name': event_name,
                'message_type': event_message_type,
                'fields': {}
            }
            
            for r in e.get_event_value():
                event_tag = r.tag
                value = r.get_protobuf_value()
                if value is not None:
                    # Try to get the field name from the event descriptor
                    field_descriptor = descriptor.get_all_fields(event_name)
                    if not field_descriptor and event_message_type:
                        # Try with the message type name
                        field_descriptor = descriptor.get_all_fields(event_message_type)
                    
                    field_name = field_descriptor.get(event_tag, f"field_{event_tag}")
                    event_data['fields'][field_name] = {
                        'tag': event_tag,
                        'value': value
                    }
            
            record_builder['events'].append(event_data)
        
        # Add unresolved events list to the result
        if unresolved_events:
            record_builder['unresolved_event_tags'] = sorted(list(unresolved_events))
        
        return record_builder
    
    @staticmethod
    def serialize(wam_record: dict) -> bytes:

        wam = WAMOutputstream()
        
        # Serialize base fields (channel 0)
        if 'fields' in wam_record:
            for field_tag, field_value in wam_record['fields'].items():
                wam.serialize(0, field_tag, field_value)
        
        # Serialize events (channels 1 and 2)
        if 'events' in wam_record:
            for event_data in wam_record['events']:
                event_tag = event_data.get('tag', 0)
                
                # Write event marker (channel 1)
                wam.serialize(1, event_tag, -1)
                
                # Write event fields (channel 2)
                if 'fields' in event_data:
                    for field_tag, field_value in event_data['fields'].items():
                        wam.serialize(2, field_tag, field_value)
        
        # Get result bytes
        byte_buffer = wam.wa_byte_array_output_stream.get_byte_buffer()
        result = byte_buffer['data'][:wam.wa_byte_array_output_stream.size()]
        
        return result



