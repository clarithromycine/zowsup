from proto import protocol_pb2
from typing import Optional, Any, List, Dict, Union
import json

class SyncActionContactActionAttribute:
    def __init__(self, fullName=None, firstName=None,lidJid=None,saveOnPrimaryAddressbook=True) -> None:

        super().__init__()
        self.fullName = fullName
        self.firstName= firstName
        self.lidJid = lidJid
        self.saveOnPrimaryAddressbook = saveOnPrimaryAddressbook        

    def encode(self) -> Any:
        pb_obj = protocol_pb2.SyncActionValue.ContactAction()

        if self.fullName is not None:
            pb_obj.fullName = self.fullName

        if self.firstName is not None:
            pb_obj.firstName = self.firstName

        if self.lidJid is not None:
            pb_obj.lidJid = self.lidJid

        if self.saveOnPrimaryAddressbook is not None:
            pb_obj.saveOnPrimaryAddressbook = self.saveOnPrimaryAddressbook                                    
                 
        return pb_obj
        

    @staticmethod
    def decodeFrom(self,pb_obj) -> Any:
        fullName = pb_obj.fullName if pb_obj.HasField("fullName") else None
        firstName = pb_obj.firstName if pb_obj.HasField("firstName") else None
        lidJid = pb_obj.lidJid if pb_obj.HasField("lidJid") else None
        saveOnPrimaryAddressbook = pb_obj.saveOnPrimaryAddressbook if pb_obj.HasField("saveOnPrimaryAddressbook") else None

        return SyncActionContactActionAttribute(
            fullName=fullName,
            firstName=firstName,
            lidJid=lidJid,
            saveOnPrimaryAddressbook=saveOnPrimaryAddressbook
        )

    def indexName(self) -> Any:
        return "contact"
    
    def actionVersion(self) -> Any:
        return 2