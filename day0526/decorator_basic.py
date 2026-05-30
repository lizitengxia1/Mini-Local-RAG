import time

"""
装饰器和继承区别：继承改类（面向对象） 装饰器添加小功能

装饰器内部工具函数可以有多个，但是必须最终返回wrapper

def 装饰器(func):
    def 工具函数1():
        pass

    def 工具函数2():
        pass

    def wrapper():       # 必须有
        工具函数1()
        func()
        工具函数2()
    return wrapper       # 必须返回

"""

# 装饰器1. 计时装饰器
def timer(func):
    def wrapper(*args, **kwargs):
        print("装饰器开始啦~~")
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"函数运行耗时：{end - start:.2f}秒")
        print("装饰器结束啦~")
        return result
    return wrapper

# 挂载装饰器
@timer
def test_loop():
    for _ in range(1000000888999999):
        pass
    print("我是普通函数，我用了计时装饰器")

test_loop()


#装饰器2：给API请求加日志
def log_api(func):
    def wrapper(*args, **kwargs):
        print(f"调用参数：{func.__name__}")
        print(f"参数：{args}{kwargs}")
        result  = func(*args, **kwargs)
        print(f"返回结果：{result}")
        return result
    return wrapper

@log_api
def api_request(url):
    return f"请求 {url} 成功"

api_request("https://api.ai.com")

# 装饰器3.权限校验装饰器
def check_permission(func):
    def wrapper(user_role, *args, **kwargs):
        if user_role != "admin":
            return "无权限！"
        return func(user_role, *args, **kwargs)
    return wrapper

@ check_permission
def delete_data(user_role):
    return("删除数据成功")

print(delete_data("admin")) # 有权限
print(delete_data("guest")) # 无权限


last_call = 0   # 记录上次调用时间
#装饰器4.限流装饰器(1秒只能调用一次)
def rate_limit(func):
    def wrapper(*args, **kwargs):
        global last_call
        now = time.time()
        if now - last_call < 1:
            return "调用太频繁，请稍后再试！"
        last_call = now 
        return func(*args, **kwargs)
    return wrapper

@rate_limit
def send_message():
    return "消息发送成功"

print(send_message())
print(send_message()) # 会被限流