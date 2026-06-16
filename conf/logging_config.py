"""
统一日志配置系统 - Zowsup Logging Configuration

版本: 1.0
目的: 提供一致的日志格式、级别控制和输出管理
特性:
  - 环境变量控制日志级别
  - 统一的格式化输出
  - 支持多种日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - 支持文件输出 (可选)
  - Thread-safe
"""

from typing import Any, Optional, Dict, List, Tuple, Union, Callable
import logging
import logging.handlers
import sys
import os
from pathlib import Path


# ============================================================================
# 自定义模块名缩略 Formatter
# ============================================================================

class ShortenedNameFormatter(logging.Formatter):
    """
    自定义 Formatter，用于缩略长的模块名
    
    模式:
    - 'full': 保持完整名称 (core.layers.network.dispatcher.dispatcher_asyncio)
    - 'short': 只显示最后2层 (dispatcher_asyncio)  
    - 'abbr': 首字母缩写 (c.l.n.d.dispatcher_asyncio)
    """
    
    def __init__(self, fmt=None, datefmt=None, mode='short'):
        super().__init__(fmt, datefmt)
        self.mode = mode
    
    def format(self, record) -> Any:
        # 根据模式缩略模块名
        if self.mode == 'short':
            # 只显示最后2层
            parts = record.name.split('.')
            if len(parts) > 2:
                record.name = '.'.join(parts[-2:])
        elif self.mode == 'abbr':
            # 首字母缩写: core.layers.network.dispatcher.dispatcher_asyncio -> c.l.n.d.dispatcher_asyncio
            parts = record.name.split('.')
            if len(parts) > 2:
                abbreviated = '.'.join([p[0] for p in parts[:-2]]) + '.' + parts[-1]
                record.name = abbreviated
        # 'full' 模式保持原样
        
        return super().format(record)


# ============================================================================
# 日志配置常数
# ============================================================================

LOG_LEVELS = {
    'DEBUG': logging.DEBUG,       # 10
    'INFO': logging.INFO,         # 20
    'WARNING': logging.WARNING,   # 30
    'ERROR': logging.ERROR,       # 40
    'CRITICAL': logging.CRITICAL, # 50
}

# 默认日志级别
DEFAULT_LOG_LEVEL = 'INFO'

# 日志格式
CONSOLE_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)-18s | %(message)s'
FILE_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)-18s | [%(filename)s:%(lineno)d] %(message)s'

# 日期格式（仅日期部分，时间+毫秒由 %(msecs)03d 补充）
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 模块名缩略模式: 'full' | 'short' | 'abbr'
# - 'full': 保留完整名称
# - 'short': 只显示最后2层 (推荐)
# - 'abbr': 首字母缩写模式
MODULE_NAME_MODE = os.getenv('LOG_MODULE_MODE', 'short')

# 日志文件配置
LOG_DIR = 'logs'
LOG_FILE = 'zowsup.log'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5  # 保留5个备份文件


# ============================================================================
# 日志配置函数
# ============================================================================

def get_log_level(level_name=None):
    """
    获取日志级别
    
    Args -> Any:
        level_name: 日志级别名称 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
                   如果为None，从环境变量 LOG_LEVEL 读取
    
    Returns:
        logging级别的数值
    """
    # 优先使用参数，其次使用环境变量，最后使用默认值
    if level_name is None:
        level_name = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
    
    level_name = level_name.upper()
    
    if level_name not in LOG_LEVELS:
        print(f"警告: 未知的日志级别 '{level_name}'，使用默认值 '{DEFAULT_LOG_LEVEL}'")
        return LOG_LEVELS[DEFAULT_LOG_LEVEL]
    
    return LOG_LEVELS[level_name]


