import requests
# 全局配置常量
from typing import Dict, List, Tuple

from utils.decorators import LLMRequestError, LLMRequestParseError


DEFAULT_LLM_MODEL = "qwen-small"
DEFAULT_TEMPERATURE = 0.1
ENABKE_MOCK = True

class LLMClient:
    def __init__(self, url: str, key: str, model_name: str = DEFAULT_LLM_MODEL, enable_mock: bool = ENABKE_MOCK, temperature: float = DEFAULT_TEMPERATURE):
        """
        初始化接口地址、密钥、默认模型、温度等全局配置
        """
        self.url = url
        self.key = key 
        self.model = model_name
        self.temperature = temperature
        self.enable_mock = enable_mock
        print(f"__init__ mock: {self.url}")
    
    def _build_qa_prompt(self, user_query: str, chunk_list: List[Dict]) -> str:
        """
        构造防幻觉提示词 + 用户问题与文本拼接
        """
        # 提取所有知识库文本，拼接为完整参考上下文
        context_lines = []
        for chunk in chunk_list:
            text = chunk["chunk_text"]
            context_lines.append(text)
        # 用分割线拼接多条文本
        context_all = "\n---\n".join(context_lines)
        # 约束模板
        prompt_tpl = """
你是专属知识库问答助手，严格遵守以下规则：
1. 你的所有回答只能依赖下方【参考知识库】内的文本，禁止调用自身训练的外部知识；
2. 如果参考知识库没有和用户问题相关的内容，直接回复：「暂无匹配的知识库资料，无法解答该问题」；
3. 禁止编造、联想、拓展任何文档以外的信息，回答简洁直白。

【参考知识库】
{ref_text}

【用户提问】
{query}
                    """
        # 填充模板变量
        final_prompt = prompt_tpl.format(ref_text=context_all, query=user_query)
        return final_prompt
    
    def _send_http_request(self,prompt_str: str) -> Dict:
        """
        封装底层网络请求
        :param prompt_str: 拼接完成的完整prompt字符串
        :param enable_mock: 模拟网络请求 默认开启
        :return: 接口返回原始json字典
        """
        print(f"---------self.url:{self.url}---------\n")
        if self.enable_mock:
            print("-----测试模式：跳过网络请求，使用模拟返回值-----")
            mock_result = {
            "id": "chatcmpl-mock001",
            "object": "chat.completion",
            "created": 1750000000,
            "model": "qwen-tiny",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "第一条模拟回答：根据检索到的知识库文本，可以解答你的问题。"
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 32,
                "total_tokens": 152
                }
            }
            return mock_result
        else:
            # 1. 请求头，携带权限密钥
            headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.key}"
            }
            # 2. 标准OpenAI兼容请求体
            req_body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt_str}
            ]
            }
            # 3. 发起请求， 15s超时
            try:
                resp = requests.post(
                url=self.url.rstrip() + "/chat/completions",
                headers=headers,
                json=req_body,
                timeout=15
                )
            except requests.exceptions.RequestException as e:
                # 捕获超时、连接失败、网络断开所有网络错误
                raise LLMRequestError(f"大模型接口网络请求失败：{str(e)}") from e
            
            # 4. 校验响应状态
            if resp.status_code != 200:
                raise LLMRequestError(f"接口请求失败，状态码：{resp.status_code}，详情：{resp.text}")
            # 5. 返回原始json数据
            return resp.json()     

             


    
    def _parse_model_response(self,raw_json: Dict) -> str:
        """
        解析大模型接口返回的原始JSON，提取回答文本
        :param raw_json: _send_http_request 返回的完整接口响应字典
        :return: 模型生成的纯文本回答
        :raise LLMRequestError: 接口返回结构缺失/字段异常时抛出
        """
        if not isinstance(raw_json, dict):
            raise LLMRequestParseError(f"接口返回数据类型错误，预期为字典，实际类型：{type(raw_json)}")
        try:
            content = raw_json["choices"][0]["message"]["content"]
        except KeyError as e:
            # 缺失字段：e.args[0] 会打印缺失的key名称，如"choices"
            raise LLMRequestParseError(f"接口返回缺失关键字段：{e.args[0]}") from e
        except IndexError as e:
            # choices数组为空，无回答
            raise LLMRequestParseError(f"接口返回choices数组为空，模型未生成任何回复") from e
        except Exception as e:
            # 兜底，捕获所有未知其他解析错误
            raise LLMRequestParseError(f"解析返回体发生未知错误：{str(e)}") from e
        return content

    def chat_with_rag(self, user_query: str, chunk_list: List[Dict]) -> Tuple[str, List[str]]:
        """
        RAG问答统一入口，串联提示词构建、网络请求、结果解析全流程
        :param user_query: 用户原始提问
        :param chunk_list: 向量检索返回的文本分片列表，每条包含source文档路径、chunk_text文本
        :return: (answer_text, source_path_list)
            answer_text: 大模型生成的完整回答
            source_path_list: 本次问答用到的全部参考文档路径
        """
        # 前置校验
        if not isinstance(user_query, str) or len(user_query.strip()) == 0:
            raise ValueError("用户提问不能为空或非空字符串类型")
        if not isinstance(chunk_list, list):
            raise TypeError("检索分片必须传入列表格式")
        # 拼接带知识库上下文的完整prompt
        full_prompt = self._build_qa_prompt(user_query, chunk_list)
        # 发起post请求，获取接口原始返回数据
        raw_response_dict = self._send_http_request(full_prompt)
        # 解析返回结构，提取模型输出文本
        answer_text = self._parse_model_response(raw_response_dict)
        # 提取本次检索用到的所有文档来源路径
        # source_path_list = [chunk["source"] for chunk in chunk_list]
        source_path_list = []
        for chunk in chunk_list:
            if "source" in chunk:
                source_path_list.append(chunk["source"])
        # 返回二元结果：回答文本+参考文档列表
        return answer_text, source_path_list

