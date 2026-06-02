from dissononce.dh.x25519.x25519 import PublicKey
from ..proto import wa5_pb2,cert_pb2
import axolotl_curve25519 as curve
import logging
import time

logger = logging.getLogger(__name__)


class CertMan:
    def __init__(self):
        self._pubkeys = {
            "WhatsAppLongTerm1": bytearray(
                [20, 35, 117, 87, 77, 10, 88, 113, 102, 170, 231, 30, 190, 81, 100, 55, 196, 162, 139,
                 115, 227, 105, 92, 108, 225, 247, 249, 84, 93, 168, 238, 107])
        }

    
    #杩欓噷鐢?.x鍗囩骇涓?.x鐨凜ertChain閫昏緫锛屾殏鏃剁浉褰撲簬娌￠獙璇佺鍚嶏紝鍚庨潰绛惧悕绠楁硶瀹屽杽涔嬪悗鍐嶇湅

    def is_valid(self, rs, certificate_data):
        """
        :param rs:
        :type rs: PublicKey
        :param certificate_data:
        :type certificate_data: bytes
        :return:
        :rtype:
        """
        cert = cert_pb2.CertChain()
        cert.ParseFromString(certificate_data)
        
        cert_details = cert_pb2.CertChain.NoiseCertificate.Details()
        cert_details.ParseFromString(cert.leaf.details)
        
        if cert.HasField("leaf"):        
            logger.debug(
                "NoiseCertificate(signature=[%d bytes], serial=%d,  ""key=[%d bytes])"
                % (
                    len(cert.leaf.signature), cert_details.serial, 
                    len(cert_details.key)
                )
            )
            
            if time.time() < cert_details.not_before   or time.time()>cert_details.not_after:
                logger.error("noise certificate may be expired")
                return False

            if cert_details.key != rs.data:
                logger.error("noise certificate key does not match proposed server static key")
                return False
        else:
            logger.error("no leaf node found in noise certificate")
            return False
                
        return True
