import datetime
from typing import List, Union
from tqsdk import TqApi
from tqsdk.tafunc import time_to_datetime
from pandas import merge, concat, isna, read_pickle, to_pickle, to_datetime, read_csv
from minibt.sqlitedata import MySqlite, Addict
# from minibt.btdb import MiniDB
from minibt import FILED, partial
from iteration_utilities import flatten
from tqdm import tqdm
import time
from enum import Enum

# options.mode.chained_assignment = None
import warnings
warnings.filterwarnings('ignore')
tick_filed = ['datetime', 'last_price', 'average', 'highest', 'lowest', 'ask_price1',
              'ask_volume1', 'bid_price1', 'bid_volume1', 'volume', 'symbol', 'duration']
timetostr_func = partial(datetime.datetime.strftime,
                         format="%Y-%m-%d %H:%M:%S")


class default_params(Enum):
    exchange_id = 'all'
    ins_class = 'contract'
    fitl_contract = None
    cycle = 60
    data_length = 10000
    futuresdel = ['SHFE.wr', 'CZCE.RI', 'CZCE.LR', 'CZCE.JR', 'CZCE.PM', 'CZCE.RS', 'CZCE.WH',
                  'DCE.bb', 'DCE.rr', 'CZCE.ZC', 'CZCE.CJ',]
    if_day = True
    keep_length = 100000
    if_fail = False
    tick = False


