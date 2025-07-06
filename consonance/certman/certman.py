from dissononce.dh.x25519.x25519 import PublicKey
from ..proto import wa5_pb2,cert_pb2
# 移除未使用的 axolotl_curve25519 导入
import logging
import time

logger = logging.getLogger(__name__)


class CertMan(object):
    def __init__(self):
        self._pubkeys = {
            "WhatsAppLongTerm1": bytearray(
                [20, 35, 117, 87, 77, 10, 88, 113, 102, 170, 231, 30, 190, 81, 100, 55, 196, 162, 139,
                 115, 227, 105, 92, 108, 225, 247, 249, 84, 93, 168, 238, 107])
        }

    
    #这里由5.x升级为6.x的CertChain逻辑，暂时相当于没验证签名，后面签名算法完善之后再看

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
