from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import abc


class TaskMsgStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def setTaskMsg(self, msg_id,task_id,src,dst):
        pass

    @abc.abstractmethod
    def getTaskMsg(self,msg_id) -> Any:
        pass

    @abc.abstractmethod
    def getMsgTaskByResponseMsg(self,sender,receive):
        pass

    @abc.abstractclassmethod
    def delExpiredTaskMsg(self) -> Any:
        pass