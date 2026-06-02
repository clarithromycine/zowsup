from axolotl.groups.state.senderkeystore import SenderKeyStore
from axolotl.groups.state.senderkeyrecord import SenderKeyRecord
import sqlite3
import sys
from typing import Any, Optional, Dict, List, Tuple

class LiteSenderKeyStore(SenderKeyStore):
    def __init__(self, dbConn) -> None:
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn
        dbConn.execute("DROP TABLE IF EXISTS sender_keys")

        dbConn.execute("CREATE TABLE IF NOT EXISTS sender_keys (_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                       "group_id TEXT NOT NULL,"
                       "device_id INTEGER,"
                       "timestamp INTEGER,"
                       "sender_account_id TEXT NOT NULL,"
                       "sender_account_type INTEGER,"
                       "record BLOB);")

        dbConn.execute("CREATE UNIQUE INDEX IF NOT EXISTS sender_keys_idx ON sender_keys (group_id, sender_account_id,sender_account_type,device_id);")

    def storeSenderKey(self, senderKeyName, senderKeyRecord) -> Any:
        """
        :type senderKeyName: SenderKeName
        :type senderKeyRecord: SenderKeyRecord
        """
        q = "INSERT OR REPLACE INTO sender_keys (group_id, sender_account_id, record) VALUES(?,?, ?)"
        cursor = self.dbConn.cursor()
        serialized = senderKeyRecord.serialize()
        if sys.version_info < (2,7):
            serialized = buffer(serialized)
        try:
            cursor.execute(q, (senderKeyName.getGroupId(), senderKeyName.getSender().getName(), serialized))
            self.dbConn.commit()
        except sqlite3.IntegrityError as e:
            q = "UPDATE sender_keys set record = ? WHERE group_id = ? and sender_account_id = ?"
            cursor = self.dbConn.cursor()
            cursor.execute(q, (serialized, senderKeyName.getGroupId(), senderKeyName.getSender().getName()))
            self.dbConn.commit()

    def loadSenderKey(self, senderKeyName) -> Any:
        """
        :type senderKeyName: SenderKeyName
        """
        q = "SELECT record FROM sender_keys WHERE group_id = ? and sender_account_id = ?"
        cursor = self.dbConn.cursor()
        cursor.execute(q, (senderKeyName.getGroupId(), senderKeyName.getSender().getName()))

        result = cursor.fetchone()
        if not result:
            return SenderKeyRecord()
        return SenderKeyRecord(serialized = result[0])
