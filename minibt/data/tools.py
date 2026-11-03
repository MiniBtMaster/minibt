from __future__ import annotations
import os
import glob
import shutil
from typing import TYPE_CHECKING
from pandas import DataFrame, read_csv
from ..other import time_to_datetime


__all__ = ["base", "DataString", "datas_dirs", "user_datas_dir",
           "list_csv_names", "package_csv_names", "get_csv_path",
           "ensure_user_copy", "import_package_data", "rewrite_datas",
           "reset_index", "add_external", "remove_external", "external_items",
           "external_paths"]
if TYPE_CHECKING:
    from .utils import LocalDatas
    from ..indicators import KLine

#: 包内**只读**基础数据目录（随包分发；开箱即用 + 测试用）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_DATAS = os.path.join(BASE_DIR, "test")
_kline = None


# ------------------------------------------------------------------ 目录解析
def user_datas_dir() -> str:
    """## 用户数据目录 ``~/.minibt/datas``

    与 ``setting.json`` 同目录（Windows 即 ``C:\\Users\\<你>\\.minibt\\datas``），
    可用环境变量 ``MINIBT_SETTINGS`` 覆盖（指向目录或 ``.../setting.json``）。
    用户自己的 CSV 放这里；同名文件会**覆盖**包内基础数据。
    """
    try:
        from ..utils import user_dir
        root = user_dir()
    except Exception:                      # 独立运行/循环导入兜底
        env = os.environ.get('MINIBT_SETTINGS')
        if env:
            p = os.path.expanduser(env)
            root = p if not os.path.splitext(p)[1] else os.path.dirname(
                os.path.abspath(p))
        else:
            root = os.path.join(os.path.expanduser('~'), '.minibt')
    return os.path.join(root, 'datas')


#: **外部数据登记表**（单个 CSV 与文件夹混存，只记路径、不复制 ✓）
EXTERNAL_FILE = os.path.join(os.path.expanduser('~'), '.minibt',
                             'datas_external.json')

#: 只读开头几行做校验（有些 CSV 几个 GB，不能整表读 ✓）
PROBE_LINES = 10


def _filed_all() -> list[str]:
    """minibt 的合法字段集 ``FILED.ALL``（`datetime/open/high/low/close/volume`）"""
    try:
        from ..other import FILED
        return [str(name) for name in FILED.ALL]
    except Exception:                                            # noqa: BLE001
        return ['datetime', 'open', 'high', 'low', 'close', 'volume']


#: 列名别名（`date/time` → datetime，`vol/v` → volume …）
_ALIASES = {
    'datetime': ('datetime', 'date_time', 'date', 'time', 'timestamp'),
    'open': ('open', 'o'), 'high': ('high', 'h'),
    'low': ('low', 'l'), 'close': ('close', 'c'),
    'volume': ('volume', 'vol', 'v'),
}


def _read_external() -> list[str]:
    try:
        import json
        with open(EXTERNAL_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str)]
    except Exception:                                            # noqa: BLE001
        pass
    return []


def _write_external(paths: list[str]) -> None:
    try:
        import json
        os.makedirs(os.path.dirname(EXTERNAL_FILE), exist_ok=True)
        with open(EXTERNAL_FILE, 'w', encoding='utf-8') as handle:
            json.dump(list(dict.fromkeys(paths)), handle, ensure_ascii=False,
                      indent=2)
    except Exception:                                            # noqa: BLE001
        pass


def _valid_csv(path: str) -> bool:
    """表头必须是 **`FILED.ALL`**（minibt 合法字段集）✓

    只读**前 `PROBE_LINES` 行**判断（大文件也能秒判，不会整表读 ✗）：

    * 取第一行非空行当表头；
    * 必须**包含** ``datetime + open + high + low + close + volume``
      （``FILED.ALL``；别名 ``date/time``、``o/h/l/c``、``vol/v`` 也认）；
    * 打不开 / 空文件 / 少字段 → 不合法 ✓
    """
    try:
        with open(path, encoding='utf-8', errors='ignore') as handle:
            lines = [handle.readline() for _ in range(PROBE_LINES)]
    except Exception:                                            # noqa: BLE001
        return False
    header = next((line.strip() for line in lines if line.strip()), '')
    if not header:
        return False
    columns = [part.strip().strip('"').strip("'").lower()
               for part in header.split(',')]
    if not columns:
        return False
    for name in _filed_all():
        aliases = _ALIASES.get(name, (name,))
        if not any(alias in columns for alias in aliases):
            return False
    return True


