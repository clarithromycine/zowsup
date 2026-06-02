import hmac
from typing import Optional, Any, List, Dict, Union
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from proto import e2e_pb2

class PollUpdateAttributes:
    def __init__(self, msgid, creator_jid, voter_jid,options) -> None:

        self._msgid = msgid
        self._creator_jid = creator_jid        
        self._voter_jid = voter_jid
        self._options = options 

    def __str__(self):
        attrs = []        
        if self.msgid is not None:
            attrs.append(("msgid", self.msgid))
        if self.creator_jid is not None:
            attrs.append(("creator_jid", self.creator_jid))
        if self.voter_jid is not None:
            attrs.append(("voter_jid", self.voter_jid))       
        if self.options is not None:
            attrs.append(("options", self.options))                     

        return "[%s]" % " ".join(map(lambda item: "%s=%s" % item, attrs))

    @property
    def msgid(self) -> Any:
        return self._msgid

    @msgid.setter
    def msgid(self, value: Any) -> None:
        self._msgid = value

    @property
    def creator_jid(self) -> Any:
        return self._creator_jid

    @creator_jid.setter
    def creator_jid(self, value: Any) -> None:
        self._creator_jid = value


    @property
    def voter_jid(self) -> Any:
        return self._voter_jid

    @voter_jid.setter
    def voter_jid(self, value: Any) -> None:
        self._voter_jid = value

    @property
    def options(self) -> Any:
        return self._options

    @options.setter
    def options(self, value: Any) -> None:
        self._options = value       
    
    @staticmethod
    def get_options_from_encrypted_content(proto,from_jid,message_db): 

        msgId = proto.poll_creation_message_key.id
        creatorJid = proto.poll_creation_message_key.remote_jid
        voterJid = from_jid 

        sign = (msgId+creatorJid+voterJid+"Poll Vote").encode()+b"\x01"

        enc_key = message_db._store.pollStore.getPollEncKey(msgId)   

        if enc_key is None:
            return None

        key0 = hmac.new(bytearray(32),enc_key,hashlib.sha256).digest()

        decKey=hmac.new(key0,sign,hashlib.sha256).digest()
                                
        text_bytes = AESGCM(decKey).decrypt(proto.vote.enc_iv, proto.vote.enc_payload,  msgId.encode()+b"\x00"+voterJid.encode())

        m = e2e_pb2.Message.PollVoteMessage()
        m.ParseFromString(text_bytes)        
        result = []  
        result = message_db._store.pollStore.decryptOptions(msgId,m.selected_options)            

        return result