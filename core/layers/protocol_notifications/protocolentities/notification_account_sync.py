from ....structs import ProtocolEntity, ProtocolTreeNode
from typing import Optional, Any, List, Dict, Union
from .notification import NotificationProtocolEntity

class AccountSyncNotificationProtocolEntity(NotificationProtocolEntity):
    '''
        <notification from="212719800440@s.whatsapp.net" type="account_sync" id="3214196751" t="1723380164">
            <devices dhash="2:ebaxe4fF">
                <device jid="212719800440@s.whatsapp.net" />
                <device jid="212719800440.0:1@s.whatsapp.net" key-index="1" />
                <key-index-list ts="1723380161">
                0x0a1808938298bb0510c1e3e2b506220a0102030405060708090a12407f312669e9cff49eb42d2f0ef368ffbbd4a814d157046f46c1b762b1181d4984c00a0a06cf49adca98e9709e3bace90ec60216159614aa1a520b3cbf594dca03
                </key-index-list>
            </devices>
        </notification>
    '''

    def __init__(self, _id,  _from, timestamp, notify, offline) -> None:
        super().__init__(_id, _from, timestamp, notify, offline)
        self.devices = []

    @staticmethod
    def fromProtocolTreeNode(node):
        entity = NotificationProtocolEntity.fromProtocolTreeNode(node)
        entity.__class__ = AccountSyncNotificationProtocolEntity
        return entity