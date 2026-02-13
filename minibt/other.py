from datetime import datetime, time, timedelta
import numpy as np
import scipy
from numpy import ndarray
import pandas as pd
import os
from types import ModuleType
import re
from typing import Optional
from functools import partial
from inspect import signature
import glob
import sys
import io
from contextlib import AbstractContextManager, contextmanager


class FilteredOutputRedirector(AbstractContextManager):
    """
    增强型输出重定向管理器：
    - filter_keywords=None：完全屏蔽所有输出（stdout/stderr）
    - filter_keywords=列表：仅过滤包含指定关键词的输出，其余内容正常打印
    :param filter_keywords: 过滤关键词列表，为None时禁用所有输出
    :param redirect_stderr: 是否同时处理标准错误流，默认开启
    """

    def __init__(self, filter_keywords: list = None, redirect_stderr: bool = True):
        self.filter_keywords = filter_keywords
        self.redirect_stderr = redirect_stderr
        # 保存原始流，用于后续恢复
        self.original_stdout = None
        self.original_stderr = None

    def __enter__(self):
        # 缓存原始输出流
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # 分支1：关键词为None，完全重定向到空流，屏蔽所有输出
        if self.filter_keywords is None:
            null_stream = io.StringIO()
            sys.stdout = null_stream
            if self.redirect_stderr:
                sys.stderr = null_stream
        # 分支2：传入关键词，仅过滤匹配内容，保留正常输出
        else:
            class FilteredStream:
                def __init__(self, stream, keywords):
                    self.stream = stream
                    self.keywords = keywords

                def write(self, msg: str):
                    # 无匹配关键词时才写入输出
                    if not any(key in msg for key in self.keywords):
                        self.stream.write(msg)

                def flush(self):
                    self.stream.flush()

            # 替换系统输出流
            sys.stdout = FilteredStream(
                self.original_stdout, self.filter_keywords)
            if self.redirect_stderr:
                sys.stderr = FilteredStream(
                    self.original_stderr, self.filter_keywords)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 无论是否发生异常，强制恢复原始输出流
        sys.stdout = self.original_stdout
        if self.redirect_stderr:
            sys.stderr = self.original_stderr
        # 返回False，不捕获代码块内的异常，便于调试
        return False


class ProcessedAttribute:

    def __init__(self, value):
        self.value = value

    def __call__(self, *args, **kwargs):
        return partial(self.value, **kwargs)


class base:

    def __getattribute__(self, name: str):
        if not name.startswith("_"):
            return ProcessedAttribute(super().__getattribute__(name))
        return super().__getattribute__(name)


def ensure_numeric_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """确保DataFrame中的数值列是正确类型"""
    data = data.copy()

    # 定义数值列
    numeric_columns = ['open', 'high', 'low', 'close', 'volume']

    for col in numeric_columns:
        if col in data.columns:
            # 处理各种可能的异常情况
            try:
                data[col] = pd.to_numeric(data[col], errors='coerce')
                # 确保最终是float64类型
                data[col] = data[col].astype(np.float64)
            except Exception as e:
                # print(f"警告: 转换列 {col} 时出错: {e}")
                # 如果转换失败，尝试其他方法
                data[col] = data[col].apply(
                    lambda x: float(x) if pd.notnull(x) else np.nan)

    # 处理datetime列
    if 'datetime' in data.columns:
        try:
            data['datetime'] = pd.to_datetime(
                data['datetime'], errors='coerce')
        except Exception as e:
            # print(f"警告: 转换datetime列时出错: {e}")
            ...

    return data


