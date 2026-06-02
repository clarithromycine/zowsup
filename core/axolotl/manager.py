from axolotl.util.keyhelper import KeyHelper
from axolotl.identitykeypair import IdentityKeyPair
from axolotl.groups.senderkeyname import SenderKeyName
from axolotl.axolotladdress import AxolotlAddress
from axolotl.sessioncipher import SessionCipher
from axolotl.groups.groupcipher import GroupCipher
from axolotl.groups.groupsessionbuilder import GroupSessionBuilder
from axolotl.sessionbuilder import SessionBuilder
from axolotl.protocol.prekeywhispermessage import PreKeyWhisperMessage
from axolotl.protocol.whispermessage import WhisperMessage
from axolotl.state.prekeybundle import PreKeyBundle
from axolotl.untrustedidentityexception import UntrustedIdentityException
from axolotl.invalidmessageexception import InvalidMessageException
from axolotl.duplicatemessagexception import DuplicateMessageException
from axolotl.invalidkeyidexception import InvalidKeyIdException
from axolotl.nosessionexception import NoSessionException
from axolotl.protocol.senderkeydistributionmessage import SenderKeyDistributionMessage
from axolotl.state.axolotlstore import AxolotlStore
from ..axolotl.store.sqlite.liteaxolotlstore import LiteAxolotlStore
from ..axolotl import exceptions
import random
import logging
import sys
import base64
from ..common.tools import WATools

logger = logging.getLogger(__name__)


