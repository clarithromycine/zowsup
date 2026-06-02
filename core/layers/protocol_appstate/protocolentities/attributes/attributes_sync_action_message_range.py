class SyncActionMessageRangeAttribute:
    def __init__(self, lastMessageTimestamp, lastSystemMessageTimestamp,messages) -> None:
        self.lastMessageTimestamp = lastMessageTimestamp
        self.lastSystemMessageTimestamp= lastSystemMessageTimestamp
        self.messages = messages        



