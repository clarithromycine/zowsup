import binascii
from typing import Optional, List, Dict, Any


class ProtocolTreeNode:
    _STR_MAX_LEN_DATA: int = 500
    _STR_INDENT: str = '  '

    def __init__(self, tag: str, attributes: Optional[Dict[str, Any]] = None, children: Optional[List['ProtocolTreeNode']] = None, data: Optional[bytes] = None) -> None:
        if data is not None:
            assert type(data) is bytes, type(data)

        self.tag: str = tag
        self.attributes: Dict[str, Any] = attributes or {}
        self.children: List['ProtocolTreeNode'] = children or []
        self.data: Optional[bytes] = data
        self._truncate_str_data: bool = True

        assert type(self.children) is list, "Children must be a list, got %s" % type(self.children)

    def __eq__(self, protocolTreeNode: Any) -> bool:
        """
        :param protocolTreeNode: ProtocolTreeNode
        :return: bool
        """
        #
        if protocolTreeNode.__class__ == ProtocolTreeNode\
            and self.tag == protocolTreeNode.tag\
            and self.data == protocolTreeNode.data\
            and self.attributes == protocolTreeNode.attributes\
            and len(self.getAllChildren()) == len(protocolTreeNode.getAllChildren()):
                found: bool = False
                for c in self.getAllChildren():
                    for c2 in protocolTreeNode.getAllChildren():
                        if c == c2:
                            found = True
                            break
                    if not found:
                        return False

                found = False
                for c in protocolTreeNode.getAllChildren():
                    for c2 in self.getAllChildren():
                        if c == c2:
                            found = True
                            break
                    if not found:
                        return False

                return True

        return False

    def __hash__(self) -> int:
        return hash(self.tag) ^ hash(tuple(self.attributes.items())) ^ hash(self.data)

    def __str__(self) -> str:
        out = "<%s" % self.tag
        attrs = " ".join(map(lambda item: "%s=\"%s\"" % item, self.attributes.items()))
        children = "\n".join(map(str, self.children))
        data = self.data or b""
        len_data = len(data)

        if attrs:
            out = f"{out} {attrs}"

        if children or data:
            out = "%s>" % out
            if children:
                out = "{}\n{}{}".format(out, self._STR_INDENT, children.replace('\n', '\n' + self._STR_INDENT))
            if len_data:
                if self._truncate_str_data and len_data > self._STR_MAX_LEN_DATA:
                    data = data[:self._STR_MAX_LEN_DATA]
                    postfix = "...[truncated %s bytes]" % (len_data - self._STR_MAX_LEN_DATA)
                else:
                    postfix = ""
                data = "0x%s" % binascii.hexlify(data).decode()
                out = f"{out}\n{self._STR_INDENT}{data}{postfix}"

            out = f"{out}\n</{self.tag}>"
        else:
            out = "%s />" % out

        return out

    def getData(self) -> Optional[bytes]:
        return self.data

    def setData(self, data: bytes) -> None:
        self.data = data


    @staticmethod
    def tagEquals(node: Optional['ProtocolTreeNode'], string: str) -> bool:
        return node is not None and node.tag is not None and node.tag == string


    @staticmethod
    def require(node: Optional['ProtocolTreeNode'], string: str) -> None:
        if not ProtocolTreeNode.tagEquals(node, string):
            raise Exception("failed require. string: "+string)


    def __getitem__(self, key: str) -> Any:
        return self.getAttributeValue(key)

    def __setitem__(self, key: str, val: Any) -> None:
        self.setAttribute(key, val)

    def __delitem__(self, key: str) -> None:
        self.removeAttribute(key)


    def getChild(self, identifier: Any) -> Optional['ProtocolTreeNode']:

        if type(identifier) == int:
            if len(self.children) > identifier:
                return self.children[identifier]
            else:
                return None

        for c in self.children:
            if identifier == c.tag:
                return c

        return None

    def hasChildren(self) -> bool:
        return len(self.children) > 0

    def addChild(self, childNode: 'ProtocolTreeNode') -> None:
        self.children.append(childNode)

    def addChildren(self, children: List['ProtocolTreeNode']) -> None:
        for c in children:
            self.addChild(c)

    def getAttributeValue(self, string: str) -> Any:
        try:
            return self.attributes[string]
        except KeyError:
            return None

    def removeAttribute(self, key: str) -> None:
        if key in self.attributes:
            del self.attributes[key]

    def setAttribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def getAllChildren(self, tag: Optional[str] = None) -> List['ProtocolTreeNode']:
        ret: List['ProtocolTreeNode'] = []
        if tag is None:
            return self.children

        for c in self.children:
            if tag == c.tag:
                ret.append(c)

        return ret
