from ....layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs.protocolentity import ProtocolEntityTest
import unittest

class OutgoingReceiptProtocolEntityTest(ProtocolEntityTest, unittest.TestCase):
    def setUp(self) -> Any:
        self.ProtocolEntity = OutgoingReceiptProtocolEntity
        self.node = OutgoingReceiptProtocolEntity("123", "target", "read").toProtocolTreeNode()