def external_paths() -> list[str]:
    """外部登记过的路径（**文件与文件夹**，只保留仍然存在的 ✓）"""
    return [path for path in _read_external() if os.path.exists(path)]


def _csv_paths_of(path: str) -> list[str]:
    """一个登记项 → 具体 CSV 文件列表（文件就一个；文件夹取下一层 `*.csv`）"""
    if os.path.isfile(path) and path.lower().endswith('.csv'):
        return [path]
    if os.path.isdir(path):
        # 只列**合法**的 K 线 CSV（表头不符合的直接忽略 ✓）
        return [csv for csv in sorted(glob.glob(os.path.join(path, '*.csv')))
                if _valid_csv(csv)]
    return []


def external_items() -> list[tuple[str, str]]:
    """外部登记的数据 → ``[(名字, 绝对路径), …]``（按登记顺序 ✓）"""
    out: list[tuple[str, str]] = []
    for path in external_paths():
        for csv in _csv_paths_of(path):
            name = os.path.splitext(os.path.basename(csv))[0]
            if name:
                out.append((name, os.path.abspath(csv)))
    return out


def add_external(*paths: str, rewrite: bool = True) -> list[str]:
    """## 把**外部 CSV / 文件夹**登记到 ``LocalDatas``（只记路径，不复制）

    支持两种方式（可一次传多个）::

        from minibt import LocalDatas

        # ① 单个 CSV
        LocalDatas.add('C:/data/bar_data.csv')

        # ② 文件夹下的**所有** CSV（扫描一层）
        LocalDatas.add('C:/Users/you/Desktop/bar_data')

    登记后 ``LocalDatas`` 里就会出现对应的名字，``get_kline(LocalDatas.bar_data)``
    直接按路径读取 —— 文件**改了内容立刻生效**（按 mtime 缓存），
    但**改名/移动/删除后需要重新 add**。

    返回实际登记（或已存在）的路径列表；不合法的 CSV 会打印提示并跳过 ✓。
    """
    recorded = _read_external()
    added: list[str] = []
    names: list[str] = []
    for raw in paths:
        path = os.path.abspath(os.path.expanduser(str(raw or '').strip()))
        if not path:
            continue
        if os.path.isdir(path):
            csvs = _csv_paths_of(path)
            if not csvs:
                print(f'[minibt] 文件夹里没有 CSV：{path}')
                continue
            valid = [csv for csv in csvs if _valid_csv(csv)]
            for csv in csvs:
                if csv not in valid:
                    print(f'[minibt] 跳过（表头不是 K 线格式）：{csv}')
            if not valid:
                continue
        elif os.path.isfile(path):
            if not _valid_csv(path):
                print(f'[minibt] 跳过（表头不是 K 线格式）：{path}')
                continue
        else:
            print(f'[minibt] 路径不存在：{path}')
            continue
        if path not in recorded:
            recorded.append(path)
        added.append(path)
        names += [os.path.splitext(os.path.basename(csv))[0]
                  for csv in _csv_paths_of(path)]
    if added:
        _write_external(recorded)
        if rewrite:
            base.rewrite()
    return added


def remove_external(*paths: str, rewrite: bool = True) -> list[str]:
    """取消登记（**不删文件**）；传文件夹会移除该条记录 ✓"""
    want = {os.path.abspath(os.path.expanduser(str(p or '').strip()))
            for p in paths if str(p or '').strip()}
    recorded = [path for path in _read_external() if path not in want]
    _write_external(recorded)
    if rewrite:
        base.rewrite()
    return recorded


