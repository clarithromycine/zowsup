# -*- cofing: utf-8 -*-


class InvalidMessageException(Exception):
    def __init__(self, message, exceptions=None):
        if exceptions:
            message += str(exceptions[0])
        super().__init__(message)
