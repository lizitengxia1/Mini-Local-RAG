# tests/test_vector_engine.py
import os
import sys
import shutil
import tempfile
import numpy as np
from pathlib import Path

# 路径兼容
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.vector_engine import NpyJsonVectorStore
from utils.decorators import VectorEngineError, CacheCorruptedError

# ============================================================
# 测试配置
# ============================================================
TEST_DIMENSION = 384
TEST_TOP_K = 2

# ============================================================
# 辅助工具：Mock Embedding 函数（避免真实模型调用）
# ============================================================
def mock_embed(text: str) -> np.ndarray:
    """模拟向量化：根据文本长度返回不同向量，用于测试排序"""
    import hashlib
    hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
    np.random.seed(hash_val % 2**32)
    vec = np.random.randn(TEST_DIMENSION).astype(np.float32)
    return vec / np.linalg.norm(vec)  # 归一化，便于相似度计算

# ============================================================
# 测试夹具：每个测试独立临时目录
# ============================================================
def setup_test_env():
    """创建独立临时目录，返回 (cache_dir, engine)"""
    temp_dir = tempfile.mkdtemp(prefix="vector_test_")
    cache_dir = Path(temp_dir) / "cache"
    engine = NpyJsonVectorStore(cache_dir=cache_dir, dimension=TEST_DIMENSION)
    return cache_dir, engine

def teardown_test_env(cache_dir: Path):
    """清理测试临时目录"""
    if cache_dir.exists():
        shutil.rmtree(cache_dir.parent, ignore_errors=True)

# ============================================================
# 测试 01：初始化与首次加载
# ============================================================
def test_01_init_and_first_load():
    """首次运行无缓存文件，load_cache 返回 False，内存形状正确"""
    cache_dir, engine = setup_test_env()
    try:
        #验证目录创建
        assert cache_dir.exists(), "缓存目录未创建"
        # 验证内存初始状态
        assert engine._vectors.shape == (0, TEST_DIMENSION)
        assert len(engine._metas) == 0
        # 首次加载应返回False
        assert engine.load_cache() is False
        # 磁盘无残留文件
        assert not (cache_dir / "vectors.py").exists()
        assert not (cache_dir / "meta.json").exists()
        assert not (cache_dir / "check.json").exists()
        print("✅ test_01_init_and_first_load 通过")
    finally:
        teardown_test_env(cache_dir)
        
def test_02_batch_add_and_save():
    """批量添加数据 -> save_cache 持久化 -> 验证磁盘文件生成"""
    cache_dir, engine = setup_test_env()
    try:
                # 构造测试文本块
        chunks = [
            {"chunk_text": "RAG检索增强生成分为四大核心步骤", "source": "doc1"},
            {"chunk_text": "文档加载：读取本地txt/md知识库文件", "source": "doc1"},
            {"chunk_text": "文本分割：分句后滑动窗口分块", "source": "doc1"},
        ]
        # 批量入库(使用mock_embed)
        engine.batch_add_chunks(chunks, embedding_func=mock_embed)
        # 验证内存数据
        assert engine._vectors.shape[0] == 3
        assert len(engine._metas) == 3
        # 持久化到磁盘
        engine.save_cache()
        # 验证磁盘文件生成
        assert (cache_dir / "vectors.npy").exists()
        assert (cache_dir / "meta.json").exists()
        assert (cache_dir / "check.json").exists()
        print("✅ test_02_batch_add_and_save 通过")
    finally:
        teardown_test_env(cache_dir)

def test_03_load_from_disk():
    """保存 -> 新建实例 -> load_cache -> 数据完全一致"""
    cache_dir, engine_a = setup_test_env()
    try:
        # 1. 写入数据持久化
        chunks = [
            {"chunk_text": "苹果是一种水果", "source": "fruit"},
            {"chunk_text": "香蕉是一种热带水果", "source": "fruit"},
        ]
        engine_a.batch_add_chunks(chunks, embedding_func=mock_embed)
        engine_a.save_cache()
        # 记录原始数据用于对比
        excepted_vecs = engine_a._vectors.copy()
        excepted_metas = engine_a._metas.copy()

        # 新建实例(模拟程序重启)
        engine_b = NpyJsonVectorStore(cache_dir=cache_dir, dimension=TEST_DIMENSION)
        assert engine_b._vectors.shape[0] == 0 # 加载前为空

        # 从磁盘加载
        load_ok = engine_b.load_cache()
        assert load_ok is True
        assert engine_b._vectors.shape == (2, TEST_DIMENSION)
        assert np.allclose(engine_b._vectors, excepted_vecs, atol=1e-6)
        assert engine_b._metas == excepted_metas
        print("✅ test_03_load_from_disk 通过")
    finally:
        teardown_test_env(cache_dir)

