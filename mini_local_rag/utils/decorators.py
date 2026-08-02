import logging
import os
import time
import asyncio
from typing import Callable, Any

# ---------------Constant Defination (No Magic Numbers)---------------
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "runtime.log")
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

# ---------------
class ProjectBaseError(Exception):
    """Base class for all custom project exceptions"""
    pass
class FileOperationError(ProjectBaseError):
    """Exception raised when file read/write failed"""
    pass
class NetworkRequestError(ProjectBaseError):
    """Exception raised when web crawler request failed"""
    pass
class PermissionError(ProjectBaseError):
    """Exception raised when user role is not admin"""
    pass
class TextSplitError(ProjectBaseError):
    """Exception raised when text-spliting falied"""
    pass
class VectorEngineError(ProjectBaseError):
    """Exception raised when vector engine failed"""
    pass
class LLMRequestError(ProjectBaseError):
    """LLM接口请求异常：网络超时、鉴权失败、服务宕机"""
    pass
class LLMRequestParseError(ProjectBaseError):
    """模型返回数据格式异常，无法解析回答"""
    pass
class VectorArrayEmpty(VectorEngineError):
    """入库后向量矩阵异常"""
    pass
class MetaListEmpty(VectorEngineError):
    """入库后源数据列表异常"""
    pass
# ---------------
def init_logger() -> None:
    """Create log directory and initialize logging config"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE_PATH,
        format=LOG_FORMAT,
        level=LOG_LEVEL,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

# -------------- Tool 1: Time decorator---
def timer(func: Callable) -> Callable:
    """
    Decorator to calculate execution time of sync function
    Args:
        func: Target wrapped function
    Returns:
        Wrapped function with timing logic
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        cost = round(end_time - start_time, 4)
        print(f"[Timer] Function {func.__name__} finished, cost {cost} seconds")
        return result
    return wrapper

# ---------------Tool2: Decorator---
def log_recorder(func: Callable) -> Callable:
    """
    Decorator to record function runtime log, capture all exceptions and write to log file
    Args:
        func: Target wrapped function
    Returns:
        Wrapped function with logging & error capture
    """
    init_logger()
    logger = logging.getLogger()

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = func.__name__
        logger.info(f"Start execute function: {func_name}")
        try:
            res = func(*args, **kwargs)
            logger.info(f"Function {func_name} completed succesfully")
            return res
        except ProjectBaseError as e:
            err_msg = f"Custom business error in {func_name}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            raise e
        except Exception as e:
            err_msg = f"Unkown system exception in {func_name}: {str(e)}"
            logger.error(err_msg, exc_info=True)
            raise e 
    return wrapper

# ---------------Tool3: decorator----
def rate_limiter(max_concurrent):
    def decorator(func: Callable) -> Callable:
        semaphore = asyncio.Semaphore(max_concurrent)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with semaphore:
                return  await func(*args, **kwargs)
        return wrapper
    return decorator        

# ---------------Tool4: decorator-------
def check_permission(role_key: str = "user_role"):
    def decorator(func:Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1.优先从关键字参数选角色
            if role_key in kwargs:
                user_role = kwargs[role_key]
            else:
                # 2.关键字不存在则取第一个位置参数
                if not args:
                    raise PermissionError("未传入用户角色参数！")
                user_role = args[0]
            # 3. 统一校验角色
            if user_role != "admin":
                raise PermissionError(f"权限不足，当前角色：{user_role}, 仅admin可访问")
            return func(*args, **kwargs)
        return wrapper
    return decorator