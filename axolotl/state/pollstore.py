import abc


class PollStore:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def deletePoll(self, poll_msg_id):
        pass

    @abc.abstractmethod
    def storePoll(self, poll_msg_id,name,options):
        pass

    @abc.abstractmethod
    def decryptOptions(self,poll_msg_id,option_sha256_list):
        pass

    @abc.abstractmethod
    def getPollEncKey(self,poll_msg_id):    
        pass
