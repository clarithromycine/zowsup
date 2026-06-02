# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# For more information, please refer to <http://unlicense.org/>

import struct
import select
from .mcs import *
import logging
import time
import threading
import socket
import ssl

try:
    FileExistsError
except NameError:
    FileExistsError = OSError
    FileNotFoundError = IOError

log = logging.getLogger("push_receiver")


class PushReceiver:
    READ_TIMEOUT_SECS = 60 * 60
    MIN_RESET_INTERVAL_SECS = 5 * 60
    MAX_SILENT_INTERVAL_SECS = 60 * 60
    MCS_VERSION = 41

    PACKET_BY_TAG = [
        HeartbeatPing,
        HeartbeatAck,
        LoginRequest,
        LoginResponse,
        Close,
        "MessageStanza",
        "PresenceStanza",
        IqStanza,
        DataMessageStanza,
        "BatchPresenceStanza",
        StreamErrorStanza,
        "HttpRequest",
        "HttpResponse",
        "BindAccountRequest",
        "BindAccountResponse",
        "TalkMetadata"
    ]

    last_reset = 0

    def __init__(self, credentials, received_persistent_ids=None):
        """
    initializes the receiver

    credentials: credentials object returned by register()
    received_persistent_ids: any persistent id's you already received.
                             array of strings
    """

        if received_persistent_ids is None:
            received_persistent_ids = []
        self.credentials = credentials
        self.persistent_ids = received_persistent_ids
        self.time_last_message_received = time.time()

    def __del__(self):
        self.checkin_thread.cancel()
        self.__close_socket()

    def __read(self, size):
        buf = b''
        while len(buf) < size:
            buf += self.socket.recv(size - len(buf))
        return buf

    # protobuf variable length integers are encoded in base 128
    # each byte contains 7 bits of the integer and the msb is set if there's
    # more. pretty simple to implement

    def __read_varint32(self):
        res = 0
        shift = 0
        while True:
            b, = struct.unpack("B", self.__read(1))
            res |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                break
            shift += 7
        return res

    def __encode_varint32(self, x):
        res = bytearray([])
        while x != 0:
            b = (x & 0x7F)
            x >>= 7
            if x != 0:
                b |= 0x80
            res.append(b)
        return bytes(res)

    def __send(self, packet):
        header = bytearray([self.MCS_VERSION, self.PACKET_BY_TAG.index(type(packet))])
        log.debug(f'Packet to seErrornd:\n{packet}')
        payload = packet.SerializeToString()
        buf = bytes(header) + self.__encode_varint32(len(payload)) + payload
        n = len(buf)
        total = 0
        while total < n:
            sent = self.socket.send(buf[total:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            total += sent

    def __recv(self, first=False):
        try:
            readable, _, _ = select.select([self.socket, ], [], [], self.READ_TIMEOUT_SECS)
            if len(readable) == 0:
                log.debug("Select read timeout")
                return None
        except select.error as e:
            log.debug(f"Select error: {e}")
            return None
        try:
            if first:
                version, tag = struct.unpack("BB", self.__read(2))
                log.debug("version {}".format(version))
                if version < self.MCS_VERSION and version != 38:
                    raise RuntimeError("protocol version {} unsupported".format(version))
            else:
                tag, = struct.unpack("B", self.__read(1))
            size = self.__read_varint32()
        except OSError as e:
            log.debug(f"Read error: {e}")
            return None
        log.debug("Received message with tag {} ({}), size {}".format(tag, self.PACKET_BY_TAG[tag], size))
        self.time_last_message_received = time.time()
        if size >= 0:
            buf = self.__read(size)
            payload = self.PACKET_BY_TAG[tag]()
            payload.parse(buf)            
            log.debug(f'Receive payload:\n{payload}')
            return payload
        return None

    def __app_data_by_key(self, p, key, blow_shit_up=True):
        for x in p.app_data:
            if x.key == key:
                return x.value
        if blow_shit_up:
            raise RuntimeError("couldn't find in app_data {}".format(key))
        return None

    def __open(self):
        HOST = "mtalk.google.com"
        context = ssl.create_default_context()
        sock = socket.create_connection((HOST, 5228))
        self.socket = context.wrap_socket(sock, server_hostname=HOST)
        log.debug("connected to ssl socket")

    def __login(self):
        self.__open()
        android_id = self.credentials["gcm"]["androidId"]
        req = LoginRequest()
        req.adaptive_heartbeat = False
        req.auth_service = 2
        req.auth_token = self.credentials["gcm"]["securityToken"]
        req.id = "chrome-98.0.3234.0"
        req.domain = "mcs.android.com"
        req.device_id = "android-%x" % int(android_id)
        req.network_type = 1
        req.resource = android_id
        req.user = android_id
        req.use_rmq2 = True
        setting = Setting()
        setting.name = "new_vc"
        setting.value = "1"
        req.setting.append(setting)
        req.received_persistent_id.extend(self.persistent_ids)
        self.__send(req)
        login_response = self.__recv(first=True)
        log.info(f'Received login response:\n{login_response}')

    def __reset(self):
        now = time.time()
        time_since_last_reset = now - self.last_reset
        if time_since_last_reset < self.MIN_RESET_INTERVAL_SECS:
            log.debug(f"{time_since_last_reset}s since last reset attempt.")
            time.sleep(self.MIN_RESET_INTERVAL_SECS - time_since_last_reset)
        self.last_reset = now
        log.debug("Reestablishing connection")
        self.__close_socket()
        self.__login()

    def __close_socket(self):
        try:
            self.socket.shutdown(2)
            self.socket.close()
        except OSError as e:
            log.debug(f"Unable to close connection {e}")

    def __handle_data_message(self, p, callback, obj):

        data = {}

        for elem in p.app_data:
            data[elem.key] = elem.value

        log.info(f'Received data message {p.persistent_id}: {data}')
        callback(obj, data, p)
        return p.persistent_id

    def __handle_ping(self, p):
        log.debug(
            f'Responding to ping: Stream ID: {p.stream_id}, Last: {p.last_stream_id_received}, Status: {p.status}')
        req = HeartbeatAck()
        req.stream_id = p.stream_id + 1
        req.last_stream_id_received = p.stream_id
        req.status = p.status
        self.__send(req)

    def __status_check(self):
        time_since_last_message = time.time() - self.time_last_message_received
        if time_since_last_message > self.MAX_SILENT_INTERVAL_SECS:
            log.info(f'No communications received in {time_since_last_message}s.  Resetting connection.')
            self.__close_socket()
            time_since_last_message = 0
        expected_timeout = 1 + self.MAX_SILENT_INTERVAL_SECS - time_since_last_message
        self.checkin_thread = threading.Timer(expected_timeout, self.__status_check)
        self.checkin_thread.start()        

    def listen(self, callback, obj=None):
        """
    listens for push notifications

    callback(obj, notification, data_message): called on notifications
    obj: optional arbitrary value passed to callback
    """
        self.__login()
        self.__status_check()
        while True:
            try:
                p = self.__recv()
                if type(p) is DataMessageStanza:
                    self.persistent_ids.append(self.__handle_data_message(p, callback, obj))
                elif type(p) is HeartbeatPing:
                    self.__handle_ping(p)
                elif p is None or type(p) is Close:
                    self.__reset()
                else:
                    log.debug(f'Unexpected message type {type(p)}.')
            except ConnectionResetError:
                log.debug("Connection Reset: Reconnecting")
                self.__login()
