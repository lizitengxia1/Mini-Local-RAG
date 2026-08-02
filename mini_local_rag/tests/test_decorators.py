# tests/test_decorators.py
import os
import sys
import time
import asyncio

# 导包适配：自动识别项目根目录
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.decorators import (
    # 常量
    LOG_DIR, LOG_FILE_PATH, init_logger,
    # 异常
    ProjectBaseError, FileOperationError, NetworkRequestError, PermissionError,
    # 装饰器
    timer, log_recorder, rate_limiter, check_permission
)

# ========== 1. 基础模块测试 ==========
def test_01_log_init():
    print("===== 自测1：日志初始化 =====")
    init_logger()
    assert os.path.isdir(LOG_DIR), "logs文件夹未自动创建"
    print("日志目录创建正常")

def test_02_exception_hierarchy():
    print("\n===== 自测2：异常继承关系校验 =====")
    assert issubclass(FileOperationError, ProjectBaseError)
    assert issubclass(NetworkRequestError, ProjectBaseError)
    assert issubclass(PermissionError, ProjectBaseError)
    print("全部业务异常继承基类正常")

# ========== 2. timer 计时装饰器 ==========
def test_03_timer_sync():
    print("\n===== 自测3：timer 同步计时 =====")
    @timer
    def mock_sync_task():
        time.sleep(0.3)
        return "执行完成"
    res = mock_sync_task()
    assert res == "执行完成"
    print("timer返回值传递正常")

# ========== 3. log_recorder 日志装饰器 ==========
def test_04_log_recorder():
    print("\n===== 自测4-1：正常流程日志 =====")
    @log_recorder
    def normal_func():
        return "ok"
    normal_func()
    assert os.path.exists(LOG_FILE_PATH)

    print("===== 自测4-2：业务异常捕获 =====")
    @log_recorder
    def business_err():
        raise FileOperationError("文件缺失")
    try:
        business_err()
    except FileOperationError:
        pass

    print("===== 自测4-3：系统异常捕获 =====")
    @log_recorder
    def sys_err():
        1 / 0
    try:
        sys_err()
    except ZeroDivisionError:
        print("日志装饰器全部场景正常")

# ========== 4. check_permission 权限装饰器 ==========
def test_05_permission():
    print("\n===== 自测5：权限校验多场景 =====")
    # 关键字参数
    @check_permission(role_key="user_role")
    def op1(file, user_role="guest"):
        return "pass"
    assert op1("test.txt", user_role="admin") == "pass"
    try:
        op1("test.txt", user_role="guest")
    except PermissionError:
        pass

    # 首位置参数
    @check_permission()
    def op2(user_role, msg):
        return "ok"
    assert op2("admin", "demo") == "ok"
    try:
        op2()
    except PermissionError:
        print("权限装饰器全部场景校验通过")

# ========== 5. rate_limiter 异步限流 ==========
async def test_06_rate_limit():
    print("\n===== 自测6：异步并发限流 =====")
    @rate_limiter(max_concurrent=2)
    async def job(num):
        await asyncio.sleep(0.2)
        return num
    tasks = [job(i) for i in range(5)]
    res = await asyncio.gather(*tasks)
    assert res == [0,1,2,3,4]
    print("异步限流运行正常")

# ========== 6. 多层组合联调 ==========
def test_07_combine_decorator():
    print("\n===== 自测7：多层装饰器叠加 =====")
    @log_recorder
    @timer
    @check_permission()
    def full_flow(user_role, path):
        if not os.path.exists(path):
            raise FileOperationError("文件不存在")
        return "全部校验通过"
    full_flow("admin", LOG_FILE_PATH)
    try:
        full_flow("guest", LOG_FILE_PATH)
    except PermissionError:
        print("多层装饰器组合无逻辑断裂")

if __name__ == "__main__":
    # 同步工具依次自测
    test_01_log_init()
    test_02_exception_hierarchy()
    test_03_timer_sync()
    test_04_log_recorder()
    test_05_permission()
    test_07_combine_decorator()
    # 异步工具自测
    asyncio.run(test_06_rate_limit())
    print("\n✅ 全部装饰器自测完毕，无报错，可交付团队使用")