def datas_dirs() -> list[str]:
    """数据目录列表（**按优先级**）：用户目录 → 包内目录。"""
    return [user_datas_dir(), _PACKAGE_DATAS]


def list_csv_names() -> list[str]:
    """扫描全部数据名（去重、排序）：用户目录 + **外部登记** + 包内。"""
    names: set[str] = set()
    for d in datas_dirs():
        if os.path.isdir(d):
            for f in glob.glob(os.path.join(d, "*.csv")):
                names.add(os.path.splitext(os.path.basename(f))[0])
    for name, _path in external_items():          # ★ 外部 CSV / 文件夹 ✓
        names.add(name)
    return sorted(names)


def package_csv_names() -> list[str]:
    """只要**包内**基础数据的名字（``minibt/data/test``）。

    打包前复位 ``LocalDatas`` 索引用（见 :func:`reset_index`），避免把本机
    ``~/.minibt/datas`` 里的私人数据名写进 wheel。
    """
    names: set[str] = set()
    if os.path.isdir(_PACKAGE_DATAS):
        for f in glob.glob(os.path.join(_PACKAGE_DATAS, "*.csv")):
            names.add(os.path.splitext(os.path.basename(f))[0])
    return sorted(names)


def get_csv_path(name: str) -> str:
    """按优先级返回某个数据的 CSV 路径（用户目录优先，包内兜底）。

    两边都没有时返回**用户目录**下的路径（方便调用方直接写入）。
    """
    for d in datas_dirs():
        path = os.path.join(d, f"{name}.csv")
        if os.path.exists(path):
            return path
    for ext_name, ext_path in external_items():    # ★ 外部登记（优先于包内）
        if ext_name == name:
            return ext_path
    return os.path.join(user_datas_dir(), f"{name}.csv")


def ensure_user_copy(name: str) -> str:
    """确保 ``~/.minibt/datas/{name}.csv`` 存在（缺失时从包内复制一份），返回该路径。"""
    user = os.path.join(user_datas_dir(), f"{name}.csv")
    if not os.path.exists(user):
        src = os.path.join(_PACKAGE_DATAS, f"{name}.csv")
        if os.path.exists(src):
            os.makedirs(user_datas_dir(), exist_ok=True)
            shutil.copyfile(src, user)
    return user


def import_package_data(*names: str, overwrite: bool = False) -> list[str]:
    """把包内基础数据**显式**导出到 ``~/.minibt/datas``（想要完整可改副本时用）。

    ``import_package_data()`` 导出全部；``import_package_data('test')`` 只导出指定项。
    ``overwrite=False``（默认）时不覆盖已存在的用户文件。
    """
    want = set(names) or None
    out: list[str] = []
    for src in glob.glob(os.path.join(_PACKAGE_DATAS, "*.csv")):
        stem = os.path.splitext(os.path.basename(src))[0]
        if want is not None and stem not in want:
            continue
        dst = os.path.join(user_datas_dir(), f"{stem}.csv")
        if overwrite or not os.path.exists(dst):
            os.makedirs(user_datas_dir(), exist_ok=True)
            shutil.copyfile(src, dst)
        out.append(dst)
    return out


# ------------------------------------------------------------------ 数据对象
class DataString(str):

    @property
    def dataframe(self) -> DataFrame | None:
        # 用户目录优先，包内兜底
        path = get_csv_path(str(self))
        if not os.path.exists(path):
            path = str(self)               # 也支持直接传绝对路径
        if not os.path.exists(path):
            return
        df = read_csv(path, index_col=0).reset_index()
        try:
            df.datetime = df.datetime.apply(time_to_datetime)
        except Exception:
            print(f"本地数据{self}的时间数据无法处理")
        return df

    def __kline(self):
        global _kline
        if _kline is None:
            from ..indicators import KLine
            _kline = KLine
        return _kline

    @property
    def kline(self) -> KLine:
        if self.dataframe is None:
            return
        return self.__kline()(self.dataframe, height=450)


