from axolotl.state.identitykeystore import IdentityKeyStore
from axolotl.identitykey import IdentityKey
from axolotl.identitykeypair import IdentityKeyPair
from axolotl.util.keyhelper import KeyHelper
from axolotl.ecc.djbec import *
import sys
from typing import Any, Optional, Dict, List, Tuple


class LiteIdentityKeyStore(IdentityKeyStore):
    def __init__(self, dbConn) -> None:
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn
        dbConn.execute("CREATE TABLE IF NOT EXISTS identities (_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                       "recipient_id INTEGER,"
                       "recipient_type INTEGER NOT NULL DEFAULT 0, "
                       "device_id INTEGER,"
                       "registration_id INTEGER, public_key BLOB, private_key BLOB,"
                       "next_prekey_id INTEGER, timestamp INTEGER);")

        if self.getLocalRegistrationId() is None or self.getIdentityKeyPair() is None:
            identity = KeyHelper.generateIdentityKeyPair()
            registration_id = KeyHelper.generateRegistrationId(True)
            self._storeLocalData(registration_id, identity)

    def getIdentityKeyPair(self) -> Any:
        q = "SELECT public_key, private_key FROM identities WHERE recipient_id = -1"
        c = self.dbConn.cursor()
        c.execute(q)
        result = c.fetchone()

        if result:
            publicKey, privateKey = result
            return IdentityKeyPair(IdentityKey(DjbECPublicKey(publicKey[1:])), DjbECPrivateKey(privateKey))
        return None

    def getLocalRegistrationId(self) -> Any:
        q = "SELECT registration_id FROM identities WHERE recipient_id = -1"
        c = self.dbConn.cursor()
        c.execute(q)
        result = c.fetchone()
        return result[0] if result else None


    def _storeLocalData(self, registrationId, identityKeyPair,deviceid=0) -> Any:
        q = "INSERT INTO identities(recipient_id, recipient_type, device_id,registration_id, public_key, private_key) VALUES(-1, 0,?, ?, ?, ?)"
        c = self.dbConn.cursor()
        pubKey = identityKeyPair.getPublicKey().getPublicKey().serialize()
        privKey = identityKeyPair.getPrivateKey().serialize()

        c.execute(q, (deviceid,
                      registrationId,
                      pubKey,
                      privKey))

        self.dbConn.commit()

    def saveIdentity(self, recipientId, recipientType, deviceId, identityKey) -> Any:


        q = "DELETE FROM identities WHERE recipient_id=? AND recipient_type=? AND device_id=?"
        self.dbConn.cursor().execute(q, (recipientId,recipientType,deviceId))
        self.dbConn.commit()

        q = "INSERT INTO identities (recipient_id, recipient_type,device_id , public_key) VALUES(?, ?, ?, ? )"
        c = self.dbConn.cursor()

        pubKey = identityKey.getPublicKey().serialize()
        c.execute(q, (recipientId, recipientType,deviceId,buffer(pubKey) if sys.version_info < (2,7) else pubKey))
        self.dbConn.commit()

    def isTrustedIdentity(self, recipientId,recipientType,deviceid,identityKey) -> Any:
        
        q = "SELECT public_key from identities WHERE recipient_id = ?  AND recipient_type=? AND  device_id=?"
        c = self.dbConn.cursor()
        c.execute(q, (recipientId,recipientType,deviceid))
        result = c.fetchone()

        if not result:
            return True
        
        pubKey = identityKey.getPublicKey().serialize()


        return result[0] == pubKey



