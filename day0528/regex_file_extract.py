import os
import re

# 安全读取文件
def read_file(filname):
    if not os.path.exists(filname):
        return "文件不存在"
    with open(filname, "r", encoding="utf-8") as f:
        return f.read()

# 写入结果文件
def write_file(filname, content):
    with open(filname, "w", encoding="utf-8") as f:
        f.write(content)

def add_file(filname, content):
    with open(filname, "a", encoding="utf-8") as f:
        f.write(content)

test_content = """
13812345678
13998765432
test@qq.com
admin@163.com
https://www.baidu.com
https://www.google.com
这是一段测试文本
"""

# 追加写入test.txt
add_file("test.txt", test_content)

# 读取文本
text = read_file("test.txt")

# 正则提取手机号
phones = re.findall(r"1[3-9]\d{9}", text)
# 正则提取邮箱
emails = re.findall(r"[\w.-]+@[\w-]+\.\w+", text)
# 正则提取网址
urls = re.findall(r"https?://[^\s]+",text)

# 拼接结果
result = ""
result += "===== 提取到的手机号 =====\n"
result += "\n".join(phones) + "\n\n"

result += "===== 提取到的邮箱 =====\n"
result += "\n".join(emails) + "\n\n"

result += "===== 提取到的网址 =====\n"
result += "\n".join(urls)

# 保存文件
write_file("提取结果.txt", result)
print(f"✅ 提取完成！文件已保存。结果内容为：{result}")