class base:

    def update(self) -> LocalDatas | base:
        """重新生成 ``minibt/data/utils.py``（``LocalDatas`` 索引）。"""
        self.rewrite()
        return self

    def deleter(self, *args) -> LocalDatas | base:
        """删除 ``~/.minibt/datas`` 里的目标文件（只动用户目录）。"""
        for name in args:
            path = os.path.join(user_datas_dir(), f"{name}.csv")
            if os.path.exists(path):
                os.remove(path)
        self.rewrite()
        return self

    def keep(self, *args) -> LocalDatas | base:
        """只保留 ``args``，其余**用户目录**里的文件删除（包内基础数据不受影响）。"""
        if not args:
            return self
        keep = set(args)
        for name in list_csv_names():
            if name in keep:
                continue
            path = os.path.join(user_datas_dir(), f"{name}.csv")
            if os.path.exists(path):
                os.remove(path)
        self.rewrite()
        return self

    def rename(self, old_name: str = "", new_name: str = "") -> LocalDatas | base:
        """重命名（先把包内同名的**懒拷贝**到用户目录，再改名）。"""
        if all([old_name, new_name]) and all(
                [isinstance(old_name, str), isinstance(new_name, str)]):
            old_path = ensure_user_copy(old_name)
            if os.path.exists(old_path):
                os.rename(old_path, os.path.join(
                    user_datas_dir(), f"{new_name}.csv"))
                self.rewrite()
        return self

    @staticmethod
    def rewrite(check: bool = False, base_only: bool = False):
        """重新生成 ``minibt/data/utils.py``（``LocalDatas`` 的索引）。

        把 ``~/.minibt/datas``（用户数据）与 ``minibt/data/test``（包内基础
        数据）两个目录里的 CSV 名字写成 ``LocalDatas`` 的类属性，这样用户能
        一眼看到有哪些本地数据可调用（``LocalDatas.pp2609_60`` …）。

        ``check=True`` 时先比较现有类属性，集合一致就**不重写**（避免每次
        ``import minibt`` 都写文件）。``get_kline(..., save='名字')`` 保存完
        数据后会自动调用本方法。只读安装下写不进去也不报错，退回动态扫描。

        ``base_only=True``：只列**包内基础数据**，忽略用户目录 —— 打包前
        复位索引用（见 :func:`reset_index`）。它**只影响索引文件**，不会删
        任何文件；要让某个名字从 ``LocalDatas`` 里消失，得用 ``deleter`` /
        ``keep`` 删掉 ``~/.minibt/datas`` 里那个真实文件。
        """
        source = package_csv_names() if base_only else list_csv_names()
        names = [n for n in source if n.isidentifier()]
        current: set[str] | None = None
        try:
            from .utils import LocalDatas as _current
            current = {k for k in _current.__class__.__dict__
                       if not k.startswith('_')}
        except Exception:
            current = None
        if check and not base_only and current is not None \
                and current == set(names):
            return None
        lines = [
            'from .tools import *',
            '',
            '',
            'class LocalDatas(base):',
            '    """本地 CSV 数据索引（自动生成，请勿手改）。',
            '',
            '    * 名字来自两个目录：``~/.minibt/datas``（用户数据，可写）与',
            '      ``minibt/data/test``（包内基础数据，随包分发、只读）；',
            '    * 同名时用户目录优先（盖上包内那份，包内文件不动）；',
            '    * **想让某个名字从这里消失，必须删掉对应的真实文件**：',
            "      用户目录用 ``LocalDatas.deleter('名字')`` 或",
            "      ``LocalDatas.keep('名字')``；只改本文件没用，",
            '      下一次 ``rewrite()`` 会把它原样生成回来；',
            '    * 增删 CSV 后 ``LocalDatas.rewrite()`` 会重新生成本文件',
            "      （``get_kline(..., save='名字')`` 会自动调用）；",
            '    * 打包前（``python -m build``）先跑一次',
            '      ``LocalDatas.rewrite(base_only=True)``（= ``reset_index()``）：',
            '      只列包内基础数据，免得把本机 ``~/.minibt/datas`` 里的',
            '      私人数据名写进 wheel；它只改索引文件、不删你的数据。',
            '    """',
            '',
        ]
        for name in names:
            lines.append(f'    {name} = DataString("{name}")')
        lines += ['', '', 'LocalDatas = LocalDatas()', '']
        try:
            with open(os.path.join(BASE_DIR, 'utils.py'), 'w',
                      encoding='utf-8') as f:
                f.write('\n'.join(lines))
        except OSError as error:          # 只读安装：退回动态扫描
            print(f'[minibt] 写不了 LocalDatas 索引（{error}），'
                  '继续用目录扫描')
        return None

    def __getitem__(self, key: str) -> DataString:
        assert key and isinstance(key, str), "key为非空字符串"
        return DataString(key)

    def __getattr__(self, name: str) -> DataString:
        if name.startswith("_"):
            raise AttributeError(name)
        # 任意名字都返回 DataString —— 支持 ``LocalDatas.任意csv名``（含 `get_kline` 用字符串）
        return DataString(name)

    def __dir__(self) -> list[str]:
        return list(dict.fromkeys([*super().__dir__(), *list_csv_names()]))

    # ---------------------------------------------------- 外部数据登记
    @staticmethod
    def add(*paths: str, rewrite: bool = True) -> list[str]:
        """## 登记**外部** CSV / 文件夹（单个文件或整个文件夹 ✓）

            LocalDatas.add('C:/data/bar_data.csv')          # ① 单个 CSV
            LocalDatas.add('C:/Users/me/Desktop/bar_data')  # ② 文件夹全部 CSV

        只记录路径（``~/.minibt/datas_external.json``），**不复制文件**；
        登记后 ``LocalDatas.名字`` / ``get_kline('名字')`` 直接按路径读取 ✓
        """
        return add_external(*paths, rewrite=rewrite)

    @staticmethod
    def remove(*paths: str, rewrite: bool = True) -> list[str]:
        """取消外部登记（**不删文件**）✓"""
        return remove_external(*paths, rewrite=rewrite)

    @staticmethod
    def externals() -> list[tuple[str, str]]:
        """已登记的外部数据 → ``[(名字, 路径), …]`` ✓"""
        return external_items()

    @staticmethod
    def get_path(name: str) -> str:
        return get_csv_path(name)

    def get_dataframe(self, name: str) -> DataFrame:
        df = read_csv(self.get_path(name))
        try:
            from ..other import time_to_datetime as _t2d
            df.datetime = df.datetime.apply(_t2d)
        except Exception:
            ...
        return df

    def get(self, name) -> DataString:
        return getattr(self, name)

    def __call__(self, name: str) -> DataString:
        return DataString(name)


def rewrite_datas(check: bool = False, base_only: bool = False):
    """重新生成 ``minibt/data/utils.py``（``LocalDatas`` 索引）。

    等价于 ``base.rewrite(check, base_only)``；
    ``other.save_and_generate_utils`` 保存完 CSV 后会调用它，让新数据立刻
    出现在 ``LocalDatas`` 里。``base_only=True`` 只列包内基础数据。
    """
    return base.rewrite(check, base_only)


def reset_index():
    """**打包前复位索引**：``LocalDatas`` 只列包内基础数据。

    等价于 ``rewrite_datas(base_only=True)``。

    ⚠ 它**只重新生成** ``minibt/data/utils.py``，**不会动任何 CSV 文件**：
    本机 ``~/.minibt/datas`` 里的用户数据依然在磁盘上（下次 ``rewrite()``
    又会把它们列回来）。要让某个名字真正从 ``LocalDatas`` 消失，请删掉真实
    文件 —— ``LocalDatas.deleter('名字')`` 或 ``LocalDatas.keep('名字')``。
    """
    return base.rewrite(base_only=True)
