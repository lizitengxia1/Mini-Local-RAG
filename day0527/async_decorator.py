import asyncio
import time

# 异步计时装饰器
def async_timer(func):
    async def wrapper(*args, **kwargs):
        print(f"异步计时器开始计时")
        start = time.time()

        #执行异步函数
        result = await func(*args, **kwargs)

        spend = time.time() - start
        print(f"异步计时器计时结束")
        print(f"耗时{func.__name__}执行完毕，耗时：{spend:.2f}s")
        return result
    return wrapper

# 异步日志装饰器
def async_logger(func):
    async def wrapper(*args, **kwargs):
        print(f"日志开始执行{func.__name__}")

        result = await func(*args, **kwargs)

        print(f"日志执行完成{func.__name__}, 返回值：{result}")
        return result
    return wrapper 

# 异步限流装饰器
def async_rate_limit(max_concurrent):
    
    def decorator(func):
        # 创建异步信号量
        semaphore = asyncio.Semaphore(max_concurrent)
        async def wrapper(*args, **kwargs):
            # 进入限流控制
            async with semaphore:
                print(f"当前semaphore的值为：{semaphore}")
                return await func(*args, **kwargs)
        return wrapper
    return decorator


@async_timer
@async_logger
@async_rate_limit(2)
async def my_task():
    print(f"my_task开始运行......")
    await asyncio.sleep(2)
    print(f"my_task结束运行......")
    return "任务完成"

async def main():
    print(f"main开始运行......")
    await my_task()
    print(f"main结束运行......")

if __name__ == "__main__":
    asyncio.run(main())