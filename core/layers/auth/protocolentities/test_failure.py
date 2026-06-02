from ....layers.auth.protocolentities.failure import FailureProtocolEntity
from typing import Optional, Any, List, Dict, Union
from ....structs import ProtocolTreeNode
from ....structs.protocolentity import ProtocolEntityTest
import unittest


class FailureProtocolEntityTest(ProtocolEntityTest, unittest.TestCase):
    def setUp(self) -> Any:
        self.ProtocolEntity = FailureProtocolEntity
        self.node = ProtocolTreeNode("failure", {"reason": "not-authorized"})