def setup_logging(level=None, enable_file=False, module_name_mode=None, log_file_name=None):
    """
    初始化日志系统
    
    Args -> Any:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
               如果为None，从环境变量 LOG_LEVEL 读取，默认为 INFO
        enable_file: 是否同时输出到文件
        module_name_mode: 模块名缩略模式 ('full'|'short'|'abbr')
                         如果为None，从 LOG_MODULE_MODE 环境变量读取，默认为 'short'
    
    Returns:
        root logger实例
    
    示例:
        # 方式1: 使用默认配置（短模式）
        setup_logging()
        
        # 方式2: 指定缩略模式
        setup_logging(module_name_mode='abbr')
        
        # 方式3: 完整配置
        setup_logging(level='DEBUG', enable_file=True, module_name_mode='short')
    """
    
    # 获取有效的日志级别
    log_level = get_log_level(level)
    level_name = [k for k, v in LOG_LEVELS.items() if v == log_level][0]
    
    # 获取模块名缩略模式
    if module_name_mode is None:
        module_name_mode = MODULE_NAME_MODE
    
    # 获取root logger
    root_logger = logging.getLogger()
    
    # 清除现有处理器（防止重复）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.setLevel(log_level)
    
    # ========================================================================
    # 1. 控制台处理器 (stdout)
    # ========================================================================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ShortenedNameFormatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT, mode=module_name_mode)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # ========================================================================
    # 2. 文件处理器 (可选)
    # ========================================================================
    if enable_file:
        # 创建日志目录
        log_path = Path(LOG_DIR)
        log_path.mkdir(exist_ok=True)

        # log_file_name 参数优先，否则使用模块级 LOG_FILE 常量
        effective_log_file = log_file_name if log_file_name else LOG_FILE
        log_file_path = log_path / effective_log_file
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_formatter = ShortenedNameFormatter(FILE_FORMAT, datefmt=DATE_FORMAT, mode=module_name_mode)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # ========================================================================
    # 3. 记录初始化信息
    # ========================================================================
    root_logger.info(
        f"Logging module initialized: level={level_name}, module_name_mode={module_name_mode},file_output={'enabled' if enable_file else 'disabled'}"
    )
    
    return root_logger


def get_logger(name):
    """
    获取模块特定的logger
    
    Args -> Any:
        name: logger名称，通常使用 __name__
    
    Returns:
        logger实例
    
    示例:
        logger = get_logger(__name__)
        logger.info("这是一条信息")
    """
    return logging.getLogger(name)


# ============================================================================
# Uvicorn 日志配置（带时间戳，与项目日志格式对齐）
# ============================================================================

def get_uvicorn_log_config() -> dict:
    """Return a logging config dict for uvicorn with millisecond timestamps."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "format": "%(asctime)s.%(msecs)03d | %(levelname)-5s | uvicorn              | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "format": '%(asctime)s.%(msecs)03d | ACCESS  | uvicorn              | %(client_addr)s - "%(request_line)s" %(status_code)s',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }

def set_log_level(level):
    """
    运行时改变日志级别
    
    Args -> Any:
        level: 日志级别名称 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    
    示例:
        set_log_level('DEBUG')  # 动态改为DEBUG级别
    """
    log_level = get_log_level(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(log_level)
    
    root_logger.info(f"日志级别已更改为: {level.upper()}")


# ============================================================================
# 便捷函数
# ============================================================================

def debug(msg, *args, **kwargs):
    """便捷函数: 记录DEBUG级别日志"""
    logging.getLogger().debug(msg, *args, **kwargs)


def info(msg, *args, **kwargs) -> Any:
    """便捷函数: 记录INFO级别日志"""
    logging.getLogger().info(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    """便捷函数: 记录WARNING级别日志"""
    logging.getLogger().warning(msg, *args, **kwargs)


def error(msg, *args, **kwargs) -> Any:
    """便捷函数: 记录ERROR级别日志"""
    logging.getLogger().error(msg, *args, **kwargs)


def critical(msg, *args, **kwargs):
    """便捷函数: 记录CRITICAL级别日志"""
    logging.getLogger().critical(msg, *args, **kwargs)


# ============================================================================
# 模块级初始化 (模块被导入时自动执行)
# ============================================================================

# 注意: 这个模块被导入时，日志系统不会自动初始化
# 需要在应用启动时显式调用 setup_logging()
#
# 推荐在应用入口点添加 -> Any:
#   from conf.logging_config import setup_logging
#   setup_logging()  # 或 setup_logging(level='DEBUG')

__all__ = [
    'setup_logging',
    'get_logger',
    'set_log_level',
    'get_log_level',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'LOG_LEVELS',
    'DEFAULT_LOG_LEVEL',
]
