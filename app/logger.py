"""日志模块"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "multi_agent",
    log_level: str = "INFO",
    log_dir: str = "logs",
) -> logging.Logger:
    """设置日志"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_file = log_path / f"multi_agent_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# 全局日志实例
logger = setup_logger()
