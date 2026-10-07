# 这个文件是空的，但必须存在！
#
# 原因：Python 靠 "__init__.py" 认"包"（文件夹形式的代码模块）
# 有了它，别的文件才能写 "from tools.csv_tool import read_csv"
# 没有它，Python 不承认 tools 是一个包，导入会报 ModuleNotFoundError
#
# 记忆方法：__init__ = initialization（初始化），
# 双下划线开头结尾的名字叫"魔法名字"，是 Python 的专用标记
