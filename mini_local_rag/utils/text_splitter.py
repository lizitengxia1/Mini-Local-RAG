import re
from typing import Dict, List

from utils.decorators import TextSplitError, log_recorder, timer
from utils.file_handler import read_text_file

# ---------------- 模块私有常量 ----------------
# 中文分句正则：匹配 。！？ 三种句末标点
SPLIT_SENTENCE_PATTERN = re.compile(r'([。！？])')
# 默认分块配置
DEFAULT_CHUNK_SIZE = 100
DEFAULT_OVERLAP = 10

def split_sentence(text: str) -> List[str]:
    """
    将长文本按中文句号、问号、感叹号拆分为完整句子列表
    Args:
        text: 原始完整文本字符串
    Returns:
        分句后的句子列表
    Raises:
        TextSplitError: 输入为空文本
    """
    if not text.strip():
        raise TextSplitError("待分割文本不能为空")
    # 正则拆分,保留分割标点
    sentence_parts = SPLIT_SENTENCE_PATTERN.split(text)
    # print("传入text", repr(text))
    # print("sentence_parts = ", sentence_parts)

    sentences = []
    # 拼接句子+标点
    for i in range(0, len(sentence_parts), 2):
        if i + 1 < len(sentence_parts):
            sent = sentence_parts[i] + sentence_parts[i+1]
            sent = sent.strip() 
            if sent:
                sentences.append(sent)
        else:
            last_part = sentence_parts[i].strip()
            if last_part:
                sentences.append(last_part)
    return sentences

@timer
@log_recorder
def split_text_by_chunck(
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP
) -> List[str]:
    """
    文本分块：先分句，再拼接为固定长度文本块，支持块重叠
    Args:
        text: 原始长文本
        chunk_size: 单块最大字符长度
        overlap: 块之间重叠字符数
    Returns:
        分割完成的文本块列表
    Raises:
        TextSplitError: 文本为空、重叠值大于等于块长度
    """
    # 边界参数校验
    if overlap >= chunk_size:
        raise TextSplitError(f"重叠长度{overlap}不能大于等于单块长度{chunk_size}")
    sentences = split_sentence(text)
    chunk_list = []
    current_chunk = ""
    for sent in sentences:
        # 加入句子后超出块长度，则生成新块
        if len(current_chunk + sent) > chunk_size and current_chunk:
            chunk_list.append(current_chunk)
            # 截取末尾overlap字符作为下一块上下文重叠
            current_chunk = current_chunk[-overlap:] + sent
        else:
            current_chunk += sent
    # 加入最后剩余文本
    if current_chunk:
        chunk_list.append(current_chunk)
    return chunk_list

@timer
@log_recorder
def batch_split_files(file_path_list:List[str]) -> List[Dict]:
    """
    批量处理多个文件：读取文件 + 文本分块，返回带来源路径的结构化数据
    Args:
        file_path_list: 文件绝对路径列表（来自scan_dir_files）
    Returns:
        [{"source": 文件路径, "chunk_text": 分块文本}]
    Raises:
        TextSplitError: 文件列表为空
    """
    if not file_path_list:
        raise TextSplitError("待处理文件路径列表不能为空")
    all_chunk_data = []
    for file_path in file_path_list:
        # 读取文件内容（复用file_handler）
        content = read_text_file(file_path)
        # 切割分块
        chunk_texts = split_text_by_chunck(content)
        # 封装结构化数据
        for chunk in chunk_texts:
            all_chunk_data.append({
                "source": file_path,
                "chunk_text": chunk
            })
    return all_chunk_data