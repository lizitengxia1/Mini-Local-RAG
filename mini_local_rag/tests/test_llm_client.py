# tests/test_vector_engine.py
import os
import sys

# 路径兼容，解决导包报错
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# tests/test_llm_client.py
from unittest.mock import patch
from utils.llm_client import (
    LLMClient,
    DEFAULT_LLM_MODEL,
    LLMRequestError,
    LLMRequestParseError
)

# -------------------------- 测试常量准备 --------------------------
TEST_URL = "https://mock-llm-endpoint/v1/chat/completions"
TEST_KEY = "fake-test-key"
TEST_CHUNK_LIST = [
    {
        "source": "rag_intro.md",
        "chunk_text": "RAG分为四大步骤：文档加载、文本分割、向量化、语义检索问答"
    }
]
TEST_QUERY = "RAG完整流程是什么？"

# 标准OpenAI兼容返回
MOCK_NORMAL_RESP = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "RAG分为4个核心步骤：文档加载、文本分割、向量化、语义检索问答。"
            }
        }
    ]
}


def test_build_prompt():
    """测试 _build_qa_prompt 正常拼接模板"""
    client = LLMClient(url=TEST_URL, key=TEST_KEY)
    prompt = client._build_qa_prompt(TEST_QUERY, TEST_CHUNK_LIST)

    # 简单断言：上下文、问题都被填充进prompt
    assert "RAG分为四大步骤" in prompt
    assert TEST_QUERY in prompt
    print("✅ test_build_prompt 通过")


def test_parse_response_normal():
    """测试 _parse_model_response 正常解析标准返回"""
    client = LLMClient(url=TEST_URL, key=TEST_KEY)
    ans = client._parse_model_response(MOCK_NORMAL_RESP)
    assert "RAG分为4个核心步骤" in ans
    print("✅ test_parse_response_normal 通过")


def test_chat_with_rag_full_flow():
    """核心：端到端测试对外主入口 chat_with_rag
    输入：vec.search_top_chunks() 标准chunk列表
    """
    client = LLMClient(url=TEST_URL, key=TEST_KEY)

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = MOCK_NORMAL_RESP
        print("传入chat_with_rag的chunk_list：", TEST_CHUNK_LIST)
        answer, source_list = client.chat_with_rag(TEST_QUERY, TEST_CHUNK_LIST)
        print("得到source_list：", source_list)
        # 校验返回二元组格式
        assert isinstance(answer, str)
        assert isinstance(source_list, list)
        assert source_list == ["rag_intro.md"]
        print("✅ test_chat_with_rag_full_flow 通过")


def test_parse_empty_choices():
    """测试 choices为空数组，预期抛出 LLMRequestParseError"""
    client = LLMClient(url=TEST_URL, key=TEST_KEY)
    empty_resp = {"choices": []}
    try:
        client._parse_model_response(empty_resp)
    except LLMRequestParseError:
        print("✅ test_parse_empty_choices 通过")
        return
    assert False, "应当抛出解析异常"


def test_parse_missing_field():
    """测试缺失choices字段，预期抛出 LLMRequestParseError"""
    client = LLMClient(url=TEST_URL, key=TEST_KEY)
    bad_resp = {}
    try:
        client._parse_model_response(bad_resp)
    except LLMRequestParseError:
        print("✅ test_parse_missing_field 通过")
        return
    assert False, "应当抛出解析异常"


if __name__ == "__main__":
    # 本地直接运行自测
    test_build_prompt()
    test_parse_response_normal()
    test_chat_with_rag_full_flow()
    test_parse_empty_choices()
    test_parse_missing_field()
    print("\n🎉 全部测试执行完成！")