if __name__ == "__main__":
    from unittest.mock import patch

    # 1. 初始化客户端，填假参数，不会真实联网
    test_client = LLMClient(
        url="https://mock-llm-api.com/v1/chat/completions",
        key="fake-test-api-key-001",
        model_name=DEFAULT_LLM_MODEL,
        temperature=DEFAULT_TEMPERATURE
    )

    # 模拟向量引擎检索返回的知识库分片（多块测试）
    mock_chunk_list = [
        {
            "source": "rag_basic.md",
            "chunk_text": "RAG分为四大步骤：文档加载、文本分割、向量化、语义检索问答"
        },
        {
            "source": "embedding_intro.md",
            "chunk_text": "向量化使用嵌入模型输出固定维度向量，用于文本相似度匹配"
        }
    ]
    mock_user_query = "RAG完整执行流程是什么？"

    # 模拟大模型接口返回的标准OpenAI兼容JSON
    mock_api_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "RAG完整流程分为4步：1.文档加载；2.文本滑动分块；3.文本向量化存入向量库；4.用户提问后检索相似片段拼接prompt送入大模型回答。"
                }
            }
        ]
    }

    # 打桩拦截requests.post，所有网络请求全部劫持，离线测试
    with patch("requests.post") as mock_post:
        # 配置mock返回对象
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_api_response

        # 核心：调用对外主入口 chat_with_rag，完整跑全链路
        answer, source_file_list = test_client.chat_with_rag(mock_user_query, mock_chunk_list)

        # 打印测试结果
        print("===== 模型生成回答 =====")
        print(answer)
        print("\n===== 本次用到的参考文档 =====")
        for path in source_file_list:
            print("-", path)

        # 可选：校验mock是否被正常调用，查看真实传递给接口的请求体
        call_args = mock_post.call_args[1]
        print("\n===== 实际发送给大模型接口的请求体 =====")
        print(call_args["json"])