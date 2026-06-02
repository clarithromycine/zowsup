from ...layers import YowLayerInterface
from typing import Optional, Any, List, Dict, Union

class YowAuthenticationProtocolLayerInterface(YowLayerInterface):
    def setCredentials(self, phone, keypair) -> Any:
        self._layer.setCredentials((phone, keypair))

    def getUsername(self, full = False) -> Any:
        return self._layer.getUsername(full)
