from axolotl.state.taskmsgstore import TaskMsgStore
from ....common.tools import Jid,WATools
import time,hashlib,base64
from typing import Any, Optional, Dict, List, Tuple


class LiteBroadcastStore(TaskMsgStore):

    def __init__(self, dbConn) -> None:
        """
        :type dbConn: Connection
        """
        self.dbConn = dbConn        
        
        dbConn.execute("CREATE TABLE IF NOT EXISTS broadcast(_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "sender TEXT,"
                "name TEXT,"
                "jids TEXT,"
                "phash TEXT,"
                "bcid TEXT);")                
        
    def phash(self,jids) -> Any:
        jids = sorted(jids)    
        h = hashlib.sha256()
        for jid in jids:
            h.update(jid.encode())                    
        return "2:"+base64.b64encode(h.digest()[:6]).decode()              
                    
    def addBroadcast(self,jids,senderJid,name=None) -> Any:
        #jids支持逗号字符串或者数组
        if isinstance(jids,str):
            jids = jids.split(",")

        newJid = []
        for jid in jids:
            newJid.append(WATools.fullJid(jid))
        
        newJid.append(WATools.fullJid(senderJid))
        
        phash = self.phash(newJid)        
        if name is None:
            name = ""
        
        bcid,phash1 = self.findBroadcastByPhash(phash)
        if bcid:
            return bcid,phash1
        else:
            bcid = "%d@broadcast" % time.time()
            q = "INSERT INTO broadcast(name,jids,phash,bcid,sender) VALUES(?,?,?,?,?)"
            self.dbConn.cursor().execute(q, (name, ",".join(newJid),phash,bcid,WATools.fullJid(senderJid)))
            
            self.dbConn.commit()
            return bcid,phash      
        
    
    def findParticipantsByBcid(self,bcid) -> Any:

        q = "SELECT jids,sender FROM broadcast WHERE bcid = ?"
        c = self.dbConn.cursor()
        c.execute(q, (bcid, ))                                
        result =  c.fetchone()                
        if result:                         
            jids = [item for item in result[0].decode().split(",") if item != result[1].decode()]            
            return jids #这里返回的是数组，除去自己
        else:            
            return None        

    def findBroadcastByPhash(self,phash) -> Any:

        q = "SELECT bcid FROM broadcast WHERE phash = ?"
        c = self.dbConn.cursor()
        c.execute(q, (phash, ))
                                
        result =  c.fetchone()
        if result:                                      
            return result[0].decode(),phash
        else:            
            return None,None        