def test_04_load_corrupted_cache():
    """手动损坏 vectors.npy, load_cache必须返回False"""
    cache_dir, engine_a = setup_test_env()
    try:
        # 正常存入缓存
        chunks = [{"chunk_text": "正常数据", "source": "test"}]
        engine_a.batch_add_chunks(chunks, embedding_func=mock_embed)
        engine_a.save_cache()

        # 损坏向量文件（追加垃圾字节）
        vec_path = cache_dir / "vectors.npy"
        with open(vec_path, "ab") as f:
            f.write(b"GARBAGE")

        # 新建实例加载，应失败
        new_engine = NpyJsonVectorStore(cache_dir=cache_dir, dimension=TEST_DIMENSION)
        load_ok = new_engine.load_cache()
        assert load_ok is False
        #内存应当被清空(Load_cache 异常分支会清空)
        assert new_engine._vectors.shape == (0, TEST_DIMENSION)
        print("✅ test_04_load_corrupted_cache 通过")
    finally:
        teardown_test_env(cache_dir)

def test_05_missing_check_file():
    """删除 check.json, load_cache 必须返回 False"""
    cache_dir, engine = setup_test_env()
    try:
        chunks = [{"chunk_text": "测试数据", "source": "test"}]
        engine.batch_add_chunks(chunks, embedding_func=mock_embed)
        engine.save_cache()

        # 删除 check.json
        (cache_dir / "check.json").unlink()

        new_engine = NpyJsonVectorStore(cache_dir=cache_dir, dimension=TEST_DIMENSION)
        load_ok = new_engine.load_cache()
        assert load_ok is False
        print("✅ test_05_missing_check_file 通过")
    finally:
        teardown_test_env(cache_dir)

def test_06_clear_cache():
    """clear_cache 清空内存且删除磁盘文件"""
    cache_dir, engine = setup_test_env()
    try: 
        chunks = [{"chunk_text": "待清除数据", "source": "test"}]
        engine.batch_add_chunks(chunks, embedding_func=mock_embed)
        engine.save_cache()

        # 确认文件存在
        assert (cache_dir / "vectors.npy").exists()
        assert (cache_dir / "meta.json").exists()

        # 执行清空
        engine.clear_cache()

        # 内存清空
        assert engine._vectors.shape == (0, TEST_DIMENSION)
        assert len(engine._metas) == 0
        # 磁盘文件删除
        assert not (cache_dir / "vectors.npy").exists()
        assert not (cache_dir / "meta.json").exists()
        assert not (cache_dir / "check.json").exists()
        print("✅ test_06_clear_cache 通过")
    finally:
        teardown_test_env(cache_dir)

def test_07_load_empty_cache():
    """保存空缓存 -> 加载时识别 record_count=0，返回 True 且内存为空"""
    cache_dir, engine = setup_test_env()
    try:
        # 直接保存空缓存
        engine.save_cache()
        # 验证check.json 中 record_count = 0
        check_data = json.loads((cache_dir / "check.json").read_text(encoding="utf-8"))
        assert check_data.get("record_count") == 0

        # 新建实例加载
        new_engine = NpyJsonVectorStore(cache_dir,dimension= TEST_DIMENSION)
        load_ok = new_engine.load_cache()
        assert load_ok is True
        assert new_engine._vectors.shape == (0, TEST_DIMENSION)
        assert len(new_engine._metas) == 0
        print("✅ test_07_load_empty_cache 通过")
    finally:
        teardown_test_env(cache_dir)

def test_08_exception_handling():
    """空列表、空文本、非法 top_k 等边界情况"""
    cache_dir, engine = setup_test_env()
    try:
        # 空列表入库
        try: 
            engine.batch_add_chunks([], embedding_func=mock_embed)
        except VectorEngineError as e:
            print(f" ✅ 空列表拦截: {e}")

        # 空文本入库
        try:
            engine.add_text_chunk({"chunk_text":"  "}, embedding_func=mock_embed)
        except VectorEngineError as e:
            print(f"  ✅ 空文本拦截: {e}")

        # 非法 top_k
        try:
            engine.search_topk(query_embedding=np.zeros(TEST_DIMENSION), top_k=0)
        except VectorEngineError as e:
            print(f"  ✅ 非法 top_k 拦截: {e}")

        print("✅ test_08_exception_handling 通过")
    finally:
        teardown_test_env(cache_dir)

def test_09_search_similarity():
    """入库后检索，验证相似度排序正确"""
    cache_dir, engine = setup_test_env()
    try:
        chunks = [
            {"chunk_text": "Python是一种编程语言", "source": "lang"},
            {"chunk_text": "RAG是检索增强生成技术", "source": "rag"},
            {"chunk_text": "机器学习需要大量数据", "source": "ml"},
        ]
        engine.batch_add_chunks(chunk_list=chunks)
        # 触发懒加载
        assert engine._model is not None

        # 查询向量 真实模型加载
        query_vec = engine._model.encode("RAG")
        # 检索
        top_k_chunks = engine.search_topk(query_embedding=query_vec, top_k=1)
        assert len(top_k_chunks) == 1
        assert "RAG是检索增强生成技术" == top_k_chunks[0]["chunk_text"]
        print("✅ test_09_search_similarity 通过")
    finally:
        teardown_test_env(cache_dir)


if __name__ == "__main__":
    import json
    import logging
    # print("🧪 开始执行 vector_engine 持久化功能测试")
    # test_01_init_and_first_load()
    # test_02_batch_add_and_save()
    # test_03_load_from_disk()

    logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # test_04_load_corrupted_cache()
    # test_05_missing_check_file()
    # test_06_clear_cache()   
    # test_07_load_empty_cache()
    # test_08_exception_handling()
    # test_09_search_similarity()