from axolotl.state.axolotlstore import AxolotlStore
from .liteidentitykeystore import LiteIdentityKeyStore
from .liteprekeystore import LitePreKeyStore
from .litesessionstore import LiteSessionStore
from .litesignedprekeystore import LiteSignedPreKeyStore
from .litesenderkeystore import LiteSenderKeyStore
from .litepollstore import LitePollStore
from .liteappstatekeystore import LiteAppStateStore
from .litecontactstore import LiteContactStore
from .litebroadcaststore import LiteBroadcastStore
import sqlite3
from typing import Any, Optional, Dict, List, Tuple



class LiteAxolotlStore(AxolotlStore):
    def __init__(self, db) -> None:
        conn = sqlite3.connect(db, check_same_thread=False)
        
        conn.text_factory = bytes
        self._db = db
        self.dbConn = conn
        self.identityKeyStore = LiteIdentityKeyStore(conn)
        self.preKeyStore = LitePreKeyStore(conn)
        self.signedPreKeyStore = LiteSignedPreKeyStore(conn)
        self.sessionStore = LiteSessionStore(conn)
        self.senderKeyStore = LiteSenderKeyStore(conn)
        self.pollStore = LitePollStore(conn)        
        self.appStateStore = LiteAppStateStore(conn)
        self.contactStore = LiteContactStore(conn)
        self.broadcastStore = LiteBroadcastStore(conn)        

    def __str__(self) -> str:
        return self._db

    def getIdentityKeyPair(self) -> Any:
        return self.identityKeyStore.getIdentityKeyPair()

    def getLocalRegistrationId(self) -> Any:
        return self.identityKeyStore.getLocalRegistrationId()

    def saveIdentity(self, recipientId, recipientType,deviceId,identityKey) -> Any:
        self.identityKeyStore.saveIdentity(recipientId,recipientType,deviceId,identityKey)

    def isTrustedIdentity(self, recipientId,recipientType,deviceId, identityKey) -> Any:
        return self.identityKeyStore.isTrustedIdentity(recipientId,recipientType,deviceId, identityKey)

    def loadPreKey(self, preKeyId) -> Any:
        return self.preKeyStore.loadPreKey(preKeyId)

    def loadPendingPreKeys(self) -> Any:
        return self.preKeyStore.loadPendingPreKeys()

    def storePreKey(self, preKeyId, preKeyRecord) -> Any:
        self.preKeyStore.storePreKey(preKeyId, preKeyRecord)

    def containsPreKey(self, preKeyId) -> Any:
        return self.preKeyStore.containsPreKey(preKeyId)

    def removePreKey(self, preKeyId) -> Any:
        self.preKeyStore.removePreKey(preKeyId)
        
    def removeAllPreKeys(self) -> Any:
        self.preKeyStore.clear()        

    def loadSession(self, recipientId, recipientType,deviceId) -> Any:
        return self.sessionStore.loadSession(recipientId, recipientType, deviceId)

    def getSubDeviceSessions(self, account) -> Any:
        return self.sessionStore.getSubDeviceSessions(account)

    def storeSession(self, recipientId, recipientType,deviceId, sessionRecord) -> Any:
        self.sessionStore.storeSession(recipientId, recipientType, deviceId,sessionRecord)

    def containsSession(self, recipientId,recipientType,deviceId) -> Any:
        return self.sessionStore.containsSession(recipientId,recipientType, deviceId)

    def deleteSession(self, recipientId, recipientType,deviceId) -> Any:
        self.sessionStore.deleteSession(recipientId, recipientType,deviceId)

    def deleteAllSessions(self, recipientId) -> Any:
        self.sessionStore.deleteAllSessions(recipientId)

    def loadSignedPreKey(self, signedPreKeyId) -> Any:
        return self.signedPreKeyStore.loadSignedPreKey(signedPreKeyId)

    def loadSignedPreKeys(self) -> Any:
        return self.signedPreKeyStore.loadSignedPreKeys()

    def storeSignedPreKey(self, signedPreKeyId, signedPreKeyRecord) -> Any:
        self.signedPreKeyStore.storeSignedPreKey(signedPreKeyId, signedPreKeyRecord)

    def containsSignedPreKey(self, signedPreKeyId) -> Any:
        return self.signedPreKeyStore.containsSignedPreKey(signedPreKeyId)

    def removeSignedPreKey(self, signedPreKeyId) -> Any:
        self.signedPreKeyStore.removeSignedPreKey(signedPreKeyId)

    def loadSenderKey(self, senderKeyName) -> Any:
        return self.senderKeyStore.loadSenderKey(senderKeyName)

    def storeSenderKey(self, senderKeyName, senderKeyRecord) -> Any:
        self.senderKeyStore.storeSenderKey(senderKeyName, senderKeyRecord)

    def getAllAccounts(self,recipientId) -> Any:
        return self.sessionStore.getAllAccounts(recipientId)
    
    def addAppStateKeys(self,keys) -> Any:
        return self.appStateStore.addAppStateKeys(keys)

    def getOneAppStateKey(self) -> Any:
        return self.appStateStore.getOneAppStateKey()

    def getAppStateKey(self,key_id) -> Any:
        return self.appStateStore.getAppStateKey(key_id)

    def removeAppStateKey(self,key_id) -> Any:
        return self.appStateStore.deleteAppStateKey(key_id)
    
    def updateContact(self,jid,lid,name=None) -> Any:
        return self.contactStore.updateContact(jid=jid,lid=lid,name=name)
        
    def removeContact(self,jid) -> Any:
        return self.contactStore.removeContact(jid)
    
    def getAllContact(self) -> Any:
        return self.contactStore.getAllContact()
    
    def findContact(self,jid) -> Any:
        

        if jid.endswith("lid"):
            return self.contactStore.findContact(jid=None,lid = jid)
        else:
            return self.contactStore.findContact(jid = jid,lid=None)
        
    
    def getContact(self,jid) -> Any:
        if jid.endswith("lid"):
            return self.contactStore.getContact(jid=None,lid = jid)
        else:
            return self.contactStore.getContact(jid = jid,lid=None)

    
    def addBroadcast(self,jids,senderJid,name=None) -> Any:
        return self.broadcastStore.addBroadcast(jids,senderJid,name)
    
    def findParticipantsByBcid(self,bcid) -> Any:
        return self.broadcastStore.findParticipantsByBcid(bcid)
    
    def updateTctoken(self,jid, lid, tctoken, tctoken_ts) -> Any:
        return self.contactStore.updateTctoken(jid=jid, lid=lid, tctoken=tctoken, tctoken_ts=tctoken_ts)
    
    def getTctoken(self,jid=None) -> Any:        

        if jid.endswith("lid"):
            return self.contactStore.getTctoken(lid=jid)    
        else:
            return self.contactStore.getTctoken(jid=jid)    