class DataProcessors:
    '''数据库更新

        exchange_id
        ------------
            CFFEX : 中金所
            SHFE : 上期所
            DCE : 大商所
            CZCE : 郑商所

        ins_class
        ------------
            contract : 主力合约
            cont : 主连
            index : 指数
        '''

    def __init__(self, api: TqApi):
        now = datetime.datetime.now()
        # if now.date().weekday() < 5:
        #     assert datetime.time(15, 0) < now.time() < datetime.time(
        #         21, 0), '非周末时间更新数据时段为15:00-21:00'
        self.api = api
        self.exchange_id: str = None
        self.ins_class: str = None
        self.fitl_contract: Union[str, List[str]] = None
        self.cycle: Union[int, List[int]] = None
        self.data_length: int = None
        self.futuresdel: List[str] = None
        self.if_day: bool = None
        self.keep_length: int = None
        self.if_fail: bool = None
        self.tick: bool = False
        for params in default_params:
            setattr(self, params.name, params.value)
        #
        self.data_args = None
        self.contract: Union[str, List[str]] = None
        # self.mysplite: MySqlite = MySqlite()
        self.mysplite: MySqlite = MySqlite()

        self.contract_dict = self.mysplite.contract_dict
        self.contract_dict_frame = self.mysplite.contract_dict_frame
        # if not self.contract_dict:
        #     self.contract_dict = {}
        #     df = read_csv('./minibt/data/contract.csv')
        #     self.mysplite.to_dataframe(df, 'contract')
        #     d = df.to_dict(orient='records')
        #     for dd in d:
        #         key = dd.pop("name")
        #         self.contract_dict.update({key: Addict(dd)})
        #     self.mysplite.contract_dict = self.contract_dict

    def set_symbol(self, data_args: dict = {}):
        if data_args:
            self.data_args = data_args
            for k, v in data_args.items():
                setattr(self, k, v)

        if self.exchange_id == 'all':
            self.exchange_id = ["SHFE", "DCE", "CZCE", "CFFEX"]
        contract_day = []
        contract_night = []

        if self.ins_class == 'contract':  # 主力合约
            for id in self.exchange_id:
                contract_day.append(self.api.query_cont_quotes(exchange_id=id))

                contract_night.append(
                    self.api.query_cont_quotes(exchange_id=id, has_night=True))

        elif self.ins_class in ['cont', 'index']:  # 主连,指数
            ins_class = self.ins_class.upper()
            for id in self.exchange_id:
                contract_day.append(self.api.query_quotes(
                    ins_class=ins_class, exchange_id=id))
                contract_night.append(self.api.query_quotes(
                    ins_class=ins_class, exchange_id=id, has_night=True))

        if self.futuresdel:
            day = [sent for sent in list(flatten(contract_day)) if not any(
                word in sent for word in self.futuresdel)]
            night = [sent for sent in list(flatten(contract_night)) if not any(
                word in sent for word in self.futuresdel)]
        else:
            day = list(flatten(contract_day))
            night = list(flatten(contract_night))
        # if self.if_fail:
        #     self.fitl_contract = list(read_pickle('./fail_to_get.pkl'))
        # if isinstance(self.fitl_contract, list):
        #     if self.fitl_contract:
        #         day = [y for x in self.fitl_contract for y in day if (
        #             x if "." in x else self.mysplite.get_contract_full_name_upper(x)) in y]
        #         night = [y for x in self.fitl_contract for y in night if (
        #             x if "." in x else self.mysplite.get_contract_full_name_upper(x)) in y]

        self.contract = day if self.if_day else night
        print(self.contract)
        print(f"共{len(self.contract)}个合约")

        # values = map(lambda x: x.split('.')[0], day)
        # keys = map(lambda x: ''.join(
        #     [y for y in x if not y.isdigit()]).split('.')[1], day)
        # print(dict(zip(keys, values)), 'contract')
        # self.mysplite.update(items=[('contract', dict(zip(keys, values))),])
        return self

    def update_sql(self, reset: bool = False):
        # print(self.exchange_id,self.ins_class,self.fitl_contract,self.cycle,self.data_length,self.futuresdel,self.if_day,self.keep_length,self.if_fail,self.tick,)
        assert self.contract is not None
        pre_contract, if_save = "", True
        start_time = time.time()
        # fail_to_get_ls = []
        if self.tick:
            self.cycle = [0,]
        else:
            if isinstance(self.cycle, int):
                self.cycle = [self.cycle,]
            elif not isinstance(self.cycle, (list, tuple)):
                raise ('周期格式错误')
        if_replace_contract_dict = False
        # volume_multiple=[]
        # price_tick=[]
        # from pandas import DataFrame
        # df=DataFrame(columns=['name','ins','price_tick','volume_multiple'])
        for cycle in self.cycle:
            print((f"更新指数{int(cycle/60)}分钟周期" if self.ins_class == 'index' else f"更新主力合约{int(cycle/60)}分钟周期") if cycle else f"更新tick数据",
                  '*'*100, sep='\n')
            with tqdm(self.contract, colour='red', leave=True, position=0, ncols=160) as pbar:
                for c in pbar:
                    st = time.time()
                    if self.ins_class == "contract":
                        ins, name = c.split('.')
                        name_ = ''.join(
                            [c_ for c_ in name if not c_.isdigit()])
                        # quote=self.api.get_quote(c)
                        # df.loc[name,:]=[name,ins,quote.price_tick,quote.volume_multiple]
                        # name = name.lower()
                        if self.tick:
                            name = '_'.join([ins, name_, 'tick'])
                        else:
                            name = '_'.join([ins, name_, str(cycle)])
                    elif self.ins_class == "index":
                        _, name = c.split('@')
                        ins, name = name.split('.')
                        name = '_'.join(
                            [ins, name.lower(), 'index', str(cycle)])
                    if pre_contract:
                        if if_save:
                            pre_desc = f"{pre_contract}保存成功"
                        else:
                            pre_desc = f"{pre_contract}保存失败"
                        desc = f"{pre_desc}，正在下载{c}"
                    else:
                        desc = f"正在下载{c}"
                    pbar.set_description(f"{desc:39}")
                    pre_contract = name
                    if_get_df = True
                    try:
                        if self.tick:
                            df = self.api.get_tick_serial(
                                c, self.data_length)[tick_filed]
                        else:
                            df = self.api.get_kline_serial(
                                c, cycle, self.data_length)
                            if ins in ["CFFEX",]:
                                df.dropna(axis=0, how="any", inplace=True)

                        # values=map(lambda x :x.split('.')[0],day)
                        # keys=map(lambda x :''.join([y for y in x if not y.isdigit()]).split('.')[1],day)
                        # self.mysplite.to_sql(dict(zip(keys,values)),'contract')
                    except:
                        # fail_to_get_ls.append(c)
                        print(f"获取{c}数据失败")
                        if_get_df = False
                    if if_get_df:
                        # quote = self.api.get_quote(c)
                        # df.dropna(inplace=True)
                        df.datetime = to_datetime(
                            df.datetime).apply(timetostr_func)
                        if name not in self.contract_dict:
                            if_replace_contract_dict = True
                            quote = self.api.get_quote(c)
                            price_tick = quote.price_tick
                            volume_multiple = quote.volume_multiple
                            self.contract_dict_frame.loc[len(self.contract_dict_frame), :] = [
                                name_, ins, '.'.join([ins, name_]), price_tick, volume_multiple]

                        # df.symbol = df.symbol.apply(lambda x: x.split('@')[1] if "@" in x else ''.join(
                        #     [y for y in x if not y.isdigit()]))
                        df = df[FILED.ALL]
                        # quote = self.api.get_quote(c)
                        # df['volume_multiple']=quote.volume_multiple
                        # df['price_tick'] = quote.price_tick
                        exc = False
                        fail = False
                        if reset:
                            self.mysplite.delete_isin(name)
                            self.mysplite.to_dataframe(df, name)
                        # self.mysplite.update(name, df)
                        else:

                            # columns = list(df.columns)
                            # old_df = self.mysplite.read_dataframe(name)
                            # _cycle = df.duration.iloc[0]

                            # print(type(df.datetime.iloc[0]),type(old_df.datetime.iloc[0]))
                            if name not in self.mysplite.tablenames:
                                self.mysplite.to_dataframe(df, name)
                            else:
                                last_datetime = self.mysplite._get_last_datetime(
                                    name)
                                # assert _cycle == old_df.duration.iloc[0], "数据库数据周期与当前数据周期不一致"
                                # old_df.datetime=old_df.datetime.apply(time_to_datetime)#to_datetime(old_df.datetime)#
                                # 旧数据最后的时间是否在新数据中，如果在（没数据可更新）则不需要更新数据
                                if last_datetime == df.datetime.iloc[-1]:
                                    continue
                                try:
                                    # last_datetime = old_df.datetime.iloc[-1]
                                    date_time = df.datetime.isin(
                                        [last_datetime,])
                                    # print(date_time.any())
                                    if date_time.any():
                                        df = df[df.datetime >=
                                                last_datetime].copy()
                                        if not df.empty:
                                            df.reset_index(
                                                drop=True, inplace=True)
                                            # df = merge(
                                            #     old_df, df, how='outer', on=columns)
                                            # if len(df) > self.keep_length:
                                            #     df = df[-self.keep_length:]
                                            #     df.reset_index(
                                            #         drop=True, inplace=True)
                                            self.mysplite.to_dataframe(
                                                df, name, "replace")
                                        else:
                                            fail = True
                                            # pbar.set_postfix_str('数据更新过快')
                                    else:
                                        # df = concat([old_df, df], axis=1)
                                        # if len(df) > self.keep_length:
                                        #     df = df[-self.keep_length:]
                                        # df.reset_index(drop=True, inplace=True)
                                        self.mysplite.to_dataframe(df, name)
                                except Exception as e:
                                    exc = True
                                    # fail_to_get_ls.append(c)
                                    pbar.set_postfix_str(f"错误 :{name}保存数据不成功")

                        if exc:
                            string = f"{desc:39},错误 :保存数据不成功"
                        elif fail:
                            string = f"{desc:39},数据更新过快"
                        else:
                            string = f"{desc:39}"
                        pbar.set_description(string)
                    et = time.time()
                    pbar.set_postfix_str(
                        f"下载{name}数据用时：{round(et-st,2)}秒，维度：{df.shape if if_get_df else None}")
                    # volume_multiple.append(self.api.get_quote(c).volume_multiple)
                    # price_tick.append(self.api.get_quote(c).price_tick)
                else:
                    print(
                        f"所有数据下载完成,共{len(self.contract)}个数据，总耗时：{round(time.time()-start_time,2)}秒！")
        # contract=[''.join([c for c in contract.split('.')[1].lower() if not c.isdigit()]) for contract in self.contract ]
        # self.mysplite.to_sql(dict(zip(contract,volume_multiple)),'volume_multiple')
        # contract=[''.join([c for c in contract.split('.')[1].lower() if not c.isdigit()]) for contract in self.contract ]
        # self.mysplite.to_sql(dict(zip(contract,price_tick)),'price_tick')
        # self.mysplite.to_dataframe(df,'contract')
        # if fail_to_get_ls:
        #     to_pickle(set(fail_to_get_ls), './fail_to_get.pkl')
        if if_replace_contract_dict:
            self.mysplite.to_dataframe(
                self.contract_dict_frame, 'contract', 'replace')
            self.contract_dict_frame.to_csv(
                './minibt/data/contract.csv', index=False)

    def close(self):
        self.api.close()
        self.mysplite.close()
