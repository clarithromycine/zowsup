# -*- coding: utf-8 -*-
"""
Cryptography库适配器
用于替换python-axolotl-curve25519，提供兼容的API接口

主要功能：
- X25519密钥协商 (ECDH)
- Ed25519数字签名
- 密钥生成和管理

作者：zowsup项目
日期：2025-07-06
"""

import os
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class CryptographyAdapter:
    """
    cryptography库的适配器类
    提供与python-axolotl-curve25519兼容的API
    """

    # 存储X25519私钥到Ed25519密钥对的映射
    _key_mapping = {}
    
    @staticmethod
    def generatePrivateKey(random_bytes):
        """
        生成Curve25519私钥

        同时生成X25519和Ed25519密钥对，并建立映射关系

        :param random_bytes: 32字节的随机数据 (兼容原API，实际不使用)
        :type random_bytes: bytes
        :return: 32字节的私钥数据
        :rtype: bytes
        """
        # 生成X25519密钥对
        x25519_private_key = x25519.X25519PrivateKey.generate()
        x25519_private_bytes = x25519_private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 使用确定性方法生成对应的Ed25519密钥对
        import hashlib
        ed25519_seed = hashlib.sha512(x25519_private_bytes + b"ed25519").digest()[:32]
        ed25519_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(ed25519_seed)
        ed25519_public_key = ed25519_private_key.public_key()

        # 存储映射关系
        x25519_private_hex = x25519_private_bytes.hex()
        CryptographyAdapter._key_mapping[x25519_private_hex] = {
            'ed25519_private': ed25519_private_key,
            'ed25519_public': ed25519_public_key
        }

        return x25519_private_bytes
    
    @staticmethod
    def generatePublicKey(private_key_bytes):
        """
        从Curve25519私钥生成对应的公钥

        :param private_key_bytes: 32字节的私钥数据
        :type private_key_bytes: bytes
        :return: 32字节的公钥数据
        :rtype: bytes
        """
        # 使用X25519生成公钥（用于密钥协商）
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key = private_key.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    @staticmethod
    def calculateAgreement(private_key_bytes, public_key_bytes):
        """
        执行X25519密钥协商 (ECDH)
        
        :param private_key_bytes: 32字节的私钥数据
        :type private_key_bytes: bytes
        :param public_key_bytes: 32字节的公钥数据
        :type public_key_bytes: bytes
        :return: 32字节的共享密钥
        :rtype: bytes
        """
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key = x25519.X25519PublicKey.from_public_bytes(public_key_bytes)
        shared_key = private_key.exchange(public_key)
        return shared_key
    
    @staticmethod
    def calculateSignature(random_bytes, private_key_bytes, message):
        """
        使用Ed25519计算数字签名

        :param random_bytes: 64字节随机数据 (兼容原API，实际不使用)
        :type random_bytes: bytes
        :param private_key_bytes: 32字节的私钥数据
        :type private_key_bytes: bytes
        :param message: 要签名的消息
        :type message: bytes
        :return: 64字节的签名
        :rtype: bytes
        """
        # 查找映射的Ed25519私钥
        private_key_hex = private_key_bytes.hex()
        if private_key_hex in CryptographyAdapter._key_mapping:
            ed25519_private_key = CryptographyAdapter._key_mapping[private_key_hex]['ed25519_private']
            signature = ed25519_private_key.sign(message)
            return signature
        else:
            # 如果没有找到映射，使用确定性方法生成
            import hashlib
            ed25519_seed = hashlib.sha512(private_key_bytes + b"ed25519").digest()[:32]
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(ed25519_seed)
            signature = private_key.sign(message)
            return signature
    
    @staticmethod
    def verifySignature(public_key_bytes, message, signature):
        """
        使用Ed25519验证数字签名

        :param public_key_bytes: 32字节的公钥数据
        :type public_key_bytes: bytes
        :param message: 原始消息
        :type message: bytes
        :param signature: 64字节的签名
        :type signature: bytes
        :return: 验证结果 (0表示成功，非0表示失败)
        :rtype: int
        """
        try:
            # 查找对应的Ed25519公钥
            # 由于我们无法从X25519公钥直接找到对应的私钥，
            # 我们需要通过相同的确定性方法重新生成Ed25519公钥

            # 方法1：尝试从映射中查找（通过遍历）
            for private_hex, key_data in CryptographyAdapter._key_mapping.items():
                # 重新生成X25519公钥来比较
                private_bytes = bytes.fromhex(private_hex)
                x25519_private = x25519.X25519PrivateKey.from_private_bytes(private_bytes)
                x25519_public = x25519_private.public_key()
                x25519_public_bytes = x25519_public.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )

                if x25519_public_bytes == public_key_bytes:
                    # 找到匹配的密钥对
                    ed25519_public_key = key_data['ed25519_public']
                    ed25519_public_key.verify(signature, message)
                    return 0  # 成功

            # 方法2：如果没有找到映射，使用确定性方法
            import hashlib
            ed25519_seed = hashlib.sha512(public_key_bytes + b"ed25519").digest()[:32]
            temp_private_key = ed25519.Ed25519PrivateKey.from_private_bytes(ed25519_seed)
            public_key = temp_private_key.public_key()
            public_key.verify(signature, message)
            return 0  # 成功

        except InvalidSignature:
            return 1  # 失败
        except Exception:
            return 1  # 其他错误也视为失败


# 为了兼容性，提供模块级别的函数接口
def generatePrivateKey(random_bytes):
    """兼容性函数：生成私钥"""
    return CryptographyAdapter.generatePrivateKey(random_bytes)


def generatePublicKey(private_key_bytes):
    """兼容性函数：生成公钥"""
    return CryptographyAdapter.generatePublicKey(private_key_bytes)


def calculateAgreement(private_key_bytes, public_key_bytes):
    """兼容性函数：密钥协商"""
    return CryptographyAdapter.calculateAgreement(private_key_bytes, public_key_bytes)


def calculateSignature(random_bytes, private_key_bytes, message):
    """兼容性函数：计算签名"""
    return CryptographyAdapter.calculateSignature(random_bytes, private_key_bytes, message)


def verifySignature(public_key_bytes, message, signature):
    """兼容性函数：验证签名"""
    return CryptographyAdapter.verifySignature(public_key_bytes, message, signature)
