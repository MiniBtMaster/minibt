from __future__ import annotations
import os
import glob
from typing import TYPE_CHECKING, Union
from pandas import DataFrame, read_csv

__all__ = ["base", "DataString"]
if TYPE_CHECKING:
    from .utils import LocalDatas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class DataString(str):

    @property
    def dataframe(self) -> DataFrame:
        path = os.path.join(BASE_DIR, "test", f"{self}.csv")
        df = read_csv(path, index_col=0)
        try:
            from ..other import time_to_datetime
            df.datetime = df.datetime.apply(time_to_datetime)
        except:
            ...
        return df


class base:

    def update(self) -> LocalDatas | base:
        """更新本地文件"""
        self.rewrite()
        return self

    def deleter(self, *args) -> LocalDatas | base:
        """删除目标文件"""
        if args:
            t = False
            for name in args:
                path = os.path.join(BASE_DIR, "test", f"{name}.csv")
                if os.path.exists(path):
                    t = True
                    os.remove(path)
            if t:
                self.rewrite()
        return self

    def keep(self, *args) -> LocalDatas | base:
        """保留目标文件，其余的删除"""
        if args:
            attr = {k: v for k, v in vars(
                self.__class__).items() if not k.startswith("_")}
            delete_names = [k for k, v in attr.items() if k not in args]
            t = False
            for name in delete_names:
                path = os.path.join(BASE_DIR, "test", f"{name}.csv")
                if os.path.exists(path):
                    t = True
                    os.remove(path)
            if t:
                self.rewrite()
        return self

    def rename(self, old_name: str = "", new_name: str = "") -> LocalDatas | base:
        if all([old_name, new_name]) and all([isinstance(old_name, str), isinstance(new_name, str)]):
            old_path = os.path.join(BASE_DIR, "test", f"{old_name}.csv")
            if os.path.exists(old_path):
                os.rename(old_path, os.path.join(
                    BASE_DIR, "test", f"{new_name}.csv"))
                self.rewrite()
        return self

    @staticmethod
    def rewrite(check=False):
        # 获取当前目录下所有CSV文件名

        csv_files = glob.glob(os.path.join(BASE_DIR, "test", "*.csv"))
        py_file_path = os.path.join(BASE_DIR, "utils.py")

        names = [os.path.splitext(os.path.basename(file))[0]
                 for file in csv_files]
        if check:
            from .utils import LocalDatas
            attr = [k for k, _ in vars(
                LocalDatas.__class__).items() if not k.startswith("__")]
            check = all([name in attr for name in names])
        if not check:
            class_content = ['from .tools import *', "", "",
                             'class LocalDatas(base):', '    """本地CSV数据"""']
            for name in names:
                class_content.append(f'    {name} = DataString("{name}")')
            class_content.extend(["", ""])
            class_content.append('LocalDatas=LocalDatas()')
            with open(py_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(class_content))

    def __getitem__(self, key: str) -> str | LocalDatas:
        assert key and isinstance(key, str), "key为非空字符串"
        return key

    def __getattr__(self, name: str) -> str | LocalDatas:
        try:
            return super().__getattr__(name)
        except:
            setattr(self, name, name)
            return name

    @staticmethod
    def get_path(name: str) -> str:
        return os.path.join(BASE_DIR, "test", f"{name}.csv")

    def get_dataframe(self, name: str) -> DataFrame:
        df = read_csv(self.get_path(name))
        try:
            from ..other import time_to_datetime
            df.datetime = df.datetime.apply(time_to_datetime)
        except:
            ...
        return df

#     def _get_valid_attributes(self) -> list[str]:
#         """获取有效的属性名列表（过滤掉非字符串和方法）"""
#         return [
#             name for name, value in vars(self.__class__).items()
#             if not name.startswith('__')
#             and isinstance(value, str)
#             and not callable(value)
#         ]

#     @property
#     def dataframe(self) -> DF:
#         return DF(self)


# class DF:
#     def __init__(self, LocalDatas: LocalDatas):
#         self.LocalDatas = LocalDatas

#     def __getattribute__(self, name: str) -> DataFrame:
#         # 特殊属性直接返回
#         if name == "LocalDatas":
#             return object.__getattribute__(self, "LocalDatas")

#         # 检查属性是否有效
#         valid_attrs = self.LocalDatas._get_valid_attributes()
#         if name not in valid_attrs:
#             raise AttributeError(f"'{name}' is not a valid data attribute")

#         return self.LocalDatas.get_dataframe(name)

#     def __dir__(self) -> list[str]:
#         """返回可供补全的有效属性列表"""
#         return self.LocalDatas._get_valid_attributes()
