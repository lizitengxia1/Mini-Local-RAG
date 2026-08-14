import json
import gc
import time
from typing import Dict, List, Tuple
from numpy.compat import Path
from utils.file_handler import get_file_fingerprint, is_knowledge_updated, save_fingerprint, scan_dir_files
from utils.llm_client import LLMClient
from utils.text_splitter import batch_split_files
from utils.vector_engine import NpyJsonVectorStore
from utils.decorators import LLMRequestError, LLMRequestParseError, MetaListEmpty, VectorArrayEmpty, VectorEngineError, timer

# 当前main.py所在文件夹 依托当前文件位置生成绝对路径，不受运行目录影响
BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path(__file__).parent / "config.json"
CACHE_DIR = "cache"
MODEL_DIMENSION = 384
# 定义指纹文件路径（通常放在缓存目录下，因为它是缓存的附属品）
FINGERPRINT_PATH = Path(CACHE_DIR) / ".docs_fingerprint"

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit("错误：缺少config.json配置文件！")
    except json.JSONDecodeError:
        raise SystemExit("错误：config.json格式非法！")
config = load_config()
DEFAULT_URL=config["llm_url"]
DEFAULT_KEY=config["llm_key"]
DEFAULT_TOP_K = config["top_k"]
DIR_PATH = BASE_DIR / "docs"
ENABLE_MOCK = False
DEFAULT_LLM_MODEL = "qwen-plus"



@timer
def init_rag_pipeline(url: str, key: str, model_name: str, enable_mock: bool) -> Tuple[NpyJsonVectorStore, LLMClient]:
    vec_store = NpyJsonVectorStore(dimension=MODEL_DIMENSION, cache_dir=CACHE_DIR)
    llm_client = LLMClient(url, key, model_name, enable_mock)
    return vec_store, llm_client
@timer
def load_knowledge(vec_store: NpyJsonVectorStore) -> int:
    # 优先初始化，预防触发NameError
    metas = []
    vectors = []
    try:
        # 如果有缓存文件
        if vec_store.load_cache() and not is_knowledge_updated(DIR_PATH, FINGERPRINT_PATH):
            print(f"存在缓存文件,跳过向量生成")
            start_time = time.perf_counter()
            metas = vec_store._metas
            vectors = vec_store._vectors
            # print(f"磁盘文件存在，已成功加载！")
            print(f"✅ 从缓存加载完成，耗时：{round(time.perf_counter() - start_time, 4)}seconds")
            return len(metas)
        else:
            print(f"缓存文件更新或缓存文件损坏,全量加载开始")
            start_time = time.perf_counter()
            # 计算文件指纹并保存
            fp = get_file_fingerprint(DIR_PATH)
            save_fingerprint(FINGERPRINT_PATH, fp)
            file_path_list = scan_dir_files(DIR_PATH)
            # print(f"文件夹读入成功！文件路径列表：{file_path_list}\n")
            chunk_list = batch_split_files(file_path_list)
            vec_store.batch_add_chunks(chunk_list)
            vec_store.save_cache()
            print(f"📦 首次构建向量索引完成，耗时：{round(time.perf_counter() - start_time, 4)}seconds")
            return len(metas)
    except VectorEngineError as e:
        raise e
  
@timer
def rag_chat(user_query: str, vec_store: NpyJsonVectorStore, llm_client: LLMClient, top_k=DEFAULT_TOP_K) -> Tuple[str, List[str]]:
    # 前置校验
    if not isinstance(user_query, str) or len(user_query.strip()) == 0:
        raise ValueError("用户提问不能为空或非空字符串类型")
    # 最相似前top_k个chunk列表
    question_vec = vec_store.query_encode(user_query)
    chunk_list = vec_store.search_topk(question_vec, top_k)
    # 问题 + 源数据
    answer_text, source_path_list = llm_client.chat_with_rag(user_query,chunk_list)
    # print(f"标记result:{result}")
    return answer_text, source_path_list


if __name__ == "__main__":
    print("正在初始化RAG系统...")
    vec_store, llm_client = init_rag_pipeline(url=DEFAULT_URL, key=DEFAULT_KEY, model_name= DEFAULT_LLM_MODEL, enable_mock=ENABLE_MOCK)
    print("加载知识库文档...")
    load_knowledge(vec_store)
    print("✅ 系统就绪！输入问题进行问答，输入 exit 退出程序\n")
    while True:
        # 获取用户输入
        user_input = input("请输入你的问题：").strip()
        start_time = time.perf_counter()
        # 退出判断
        if user_input.lower() in ["exit", "quit"]:
            print("程序退出，再见！")
            break
        # 跳过空输入
        if not user_input:
            print("请输入有效问题：")
            continue
        answer_text, source_path_list = rag_chat(user_input, vec_store, llm_client)
        print(f"answer:{answer_text}")
        print(f"接受回调结果成功，耗时：{round(time.perf_counter() - start_time, 4)}seconds")
        gc.collect()