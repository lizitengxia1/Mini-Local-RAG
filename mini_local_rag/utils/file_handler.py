import hashlib
import os
from typing import List

from numpy.compat import Path

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

def get_file_fingerprint(dir_path: Path) -> str:
    """
    计算文档目录的指纹（基于所有文件的修改时间 + 大小 + 相对路径）
    用于检测知识库是否发生了新增、修改或删除。
    
    Args:
        doc_dir: 文档根目录 (Path 对象)
        
    Returns:
        32位 MD5 十六进制字符串，如果目录不存在则返回空字符串。
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return ""

    hasher = hashlib.md5()
    # 递归获取所有文件（按路径排序保证一致性）
    file_paths: List[Path] = sorted(dir_path.rglob("*"))
    for file_path in file_paths:
        if file_path.is_file():
            # 忽略隐藏文件（如 .DS_Store）和临时文件（以 ~ 结尾）
            if file_path.name.startswith(".") or file_path.name.endswith("~"):
                continue
            try:
                # file_path.stat()返回一个包含 最后修改时间、文件大小、创建时间、最后访问时间的对象
                stat = file_path.stat()
                # 关键：组合 相对路径 + 修改时间 + 文件大小
                relative_path = str(file_path.relative_to(dir_path))
                hasher.update(relative_path.encode("utf-8"))
                hasher.update(str(stat.st_mtime).encode("utf-8")) # 记录修改时间
                hasher.update(str(stat.st_size).encode("utf-8")) # 记录文件大小
            except OSError:
                # 文件权限问题，跳过
                continue
                
    return hasher.hexdigest()

def load_stored_fingerprint(fingerprint_path: Path) -> str:
    """从指定路径读取上次保存的指纹"""
    if fingerprint_path.exists():
        return fingerprint_path.read_text(encoding="utf-8").strip()
    return ""

def save_fingerprint(fingerprint_path: Path, fingerprint: str) -> None:
    """保存指纹到指定路径（目录不存在则自动创建）"""
    fingerprint_path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint_path.write_text(fingerprint, encoding="utf-8")


def is_knowledge_updated(dir_path: Path, fingerprint_path: Path) -> bool:
    """
    高层封装：一步判断知识库是否需要重建
    Returns:
        True: 需要重建（首次运行 / 文件有变动 / 缓存失效）
        False: 无需重建，直接读缓存即可
    """
    current_fp = get_file_fingerprint(dir_path)
    stored_fp = load_stored_fingerprint(fingerprint_path)
    
    # 如果 doc_dir 为空或不存在，指纹返回 ""，与 stored_fp 对比
    if current_fp != stored_fp:
        # 指纹不匹配，需要重建
        return True
    return False
