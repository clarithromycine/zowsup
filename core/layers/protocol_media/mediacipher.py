from axolotl.kdf.hkdfv3 import HKDFv3
from typing import Optional, Any, List, Dict, Union
from axolotl.util.byteutil import ByteUtil

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import hmac
import hashlib


class MediaCipher:
    INFO_IMAGE = b"WhatsApp Image Keys"
    INFO_AUDIO = b"WhatsApp Audio Keys"
    INFO_VIDEO = b"WhatsApp Video Keys"
    INFO_DOCUMENT = b"WhatsApp Document Keys"
    INFO_HISTORY_SYNC = b"WhatsApp History Keys"
    INFO_APP_STATE= b"WhatsApp App State Keys"
    INFO_STICKER = b"WhatsApp Sticker Pack Keys"

    def encrypt_image(self, plaintext, ref_key) -> Any:
        return self.encrypt(plaintext, ref_key, self.INFO_IMAGE)

    def encrypt_audio(self, ciphertext, ref_key) -> Any:
        return self.encrypt(ciphertext, ref_key, self.INFO_AUDIO)

    def encrypt_video(self, ciphertext, ref_key) -> Any:
        return self.encrypt(ciphertext, ref_key, self.INFO_VIDEO)

    def encrypt_document(self, ciphertext, ref_key) -> Any:
        return self.encrypt(ciphertext, ref_key, self.INFO_DOCUMENT)
    
    def encrypt_history_sync(self,ciphertext,ref_key) -> Any:
        return self.encrypt(ciphertext, ref_key, self.INFO_HISTORY_SYNC)
    
    def encrypt_app_state(self,ciphertext,ref_key) -> Any:
        return self.encrypt(ciphertext,ref_key,self.INFO_APP_STATE)  

    def encrypt_sticker(self,ciphertext,ref_key) -> Any:
        return self.encrypt(ciphertext,ref_key,self.INFO_STICKER)          

    def decrypt_image(self, ciphertext, ref_key) -> Any:
        return self.decrypt(ciphertext, ref_key, self.INFO_IMAGE)

    def decrypt_audio(self, ciphertext, ref_key) -> Any:
        return self.decrypt(ciphertext, ref_key, self.INFO_AUDIO)

    def decrypt_video(self, ciphertext, ref_key) -> Any:
        return self.decrypt(ciphertext, ref_key, self.INFO_VIDEO)

    def decrypt_document(self, ciphertext, ref_key) -> Any:
        return self.decrypt(ciphertext, ref_key, self.INFO_DOCUMENT)
    
    def decrypt_history_sync(self,ciphertext,ref_key) -> Any:
        return self.decrypt(ciphertext, ref_key, self.INFO_HISTORY_SYNC)
    
    def decrypt_app_state(self,ciphertext,ref_key) -> Any:
            return self.decrypt(ciphertext, ref_key, self.INFO_APP_STATE)
    
    def decrypt_sticker(self,ciphertext,ref_key) -> Any:
            return self.decrypt(ciphertext, ref_key, self.INFO_STICKER)


    def encrypt(self, plaintext, ref_key, media_info) -> Any:
        derived = HKDFv3().deriveSecrets(ref_key, media_info, 112)
        parts = ByteUtil.split(derived, 16, 32)
        iv = parts[0]
        key = parts[1]
        mac_key = derived[48:80]

        cipher_encryptor = Cipher(
            algorithms.AES(key), modes.CBC(iv), backend=default_backend()
        ).encryptor()
        if len(plaintext) % 16 != 0:
            padder = padding.PKCS7(128).padder()
            padded_plaintext = padder.update(plaintext) + padder.finalize()
        else:
            padded_plaintext = plaintext
        ciphertext = cipher_encryptor.update(padded_plaintext) + cipher_encryptor.finalize()

        mac = hmac.new(mac_key, digestmod=hashlib.sha256)
        mac.update(iv)
        mac.update(ciphertext)

        return ciphertext + mac.digest()[:10]

    def decrypt(self, ciphertext, ref_key, media_info) -> Any:
        derived = HKDFv3().deriveSecrets(ref_key, media_info, 112)
        parts = ByteUtil.split(derived, 16, 32)
        iv = parts[0]
        key = parts[1]
        mac_key = derived[48:80]
        media_ciphertext = ciphertext[:-10]
        mac_value = ciphertext[-10:]

        mac = hmac.new(mac_key, digestmod=hashlib.sha256)
        mac.update(iv)
        mac.update(media_ciphertext)

        if mac_value != mac.digest()[:10]:
            raise ValueError("Invalid MAC")

        cipher_decryptor = Cipher(
            algorithms.AES(key), modes.CBC(iv), backend=default_backend()
        ).decryptor()

        decrypted = cipher_decryptor.update(media_ciphertext) + cipher_decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(decrypted) + unpadder.finalize()
