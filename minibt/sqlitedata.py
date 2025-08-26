from pandas import DataFrame, read_sql, Series, unique, read_csv, to_datetime
from sqlalchemy import create_engine, text
import sqlalchemy.ext.declarative
from sqlalchemy.orm import Session
import os
from typing import List, Dict, Union, Optional
from addict import Addict
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class MySqlite:
    contract_dict = {}
    _tables_names = []
    index_dict = {}

    def __init__(self, data_dir: str = None) -> None:
        if not data_dir:
            dir = os.path.join(BASE_DIR, 'data', 'data.db')
        else:
            dir = ""
            assert isinstance(data_dir, str), '路径非字符串'
            if data_dir.endswith('.db'):
                dir = data_dir
            else:
                dir = os.path.join(data_dir, 'data', 'data.db')
                if not os.path.isfile(dir):
                    dir = os.path.join(data_dir, 'data.db')
        assert isinstance(dir, str)
        self.db_dir = f'sqlite:///{dir}'
        assert os.path.isfile(dir), '找不到文件'
        print(f'sqlite data from : {self.db_dir}')
        self.engine = create_engine(self.db_dir)
        # 创建Session
        self.conn = Session(bind=self.engine.connect())

        # 使用cursor.fast_executemany加速批量插入操作
        self.cursor = self.conn.connection().connection.cursor()
        # self.cursor.fast_executemany = True
        # self.drop_all_tables()
        # self.__base()
        # self.delete_isin("CFFEX")
        self.contract_dict = Addict()
        try:
            self.contract_dict_frame = self.read_dataframe('contract')
            if self.contract_dict_frame.empty:
                self.contract_dict_frame = read_csv(
                    "./minibt/data/contract.csv")
                self.to_dataframe(self.contract_dict_frame, 'contract')
            d = self.contract_dict_frame.to_dict(orient="records")
            for dd in d:
                key = dd.pop("name")
                self.contract_dict.update({key: Addict(dd)})
        except:
            self.contract_dict_frame = DataFrame(
                columns=['name', 'ins', 'symbol', 'price_tick', 'volume_multiple'])
        # print(self.contract_dict)
        # self.contract_dict=self.read_sql('contract')
        # self.set_full_name()
        # if 'pd' in self.tablenames:
        #     self.contract_params_dict=self.read_sql('pd')

        # if 'index' in self.tablenames:
        #     self.index_dict=self.read_sql('index')

    # def __base(self) -> None:
    #     self.base = sqlalchemy.ext.declarative.declarative_base()
    #     self.base.metadata.reflect(self.engine)
    #     self.tables = self.base.metadata.tables
    #     self._tables_names = list(self.tables.keys())

    def rowid(self, name):
        self.cursor.execute(f"SELECT count(*) FROM {name}")
        fetchone = self.cursor.fetchone()
        return fetchone[0]

    @property
    def tablenames(self):
        """get the names of the tables in an sqlite db as a list"""
        GET_TABLENAMES = 'SELECT name FROM sqlite_master WHERE type="table"'
        self.cursor.execute(GET_TABLENAMES)
        return [name[0] for name in self.cursor.fetchall()]

    def _get_last_datetime(self, name) -> str:
        if name not in self.tablenames:
            print(f"表格{name}不存在")
            return ""
        self.cursor.execute(
            f"SELECT datetime FROM {name} WHERE datetime = (SELECT MAX(datetime) FROM {name});",)
        item = self.cursor.fetchone()
        return item[0] if item else ""
        # with self.engine.connect() as conn:
        #     conn.execute(f"SELECT * FROM {name}")
        #     fetchone = self.cursor.fetchone()
        #     # read_sql(f"SELECT * FROM {name}", con=conn).to_dict()[-1]["datetime"]
        #     return fetchone

    def _get_data(self, name, start=None, end=None, length=0):
        if length > 0:
            string = f"SELECT * FROM {name} LIMIT {max(1,self.rowid(name)-length)},{length}"
        elif start:
            if end:
                string = f"select * from {name} where datetime between '{start}' and '{end}'"
            else:
                string = f"select * from {name} where datetime >= '{start}'"
        self.cursor.execute(string)
        return self.cursor.fetchall()

    @property
    def table_names(self) -> List[str]:
        """数据库中的表格名称"""
        return self._tables_names

    def execute(self, sql_text: str) -> None:
        """执行sql语句"""
        assert isinstance(sql_text, str)
        if sql_text:
            with self.engine.connect() as conn:
                conn.execute(text(sql_text))

    def rename(self, old, new) -> None:
        assert isinstance(old, str) and isinstance(new, str)
        if old not in self.tablenames:
            return print(f"表格{old}不存在")
        with self.engine.connect() as conn:
            conn.execute(text(f'alter table {old} rename to {new}'))

    def to_dataframe(self, frame: DataFrame, name: str, if_exists='append', index=False, if_print=False) -> None:
        """dataframe写入数据库"""
        assert isinstance(name, str) and name
        assert isinstance(frame, DataFrame)
        frame.to_sql(name, self.engine, if_exists=if_exists, index=index)
        if if_print:
            print(f"{name}保存成功")

    def read_dataframe(self, table_name) -> DataFrame:
        """从数据库中读取dataframe"""
        if table_name not in self.tablenames:
            print(f"表格{table_name}不存在")
            return DataFrame()
        with self.engine.connect() as conn:
            return read_sql(table_name, con=conn)

    def delete(self, table_name: Union[str, List[str]]) -> None:
        """从数据库中删除dataframe"""
        if isinstance(table_name, str):
            if table_name not in self.tablenames:
                return print(f"表格{table_name}不存在")
            with self.engine.connect() as conn:
                conn.execute(text(f'drop table if exists {table_name}'))
        elif isinstance(table_name, (list, tuple)):
            if table_name:
                with self.engine.connect() as conn:
                    for name in table_name:
                        if name in self.tablenames:
                            conn.execute(text(f'drop table if exists {name}'))

    def drop_all_tables(self):
        for name in self.tablenames:
            with self.engine.connect() as conn:
                conn.execute(text(f'drop table if exists {name}'))

    def delete_isin(self, string: str):
        assert isinstance(string, str)
        names = []
        if self.tablenames:
            for name in self.tablenames:
                if string in name:
                    names.append(name)
            self.delete(names)

    def delete_cycle(self, cycle: int):
        """删除周期所有数据"""
        names = []
        if self.tablenames:
            for name in self.tablenames:
                if ''.join(['_', str(cycle)]) in name:
                    names.append(name)
            self.delete(names)

    def to_sql(self, obj: object, name: str) -> None:
        """保存数据到数据库"""
        if isinstance(obj, DataFrame):
            frame = obj
        elif isinstance(obj, Series):
            frame = DataFrame({'Series': obj})
        else:
            dtype = type(obj)
            if isinstance(obj, (list, tuple, set)):
                dict_ = {str(dtype): list(obj)}
            elif isinstance(obj, dict):
                dict_ = dict(keys=list(obj.keys()), values=list(obj.values()))
            else:
                dict_ = {str(dtype): [obj,]}
            frame = DataFrame(dict_)
        self.to_dataframe(frame, name)

    def read_sql(self, name: str):
        """获取数据库数据"""
        if name not in self.tablenames:
            return print(f"表格{name}不存在")
        frame = self.read_dataframe(name)
        if frame is None:
            return
        if not frame.empty:
            columns = list(frame.columns)
            if len(columns) == 1:
                if columns[0] in ['list', 'tuple', 'set', 'Series']:
                    ojb = eval(columns)(frame[columns[0]].to_list())
                    return ojb
                else:
                    return ojb.values[0][0]
            else:
                keys, values = frame.values[:, 0].tolist(
                ), frame.values[:, 1].tolist()
                return dict(zip(keys, values))

    def quick_real_dataframe(self, name, cycle=60, data_length=None, index=False, tick=False) -> DataFrame:
        """通过合约小写简称获取数据"""
        table_name = ''
        if index:
            if self.index_dict:
                _index = self.index_dict.get(name)
                ins, _ = _index.split('@')[1].split('.')
                table_name = '_'.join([ins, name, 'index', str(cycle)])
            else:
                table_name = '_'.join([self.contract_dict.get(
                    name)['ins'], name, 'index', str(cycle)])
        else:
            if self.contract_dict:
                try:
                    ff = self.contract_dict.get(name)['ins']
                except:
                    ff = ""
                table_name = '_'.join(
                    [ff, name, 'tick' if tick else str(cycle)])

        if table_name in self.tablenames:
            data = self.read_dataframe(table_name)
            data.datetime = to_datetime(data.datetime)
            cols = list(data.columns)
            if self.contract_dict:
                if 'symbol' not in cols or index:
                    data["symbol"] = self.contract_dict.get(
                        name)['symbol']
                if 'duration' not in cols or index:
                    data["duration"] = int(cycle)
                if 'price_tick' not in cols or index:
                    data["price_tick"] = self.contract_dict.get(
                        name)['price_tick']  # self.read_sql("price_tick")[name]
                if 'volume_multiple' not in cols or index:
                    data["volume_multiple"] = self.contract_dict.get(
                        name)['volume_multiple']  # self.read_sql("volume_multiple")[name]
            if isinstance(data_length, int) and 0 < data_length < len(data):
                data = data[-data_length:]
                data.reset_index(drop=True, inplace=True)
            return data
        return DataFrame()

    def set_full_name(self):
        self.contract_full_lower_dict = {}
        self.contract_full_upper_dict = {}
        try:
            if self.contract_dict:
                for k, v in self.contract_dict.items():
                    self.contract_full_upper_dict.update({k: '.'.join([v, k])})
                    self.contract_full_lower_dict.update(
                        {k: '.'.join([v, k.lower()])})
        except:
            ...

    def get_contract_full_name_lower(self, short_name: str) -> Optional[str]:
        """小写全称"""
        if self.contract_full_lower_dict:
            return self.contract_full_lower_dict.get(short_name, None)

    def get_contract_full_name_upper(self, short_name: str) -> Optional[str]:
        """大写全称"""
        if self.contract_full_upper_dict:
            return self.contract_full_upper_dict.get(short_name, None)

    @property
    def contract_names(self, upper=True) -> Optional[List[str]]:
        """合约全称（不含数字）"""
        if self.contract_full_upper_dict:
            if upper:
                return list(self.contract_full_upper_dict.values())
            else:
                return list(self.contract_full_lower_dict.values())

    @property
    def contract(self) -> List[str]:
        """合约小写简称"""
        return list(self.contract_dict.keys())

    def contract_data(self, cycle=60, length=None) -> Dict[str, DataFrame]:
        """取周期为cycle,长度为length的所有dataframe数据"""
        n = ''.join(['_', str(cycle)])
        data = {}
        for name in self.tablenames:
            if n in name:
                _name = name.split('_')[1]
                d = self.read_dataframe(name)
                if length:
                    d = d[-length:]
                    d.reset_index(drop=True, inplace=True)
                data.update({_name: d})
        return data

    def close(self):
        """销毁数据库连接"""
        self.engine.dispose()

    def save_pd(self, contract: str, pd: int):
        """保存pd"""
        assert contract in self.contract_params_dict, '合约简称不正确'
        x, y = divmod(pd, 10)
        assert 5 <= x <= 30 and 1 <= y <= 9, 'pd值不正确'
        self.contract_params_dict[contract] = pd
        self.to_sql(self.contract_params_dict, 'pd')

    def resetdata(self):
        if self.tablenames:
            for name in self.tablenames:
                if '_' in name:
                    data = self.read_dataframe(name)
                    if len(data) != len(unique(data.datetime)):
                        data.drop_duplicates(
                            'datetime', keep='last', ignore_index=True, inplace=True)
                        self.to_dataframe(data, name)
