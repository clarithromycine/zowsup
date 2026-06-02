from ...layers import YowLayer
from typing import Optional, Any, List, Dict, Union
from .encoder import WriteEncoder
from .decoder import ReadDecoder
from .tokendictionary import TokenDictionary
import asyncio
import zlib
import logging
import threading

logger = logging.getLogger(__name__)

class YowCoderLayer(YowLayer):

    def __init__(self) -> None:
        YowLayer.__init__(self)
        tokenDictionary = TokenDictionary()
        self.writer = WriteEncoder(tokenDictionary)
        self.reader = ReadDecoder(tokenDictionary)

    
    async def send(self, data) -> Any:                        
        out = self.writer.protocolTreeNodeToBytes(data)    
        await self.write(out)

    async def receive(self, data) -> Any:      
        node = self.reader.getProtocolTreeNode(bytearray(data))     
        if node:
            await self.toUpper(node)


    async def write(self, i) -> Any:
        if(type(i) in(list, tuple,bytearray)):
            await self.toLower(bytearray(i))
        else:
            await self.toLower(bytearray([i]))

    def __str__(self):
        return "Coder Layer"
