import os

# 读取文件
def read_file(filname):
    try:
        with open(filname, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("错误：文件不存在！")
    except Exception as e:
        print("未知错误：", e)

# 写入文件(覆盖)
def write_file(filname, content):
    with open(filname, "w", encoding="utf-8") as f:
        f.write(content)

# 追加文件
def append_file(filname, content):
    with open(filname, "a", encoding="utf-8") as f:
        f.write(content + "\n")

# 测试
if __name__ == "__main__":
    write_file("test.txt", "13812345678\n13998765432\ntest@qq.com")
    content = read_file("test.txt")
    print("读取内容：")
    print(content)