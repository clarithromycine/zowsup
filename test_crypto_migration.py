#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curve25519迁移测试脚本

测试从python-axolotl-curve25519迁移到cryptography库后的功能完整性

测试内容：
1. 密钥生成功能
2. 密钥协商 (ECDH)
3. 数字签名和验证
4. 与原有代码的集成测试

作者：zowsup项目
日期：2025-07-06
"""

import sys
import os
import traceback

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_crypto_adapter():
    """测试cryptography适配器的基本功能"""
    print("=" * 60)
    print("测试 1: Cryptography适配器基本功能")
    print("=" * 60)
    
    try:
        from axolotl.ecc.crypto_adapter import CryptographyAdapter
        
        # 测试密钥生成
        print("1.1 测试密钥生成...")
        rand_bytes = os.urandom(32)
        private_key = CryptographyAdapter.generatePrivateKey(rand_bytes)
        public_key = CryptographyAdapter.generatePublicKey(private_key)
        
        print(f"   私钥长度: {len(private_key)} 字节")
        print(f"   公钥长度: {len(public_key)} 字节")
        assert len(private_key) == 32, "私钥长度应为32字节"
        assert len(public_key) == 32, "公钥长度应为32字节"
        print("   ✓ 密钥生成测试通过")
        
        # 测试密钥协商
        print("\n1.2 测试密钥协商...")
        # 生成两对密钥
        private_key_a = CryptographyAdapter.generatePrivateKey(os.urandom(32))
        public_key_a = CryptographyAdapter.generatePublicKey(private_key_a)
        
        private_key_b = CryptographyAdapter.generatePrivateKey(os.urandom(32))
        public_key_b = CryptographyAdapter.generatePublicKey(private_key_b)
        
        # 计算共享密钥
        shared_key_a = CryptographyAdapter.calculateAgreement(private_key_a, public_key_b)
        shared_key_b = CryptographyAdapter.calculateAgreement(private_key_b, public_key_a)
        
        print(f"   共享密钥A长度: {len(shared_key_a)} 字节")
        print(f"   共享密钥B长度: {len(shared_key_b)} 字节")
        assert shared_key_a == shared_key_b, "双方计算的共享密钥应该相同"
        assert len(shared_key_a) == 32, "共享密钥长度应为32字节"
        print("   ✓ 密钥协商测试通过")
        
        # 测试数字签名
        print("\n1.3 测试数字签名...")
        message = b"Hello, World! This is a test message."
        rand_bytes = os.urandom(64)
        
        # 生成签名密钥对
        sign_private_key = CryptographyAdapter.generatePrivateKey(os.urandom(32))
        sign_public_key = CryptographyAdapter.generatePublicKey(sign_private_key)
        
        # 计算签名
        signature = CryptographyAdapter.calculateSignature(rand_bytes, sign_private_key, message)
        print(f"   签名长度: {len(signature)} 字节")
        assert len(signature) == 64, "Ed25519签名长度应为64字节"
        
        # 验证签名
        verify_result = CryptographyAdapter.verifySignature(sign_public_key, message, signature)
        print(f"   验证结果: {verify_result}")
        assert verify_result == 0, "签名验证应该成功"
        
        # 测试错误签名
        wrong_message = b"Wrong message"
        verify_result_wrong = CryptographyAdapter.verifySignature(sign_public_key, wrong_message, signature)
        print(f"   错误消息验证结果: {verify_result_wrong}")
        assert verify_result_wrong != 0, "错误消息的签名验证应该失败"
        
        print("   ✓ 数字签名测试通过")
        
        return True
        
    except Exception as e:
        print(f"   ✗ 适配器测试失败: {e}")
        traceback.print_exc()
        return False


def test_curve_integration():
    """测试与Curve类的集成"""
    print("\n" + "=" * 60)
    print("测试 2: Curve类集成测试")
    print("=" * 60)
    
    try:
        from axolotl.ecc.curve import Curve
        
        # 测试密钥对生成
        print("2.1 测试Curve密钥对生成...")
        key_pair = Curve.generateKeyPair()
        
        print(f"   公钥类型: {type(key_pair.getPublicKey())}")
        print(f"   私钥类型: {type(key_pair.getPrivateKey())}")
        print(f"   公钥序列化长度: {len(key_pair.getPublicKey().serialize())} 字节")
        print(f"   私钥序列化长度: {len(key_pair.getPrivateKey().serialize())} 字节")
        
        assert key_pair.getPublicKey().getType() == Curve.DJB_TYPE
        assert key_pair.getPrivateKey().getType() == Curve.DJB_TYPE
        print("   ✓ Curve密钥对生成测试通过")
        
        # 测试密钥协商
        print("\n2.2 测试Curve密钥协商...")
        key_pair_a = Curve.generateKeyPair()
        key_pair_b = Curve.generateKeyPair()
        
        shared_secret_a = Curve.calculateAgreement(key_pair_b.getPublicKey(), key_pair_a.getPrivateKey())
        shared_secret_b = Curve.calculateAgreement(key_pair_a.getPublicKey(), key_pair_b.getPrivateKey())
        
        print(f"   共享密钥长度: {len(shared_secret_a)} 字节")
        assert shared_secret_a == shared_secret_b, "双方计算的共享密钥应该相同"
        print("   ✓ Curve密钥协商测试通过")
        
        # 测试签名和验证
        print("\n2.3 测试Curve签名和验证...")
        message = bytearray(b"Test message for signature")
        
        signature = Curve.calculateSignature(key_pair_a.getPrivateKey(), message)
        print(f"   签名长度: {len(signature)} 字节")
        
        is_valid = Curve.verifySignature(key_pair_a.getPublicKey(), message, signature)
        print(f"   签名验证结果: {is_valid}")
        assert is_valid == True, "签名验证应该成功"
        
        # 测试错误签名
        wrong_signature = bytearray(os.urandom(64))
        is_invalid = Curve.verifySignature(key_pair_a.getPublicKey(), message, wrong_signature)
        print(f"   错误签名验证结果: {is_invalid}")
        assert is_invalid == False, "错误签名验证应该失败"
        
        print("   ✓ Curve签名和验证测试通过")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Curve集成测试失败: {e}")
        traceback.print_exc()
        return False


def test_keyhelper_integration():
    """测试与KeyHelper的集成"""
    print("\n" + "=" * 60)
    print("测试 3: KeyHelper集成测试")
    print("=" * 60)
    
    try:
        from axolotl.util.keyhelper import KeyHelper
        
        # 测试身份密钥对生成
        print("3.1 测试身份密钥对生成...")
        identity_key_pair = KeyHelper.generateIdentityKeyPair()
        
        print(f"   身份公钥类型: {type(identity_key_pair.getPublicKey())}")
        print(f"   身份私钥类型: {type(identity_key_pair.getPrivateKey())}")
        print("   ✓ 身份密钥对生成测试通过")
        
        # 测试预密钥生成
        print("\n3.2 测试预密钥生成...")
        pre_keys = KeyHelper.generatePreKeys(1, 5)
        
        print(f"   生成预密钥数量: {len(pre_keys)}")
        assert len(pre_keys) == 5, "应该生成5个预密钥"
        
        for i, pre_key in enumerate(pre_keys):
            print(f"   预密钥 {i+1} ID: {pre_key.getId()}")
            assert pre_key.getKeyPair().getPublicKey().getType() == 5  # DJB_TYPE
        
        print("   ✓ 预密钥生成测试通过")
        
        # 测试签名预密钥生成
        print("\n3.3 测试签名预密钥生成...")
        signed_pre_key = KeyHelper.generateSignedPreKey(identity_key_pair, 1)
        
        print(f"   签名预密钥ID: {signed_pre_key.getId()}")
        print(f"   签名长度: {len(signed_pre_key.getSignature())} 字节")
        assert len(signed_pre_key.getSignature()) == 64, "Ed25519签名长度应为64字节"
        print("   ✓ 签名预密钥生成测试通过")
        
        return True
        
    except Exception as e:
        print(f"   ✗ KeyHelper集成测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("Curve25519迁移测试开始")
    print("测试cryptography库替换python-axolotl-curve25519的功能完整性")
    print()
    
    test_results = []
    
    # 运行所有测试
    test_results.append(("Cryptography适配器", test_crypto_adapter()))
    test_results.append(("Curve类集成", test_curve_integration()))
    test_results.append(("KeyHelper集成", test_keyhelper_integration()))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:20} : {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！Curve25519迁移成功！")
        print("cryptography库已成功替换python-axolotl-curve25519")
        return 0
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
