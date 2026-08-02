from typing import Dict, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.decorators import VectorEngineError, log_recorder, timer

# 全局配置常量
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 3

class LocalVectorStore:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        """
        本地内存向量库初始化
        :param model_name: 预训练句向量模型名称
        """
        try:
        # vec_store = LocalVectorStore()
            # 加载嵌入模型，首次自动下载缓存
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception as e:
            raise VectorEngineError(f"嵌入模型加载失败，网络无法访问或本地无缓存：{str(e)}") from e
        # 二维numpy数组：每组对应一行文本384维向量
        self.vector_array: np.ndarray = np.array([])
        # 元数据列表：与vector_array下标完全对齐
        self.meta_list: List[Dict] = []

    @staticmethod
    def _calc_cosine_sim(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        私有静态方法：手动计算余弦相似度
        :param vec1: 查询向量
        :param vec2: 库内存量向量
        :return: [-1,1] 相似度分数
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        # 零向量保护，避免除以0报错
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1*norm2))
    
    @timer 
    @log_recorder 
    def add_text_chunk(self, chunk_data: Dict):
        """
        单条文本分块向量化入库
        :param chunk_data: {"source": 文件路径, "chunk_text": 文本片段}
        """
        # 入参校验
        if "chunk_text" not in chunk_data or not chunk_data["chunk_text"].strip():
            raise VectorEngineError("分块文本不能为空，缺失chunk_text字段")
        text = chunk_data["chunk_text"]
        # 文本转向量
        emb_vec = self.model.encode(text)
        # 保存元数据
        self.meta_list.append(chunk_data)
        # 向量拼接处理
        if self.vector_array.size == 0:
            # 一维向量转为单行二维数组，用于vstack堆叠
            self.vector_array = emb_vec.reshape(1, -1)
        else:
            self.vector_array = np.vstack([self.vector_array, emb_vec])

    @timer
    @log_recorder
    def batch_add_chunks(self, chunk_data_list: List[Dict]):
        """
        批量入库，对接text_splitter批量输出
        :param chunk_data_list: 分块结构化列表
        """
        if not chunk_data_list:
            raise VectorEngineError("待入库分块数据列表不能为空")
        for chunk in chunk_data_list:
            self.add_text_chunk(chunk)

    def search_top_similar(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Tuple[float, Dict]]:
        """
        用户提问语义检索，返回Top-K相似文本
        :param query: 用户问题
        :param top_k: 返回匹配条数
        :return: [(相似度分数, 元数据字典)] 降序排列
        """
        # 多层参数拦截
        if not query.strip():
            raise VectorEngineError("检索提问不能为空")
        if self.vector_array.size == 0:
            raise VectorEngineError("向量库为空，请先导入文档数据")
        if top_k <= 0:
            raise VectorEngineError("top_k必须为正整数")
        
        # 提问向量化
        query_vec = self.model.encode(query)
        sim_result = []
        # 暴力遍历全部向量计算相似度
        for idx, vec in enumerate(self.vector_array):
            score = self._calc_cosine_sim(query_vec, vec)
            sim_result.append((score, self.meta_list[idx]))
        # 相似度从高到低排序
        sim_result.sort(key=lambda x: x[0], reverse=True)
        # 截取前top_k返回
        return sim_result[:top_k]
      
    def search_top_chunks(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        """
        专供RAG流程调用，直接返回纯分片字典列表，丢弃相似度分数
        """
        sim_tuple_list = self.search_top_similar(query, top_k)
        return [meta for (score, meta) in sim_tuple_list]

    def clear_store(self):
        """清空内存向量库与所有元数据"""
        self.vector_array = np.array([])
        self.meta_list = []

    def get_all_meta(self) -> List[Dict]:
        """获取全部入库文档元数据（测试校验用）"""
        return self.meta_list.copy()
    
if __name__ == "__main__":
    vec_store = LocalVectorStore()
        # 加载嵌入模型，首次自动下载缓存
    # 模拟入库分片
    test_chunk = {"source": "rag_intro.txt", "chunk_text": "RAG分为四大步骤：加载、分割、向量化、检索"}
    vec_store.add_text_chunk(test_chunk)
    # 测试专用RAG检索方法
    res_chunks = vec_store.search_top_chunks("RAG流程是什么？")
    print("适配LLM的chunk列表：", res_chunks)
    # 打印结构确认：纯字典列表，无分数
    print("单条chunk格式：", res_chunks[0])
    