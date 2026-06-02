from typing import Any, Optional, Dict, List, Tuple, Union, Callable
class PreKeyBundle:
    def __init__(self, registrationId, deviceId, preKeyId, ECPublicKey_preKeyPublic,
                 signedPreKeyId, ECPublicKey_signedPreKeyPublic, signedPreKeySignature,
                 identityKey) -> Any:
        self.registrationId = registrationId
        self.deviceId = deviceId
        self.preKeyId = preKeyId
        self.preKeyPublic = ECPublicKey_preKeyPublic
        self.signedPreKeyId = signedPreKeyId
        self.signedPreKeyPublic = ECPublicKey_signedPreKeyPublic
        self.signedPreKeySignature = signedPreKeySignature
        self.identityKey = identityKey

    def getDeviceId(self):
        return self.deviceId

    def getPreKeyId(self) -> Any:
        return self.preKeyId

    def getPreKey(self):
        return self.preKeyPublic

    def getSignedPreKeyId(self) -> Any:
        return self.signedPreKeyId

    def getSignedPreKey(self):
        return self.signedPreKeyPublic

    def getSignedPreKeySignature(self) -> Any:
        return self.signedPreKeySignature

    def getIdentityKey(self):
        return self.identityKey

    def getRegistrationId(self) -> Any:
        return self.registrationId