from typing import Optional, Any, List, Dict, Tuple
class AxolotlManager:

    COUNT_GEN_PREKEYS = 812
    THRESHOLD_REGEN = 10
    MAX_SIGNED_PREKEY_ID = 16777215

    def __init__(self, store: LiteAxolotlStore, username: str) -> None:
        """
        :param store:
        :type store: AxolotlStore
        :param username:
        :type username: str
        """
        self._username = username 
        self._store = store 
        self._identity = self._store.getIdentityKeyPair() # type: IdentityKeyPair
        self._registration_id = self._store.getLocalRegistrationId() # type: int | None

        assert self._registration_id is not None
        assert self._identity is not None

        self._group_session_builder = GroupSessionBuilder(self._store) # type: GroupSessionBuilder
        self._session_ciphers = {} # type: dict[str, SessionCipher]
        self._group_ciphers = {} # type: dict[str, GroupCipher]
        logger.debug(f"Initialized AxolotlManager [username={self._username}, db={store}]")


    @property
    def registration_id(self) -> Any:
        return self._registration_id

    @property
    def identity(self) -> Any:
        return self._identity
    
    def get_all_accounts(self,recipientId) -> Any:
        ret = self._store.getAllAccounts(recipientId)        
        return ret

    def level_prekeys(self, force=False) -> None:
        logger.debug("level_prekeys(force=%s)" % force)
        len_pending_prekeys = len(self._store.loadPendingPreKeys())
        logger.debug("len(pending_prekeys) = %d" % len_pending_prekeys)
        
        
        if force or len_pending_prekeys < self.THRESHOLD_REGEN:
            count_gen = self.COUNT_GEN_PREKEYS
            max_prekey_id = self._store.preKeyStore.loadMaxPreKeyId()
            logger.info("Generating %d prekeys, current max_prekey_id=%d" % (count_gen, max_prekey_id))
            prekeys = KeyHelper.generatePreKeys(max_prekey_id + 1, count_gen)
            logger.info("Storing %d prekeys" % len(prekeys))
            
            # Batch store prekeys for better performance (single database commit)
            prekey_records = [(key.getId(), key) for key in prekeys]
            self._store.preKeyStore.storePreKeyBatch(prekey_records)

            return prekeys
        
        
        return []


    def load_unsent_prekeys(self) -> Any:
        logger.debug("load_unsent_prekeys")
        unsent = self._store.preKeyStore.loadUnsentPendingPreKeys()
        if len(unsent) > 0:
            logger.info("Loaded %d unsent prekeys" % len(unsent))
        return unsent

    def set_prekeys_as_sent(self, prekeyIds) -> None:
        """
        :param prekeyIds:
        :type prekeyIds: list
        :return:
        :rtype:
        """
        logger.debug("set_prekeys_as_sent(prekeyIds=[%d prekeyIds])" % len(prekeyIds))
        self._store.preKeyStore.setAsSent([prekey.getId() for prekey in prekeyIds])

    def generate_signed_prekey(self) -> Any:
        logger.debug("generate_signed_prekey")
        latest_signed_prekey = self.load_latest_signed_prekey(generate=False)
        if latest_signed_prekey is not None:                        
            if latest_signed_prekey.getId() == self.MAX_SIGNED_PREKEY_ID:
                new_signed_prekey_id = (self.MAX_SIGNED_PREKEY_ID / 2) + 1
            else:
                new_signed_prekey_id = latest_signed_prekey.getId() + 1
        else:
            new_signed_prekey_id = random.randint(0,800)            
        signed_prekey = KeyHelper.generateSignedPreKey(self._identity, new_signed_prekey_id)
        self._store.storeSignedPreKey(signed_prekey.getId(), signed_prekey)
        return signed_prekey

    def load_latest_signed_prekey(self, generate=False) -> Any:
        logger.debug("load_latest_signed_prekey")
        signed_prekeys = self._store.loadSignedPreKeys()
        if len(signed_prekeys):
            return signed_prekeys[-1]

        return self.generate_signed_prekey() if generate else None
    
    def _get_session_cipher(self, recipientId,recipientType,deviceid=0):        
        key = "%s.%d:%d" % (recipientId,recipientType,deviceid)        
        logger.debug("get_session_cipher(username=%s)" % key)
        if key in self._session_ciphers:
            session_cipher = self._session_ciphers[key]
        else:                        
            session_cipher= SessionCipher(self._store, self._store, self._store, self._store, recipientId,recipientType,deviceid)
            self._session_ciphers[key] = session_cipher
        return session_cipher

    def _get_group_cipher(self, groupid, username):
        logger.debug(f"get_group_cipher(groupid={groupid}, username={username})")
        senderkeyname = SenderKeyName(groupid, AxolotlAddress(username, 0))
        if senderkeyname in self._group_ciphers:
            group_cipher = self._group_ciphers[senderkeyname]
        else:
            group_cipher = GroupCipher(self._store.senderKeyStore, senderkeyname)
            self._group_ciphers[senderkeyname] = group_cipher
        return group_cipher

    def _generate_random_padding(self):
        logger.debug("generate_random_padding")
        num = random.randint(1,255)
        return bytes(bytearray([num] * num))

    def _unpad(self, data):
        padding_byte = data[-1] if type(data[-1]) is int else ord(data[-1]) # bec inconsistent API?
        padding = padding_byte & 0xFF
        return data[:-padding]

    def encrypt(self, username, message):
        # to avoid the hassle of encoding issues and associated unnecessary crashes,
        # don't log the message content.
        # see https://github.com/tgalal/yowsup/issues/2732
        logger.debug("encrypt(username=%s, message=[omitted])" % username)
        """
        :param username:
        :type username: str
        :param data:
        :type data: bytes
        :return:
        :rtype:
        """
        recipientId,recipientType,deviceId = WATools.jidDecode(username)

        cipher = self._get_session_cipher(recipientId,recipientType,deviceId)        
        return cipher.encrypt(message + self._generate_random_padding())
    
    def decrypt_pkmsg(self, senderid, data, unpad) -> Any:
        logger.debug(f"decrypt_pkmsg(senderid={senderid}, data=(omitted), unpad={unpad})")
        pkmsg = PreKeyWhisperMessage(serialized=data)
        

        recipientId,recipientType,deviceId = WATools.jidDecode(senderid)        
        try:
            plaintext = self._get_session_cipher(recipientId,recipientType,deviceId).decryptPkmsg(pkmsg)
            return self._unpad(plaintext) if unpad else plaintext
        except NoSessionException:
            raise exceptions.NoSessionException()
        except InvalidKeyIdException:
            raise exceptions.InvalidKeyIdException()
        except InvalidMessageException:
            raise exceptions.InvalidMessageException()
        except DuplicateMessageException:
            raise exceptions.DuplicateMessageException()


    def decrypt_msg(self, senderid, data, unpad) -> Any:
        logger.debug(f"decrypt_msg(senderid={senderid}, data=[omitted], unpad={unpad})")
        msg = WhisperMessage(serialized=data)
        recipientId,recipientType,deviceId = WATools.jidDecode(senderid)

        try:
            plaintext = self._get_session_cipher(recipientId,recipientType,deviceId).decryptMsg(msg)

            return self._unpad(plaintext) if unpad else plaintext
        except NoSessionException:
            raise exceptions.NoSessionException()
        except InvalidKeyIdException:
            raise exceptions.InvalidKeyIdException()
        except InvalidMessageException:
            raise exceptions.InvalidMessageException()
        except DuplicateMessageException:
            raise exceptions.DuplicateMessageException()

    def group_encrypt(self, groupid, message):
        """
        :param groupid:
        :type groupid: str
        :param message:
        :type message: bytes
        :return:
        :rtype:
        """
        # to avoid the hassle of encoding issues and associated unnecessary crashes,
        # don't log the message content.
        # see https://github.com/tgalal/yowsup/issues/2732
        logger.debug("group_encrypt(groupid=%s, message=[omitted])" % groupid)
        group_cipher = self._get_group_cipher(groupid, self._username)
        return group_cipher.encrypt(message + self._generate_random_padding())

    def group_decrypt(self, groupid, participantid, data):
        logger.debug(f"group_decrypt(groupid={groupid}, participantid={participantid}, data=[omitted])")
        group_cipher = self._get_group_cipher(groupid, participantid)
        try:
            plaintext = group_cipher.decrypt(data)
            plaintext = self._unpad(plaintext)
            return plaintext
        except NoSessionException:
            raise exceptions.NoSessionException()
        except DuplicateMessageException:
            raise exceptions.DuplicateMessageException()
        except InvalidMessageException:
            raise exceptions.InvalidMessageException()

    def group_create_skmsg(self, groupid):
        logger.debug("group_create_skmsg(groupid=%s)" % groupid)
        senderKeyName = SenderKeyName(groupid, AxolotlAddress(self._username, 0))
        return self._group_session_builder.create(senderKeyName)

    def group_create_session(self, groupid, participantid, skmsgdata) -> None:
        """
        :param groupid:
        :type groupid: str
        :param participantid:
        :type participantid: str
        :param skmsgdata:
        :type skmsgdata: bytearray
        :return:
        :rtype:
        """
        logger.debug("group_create_session(groupid=%s, participantid=%s, skmsgdata=[omitted])"
                     % (groupid, participantid))
        senderKeyName = SenderKeyName(groupid, AxolotlAddress(participantid, 0))
        senderkeydistributionmessage = SenderKeyDistributionMessage(serialized=skmsgdata)
        self._group_session_builder.process(senderKeyName, senderkeydistributionmessage)

    def create_session(self, username, prekeybundle, autotrust=False) -> None:
        """
        :param username:
        :type username: str
        :param prekeybundle:
        :type prekeybundle: PreKeyBundle
        :return:
        :rtype:
        """
        logger.debug(f"create_session(username={username}, prekeybundle=[omitted], autotrust={autotrust})")
        
        recipientId,recipientType,deviceId = WATools.jidDecode(username)     

        session_builder = SessionBuilder(self._store, self._store, self._store, self._store, recipientId, recipientType,deviceId)        
        try:                                    
            session_builder.processPreKeyBundle(prekeybundle)                        
        except UntrustedIdentityException as ex:                        
            if autotrust:
                self.trust_identity(ex.getName(), ex.getIdentityKey())
            else:
                raise exceptions.UntrustedIdentityException(ex.getName(), ex.getIdentityKey())

    def session_exists(self, username):
        """
        :param username:
        :type username: str
        :return:
        :rtype:
        """        
        logger.debug("session_exists(%s)?" % username)
        recipientId,recipientType,deviceId = WATools.jidDecode(username)   
        return self._store.containsSession(recipientId, recipientType,deviceId)
    
    def get_all_session_usernames(self,username) -> Any:
        #获取一个用户名的所有关联终端的session，主要用来用来发消息
        logger.debug("get_all_session_usernames")
        return self._store.get_all_session_usernames(username)

    def load_senderkey(self, groupid) -> Any:
        logger.debug("load_senderkey(groupid=%s)" % groupid)
        senderkeyname = SenderKeyName(groupid, AxolotlAddress(self._username, 0))
        return self._store.loadSenderKey(senderkeyname)

    def trust_identity(self, account ,identitykey) -> None:
        logger.debug("trust_identity(account=%s, identitykey=[omitted])" % account)

        recipientId,recipientType,deviceid = WATools.jidDecode(account) 
        self._store.saveIdentity(recipientId,recipientType,deviceid,identitykey)
