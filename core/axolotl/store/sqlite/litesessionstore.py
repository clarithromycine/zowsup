from axolotl.state.sessionstore import SessionStore
from axolotl.state.sessionrecord import SessionRecord
import sys
from typing import Any, Optional, Dict, List, Tuple

class LiteSessionStore(SessionStore):

    def __init__(self, dbConn) -> None:
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn
        #dbConn.execute("DROP TABLE IF EXISTS sessions")
        dbConn.execute("CREATE TABLE IF NOT EXISTS sessions (_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                       "recipient_id INTEGER,"
                       "recipient_type INTEGER NOT NULL DEFAULT 0,"
                       "device_id INTEGER, record BLOB, timestamp INTEGER);")

    def loadSession(self, recipientId , recipientType, deviceId) -> Any:

        q = "SELECT record FROM sessions WHERE recipient_id = ? AND recipient_type=? AND device_id = ?"
        c = self.dbConn.cursor()
        c.execute(q, (recipientId, recipientType, deviceId))
        result = c.fetchone()

        if result:            
            return SessionRecord(serialized=result[0])
        else:            
            return SessionRecord()

    def getSubDeviceSessions(self, recipientId) -> Any:

        q = "SELECT device_id from sessions WHERE recipient_id = ?"
        c = self.dbConn.cursor()
        c.execute(q, (recipientId,))
        result = c.fetchall()

        deviceIds = [r[0] for r in result]
        return deviceIds

    def storeSession(self, recipientId, recipientType, deviceId, sessionRecord) -> Any:
                        
        self.deleteSession(recipientId, recipientType, deviceId)

        q = "INSERT INTO sessions(recipient_id, recipient_type, device_id, record) VALUES(?,?,?,?)"
        c = self.dbConn.cursor()
        serialized = sessionRecord.serialize()
        c.execute(q, (recipientId, recipientType, deviceId, buffer(serialized) if sys.version_info < (2,7) else serialized))
        self.dbConn.commit()

    def containsSession(self, recipientId, recipientType, deviceId) -> Any:

        q = "SELECT record FROM sessions WHERE recipient_id = ?  AND recipient_type=? AND device_id = ?"
        c = self.dbConn.cursor()
        c.execute(q, (recipientId, recipientType, deviceId))
        result = c.fetchone()

        return result is not None

    def deleteSession(self, recipientId ,recipientType, deviceId) -> Any:
        q = "DELETE FROM sessions WHERE recipient_id = ? AND recipient_type = ? AND device_id = ?"
        self.dbConn.cursor().execute(q, (recipientId, recipientType,deviceId))
        self.dbConn.commit()

    def deleteAllSessions(self, recipientId) -> Any:
        q = "DELETE FROM sessions WHERE recipient_id = ?"
        self.dbConn.cursor().execute(q, (recipientId,))
        self.dbConn.commit()

    def getAllAccounts(self,recipientId) -> Any:
        q = "SELECT recipient_id,recipient_type,device_id from sessions WHERE recipient_id = ?"
        c = self.dbConn.cursor()
        c.execute(q, (recipientId,))
        result = c.fetchall()        
        accounts = ["%d.%d:%d@lid" % (r[0],r[1],r[2]) for r in result]
        return accounts

