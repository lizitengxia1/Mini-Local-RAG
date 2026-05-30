# 1. 先定义父类：动物类
class Animal:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def eat(self):
        """吃饭的方法，所有动物都有"""
        return f"{self.name} 正在吃饭！"

    def sleep(self):
        """睡觉的方法，所有动物都有"""
        return f"{self.name} 正在睡觉，zzz..."

    def make_sound(self):
        """发出声音的方法，不同动物会重写这个方法"""
        return f"{self.name} 发出了声音！"


# 2. 定义子类：猫类，继承自动物类
class Cat(Animal):
    def __init__(self, name, age, color):
        # 调用父类的初始化方法，继承name和age属性
        super().__init__(name, age)
        # 子类新增的属性
        self.color = color

    # 重写父类的make_sound方法，实现猫的专属叫声
    def make_sound(self):
        return f"{self.name} 说：喵呜~"

    # 子类新增的专属方法
    def catch_mouse(self):
        return f"{self.name} 正在抓老鼠！"


# 3. 定义子类：狗类，继承自动物类
class Dog(Animal):
    def __init__(self, name, age, breed):
        super().__init__(name, age)
        self.breed = breed

    # 重写父类的make_sound方法，实现狗的专属叫声
    def make_sound(self):
        return f"{self.name} 说：汪汪汪！"

    # 子类新增的专属方法
    def watch_house(self):
        return f"{self.name} 正在看家！"


# 4. 创建实例，验证继承效果
print("===== 猫类实例 =====")
orange_cat = Cat(name="大橘", age=3, color="橘色")
print(orange_cat.eat())       # 调用父类继承的方法
print(orange_cat.sleep())     # 调用父类继承的方法
print(orange_cat.make_sound())# 调用子类重写的方法
print(orange_cat.catch_mouse())# 调用子类新增的方法
print(f"大橘的颜色：{orange_cat.color}")

print("\n===== 狗类实例 =====")
golden_dog = Dog(name="大黄", age=4, breed="金毛")
print(golden_dog.eat())       # 调用父类继承的方法
print(golden_dog.sleep())     # 调用父类继承的方法
print(golden_dog.make_sound())# 调用子类重写的方法
print(golden_dog.watch_house())# 调用子类新增的方法
print(f"大黄的品种：{golden_dog.breed}")

print("\n===== 父类实例 =====")
generic_animal = Animal(name="小动物", age=1)
print(generic_animal.eat())
print(generic_animal.make_sound())