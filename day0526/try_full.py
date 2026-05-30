try:
    num = int(input("请输入一个整数："))
except ValueError:
    print("输入错误：请输入有效整数")
except Exception as e:
    # 捕获所有未预判的异常
    print(f"未知错误：{e}")
else:
    print(f"成功输入数字，数字为：{num}")
finally:
    print("异常处理流程执行完毕")