from axolotl.state.taskmsgstore import TaskMsgStore

import time
import logging
from typing import Any, Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

class LiteContactStore(TaskMsgStore):

    def __init__(self, dbConn):
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn        
        dbConn.execute("CREATE TABLE IF NOT EXISTS contact(_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "name TEXT,"
                "jid TEXT,"
                "lid TEXT,"
                "tctoken BLOB,"
                "tctoken_ts INTEGER,"
                "timestamp INTEGER);")                                    
                    
    def updateContact(self, jid,lid, name=None):
        
        if jid is not None and not jid.endswith("s.whatsapp.net"):
            return None
        
        if lid is not None and not lid.endswith("lid"):
            return None
                                                            
        if not self.findContact(jid,lid):
            q = "INSERT INTO contact(name,jid,lid,timestamp) VALUES(?,?,?,?)"
            self.dbConn.cursor().execute(q, (name, jid, lid, int(time.time())))
            self.dbConn.commit()
            return jid
        else:
            # If both jid and lid are now known, fill in whichever was previously NULL
            if jid is not None and lid is not None:
                c = self.dbConn.cursor()
                c.execute(
                    "UPDATE contact SET jid=COALESCE(jid,?), lid=COALESCE(lid,?) WHERE jid=? OR lid=?",
                    (jid, lid, jid, lid)
                )
                self.dbConn.commit()
            if name is not None:
                self.updateName(jid, lid, name)

        return None


    def findContact(self, jid=None, lid=None):
        if jid is None and lid is None:
            return False

        if lid is not None and not lid.endswith("lid"):
            return False
        if jid is not None and not jid.endswith("s.whatsapp.net"):
            return False

        c = self.dbConn.cursor()
        if lid is not None and jid is not None:
            c.execute("SELECT 1 FROM contact WHERE lid = ? OR jid = ? LIMIT 1", (lid, jid))
        elif lid is not None:
            c.execute("SELECT 1 FROM contact WHERE lid = ? LIMIT 1", (lid,))
        else:
            c.execute("SELECT 1 FROM contact WHERE jid = ? LIMIT 1", (jid,))

        ret = c.fetchone() is not None

        return ret
                                                    
    def removeContact(self, jid=None, lid=None):
        if jid is None and lid is None:
            return False

        if jid is not None and not jid.endswith("s.whatsapp.net"):
            return False
        if lid is not None and not lid.endswith("lid"):
            return False

        c = self.dbConn.cursor()
        if lid is not None and jid is not None:
            c.execute("DELETE FROM contact WHERE jid = ? OR lid = ?", (jid, lid))
        elif lid is not None:
            c.execute("DELETE FROM contact WHERE lid = ?", (lid,))
        else:
            c.execute("DELETE FROM contact WHERE jid = ?", (jid,))

        self.dbConn.commit()
        return True
    
    def getAllContact(self):
        #返回一个jid数组        
        q = "SELECT jid,lid FROM contact"
        c = self.dbConn.cursor()
        c.execute(q)

        results = c.fetchall()
        jids = []
        for item in results:
            jids.append({
                "jid":item[0],
                "lid":item[1]
            })

        return jids
    
    def updateName(self, jid=None, lid=None, name=None):
        if name is None:
            return False
                
        if not self.findContact(jid, lid):
            self.updateContact(jid, lid, name=name)
            return True
                
        c = self.dbConn.cursor()
        if lid is not None and jid is not None:
            c.execute("UPDATE contact SET name=? WHERE jid=? OR lid=?", (name, jid, lid))
        elif lid is not None:            
            c.execute("UPDATE contact SET name=? WHERE lid=?", (name, lid))
        else:            
            c.execute("UPDATE contact SET name=? WHERE jid=?", (name, jid))

        self.dbConn.commit()

        return True
            
    def updateTctoken(self, jid=None, lid=None, tctoken=None, tctoken_ts=None):
        if tctoken is None:
            return False

        if tctoken_ts is None:
            tctoken_ts = int(time.time())

        c = self.dbConn.cursor()
        if self.findContact(jid, lid):
            if lid is not None and jid is not None:
                c.execute("UPDATE contact SET tctoken=?, tctoken_ts=? WHERE jid=? OR lid=?",
                          (tctoken, tctoken_ts, jid, lid))
            elif lid is not None:
                c.execute("UPDATE contact SET tctoken=?, tctoken_ts=? WHERE lid=?",
                          (tctoken, tctoken_ts, lid))
            else:
                c.execute("UPDATE contact SET tctoken=?, tctoken_ts=? WHERE jid=?",
                          (tctoken, tctoken_ts, jid))
        else:
            c.execute("INSERT INTO contact(jid, lid, tctoken, tctoken_ts) VALUES(?, ?, ?, ?)",
                      (jid, lid, tctoken, tctoken_ts))

        self.dbConn.commit()
        return True                        

    def getTctoken(self,jid=None,lid=None):               

        token = None

        if token is None and jid is not None:
            q = "SELECT tctoken FROM contact WHERE jid = ?"
            c = self.dbConn.cursor()
            c.execute(q, (jid, ))                                
            result = c.fetchone()
            token = result[0] if result else None
                    
        if token is None and lid is not None:
            q = "SELECT tctoken FROM contact WHERE lid = ?"
            c = self.dbConn.cursor()
            c.execute(q, (lid,))                                
            result = c.fetchone()
            token = result[0] if result else None            

        return token        
    
    def removeTctoken(self,jid=None,lid=None):

        if jid is not None:
            q = "UPDATE contact SET tctoken=NULL,tctoken_ts=NULL WHERE jid=?"
            self.dbConn.cursor().execute(q, (jid,))
        
        elif lid is not None:
            q = "UPDATE contact SET tctoken=NULL,tctoken_ts=NULL WHERE lid=?"
            self.dbConn.cursor().execute(q, (lid,))

        self.dbConn.commit()
        return True   
    