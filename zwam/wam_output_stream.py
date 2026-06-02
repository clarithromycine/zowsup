
import struct
from typing import Optional, Union
import io

from .record import Record
from .wa_byte_array_output_stream import WAByteArrayOutputStream


class WAMOutputstream:    
    
    def __init__(self):        
        self.cur_index = -1
        self.a_01 = 0
        self.wa_byte_array_output_stream = WAByteArrayOutputStream()
    
    @staticmethod
    def write_long(value: int, output_stream: WAByteArrayOutputStream) -> int:
        if value == 0:
            return 1
        
        if value == 1:
            return 2
        
        # Write first byte
        output_stream.write_byte(value & 0xFF)
        
        if -0x80 <= value <= 0x7F:
            return 3
        
        # Write second byte
        output_stream.write_byte((value >> 8) & 0xFF)
        
        if -0x8000 <= value <= 0x7FFF:
            return 4
        
        # Write third and fourth bytes
        output_stream.write_byte((value >> 16) & 0xFF)
        output_stream.write_byte((value >> 24) & 0xFF)
        
        if -0x80000000 <= value <= 0x7FFFFFFF:
            return 5
        
        # Write remaining bytes for 64-bit value
        output_stream.write_byte((value >> 32) & 0xFF)
        output_stream.write_byte((value >> 40) & 0xFF)
        output_stream.write_byte((value >> 48) & 0xFF)
        output_stream.write_byte((value >> 56) & 0xFF)
        
        return 6
    
    @staticmethod
    def write_long_as_int(value: int, output_stream: WAByteArrayOutputStream) -> int:
        if 0 <= value <= 0xFFFFFFFF:
            output_stream.write_byte(value & 0xFF)
            
            if value <= 0xFF:
                return 1
            
            output_stream.write_byte((value >> 8) & 0xFF)
            
            if value <= 0xFFFF:
                return 2
            
            output_stream.write_byte((value >> 16) & 0xFF)
            output_stream.write_byte((value >> 24) & 0xFF)
            
            return 4
        
        raise ValueError("Value is not an unsigned integer")
    
    @staticmethod
    def byte_buffer_to_long(length: int, byte_buffer: io.BytesIO) -> int:
        
        if length <= 4:
            value = 0
            for i in range(length):
                byte = byte_buffer.read(1)
                if not byte:
                    break
                value |= (byte[0] & 0xFF) << (i << 3)
            
            return value
        
        raise ValueError("Invalid number of bytes")
    
    @staticmethod
    def byte_buffer_to_string(length: int, byte_buffer: io.BytesIO) -> str:


        data = byte_buffer.read(length)        
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                'utf-8', data, 0, len(data),
                f"UnsupportedEncoding: {e}"
            )
    
    @staticmethod
    def byte_buffer_to_record(byte_buffer: io.BytesIO) -> Record:

        # Set little-endian byte order        
        at = byte_buffer.tell()
        
        #print(byte_buffer.getvalue()[at:].hex())
        
        # Read record type byte
        record_type_byte = byte_buffer.read(1)                      
                
        if not record_type_byte:
            raise Exception("No data in buffer")
        
        record_type = record_type_byte[0]
        channel = record_type & 3        
                                
        if channel > 2:
            raise ValueError("Invalid record type")
        
        # Determine tag length
        flag = 1 if (record_type & 8) != 0 else 0


        tag = int(WAMOutputstream.byte_buffer_to_long(
            2 if flag == 1 else 1, byte_buffer
        ))
        
        
        # Get value type from upper nibble
        value_type = (record_type >> 4) & 0xF

        
        if value_type <= 10:
            try:
                if value_type == 0:
                    return Record(channel, tag, None)
                elif value_type == 1:
                    return Record(channel, tag, 0)
                elif value_type == 2:
                    return Record(channel, tag, 1)
                elif value_type == 3:
                    byte_val = byte_buffer.read(1)
                    return Record(channel, tag, byte_val[0] if byte_val else 0)
                elif value_type == 4:
                    short_bytes = byte_buffer.read(2)
                    if len(short_bytes) == 2:
                        return Record(channel, tag, struct.unpack('<h', short_bytes)[0])
                    return Record(channel, tag, 0)
                elif value_type == 5:
                    int_bytes = byte_buffer.read(4)
                    if len(int_bytes) == 4:
                        return Record(channel, tag, struct.unpack('<i', int_bytes)[0])
                    return Record(channel, tag, 0)
                elif value_type == 6:
                    long_bytes = byte_buffer.read(8)
                    if len(long_bytes) == 8:
                        return Record(channel, tag, struct.unpack('<q', long_bytes)[0])
                    return Record(channel, tag, 0)
                elif value_type == 7:
                    double_bytes = byte_buffer.read()
                    if len(double_bytes) == 8:
                        return Record(channel, tag, struct.unpack('<d', double_bytes)[0])
                    return Record(channel, tag, 0.0)
                elif value_type == 8:                                            
                    str_len = int(WAMOutputstream.byte_buffer_to_long(1, byte_buffer))    
                                                                     
                    return Record(channel, tag, WAMOutputstream.byte_buffer_to_string(str_len, byte_buffer))                                        
                elif value_type == 9:
                    str_len = int(WAMOutputstream.byte_buffer_to_long(2, byte_buffer))
                    return Record(channel, tag, WAMOutputstream.byte_buffer_to_string(str_len, byte_buffer))
                elif value_type == 10:
                    str_len = int(WAMOutputstream.byte_buffer_to_long(4, byte_buffer))
                    return Record(channel, tag, WAMOutputstream.byte_buffer_to_string(str_len, byte_buffer))
           
                
            except Exception as e:
                raise Exception(f"Failed to parse record value type {value_type}: {e}")
            
        
        #return None
        raise ValueError(f"Invalid value type {value_type} at position {at}, tag: {format(record_type, '02X ')}")
    
    def reset(self) -> None:

        self.wa_byte_array_output_stream = WAByteArrayOutputStream()
        self.cur_index = -1
        self.a_01 = 0
    
    def serialize(self, channel: int, tag: int, obj) -> None:

        self.cur_index = self.wa_byte_array_output_stream.size()
        flag = 0
        
        # Write placeholder for record type byte
        self.wa_byte_array_output_stream.write_byte(0)
        
        # Write tag
        tag_bytes = WAMOutputstream.write_long_as_int(tag, self.wa_byte_array_output_stream)
        
        if tag_bytes != 1:
            if tag_bytes == 2:
                flag = 1
            else:
                raise ValueError("Tag too big to fit in 2 bytes")
        
        v0 = 0
        
        if obj is None:
            v0 = 0
        elif isinstance(obj, bool):
            v0 = WAMOutputstream.write_long(
                1 if obj else 0,
                self.wa_byte_array_output_stream
            )
            current_bytes = bytearray(self.wa_byte_array_output_stream.get_bytes())
            current_bytes[self.cur_index] = channel | (v0 << 4 | flag << 3)
            self.wa_byte_array_output_stream = WAByteArrayOutputStream()
            self.wa_byte_array_output_stream.write(current_bytes)
            self.a_01 += 1
            return
        elif isinstance(obj, int):
            v0 = WAMOutputstream.write_long(obj, self.wa_byte_array_output_stream)
            current_bytes = bytearray(self.wa_byte_array_output_stream.get_bytes())
            current_bytes[self.cur_index] = channel | (v0 << 4 | flag << 3)
            self.wa_byte_array_output_stream = WAByteArrayOutputStream()
            self.wa_byte_array_output_stream.write(current_bytes)
            self.a_01 += 1
            return
        elif isinstance(obj, float):
            v4 = obj
            v2 = int(v4)
            
            if float(v2) == v4:
                v0 = WAMOutputstream.write_long(v2, self.wa_byte_array_output_stream)
            else:
                # Write double as 8 bytes
                double_bytes = struct.pack('<d', v4)
                self.wa_byte_array_output_stream.write(double_bytes)
                v0 = 7
                current_bytes = bytearray(self.wa_byte_array_output_stream.get_bytes())
                current_bytes[self.cur_index] = channel | (v0 << 4 | flag << 3)
                self.wa_byte_array_output_stream = WAByteArrayOutputStream()
                self.wa_byte_array_output_stream.write(current_bytes)
                self.a_01 += 1
                return
        elif isinstance(obj, str):
            try:
                v4_1 = obj.encode('utf-8')
            except UnicodeEncodeError as e:
                raise ValueError(f"UTF-8 encoding failed: {e}")
            
            max_len = 0x400  # 1024 bytes max
            if len(v4_1) > max_len:
                # Log warning (in Java it was Log.w)
                pass
            
            v2_1 = min(len(v4_1), max_len)
            v1_2 = WAMOutputstream.write_long_as_int(v2_1, self.wa_byte_array_output_stream)
            self.wa_byte_array_output_stream.write(v4_1[:v2_1])
            
            if v1_2 == 1:
                v0 = 8
            elif v1_2 == 2:
                v0 = 9
            elif v1_2 == 4:
                v0 = 10
            else:
                raise ValueError("Impossible tag length")
        else:
            raise TypeError(f"Expected bool, int, float, or str, got {type(obj).__name__}")
        
        current_bytes = bytearray(self.wa_byte_array_output_stream.get_bytes())
        current_bytes[self.cur_index] = channel | (v0 << 4 | flag << 3)
        self.wa_byte_array_output_stream = WAByteArrayOutputStream()
        self.wa_byte_array_output_stream.write(current_bytes)
        self.a_01 += 1
