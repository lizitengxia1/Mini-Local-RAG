import json
import gc
from typing import Dict, List, Tuple
from numpy.compat import Path
from utils.file_handler import scan_dir_files
from utils.llm_client import LLMClient
from utils.text_splitter import batch_split_files
from utils.vector_engine import LocalVectorStore
from utils.decorators import LLMRequestError, LLMRequestParseError, MetaListEmpty, VectorArrayEmpty, VectorEngineError
# 当前main.py所在文件夹 依托当前文件位置生成绝对路径，不受运行目录影响
BASE_DIR = Path(__file__).parent
CONFIG_PATH = Path(__file__).parent / "config.json"

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




def init_rag_pipeline(url: str, key: str, model_name: str, enable_mock: bool) -> Tuple[LocalVectorStore, LLMClient]:
    vec_store = LocalVectorStore()
    llm_client = LLMClient(url, key, model_name, enable_mock)
    return vec_store, llm_client

def load_knowledge(vec_store: LocalVectorStore) -> int:
    # 优先初始化，预防触发NameError
    chunk_list = []
    file_path_list = []
    try:
        # print(f"文件夹路径为：{DIR_PATH}")
        file_path_list = scan_dir_files(DIR_PATH)
        print(f"文件夹读入成功！文件路径列表：{file_path_list}\n")
        chunk_list = batch_split_files(file_path_list)
        vec_store.batch_add_chunks(chunk_list)
    except VectorEngineError as e:
        raise VectorEngineError(f"嵌入模型加载失败，网络无法访问或本地无缓存：{str(e)}") from e
    if len(vec_store.vector_array) == 0:
        raise VectorArrayEmpty(f"向量矩阵为空") 
    if len(vec_store.meta_list) == 0:
        raise MetaListEmpty(f"源数据列表为空")
    print(f"chunk_list准备完成，共计条数：{len(chunk_list)}\n")
    return len(chunk_list)
  

def rag_chat(user_query: str, vec_store: LocalVectorStore, llm_client: LLMClient, top_k=DEFAULT_TOP_K) -> Tuple[str, List[str]]:
    # 前置校验
    if not isinstance(user_query, str) or len(user_query.strip()) == 0:
        raise ValueError("用户提问不能为空或非空字符串类型")
    # 最相似前top_k个chunk列表
    chunk_list = vec_store.search_top_chunks(user_query, top_k)
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
        gc.collect()