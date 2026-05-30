# 面向对象 + 参数校验 + 异常捕获
class Cat:
    # 类的属性：所有猫的共同特征
    species = "猫科动物"

    # 初始化方法：创建实例时自动调用，设置实例的专属属性
    def __init__(self, name, age, color):
        # 自定义参数规则
        if not name or name.strip() == "":
            raise ValueError("名字不能为空！")
        # 年龄必须是整数
        if not isinstance(age, int):
            raise TypeError("年龄必须是整数！")
        if age <= 0:
            raise ValueError("年龄必须大于0！")
        self.name = name    # 实例属性：名字
        self.age = age      # 实例属性：年龄
        self.color = color  # 实例熟悉：颜色
    
    # 实例方法：猫的行为
    def meow(self):
        """猫叫的方法"""
        return f"{self.name} 说：喵呜~"

    def run(self):
        """跑步的方法"""
        return f"{self.name} 正在飞快地跑！"

    def get_info(self):
        """获取猫的完整信息"""
        return f"名字：{self.name}, 年龄：{self.age}，颜色：{self.color}，物种：{self.species}"

# 2. 创建类的实例（具体的猫）
try:
    orange_cat = Cat(name="大橘", age=-1, color="橘色") # 年龄异常
except (TypeError, ValueError) as e:                    # (TypeError, ValueError): 同时等待捕获多种异常
    print(e)
try:
    black_cat = Cat(name="", age=2, color="黑色")       # 空值异常
except (TypeError, ValueError) as e:
    print(e)
# # 3. 调用实例的属性和方法
# print("===========大橘的信息=========")
# print(orange_cat.get_info())
# print(orange_cat.meow())
# print(orange_cat.run())

# print("===========煤球的信息=========")
# print(black_cat.get_info())
# print(black_cat.meow())
# print(black_cat.run())

# # 4. 直接访问实例属性
# print(f"\n大橘的年龄是：{orange_cat.age} 岁")
# print(f"煤球的年龄是： {black_cat.age}")