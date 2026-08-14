# 【版本局限注释】
# 当前版本：单进程设计。
# 如果多个进程同时运行：进程A load_cache读完释放锁之后，进程B save_cache更新磁盘；
# 进程A内存仍然是旧向量，不会自动感知磁盘变化。
# 后续迭代：版本号/mtime检测 或者 迁移sqlite/pgvector。
from abc import ABC, abstractmethod
import hashlib
import json
import os
import time
from typing import Dict, List, Tuple

import numpy as np
from numpy.compat import Path

from utils.decorators import (
    CacheCorruptedError,
    VectorEngineError, 
    CacheFileMissingError,
    CacheDimensionMismatchError,
    CacheDataInconsistentError,
    CacheLockConflictError,
    MetaListEmpty,
    VectorArrayEmpty,
    VectorStoreMemoryEmptyError,
    log_recorder, 
    timer
)
import logging
logger = logging.getLogger(__name__)
# 全局配置常量
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 3
MAX_RETRY = 8       # 最多重试8次
RETRY_DELAY = 0.05  # 每次等待50ms


# 模块化私有工具函数
def _calc_file_sha256(file_path: Path) -> str:
    """
    分块流式计算文件SHA256，规避大文件内存溢出
    :raises FileNotFoundError: 文件不存在时抛出，交由上层业务处理
    """
    sha256_handler = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                sha256_handler.update(chunk)
    except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在：{file_path}")
    return sha256_handler.hexdigest()

