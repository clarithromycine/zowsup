from ...layers import YowLayer
from typing import Optional, Any, List, Dict, Union
import logging
logger = logging.getLogger(__name__)
class YowLoggerLayer(YowLayer):

    async def send(self, data) -> Any:
        ldata = list(data) if type(data) is bytearray else data
        logger.debug("tx:\n%s" % ldata)
        await self.toLower(data)

    async def receive(self, data) -> Any:
        ldata = list(data) if type(data) is bytearray else data
        logger.debug("rx:\n%s" % ldata)
        await self.toUpper(data)

    def __str__(self):
        return "Logger Layer"