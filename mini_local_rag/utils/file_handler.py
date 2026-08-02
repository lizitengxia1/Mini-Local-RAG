import os
from typing import List

# 导入项目通用工具、异常、装饰器
from utils.decorators import log_recorder, timer, FileOperationError

# ------模块化私有常量（文件白名单）----
SUPPORT_SUFFIX = {".txt", ".md" ,".pdf"}

@timer
@log_recorder
def check_file_suffix(file_path: str) -> bool:
    """
    校验文件后缀是否在支持读取的白名单内
    Args:
        file_path: 文件绝对/相对路径
    Returns:
        合法文件返回True
    Raises:
        FileOperationError: 文件后缀不支持
    """
    # 提取文件后缀，统一小写避免大小写干扰
    suffix = os.path.splitext(file_path)[-1].lower()
    if suffix not in SUPPORT_SUFFIX:
        raise FileOperationError(f"不支持的格式 {suffix}，仅支持{SUPPORT_SUFFIX}")
    return True

@timer
@log_recorder
def read_text_file(file_path: str, encoding: str = "utf-8") -> str:
    """
    读取单个文本文件内容，自动校验路径、文件格式
    Args:
        file_path: 文件路径
        encoding: 文件编码，默认utf-8
    Returns:
        文件完整文本字符串
    Raises:
        FileOperationError: 文件不存在、格式不支持、读写失败
    """
    # 1. 判断文件是否真实存在
    if not os.path.isfile(file_path):
        raise FileOperationError(f"目标文件不存在：{file_path}")

    # 2. 校验文件后缀合法性
    check_file_suffix(file_path)

    # 3. 读取文件，捕获原生IO异常，转换为项目统一业务异常
    try:
        with open(file_path, "r", encoding=encoding) as f:
            content = f.read()
    except IOError as e:
        raise FileOperationError(f"文件读取失败：{str(e)}") from e
    return content

@timer
@log_recorder
def scan_dir_files(dir_path: str) -> List[str]:
    """
    递归扫描文件夹，过滤所有支持的文档，返回文件绝对路径列表
    Args:
        dir_path: 目标文件夹路径
    Returns:
        合法文件路径列表
    Raises:
        FileOperationError: 目标路径不是文件夹
    """
    if not os.path.isdir(dir_path):
        raise FileOperationError(f"目标路径不是有效文件夹：{dir_path}")
    
    file_path_list = []
    # 递归遍历目录
    for root, _, files in os.walk(dir_path):
        for file_name in files:
            full_path = os.path.join(root, file_name)
            try:
                # 校验后缀
                check_file_suffix(full_path)
                file_path_list.append(full_path)
            except FileOperationError:
                # 后缀不支持直接跳过，不中断遍历
                continue
    return file_path_list