def _is_pid_alive(pid: int) -> bool:
    """
    Linux/WSL进程存活探测（kill -0 非杀伤探测）
    :return: True进程存活 False进程消亡
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        # 进程已死
        return False
    except PermissionError:
        # 无权限探测=进程存活
        return True
    
def _is_orphan_lock(lock_path: Path) -> bool:
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text(encoding="utf-8").strip())
            if _is_pid_alive(pid):
                return False
            else:
                return True
        except (ValueError, UnicodeDecodeError):
            # 文件损坏 无法解析pid 视为孤儿锁
            return True
    else:
        return False
    
class BaseVectorStore(ABC):

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

    @abstractmethod
    def _insert_single(self, emb_vec: np.ndarray, chunk_data: Dict) -> None:
        pass

    @abstractmethod
    def add_text_chunk(self, chunk_data: Dict, embedding_func):
        """
        单条文本分块向量化入库
        :param chunk_data: {"source": 文件路径, "chunk_text": 文本片段}
        """
        pass

    @abstractmethod
    def batch_add_chunks(self, chunk_list: List[Dict], embedding_func) -> None:
        """
        批量写入文本分片并生成向量
        工业规范：本实现仅更新内存，持久化由显式save_cache触发（高频IO优化）
        :param chunk_list: 分片元数据列表，包含text/source等字段
        :param embedding_func: 外部传入向量生成回调函数
        """
        pass

    @abstractmethod
    def search_topk(self, query_embedding: np.ndarray, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        """
        用户提问语义检索，返回Top-K相似文本
        :param query: 用户问题
        :param top_k: 返回匹配条数
        :return: [(相似度分数, 元数据字典)] 降序排列
        """
        pass

    @abstractmethod
    def clear_cache(self):
        """清空内存数据 + 删除磁盘缓存"""
        pass

    @abstractmethod
    def save_cache(self) -> None:
        """将当前内存向量快照原子化持久化至磁盘（扩展标准接口）"""
        pass

    @abstractmethod
    def load_cache(self) -> bool:
        """加载磁盘缓存至内存，返回True=加载成功 False=无可用缓存"""
        pass

class NpyJsonVectorStore(BaseVectorStore):
     # 版本边界注释（工业强制标注架构局限）
    """
    架构约束：单进程设计
    风险边界：load_cache释放读锁后，其他进程更新磁盘缓存时，当前进程内存不会自动刷新
    后续迭代方向：mtime版本校验 / SQLite向量引擎 / pgvector
    """

    # 类变量：所有实例共享同一个模型对象
    _shared_model = None
    def __init__(self,  dimension: int, cache_dir: str | Path):
        # 缓存根目录
        self.cache_dir: Path = Path(cache_dir)
        # 业务文件路径
        self.vec_npy_path: Path = self.cache_dir / "vectors.npy"
        self.meta_json_path: Path = self.cache_dir / "meta.json"
        self.check_path: Path = self.cache_dir / "check.json"
        # 锁文件
        self.lock_path: Path = self.cache_dir / "cache.lock"

        # 内存运行时数据
        self._dimension: int = dimension # 模型向量维度
        self._vectors: np.ndarray = np.empty((0, self._dimension), dtype=np.float32)
        self._metas: List[dict] = []

        # 标记：当前实例是否持有锁
        self._has_lock: bool = False

        # 确保缓存文件夹存在，不存在就创建
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _acquire_exclusive_lock(self) -> None:
        """获取独占写锁，孤儿锁由上层检测并清理"""
        if self._has_lock:
            raise CacheLockConflictError("当前实例已经持有排他锁，禁止重复获取锁")

        # 判断是否孤儿锁
        if _is_orphan_lock(self.lock_path):
            # 确认孤儿锁，在此处执行删除 先判断再删除
            if self.lock_path.exists():
                self.lock_path.unlink()

        # 删除孤儿锁之后，如果锁文件还存在：说明有别的**活跃进程**抢占持有锁
        if self.lock_path.exists():
            raise CacheLockConflictError("其他进程正在占用缓存排他锁，请稍后重试")

        # 写入本进程PID，占有锁
        self.lock_path.write_text(str(os.getpid()), encoding="utf-8")
        self._has_lock = True

    def _release_lock(self) -> None:
        """安全释放锁，仅实例持有锁时执行删除"""
        if self._has_lock and self.lock_path.exists():
            self.lock_path.unlink()
        self._has_lock = False

    def _get_model(self):
        """
        懒加载 SentenceTransformer 模型 :使用国内镜像加速
        """
        if NpyJsonVectorStore._shared_model is not None:
            return NpyJsonVectorStore._shared_model

        import os
        # 设置镜像站（hf-mirror.com 是官方推荐的国内镜像）
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from sentence_transformers import SentenceTransformer
        # 这里不需要指定路径，它会自动去镜像站下载（如果缓存没有的话）
        # 缓存位置：~/.cache/huggingface/hub/
        NpyJsonVectorStore._shared_model = SentenceTransformer(DEFAULT_MODEL_NAME)
        self._dimension = NpyJsonVectorStore._shared_model.get_embedding_dimension()
        return NpyJsonVectorStore._shared_model

    def _insert_single(self, emb_vec: np.ndarray, chunk_data: Dict) -> None:
        """
        【私有底层】只接收算好的向量，只操作内存
        ❗不调用任何embedding、无网络IO
        """
        emb_vec = emb_vec.reshape(1, -1)
        if self._vectors.size == 0:
            self._vectors = emb_vec 
        else:
            self._vectors = np.vstack([self._vectors, emb_vec])
        self._metas.append(chunk_data)

    def add_text_chunk(self, chunk_data: Dict, embedding_func=None):
        """对外单条接口：只给外部真正单次新增使用，禁止batch内部调用"""
        # 入参校验
        if "chunk_text" not in chunk_data or not chunk_data["chunk_text"].strip():
            raise VectorEngineError("分块文本不能为空，缺失chunk_text字段")
        text = chunk_data["chunk_text"]
        if embedding_func is not None:
            # 测试传入mock_embed
            emb_vec = embedding_func(text)
        else:
            # 生产环境，外部没传函数，出发懒加载(第一次调用才会加载模型)
            model = self._get_model()
            emb_vec = model.encode(text)
        self._insert_single(emb_vec, chunk_data)

    def batch_add_chunks(self, chunk_list: List[Dict], embedding_func=None) -> None:
        """批量，预计算全部存入临时buffer，全部成功再写内存，保证原子性"""
        if not chunk_list:
            raise VectorEngineError("待入库分块数据列表不能为空")

        temp_buffer: List[Tuple[np.ndarray, Dict]] = []
        # 阶段1：全部做向量化，只写临时buffer，完全不动实例内存
        for chunk in chunk_list:
            if "chunk_text" not in chunk or not chunk["chunk_text"].strip():
                raise VectorEngineError("分块文本不能为空，缺失chunk_text字段")

            if embedding_func is not None:                
                vec = embedding_func(chunk["chunk_text"].strip())
            else:
                model = self._get_model()
                vec = model.encode(chunk["chunk_text"].strip())
            temp_buffer.append((vec, chunk))

        # 阶段2：全部向量化无异常，才写入实例内存
        for vec, chunk in temp_buffer:
            self._insert_single(vec, chunk)

    def search_topk(self, query_embedding: np.ndarray, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        """
        内存内向量余弦相似度检索底层方法，输入已经embedding完成的查询向量，返回相似度最高的top‑k元数据列表
        注意：本函数只接收向量，不做文本向量化；对外上层调用请使用 batch_add_chunks

        Args:
            query_embedding: 查询语句经过Embedding模型输出的一维向量, np.ndarray
            top_k: 需要返回的最相似结果条数

        Returns:
            List[Dict]: 匹配到的chunk元数据列表；向量库为空时返回空列表[]

        Notes:
            当前实现：全部计算相似度后使用np.argsort全局排序。
            当向量规模极大(N >> top_k)，可优化为堆top‑k / np.argpartition，降低时间与空间开销。
        """
        if self._vectors.shape[0] == 0:
            return []
        if top_k < 1:
            raise VectorEngineError(f"k值不能小于1！")
        query = query_embedding.astype(np.float32)
        norm_q = np.linalg.norm(query)
        norm_all = np.linalg.norm(self._vectors, axis=1)
        similarity = np.dot(self._vectors, query) / (norm_all * norm_q + 1e-8)
        top_idx = np.argsort(similarity)[::-1][:top_k]
        return [self._metas[i] for i in top_idx]
    def query_encode(self, user_query: str) -> np.ndarray:
        """仅处理question text"""
        if not user_query or not user_query.strip():
            return []
        start_time = time.perf_counter()
        model = self._get_model()
        print(f"model加载成功，耗时：{round(time.perf_counter() - start_time, 4)}seconds")
        query_vec = model.encode(user_query.strip())
        return query_vec
        
    def save_cache(self) -> None:
        # 空向量前置校验，预警误覆盖风险
        if self._vectors.shape[0] == 0:
            logger.warning("内存向量为空，将写入空缓存文件，请确认是否为首次运行或数据源无内容")
        # 临时文件原子写入规范
        tmp_vec = self.cache_dir / "vectors.tmp.npy"
        tmp_meta = self.cache_dir / "meta.tmp.json"
        tmp_check = self.cache_dir / "check.tmp.json"
        try:
            self._acquire_exclusive_lock()
            # 写入临时文件
            np.save(tmp_vec, self._vectors)
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump({"meta_list": self._metas}, f, ensure_ascii=False, indent=2)
            # 强制内核刷盘（工业关键步骤，杜绝页缓存丢失）
            vec_fd = os.open(tmp_vec, os.O_RDWR)
            os.fsync(vec_fd)
            os.close(vec_fd)
            meta_fd = os.open(tmp_meta, os.O_RDWR)
            os.fsync(meta_fd)
            os.close(meta_fd)
            # 计算临时文件指纹写入元数据
            vec_hash = _calc_file_sha256(tmp_vec)
            meta_hash = _calc_file_sha256(tmp_meta)
            if tmp_check.exists():
                tmp_check_data = json.loads(tmp_check.read_text(encoding="utf-8"))
            else:
                tmp_check_data = {}
            tmp_check_data["vec_sha256"] = vec_hash
            tmp_check_data["meta_sha256"] = meta_hash
            tmp_check_data["record_count"] = int(self._vectors.shape[0])  # 记录数量，便于load判断
            # 写入check文件
            tmp_check.write_text(
                json.dumps(tmp_check_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            # 再刷一遍脏页
            fd = os.open(tmp_check, os.O_RDWR)
            os.fsync(fd)
            os.close(fd)
            # 原子rename替换正式文件（系统调用原子性保障）
            os.replace(tmp_vec, self.vec_npy_path)
            os.replace(tmp_meta, self.meta_json_path)
            os.replace(tmp_check, self.check_path)
            logger.info(f"缓存保存成功，向量数: {self._vectors.shape[0]}")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            # 异常时清理残留临时文件，防止垃圾文件堆积
            for tmp_file in (tmp_vec, tmp_meta, tmp_check):
                if tmp_file.exists():
                    tmp_file.unlink()
            raise VectorEngineError(f"缓存写入磁盘失败")    
        finally:
            # finally强制释放锁，异常场景绝不死锁（工业容错核心）
            self._release_lock()

    def load_cache(self) -> bool:
        if not self.vec_npy_path.exists() or not self.meta_json_path.exists():
            logger.info("缓存文件不存在，跳过加载")
            return False
        self._acquire_exclusive_lock() # 上锁要在try之前
        try:
            # 调用之前强制清理内存
            self._vectors = np.empty((0, self._dimension), dtype=np.float32)
            self._metas.clear()

            if not self.check_path.exists():
                logger.error("check.json 不存在，无法验证完整性")
                self.clear_cache()
                return False
            try:
                # 读取基准哈希
                check_path_data = json.loads(self.check_path.read_text(encoding="utf-8"))
                std_vec_hash = check_path_data.get("vec_sha256")
                std_meta_hash = check_path_data.get("meta_sha256")
                record_count = check_path_data.get("record_count", -1)
                
                # 如果是空缓存，直接加载空数据（跳过哈希验证）
                if record_count == 0:
                    logger.info("加载空缓存（首次运行或数据为空）")
                    return True

                if not std_vec_hash or not std_meta_hash:
                    logger.info("缓存缺失校验指纹")
                    self.clear_cache()
                    return False
                else:
                    # 实时校验当前文件哈希
                    now_vec_hash = _calc_file_sha256(self.vec_npy_path)
                    now_meta_hash = _calc_file_sha256(self.meta_json_path)
                    if now_vec_hash != std_vec_hash or now_meta_hash != std_meta_hash:
                        logger.error(f"向量文件哈希不匹配: 期望={std_vec_hash[:8]}..., 实际={now_vec_hash[:8]}...")
                        logger.error(f"元数据文件哈希不匹配: 期望={std_meta_hash[:8]}..., 实际={now_meta_hash[:8]}...")

                        # 删除所有相关的缓存文件
                        self.clear_cache()      
                        return False
            except  json.JSONDecodeError as e:
                logger.error(f"check.json 格式损坏: {e}")
                self.clear_cache()
                return False 
            
            # 加载至内存
            self._vectors = np.load(self.vec_npy_path).astype(np.float32)
            with open(self.meta_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._metas = data["meta_list"]

            # 验证数据一致性
            if len(self._metas) != self._vectors.shape[0]:
                logger.error(f"数据不一致: 向量数={self._vectors.shape[0]}, 元数据数={len(self._metas)}")
                self.clear_cache()
                return False
                
            logger.info(f"缓存加载成功，向量数: {self._vectors.shape[0]}")   
            return True
        except CacheCorruptedError:
            logger.error("缓存损坏")
            self.clear_cache()
            return False
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            self.clear_cache()
            return False
        finally:
            self._release_lock()

    def clear_cache(self) -> None:
        should_release = False
        if not self._has_lock:
            self._acquire_exclusive_lock()
            should_release = True
        try:
            self._vectors = np.empty((0, self._dimension), dtype=np.float32)
            self._metas.clear()
            for file in [self.vec_npy_path, self.meta_json_path, self.check_path]:
                if file.exists():
                    file.unlink()
                    logger.info(f"已删除缓存文件: {file.name}")
        finally:
            if should_release:
                self._release_lock()

        # finally:
        #     self._release_lock()

# if __name__ == "__main__":
#     _calc_file_sha256("./test_none.txt")



    