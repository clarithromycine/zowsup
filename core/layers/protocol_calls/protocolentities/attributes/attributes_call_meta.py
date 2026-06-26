class CallMetaAttributes:

    def __init__(self, id=None,sender=None,recipient=None,timestamp=None,version=None,platform=None,notify=None,e=None,retry=None,offline=None) -> None:
        self.id = id
        self.sender = sender
        self.recipient = recipient
        self.timestamp = int(timestamp) if timestamp else None
        self.version = version
        self.platform = platform
        self.notify = notify
        self.e = e 
        self.retry = int(retry) if retry else None
        self.offline = offline

    @staticmethod
    def from_call_protocoltreenode(node,proto=None):
        return CallMetaAttributes(node["id"], node["from"],node["to"],node["t"],node["version"],node["platform"],node["notify"],node["e"],node["retry"],node["offline"])
