# tests/test_vector_engine.py
import os
import sys

# 路径兼容，解决导包报错
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.vector_engine import LocalVectorStore
from utils.text_splitter import batch_split_files
from utils.file_handler import scan_dir_files
from utils.decorators import VectorEngineError

# 初始化向量库实例
vec_store = LocalVectorStore()
temp_dir = "temp_vector_test"

def test_01_batch_import():
    print("===== 测试1：批量文档向量化入库 =====")
    # 创建临时测试文档
    os.makedirs(temp_dir, exist_ok=True)
    test_file = os.path.join(temp_dir, "rag_knowledge.txt")
    content = """RAG检索增强生成分为四大核心步骤。
1. 文档加载：读取本地txt/md知识库文件；
2. 文本分割：分句后滑动窗口分块，保留块间重叠上下文；
3. 向量化：文本转为384维语义向量存入内存向量库；
4. 语义检索：匹配用户问题最相关的文本片段给大模型。"""
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)
    # 扫描文件 + 分局分块
    file_list = scan_dir_files(temp_dir)
    chunk_data = batch_split_files(file_list)
    # 批量入库
    vec_store.batch_add_chunks(chunk_data)
    meta = vec_store.get_allmeta()
    assert len(meta) > 0
    print(f"入库完成，共存储{len(meta)}条文本块")

    # 反向用例
    try:
        vec_store.batch_add_chunks([])
    except VectorEngineError:
        print("空列表拦截异常通过")

# test_01_batch_import()
def test_02_search_similar():
    print("\n===== 测试2：Top-K相似度检索 =====")
    query = "RAG完整执行流程有几步？"
    res = vec_store.search_top_similar(query, top_k=2)
    assert len(res) == 2
    print("检索匹配结果：")
    for score, info in res:
        print(f"相似度：{score:.4f} | 原文：{info['chunk_text']}")

    # 反向用例：空提问、非法top_k
    try:
        vec_store.search_top_similar("   ")
    except VectorEngineError:
        print("空提问拦截异常通过")
    try:
        vec_store.search_top_similar("RAG是什么", top_k=0)
    except VectorEngineError:
        print("非法top_k参数拦截异常通过")

def test_03_clear_vector_store():
    print("\n===== 测试3：清空向量库 =====")
    vec_store.clear_store()
    assert len(vec_store.get_all_meta()) == 0
    # 空库检索报错
    try:
        vec_store.search_top_similar("测试")
    except VectorEngineError:
        print("空库检索拦截异常通过")
    print("向量库清空功能正常")

if __name__ == "__main__":
    try:
        test_01_batch_import()
        test_02_search_similar()
        test_03_clear_vector_store()
        print("\n✅ vector_engine 全部测试用例执行完成")
    finally:
        # 自动清理临时文件
        f_path = os.path.join(temp_dir, "rag_knowledge.txt")
        if os.path.exists(f_path):
            os.remove(f_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)