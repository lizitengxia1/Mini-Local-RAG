import os 
import sys
# 路径兼容适配
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.file_handler import scan_dir_files
from utils.decorators import TextSplitError
from utils.text_splitter import batch_split_files, split_sentence, split_text_by_chunck

# ---------------- 测试1：分句函数 split_sentence ----------------
def test_01_split_sentence():
    print("===== 自测1：中文分句测试 =====")
    test_text = "人工智能是什么？大模型可以做RAG检索。本地知识库部署简单！"
    try:
        sentences = split_sentence(test_text)
    except Exception as e:
        print("分割抛出异常：", type(e), str(e))
    # print("拆分后的句子列表：",sentences)
    # print("实际句子数量：", len(sentences))
    # 预期拆分3句
    assert len(sentences) == 3
    print("正常文本分句通过")

    #反向：空文本预期抛出异常
    try:
        split_sentence("   ")
    except TextSplitError:
        print("空文本拦截异常通过")

# test_01_split_sentence()

# ---------------- 测试2：定长分块 split_text_by_chunk ----------------
def test_02_split_chunk():
    print("\n===== 自测2：定长重叠分块测试 =====")
    # 构造长测试文本
    long_text = "这是第一句。这是第二句。这是第三句。这是第四句。这是第五句。"
    # 设置小分块长度，强制切分多块
    chunks = split_text_by_chunck(long_text, chunk_size=20, overlap=5)
    # print("chunks结果：", chunks)
    assert len(chunks) > 1
    print("长文本自动分块通过")

    # 反向：重叠大于块长度，预期报错
    try:
        split_text_by_chunck(long_text, chunk_size=20, overlap=30)
    except TextSplitError:
        print("非法重叠参数拦截异常通过")

# test_02_split_chunk()

# ---------------- 测试3：批量文件分块 batch_split_files ----------------
def test_03_batch_split():
    print("\n===== 自测3：批量文件读取+分块 =====")
    # 创建临时测试目录与文件
    temp_dir = "temp_split_dir"
    os.makedirs(temp_dir, exist_ok=True)
    test_file = os.path.join(temp_dir, "rag_test.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("RAG检错增强生成技术。分为文档加载、文本分割、向量存储、检索问答四步。")
    # 扫描文件路径
    file_list = scan_dir_files(temp_dir)
    # 批量分割
    chunk_data = batch_split_files(file_list)
    assert len(chunk_data) > 0
    # 校验来源路径
    assert chunk_data[0]["source"] == test_file
    print("批量文件分块执行正常")

    # 反向
    try:
        batch_split_files([])
    except TextSplitError:
        print("空文件列表拦截异常通过")

    # 清理临时资源
    os.remove(test_file)
    os.rmdir(temp_dir)

test_03_batch_split()