def read_unknown_file(file_path: str) -> Optional[pd.DataFrame]:
    """
    读取未知格式的文件并转换为pandas DataFrame，支持常见数据格式

    Args:
        file_path: 文件路径（含文件名）

    Returns:
        成功则返回DataFrame，失败则返回None并提示错误
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 - {file_path}")
        return None

    # 获取文件扩展名（小写）
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()  # 统一转为小写，避免大小写问题（如.CSV和.csv）

    # 定义：扩展名 -> (读取函数, 必要参数)
    format_handlers = {
        # 文本格式
        '.csv': (pd.read_csv, {}),
        '.tsv': (pd.read_csv, {'sep': '\t'}),  # 制表符分隔
        '.txt': (pd.read_csv, {}),  # 尝试用csv默认方式读取文本

        # Excel格式
        '.xlsx': (pd.read_excel, {'engine': 'openpyxl'}),
        '.xls': (pd.read_excel, {'engine': 'xlrd'}),

        # 结构化格式
        '.json': (pd.read_json, {}),
        '.parquet': (pd.read_parquet, {}),
        '.feather': (pd.read_feather, {}),
        '.pkl': (pd.read_pickle, {}),
        '.pickle': (pd.read_pickle, {}),

        # 其他格式
        '.html': (pd.read_html, {}),  # 读取HTML表格（返回列表，取第一个）
    }

    # 尝试1：根据扩展名读取
    if ext in format_handlers:
        reader, kwargs = format_handlers[ext]
        try:
            if ext == '.html':
                # read_html返回列表，取第一个表格
                df_list = reader(file_path, **kwargs)
                return df_list[0] if df_list else None
            return reader(file_path, ** kwargs)
        except Exception as e:
            print(f"按扩展名{ext}读取失败：{str(e)}，尝试其他格式...")

    # 尝试2：如果无扩展名或扩展名未知，按常见格式顺序尝试
    unknown_ext_formats = [
        '.csv', '.json', '.parquet', '.xlsx', '.pkl'  # 优先级从高到低
    ]
    for fmt in unknown_ext_formats:
        if fmt == ext:
            continue  # 跳过已尝试过的格式
        reader, kwargs = format_handlers[fmt]
        try:
            if fmt == '.html':
                df_list = reader(file_path, **kwargs)
                return df_list[0] if df_list else None
            return reader(file_path, ** kwargs)
        except:
            continue  # 失败则尝试下一种

    # 所有尝试失败
    print(f"无法识别文件格式，已尝试所有支持的格式：{list(format_handlers.keys())}")
    return None


class FILED:
    """数据字段
    ----------

    >>> ALL = np.array(['datetime', 'open', 'high', 'low','close', 'volume'])
        TALL = np.array(['time', 'open', 'high', 'low',
                        'close', 'volume'], dtype='<U16')
        TICK = np.array(['time', 'volume', 'price'], dtype='<U16')
        Quote = np.array(['datetime', 'open', 'high', 'low','close',
                         'volume',"symbol", "duration","price_tick", "volume_multiple"])
        DOHLV = np.array(['datetime', 'open', 'high',
                         'low', 'volume'], dtype='<U16')
        C = np.array(['close',])
        V = np.array(['volume'])
        CV = np.array(['close', 'volume'])
        OC = np.array(['open', 'close'])
        HL = np.array(['high', 'low'])
        HLC = np.array(['high', 'low','close'])
        HLV = np.array(['high', 'low', 'volume'])
        OHLC = np.array(['open', 'high', 'low','close'])
        HLCV = np.array(['high', 'low','close', 'volume'])
        OHLCV = np.array(['open', 'high', 'low','close', 'volume'])
        dtype : ndarray
    """
    ALL = np.array(['datetime', 'open', 'high', 'low',
                   'close', 'volume'], dtype='<U16')
    TALL = np.array(['time', 'open', 'high', 'low',
                     'close', 'volume'], dtype='<U16')
    TICK = np.array(['time', 'volume', 'price'], dtype='<U16')
    TPV = np.array(['time', 'price', 'volume'], dtype='<U16')
    Quote = np.append(ALL, ["symbol", "duration",
                      "price_tick", "volume_multiple"])
    DOHLV = np.array(['datetime', 'open', 'high',
                     'low', 'volume'], dtype='<U16')
    D = ALL[0:1]
    O = ALL[1:2]
    H = ALL[2:3]
    L = ALL[3:4]
    C = ALL[4:5]
    V = ALL[5:]
    CV = ALL[4:]
    OC = ALL[[1, 4]]
    HL = ALL[2:4]
    OHL = ALL[1:4]
    HLC = ALL[2:5]
    HLV = ALL[[2, 3, 5]]
    OHLC = ALL[1:5]
    HLCV = ALL[2:]
    OHLCV = ALL[1:]
    DV = ALL[[0, 5]]
    DCV = ALL[[0, 4, 5]]
    TV = TALL[[0, 5]]
    TCV = TALL[[0, 4, 5]]
    TP = TICK[[0, 2]]
    TOHLC = TALL[:5]


def save_and_generate_utils(data: pd.DataFrame, base_dir: str, save: Optional[str], name: Optional[str]):
    # 处理文件名（默认用symbol，支持自定义）
    file_name = save if isinstance(save, str) else name
    if "." in file_name:
        file_name = file_name.split(".")[1]
    file_name = f"{file_name}.csv"
    # 保存路径（BASE_DIR/data/test/）
    path = os.path.join(base_dir, "data", "test", file_name)
    data.to_csv(path, index=False)
    # 自动更新本地数据工具类（生成utils.py，包含所有CSV数据的引用）
    csv_files = glob.glob(os.path.join(
        base_dir, "data", "test", "*.csv"))
    py_file_path = os.path.join(base_dir, "data", "utils.py")
    # 生成工具类内容
    class_content = [
        'from .tools import *', "", "",
        'class LocalDatas(base):', '    """本地CSV数据"""']
    for file in csv_files:
        file_name = os.path.splitext(os.path.basename(file))[0]
        class_content.append(
            f'    {file_name} = DataString("{file_name}")')
    class_content.extend(["", ""])
    class_content.append('LocalDatas=LocalDatas()')
    # 写入文件
    with open(py_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(class_content))


def find_pth_files(cwd=None, file_extension=".pth"):
    """获取指定目录下所有.pth文件的完整路径"""
    if cwd is None:
        cwd = os.getcwd()  # 默认当前工作目录
    pth_files = []
    for root, _, files in os.walk(cwd):
        for file in files:
            if file.endswith(file_extension):
                pth_files.append(os.path.join(root, file))
    return pth_files


def extract_numeric_key(file_path):
    """从文件路径中提取文件名的数字部分，转换为数值元组作为排序键"""
    file_name = os.path.basename(file_path)  # 提取文件名（不含路径）
    # 匹配所有数字部分（支持整数和小数，如"0002048"、"1501.000"）
    numeric_strings = re.findall(r"\d+\.?\d*", file_name)
    # 将数字字符串转换为数值类型（int或float）
    numeric_values = []
    for s in numeric_strings:
        if "." in s:
            numeric_values.append(float(s))  # 小数部分
        else:
            numeric_values.append(int(s))    # 整数部分
    return tuple(numeric_values)  # 以元组形式返回，支持多数字部分排序


def get_sorted_pth_files(cwd: str, file_extension: str = ".pth") -> list:
    """### 获取指定目录下所有.pth文件，并按文件名中的数字从大到小排序
    ### 1. 获取所有.pth文件路径
    >>> pth_paths = find_pth_files()

    ### 2. 按文件名中的数字从大到小排序
    >>> sorted_paths = sorted(pth_paths, key=extract_numeric_key, reverse=True)

    ### 3. 输出排序后的路径
    >>> print("按数字从大到小排序的.pth文件路径：")
        for path in sorted_paths:
            print(path)"""
    pth_files = find_pth_files(cwd, file_extension)
    sorted_files = sorted(pth_files, key=extract_numeric_key, reverse=True)
    return sorted_files


class DisabledModule(ModuleType):
    """禁用的模块，防止任意导入"""

    def __getattr__(self, name):
        raise RuntimeError(f"在安全模式下禁止访问模块 '{self.__name__}' 的属性 '{name}'")


class SafeLoader:
    """安全加载器，限制全局命名空间"""

    def __init__(self, allowed_classes=None):
        self.allowed_classes = allowed_classes or []
        self.original_builtins = None
        self.original_import = None

    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """安全导入函数，只允许特定模块"""
        # 允许的模块列表（根据需要扩展）
        allowed_modules = ["torch", "torch.nn", "numpy", "builtins"]

        # 检查模块是否允许
        if any(name.startswith(mod) for mod in allowed_modules):
            return self.original_import(name, globals, locals, fromlist, level)

        # 对于不允许的模块，返回禁用的模块对象
        return DisabledModule(name)

    def __enter__(self):
        global __builtins__  # 明确引用全局的 __builtins__

        # 备份原始的内置命名空间和导入函数
        if isinstance(__builtins__, dict):
            self.original_builtins = __builtins__.copy()
        else:
            # 在某些环境中，__builtins__ 可能是模块对象
            self.original_builtins = __builtins__.__dict__.copy()

        self.original_import = __builtins__['__import__']

        # 创建安全的全局命名空间
        safe_globals = {}

        # 添加允许的类
        for cls in self.allowed_classes:
            safe_globals[cls.__name__] = cls

        # 添加基本的内置函数和类型
        if isinstance(__builtins__, dict):
            builtins_dict = __builtins__
        else:
            builtins_dict = __builtins__.__dict__

        for name, obj in builtins_dict.items():
            if isinstance(obj, type) or callable(obj):
                safe_globals[name] = obj

        # 替换内置命名空间和导入函数
        __builtins__ = safe_globals
        __builtins__['__import__'] = self._safe_import

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        global __builtins__  # 明确引用全局的 __builtins__

        # 恢复原始的内置命名空间和导入函数
        if isinstance(self.original_builtins, dict):
            __builtins__ = self.original_builtins
        else:
            __builtins__.clear()
            __builtins__.update(self.original_builtins)

        __builtins__['__import__'] = self.original_import
        return False  # 不抑制异常


@contextmanager
def safe_globals(allowed_classes):
    """### 安全全局命名空间上下文管理器
    ### 使用方法
    >>> from minibt.elegantrl.agents import AgentDiscretePPO
        with safe_globals([AgentDiscretePPO]):
            model = torch.load("model.pth", map_location="cpu")"""
    with SafeLoader(allowed_classes) as loader:
        yield loader


class Meta(type):
    """可迭代元类"""
    def __iter__(cls):
        # 仅迭代非特殊属性（可选）
        return iter([v for k, v in vars(cls).items() if not k.startswith('__')])

    def __contains__(cls, item):
        # 仅检查非特殊属性的值
        return item in [v for k, v in vars(cls).items() if not k.startswith('__')]


class KeyMeta(type):
    """可迭代元类"""
    def __iter__(cls):
        # 仅迭代键属性
        return iter([k for k, _ in vars(cls).items() if not k.startswith('__')])

    def __contains__(cls, item):
        # 仅检查键属性
        return item in [k for k, _ in vars(cls).items() if not k.startswith('__')]


def get_func_args_dict(func, *args, **kwargs) -> dict:
    """
    将函数调用的参数（位置参数+关键字参数）转换为「参数名:参数值」的字典，包含默认参数

    Args:
        func: 目标函数（如 test）
        *args: 函数调用的位置参数（如 3,4,5,6）
        **kwargs: 函数调用的关键字参数（如 c=5,d=6）

    Returns:
        包含所有参数名与对应值的字典
    """
    # 1. 获取函数的参数签名
    func_sig = signature(func)
    # 2. 绑定参数（支持位置+关键字参数，自动匹配参数名）
    bound_args = func_sig.bind_partial(*args, **kwargs)
    # 3. 填充函数的默认参数（未传的默认参数会自动补全）
    bound_args.apply_defaults()
    # 4. 返回参数名与值的字典（arguments 属性本身就是有序字典，Python3.7+ 会保留参数顺序）
    return dict(bound_args.arguments)


def pad_lists(list1, list2, fill_value=False) -> zip:
    padded_list2 = len(list1) > len(list2) and list2 + \
        [fill_value] * (len(list1) - len(list2)) or list2[:len(list1)]
    return zip(list1, padded_list2)


def format_3col_report(metrics: list[str, float, str], name="", col_width: int = 30):
    # 构造分组（每3个指标为一组）
    metric_groups = [metrics[i:i+3] for i in range(0, len(metrics), 3)]

    # 构建报告内容
    report = []
    total_width = (col_width+3) * 3 - 1  # 3列宽度 + 分隔符
    separator = "║" + "═" * total_width + "║"

    report.append(separator)
    report.append("║{:^{total_width}}║".format(
        f"{name} Strategy performance reports", total_width=total_width))
    report.append(separator)

    for group in metric_groups:
        line: list[str] = []
        for metric in group:
            name, value, fmt = metric
            # 固定名称和数值宽度
            name_part = name.ljust(int(col_width/2)-1)
            value_part = fmt.format(value).rjust(int(col_width/2)-1)
            line.append(f"{name_part}{value_part}")
        # 补足空白列并保持对齐
        while len(line) < 3:
            line.append(" " * (col_width - 1))  # -2 补偿分隔符空间
        # 构建行
        report_line = "║ {} │ {} │ {} ║".format(*[
            item.ljust(col_width, " ")  # '　')  # 使用全角空格填充
            for item in line
        ])
        report.append(report_line)

    report.append(separator)
    return "\n".join(report)


def _datetime_to_timestamp_nano(dt: datetime) -> int:
    # timestamp() 返回值精度为 microsecond,直接乘以 1e9 可能有精度问题
    return int(dt.timestamp() * 1000000) * 1000


def _str_to_timestamp_nano(current_datetime: str, fmt="%Y-%m-%d %H:%M:%S") -> int:
    return _datetime_to_timestamp_nano(datetime.strptime(current_datetime, fmt))


def _to_ns_timestamp(input_time):
    """
    辅助函数: 将传入的时间转换为int类型的纳秒级时间戳

    Args:
    input_time (str/ int/ float/ datetime.datetime): 需要转换的时间:
        * str: str 类型的时间,如Quote行情时间的datetime字段 (eg. 2019-10-14 14:26:01.000000)

        * int: int 类型纳秒级或秒级时间戳

        * float: float 类型纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)

        * datetime.datetime: datetime 模块中 datetime 类型

    Returns:
        int : int 类型纳秒级时间戳
    """
    if type(input_time) in {int, float, np.float64, np.float32, np.int64, np.int32}:  # 时间戳
        if input_time > 2 ** 32:  # 纳秒( 将 > 2*32数值归为纳秒级)
            return int(input_time)
        else:  # 秒
            return int(input_time * 1e9)
    elif isinstance(input_time, str):  # str 类型时间
        return _str_to_timestamp_nano(input_time)
    elif isinstance(input_time, datetime):  # datetime 类型时间
        return _datetime_to_timestamp_nano(input_time)
    else:
        raise TypeError("暂不支持此类型的转换")


def time_to_str(input_time):
    """
    将传入的时间转换为 %Y-%m-%d %H:%M:%S.%f 格式的 str 类型

    Args:
        input_time (int/ float/ datetime.datetime): 需要转换的时间:

            * int: int 类型的纳秒级或秒级时间戳

            * float: float 类型的纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)

            * datetime.datetime: datetime 模块中的 datetime 类型时间

    Returns:
        str : %Y-%m-%d %H:%M:%S.%f 格式的 str 类型时间

    Example::

        from tqsdk.tafunc import time_to_str
        print(time_to_str(1.57103449e+18))  # 将纳秒级时间戳转为%Y-%m-%d %H:%M:%S.%f 格式的str类型时间
        print(time_to_str(1571103122))  # 将秒级时间戳转为%Y-%m-%d %H:%M:%S.%f 格式的str类型时间
        print(time_to_str(datetime.datetime(2019, 10, 14, 14, 26, 1)))  # 将datetime.datetime时间转为%Y-%m-%d %H:%M:%S.%f 格式的str类型时间
    """
    # 转为秒级时间戳
    ts = _to_ns_timestamp(input_time) / 1e9
    # 转为 %Y-%m-%d %H:%M:%S.%f 格式的 str 类型时间
    dt = datetime.fromtimestamp(ts)
    dt = dt.strftime('%Y-%m-%d %H:%M:%S')
    return dt


def time_to_datetime(input_time):
    """
    将传入的时间转换为 datetime.datetime 类型

    Args:
        input_time (int/ float/ str): 需要转换的时间:

            * int: int 类型的纳秒级或秒级时间戳

            * float: float 类型的纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)

            * str: str 类型的时间,如Quote行情时间的 datetime 字段 (eg. 2019-10-14 14:26:01.000000)

    Returns:
        datetime.datetime : datetime 模块中的 datetime 类型时间

    Example::

        from tqsdk.tafunc import time_to_datetime
        print(time_to_datetime(1.57103449e+18))  # 将纳秒级时间戳转为datetime.datetime时间
        print(time_to_datetime(1571103122))  # 将秒级时间戳转为datetime.datetime时间
        print(time_to_datetime("2019-10-14 14:26:01.000000"))  # 将%Y-%m-%d %H:%M:%S.%f 格式的str类型时间转为datetime.datetime时间
    """
    # 转为秒级时间戳
    ts = _to_ns_timestamp(input_time) / 1e9
    # 转为datetime.datetime类型
    dt = datetime.fromtimestamp(ts)
    return dt


def timestamp_to_time(input_time):
    raise time_to_datetime(input_time).time()


def time_to_s_timestamp(input_time):
    """
    将传入的时间转换为int类型的秒级时间戳

    Args:
        input_time (str/ int/ float/ datetime.datetime): 需要转换的时间:
            * str: str 类型的时间,如Quote行情时间的datetime字段 (eg. 2019-10-14 14:26:01.000000)

            * int: int 类型的纳秒级或秒级时间戳

            * float: float 类型的纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)

            * datetime.datetime: datetime 模块中的 datetime 类型时间

    Returns:
        int : int类型的秒级时间戳

    Example::

        from tqsdk.tafunc import time_to_s_timestamp
        print(time_to_s_timestamp(1.57103449e+18))  # 将纳秒级时间戳转为秒级时间戳
        print(time_to_s_timestamp("2019-10-14 14:26:01.000000"))  # 将%Y-%m-%d %H:%M:%S.%f 格式的str类型时间转为秒级时间戳
        print(time_to_s_timestamp(datetime.datetime(2019, 10, 14, 14, 26, 1)))  # 将datetime.datetime时间转为秒时间戳
    """
    return int(_to_ns_timestamp(input_time) / 1e9)


def time_to_ns_timestamp(input_time):
    """
    将传入的时间转换为int类型的纳秒级时间戳

    Args:
        input_time (str/ int/ float/ datetime.datetime): 需要转换的时间:
            * str: str 类型的时间,如Quote行情时间的datetime字段 (eg. 2019-10-14 14:26:01.000000)

            * int: int 类型的纳秒级或秒级时间戳

            * float: float 类型的纳秒级或秒级时间戳,如K线或tick的datetime字段 (eg. 1.57103449e+18)

            * datetime.datetime: datetime 模块中的 datetime 类型时间

    Returns:
        int : int 类型的纳秒级时间戳

    Example::

        from tqsdk.tafunc import time_to_ns_timestamp
        print(time_to_ns_timestamp("2019-10-14 14:26:01.000000"))  # 将%Y-%m-%d %H:%M:%S.%f 格式的str类型转为纳秒时间戳
        print(time_to_ns_timestamp(1571103122))  # 将秒级转为纳秒时间戳
        print(time_to_ns_timestamp(datetime.datetime(2019, 10, 14, 14, 26, 1)))  # 将datetime.datetime时间转为纳秒时间戳
    """
    return _to_ns_timestamp(input_time)


def compute_time(signal, fs) -> np.ndarray:
    """Creates the signal correspondent time array.

    Parameters
    ----------
    signal: nd-array
        Input from which the time is computed.
    fs: int
        Sampling Frequency

    Returns
    -------
    time : float list
        Signal time

    """

    return np.arange(0, len(signal))/fs


def calc_fft(signal, fs):
    """ This functions computes the fft of a signal.

    Parameters
    ----------
    signal : nd-array
        The input signal from which fft is computed
    fs : float
        Sampling frequency

    Returns
    -------
    f: nd-array
        Frequency values (xx axis)
    fmag: nd-array
        Amplitude of the frequency values (yy axis)

    """

    fmag = np.abs(np.fft.rfft(signal))
    f = np.fft.rfftfreq(len(signal), d=1/fs)

    return f.copy(), fmag.copy()


def filterbank(signal, fs, pre_emphasis=0.97, nfft=512, nfilt=40):
    """Computes the MEL-spaced filterbank.

    It provides the information about the power in each frequency band.

    Implementation details and description on:
    https://www.kaggle.com/ilyamich/mfcc-implementation-and-tutorial
    https://haythamfayek.com/2016/04/21/speech-processing-for-machine-learning.html#fnref:1

    Parameters
    ----------
    signal : nd-array
        Input from which filterbank is computed
    fs : float
        Sampling frequency
    pre_emphasis : float
        Pre-emphasis coefficient for pre-emphasis filter application
    nfft : int
        Number of points of fft
    nfilt : int
        Number of filters

    Returns
    -------
    nd-array
        MEL-spaced filterbank

    """

    # Signal is already a window from the original signal, so no frame is needed.
    # According to the references it is needed the application of a window function such as
    # hann window. However if the signal windows don't have overlap, we will lose information,
    # as the application of a hann window will overshadow the windows signal edges.

    # pre-emphasis filter to amplify the high frequencies

    emphasized_signal = np.append(np.array(signal)[0], np.array(
        signal[1:]) - pre_emphasis * np.array(signal[:-1]))

    # Fourier transform and Power spectrum
    mag_frames = np.absolute(np.fft.rfft(
        emphasized_signal, nfft))  # Magnitude of the FFT

    pow_frames = ((1.0 / nfft) * (mag_frames ** 2))  # Power Spectrum

    low_freq_mel = 0
    high_freq_mel = (2595 * np.log10(1 + (fs / 2) / 700))  # Convert Hz to Mel
    # Equally spaced in Mel scale
    mel_points = np.linspace(low_freq_mel, high_freq_mel, nfilt + 2)
    hz_points = (700 * (10 ** (mel_points / 2595) - 1))  # Convert Mel to Hz
    filter_bin = np.floor((nfft + 1) * hz_points / fs)

    fbank = np.zeros((nfilt, int(np.floor(nfft / 2 + 1))))
    for m in range(1, nfilt + 1):

        f_m_minus = int(filter_bin[m - 1])  # left
        f_m = int(filter_bin[m])  # center
        f_m_plus = int(filter_bin[m + 1])  # right

        for k in range(f_m_minus, f_m):
            fbank[m - 1, k] = (k - filter_bin[m - 1]) / \
                (filter_bin[m] - filter_bin[m - 1])
        for k in range(f_m, f_m_plus):
            fbank[m - 1, k] = (filter_bin[m + 1] - k) / \
                (filter_bin[m + 1] - filter_bin[m])

    # Area Normalization
    # If we don't normalize the noise will increase with frequency because of the filter width.
    enorm = 2.0 / (hz_points[2:nfilt + 2] - hz_points[:nfilt])
    fbank *= enorm[:, np.newaxis]

    filter_banks = np.dot(pow_frames, fbank.T)
    filter_banks = np.where(filter_banks == 0, np.finfo(
        float).eps, filter_banks)  # Numerical Stability
    filter_banks = 20 * np.log10(filter_banks)  # dB

    return filter_banks


def autocorr_norm(signal):
    """Computes the autocorrelation.

    Implementation details and description in:
    https://ccrma.stanford.edu/~orchi/Documents/speaker_recognition_report.pdf

    Parameters
    ----------
    signal : nd-array
        Input from linear prediction coefficients are computed

    Returns
    -------
    nd-array
        Autocorrelation result

    """

    variance = np.var(signal)
    signal = np.copy(signal - signal.mean())
    r = scipy.signal.correlate(signal, signal)[-len(signal):]

    if (signal == 0).all():
        return np.zeros(len(signal))

    acf = r / variance / len(signal)

    return acf


def create_symmetric_matrix(acf, order=11):
    """Computes a symmetric matrix.

    Implementation details and description in:
    https://ccrma.stanford.edu/~orchi/Documents/speaker_recognition_report.pdf

    Parameters
    ----------
    acf : nd-array
        Input from which a symmetric matrix is computed
    order : int
        Order

    Returns
    -------
    nd-array
        Symmetric Matrix

    """

    smatrix = np.empty((order, order))
    xx = np.arange(order)
    j = np.tile(xx, order)
    i = np.repeat(xx, order)
    smatrix[i, j] = acf[np.abs(i - j)]

    return smatrix


def lpc(signal, n_coeff=12):
    """Computes the linear prediction coefficients.

    Implementation details and description in:
    https://ccrma.stanford.edu/~orchi/Documents/speaker_recognition_report.pdf

    Parameters
    ----------
    signal : nd-array
        Input from linear prediction coefficients are computed
    n_coeff : int
        Number of coefficients

    Returns
    -------
    nd-array
        Linear prediction coefficients

    """

    if signal.ndim > 1:
        raise ValueError("Only 1 dimensional arrays are valid")
    if n_coeff > signal.size:
        raise ValueError("Input signal must have a length >= n_coeff")

    # Calculate the order based on the number of coefficients
    order = n_coeff - 1

    # Calculate LPC with Yule-Walker
    acf = np.correlate(signal, signal, 'full')

    r = np.zeros(order+1, 'float32')
    # Assuring that works for all type of input lengths
    nx = np.min([order+1, len(signal)])
    r[:nx] = acf[len(signal)-1:len(signal)+order]

    smatrix = create_symmetric_matrix(r[:-1], order)

    if np.sum(smatrix) == 0:
        return tuple(np.zeros(order+1))

    lpc_coeffs = np.dot(np.linalg.inv(smatrix), -r[1:])

    return tuple(np.concatenate(([1.], lpc_coeffs)))


def create_xx(features):
    """Computes the range of features amplitude for the probability density function calculus.

    Parameters
    ----------
    features : nd-array
        Input features

    Returns
    -------
    nd-array
        range of features amplitude

    """

    features_ = np.copy(features)

    if max(features_) < 0:
        max_f = - max(features_)
        min_f = min(features_)
    else:
        min_f = min(features_)
        max_f = max(features_)

    if min(features_) == max(features_):
        xx = np.linspace(min_f, min_f + 10, len(features_))
    else:
        xx = np.linspace(min_f, max_f, len(features_))

    return xx


def kde(features):
    """Computes the probability density function of the input signal using a Gaussian KDE (Kernel Density Estimate)

    Parameters
    ----------
    features : nd-array
        Input from which probability density function is computed

    Returns
    -------
    nd-array
        probability density values

    """
    features_ = np.copy(features)
    xx = create_xx(features_)

    if min(features_) == max(features_):
        noise = np.random.randn(len(features_)) * 0.0001
        features_ = np.copy(features_ + noise)

    kernel = scipy.stats.gaussian_kde(features_, bw_method='silverman')

    return np.array(kernel(xx) / np.sum(kernel(xx)))


def gaussian(features):
    """Computes the probability density function of the input signal using a Gaussian function

    Parameters
    ----------
    features : nd-array
        Input from which probability density function is computed
    Returns
    -------
    nd-array
        probability density values

    """

    features_ = np.copy(features)

    xx = create_xx(features_)
    std_value = np.std(features_)
    mean_value = np.mean(features_)

    if std_value == 0:
        return 0.0
    pdf_gauss = scipy.stats.norm.pdf(xx, mean_value, std_value)

    return np.array(pdf_gauss / np.sum(pdf_gauss))


def wavelet(signal, function=scipy.signal.ricker, widths=np.arange(1, 10)):
    """Computes CWT (continuous wavelet transform) of the signal.

    Parameters
    ----------
    signal : nd-array
        Input from which CWT is computed
    function :  wavelet function
        Default: scipy.signal.ricker
    widths :  nd-array
        Widths to use for transformation
        Default: np.arange(1,10)

    Returns
    -------
    nd-array
        The result of the CWT along the time axis
        matrix with size (len(widths),len(signal))

    """

    if isinstance(function, str):
        function = eval(function)

    if isinstance(widths, str):
        widths = eval(widths)

    cwt = scipy.signal.cwt(signal, function, widths)

    return cwt


def calc_ecdf(signal):
    """Computes the ECDF of the signal.

      Parameters
      ----------
      signal : nd-array
          Input from which ECDF is computed
      Returns
      -------
      nd-array
        Sorted signal and computed ECDF.

      """
    return np.sort(signal), np.arange(1, len(signal)+1)/len(signal)


def get_lennan(*args: tuple[ndarray, pd.Series]) -> int:
    """参数必须为np.ndarray"""
    args = [arg.values if hasattr(arg, "values") else arg for arg in args]
    result = [len(arg[pd.isnull(arg)])
              for arg in args if isinstance(arg, ndarray)]
    if len(result) == 1:
        return result[0]
    return max(*result)


def get_final_html(report_name: str, final_css: str, nav_html: str, merged_content: str, final_js: str) -> str:
    return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>合并版QuantStats分析报告 - {report_name}</title>
            <style type="text/css">
                {final_css}
                /* 全局样式 */
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: #fafafa;
                    color: #2d3748;
                    margin: 0;
                    padding: 0;
                }}
                .strategy-report {{
                    margin: 25px 0;
                    padding: 20px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background: #fff;
                    display: none;
                }}
                .strategy-report.active {{
                    display: block !important;
                }}
                #report-nav {{
                    position: fixed;
                    left: 0;
                    top: 0;
                    width: 250px;
                    height: 100%;
                    overflow-y: auto;
                    background: #f7fafc;
                    padding: 20px;
                    box-shadow: 2px 0 5px rgba(0,0,0,0.1);
                    z-index: 1000;
                }}
                #report-nav ul li {{
                    margin-bottom: 10px;
                }}
                #report-nav ul li a {{
                    color: #3182ce;
                    text-decoration: none;
                    display: block;
                    padding: 8px 12px;
                    border-radius: 4px;
                    transition: background 0.2s;
                }}
                #report-nav ul li a:hover {{
                    background: #edf2f7;
                }}
                #report-nav ul li a.active {{
                    background: #3182ce;
                    color: white;
                }}
                #content-area {{
                    margin-left: 270px;
                    padding: 20px;
                }}
                /* 响应式设计 */
                @media (max-width: 768px) {{
                    #report-nav {{
                        position: relative;
                        width: 100%;
                        height: auto;
                        margin-bottom: 20px;
                    }}
                    #content-area {{
                        margin-left: 0;
                    }}
                }}
            /* 强制使用亮色主题 */
            body {{
                background-color: #ffffff !important;
                color: #000000 !important;
            }}
            .js-plotly-plot .plotly, .plot-container {{
                background-color: #ffffff !important;
            }}
            .modebar {{
                background-color: #ffffff !important;
            }}
            .main-svg {{
                background-color: #ffffff !important;
            }}
            .bg-dark {{
                background-color: #f8f9fa !important;
                color: #000000 !important;
            }}
            .text-white {{
                color: #000000 !important;
            }}
            .navbar-dark {{
                background-color: #f8f9fa !important;
            }}
            .navbar-dark .navbar-nav .nav-link {{
                color: rgba(0, 0, 0, 0.8) !important;
            }}
            .card {{
                background-color: #ffffff !important;
                border: 1px solid #e0e0e0 !important;
            }}
            .table {{
                color: #000000 !important;
            }}
            </style>
        </head>
        <body>
            {nav_html}
            <div id="content-area">
                {''.join(merged_content)}
            </div>
            <script type="text/javascript">
                {final_js}
                
                // 修复：使用更可靠的方式确保DOM完全加载
                function initReports() {{
                    // 获取所有策略报告
                    const strategyReports = document.querySelectorAll('.strategy-report');
                    
                    // 显示第一个策略报告
                    if (strategyReports.length > 0) {{
                        strategyReports[0].classList.add('active');
                        // 激活第一个导航链接
                        const firstNavLink = document.querySelector('.nav-link');
                        if (firstNavLink) {{
                            firstNavLink.classList.add('active');
                        }}
                    }}
                    
                    // 为导航链接添加点击事件
                    const navLinks = document.querySelectorAll('.nav-link');
                    navLinks.forEach(link => {{
                        link.addEventListener('click', function(e) {{
                            e.preventDefault();
                            const targetId = this.getAttribute('data-target');
                            scrollToStrategy(targetId);
                            
                            // 更新导航链接激活状态
                            navLinks.forEach(l => l.classList.remove('active'));
                            this.classList.add('active');
                        }});
                    }});
                }}
                
                // 滚动到指定策略报告
                function scrollToStrategy(strategyId) {{
                    // 隐藏所有策略报告
                    const strategyReports = document.querySelectorAll('.strategy-report');
                    strategyReports.forEach(report => {{
                        report.classList.remove('active');
                    }});
                    
                    // 显示选中的策略报告
                    const targetReport = document.getElementById(strategyId);
                    if (targetReport) {{
                        targetReport.classList.add('active');
                        
                        // 滚动到报告位置
                        window.scrollTo({{
                            top: targetReport.offsetTop - 20,
                            behavior: 'smooth'
                        }});
                    }}
                }}
                
                // 修复：多种方式确保初始化代码执行
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initReports);
                }} else {{
                    initReports();
                }}
                
                // 额外保险：延迟执行确保所有元素已加载
                setTimeout(initReports, 100);
            </script>
        </body>
        </html>
        """


