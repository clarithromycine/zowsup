from ...layers import YowLayerInterface
from typing import Optional, Any, List, Dict, Union
class YowNetworkLayerInterface(YowLayerInterface):
    async def connect(self) -> Any:
        self._layer.createConnection()

    async def disconnect(self) -> Any:
        self._layer.destroyConnection()

    def getStatus(self) -> Any:
        return self._layer.getStatus()