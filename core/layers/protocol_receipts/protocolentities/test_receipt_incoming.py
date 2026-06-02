from ....layers.protocol_receipts.protocolentities import IncomingReceiptProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs.protocolentity import ProtocolEntityTest
import unittest
import time

class IncomingReceiptProtocolEntityTest(ProtocolEntityTest, unittest.TestCase):
    def setUp(self) -> Any:
        self.ProtocolEntity = IncomingReceiptProtocolEntity
        self.node = IncomingReceiptProtocolEntity("123", "sender", int(time.time())).toProtocolTreeNode()