def get_nav_html(nav_items: list[str]) -> str:
    return f"""
        <div id="report-nav" style="position: fixed; left: 0; top: 0; width: 250px; height: 100%; 
                overflow-y: auto; background: #f7fafc; padding: 20px; box-shadow: 2px 0 5px rgba(0,0,0,0.1); z-index: 1000;">
            <h3 style="margin: 0 0 15px 0; color: #2d3748;">策略导航</h3>
            <ul style="list-style: none; padding: 0; margin: 0;">
                {''.join(nav_items)}
            </ul>
        </div>
        """ if nav_items else ""


def get_final_merged_html(final_merged_output, data_uri, filename, escaped_html, report_height) -> tuple[str]:
    return f"""
        <p>📊 合并报告:</p>
        <!-- 浏览器渲染打开（默认显示页面效果） -->
        <a href="{final_merged_output}" target="_blank" style="display: inline-block; margin-right: 15px; padding: 8px 12px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px;">
            → 点击查看HTML源文件：{filename}
        </a>
        
        <!-- 下载HTML源文件 -->
        <a href="{data_uri}" download="{filename}" style="display: inline-block; padding: 8px 12px; background: #2196F3; color: white; text-decoration: none; border-radius: 4px;">
            → 点击下载HTML源文件：{filename}
        </a>""", f"""
        <div style="margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; padding: 10px;">
            <h4 style="margin-top: 0;">合并报告预览</h4>
            <iframe 
                srcdoc='{escaped_html}' 
                width="100%" 
                height="{report_height}" 
                frameborder="0"
                style="border: 1px solid #eee; border-radius: 3px;"
            ></iframe>
            <p style="font-size: 12px; color: #666; margin: 10px 0 0 0;">
                如果图表未正常显示，请点击上方链接查看完整报告
            </p>
        </div>
        """
