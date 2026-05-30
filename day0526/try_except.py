try:
    # 可能出错的代码
    result = 1 / 0
    print("除以0错误捕获之后看看运行了没")
    a = [1,2]
    # 数组越界错误
    b = a[2]
except ZeroDivisionError:
    # 处理除零错误
    print("X 错误：除数不能为0！")
except Exception as e:
    print(f"X 未知错误：{e}")

# 程序不会崩溃，继续执行
print("程序正常结束")
