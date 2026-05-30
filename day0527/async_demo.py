import asyncio
import time

# 定义异步函数
async def async_task(name, delay):
    print(f"任务{name} 开始，等待{delay}秒")
    await asyncio.sleep(delay) # 异步休眠：不阻塞整个线程
    print(f"任务{name}结束")

# 异步入口函数
async def main():
    start = time.time()
    # 串行执行
    await async_task("A", 2)
    await async_task("B", 2)
    await async_task("C", 2)
    end = time.time()
    print(f"总耗时：{end - start:.2f}秒")

    # 并发执行多个任务
    task1 = async_task("D", 3)
    task2 = async_task("E", 2)
    task3 = async_task("F", 1)
    await asyncio.gather(task1, task2, task3)
    end = time.time()
    print(f"总耗时：{end - start:.2f} 秒")

    # 创建任务，加入事件循环调度(Evet Loof)
    t1 = asyncio.create_task(async_task("G",2))
    t2 = asyncio.create_task(async_task("H",2))
    t3 = asyncio.create_task(async_task("I",2))
    # 等待所有任务完成
    await t1
    await t2
    await t3

# 启动异步程序
if __name__ == "__main__":
    asyncio.run(main())