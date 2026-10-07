# ============ 文件开头：导入需要的"工具箱" ============

# import dotenv ：dotenv 是一个小库，专门负责"读取 .env 文件"
# 它的作用：把 .env 里写的 OPENAI_API_KEY=xxx 这行，
# 变成系统环境变量，让后面的代码能取到密钥
import dotenv

# dotenv.load_dotenv() ：执行读取动作
# 相当于说："请把当前文件夹下 .env 文件里的内容装进系统环境变量"
# 这一行必须在使用密钥之前执行，所以放在文件最顶部
dotenv.load_dotenv()

# from 库名 import 类名 ：只从 langchain_openai 这个库里借 ChatOpenAI 一个东西
# ChatOpenAI 是 LangChain 提供的"大模型聊天对象"，
# 创建它之后，它就是我们代码里"那个大模型"的替身，
# 以后想让模型干活，就叫这个替身做事（替身会去网络另一端找真模型）
from langchain_openai import ChatOpenAI

# 创建模型替身，起名叫 llm（large language model 大语言模型的缩写）
# 就像 new 一个对象：等号左边是变量名，右边是"制造"它的过程
llm = ChatOpenAI(
    # model="qwen3.7-max" ：指定用哪个模型
    # 想换模型（比如换成 gpt-4o）只需要改这一个字符串
    model="qwen3.7-plus",

    # temperature=0 ：模型的"发散程度"，范围 0~1
    # 0 = 最严谨：同样的问题永远给同样答案，不瞎编
    # 1 = 最奔放：答案多样有创意，但可能跑偏
    # 我们做的是数据分析，要准确不要创意，所以用 0
    temperature=0,
)
# 注意：它没传 api_key 参数——因为 load_dotenv 已经把密钥装进环境变量，
# ChatOpenAI 会自动去找，找不到才会报错。这就是"约定优于配置"。
