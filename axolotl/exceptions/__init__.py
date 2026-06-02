"""
统一异常体系 - Zowsup Protocol Exception Hierarchy

版本: 1.0
目的: 提供结构化、可追踪的错误处理机制
"""


class ProtocolError(Exception):
    """
    所有协议相关错误的基类
    
    属性:
        error_code: 错误代码 (如 "AUTH_FAIL", "TIMEOUT")
        context: 字典,包含诊断信息 (如 iq_id, retry_count, timeout_ms)
    """
    
    def __init__(self, message, error_code=None, context=None):
        """
        初始化协议异常
        
        Args:
            message: 错误描述信息
            error_code: 可选错误代码,便于分类和追踪
            context: 可选字典,包含额外的诊断数据
        """
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
    
    def __str__(self):
        """格式化错误输出"""
        # 构建基础信息
        base = f"[{self.error_code}] {super().__str__()}" if self.error_code else super().__str__()
        
        # 附加上下文信息
        if self.context:
            context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base} | {context_str}"
        return base
    
    def __repr__(self):
        return f"{self.__class__.__name__}(error_code={self.error_code!r}, context={self.context!r})"


class AuthenticationError(ProtocolError):
    """
    认证失败错误
    
    触发场景:
        - 登录凭证验证失败
        - 会话令牌过期
        - 签名校验失败
    
    示例:
        raise AuthenticationError(
            "登录验证失败: 无效的密钥",
            error_code="AUTH_FAIL",
            context={"reason": "invalid_key", "attempt": 3}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="AUTH_FAIL", context=context)


class TimeoutError(ProtocolError):
    """
    网络超时错误
    
    触发场景:
        - IQ请求超过30秒未响应
        - 消息发送无应答
        - 连接建立超时
    
    示例:
        raise TimeoutError(
            "IQ请求超时",
            context={"iq_type": "account", "timeout_ms": 30000, "iq_id": "abc123"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="TIMEOUT", context=context)


class NoSessionError(ProtocolError):
    """
    会话不存在错误
    
    触发场景:
        - 尝试在未登录的状态下执行命令
        - 会话被服务器销毁
        - 连接断开
    
    示例:
        raise NoSessionError(
            "无有效会话,请先登录",
            context={"bot_id": "1234567890", "state": "disconnected"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="NO_SESSION", context=context)


class NetworkError(ProtocolError):
    """
    网络层错误
    
    触发场景:
        - 网络连接失败
        - 代理配置错误
        - DNS解析失败
        - SSL/TLS握手失败
    
    示例:
        raise NetworkError(
            "SSL握手失败",
            context={"error": "certificate_verify_failed", "server": "c.whatsapp.net"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="NETWORK_ERROR", context=context)


class InvalidMessageError(ProtocolError):
    """
    消息格式错误
    
    触发场景:
        - 解密失败
        - 消息格式不合法
        - Protobuf反序列化失败
    
    示例:
        raise InvalidMessageError(
            "消息解密失败",
            context={"reason": "key_mismatch", "from_jid": "1234567890@s.whatsapp.net"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="INVALID_MESSAGE", context=context)


class InvalidKeyError(ProtocolError):
    """
    密钥相关错误
    
    触发场景:
        - 身份密钥验证失败
        - 预密钥不存在
        - 密钥格式无效
    
    示例:
        raise InvalidKeyError(
            "身份密钥不可信",
            context={"jid": "1234567890@s.whatsapp.net"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="INVALID_KEY", context=context)


class IQError(ProtocolError):
    """
    IQ请求/响应错误
    
    触发场景:
        - IQ请求返回错误类型
        - 无效的IQ结构
        - IQ响应包含error元素
    
    示例:
        raise IQError(
            "IQ请求返回错误",
            context={"iq_id": "abc123", "error_type": "bad-request"}
        )
    """
    
    def __init__(self, message, context=None):
        super().__init__(message, error_code="IQ_ERROR", context=context)


# ============================================================================
# 向后兼容性导出 - 保证现有代码不破损
# ============================================================================

# 保持现有异常名称可用但推荐新名称
NoSessionException = NoSessionError
AuthenticationException = AuthenticationError

__all__ = [
    "ProtocolError",
    "AuthenticationError",
    "TimeoutError",
    "NoSessionError",
    "NetworkError",
    "InvalidMessageError",
    "InvalidKeyError",
    "IQError",
    # 向后兼容
    "NoSessionException",
    "AuthenticationException",
]
