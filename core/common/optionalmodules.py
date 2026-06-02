import importlib
from typing import Optional, Any, List, Dict, Union
import logging

logger = logging.getLogger(__name__)


class OptionalModule:
    def __init__(self, modulename, failMessage = None, require = False):
        self.modulename = modulename
        self.require = require
        self.failMessage = failMessage

    def __enter__(self) -> Any:        
        return self.importFn

    def importFn(self, what = None):
        imp = self.modulename if not what else (f"{self.modulename}.{what}")
        ss = importlib.import_module(imp)
        return importlib.import_module(imp)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, ImportError):
            failMessage = self.failMessage if self.failMessage is not None else ("%s import failed" % self.modulename)
            if failMessage:
                logger.error(failMessage)
            if self.require:
                raise
            return True

class PILOptionalModule(OptionalModule):
    def __init__(self, failMessage = None, require = False):
        super().__init__("PIL",
                failMessage= failMessage,
                require = require)

class FFMpegOptionalModule(OptionalModule):
    def __init__(self, failMessage = None, require = False):
        super().__init__("ffmpeg",
                failMessage=failMessage,
                require=require)
