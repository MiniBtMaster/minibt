from tqsdk import TqApi, TqAuth, TqKq
from tqsdk.tafunc import time_to_datetime
import os
from pandas import merge,to_pickle,read_csv,to_datetime,isna
from pandas import read_pickle as read_pkl
from iteration_utilities import flatten
import pandas as pd
FuturesDel = ['SHFE.wr', 'CZCE.RI', 'CZCE.LR', 'CZCE.JR', 'CZCE.PM', 'CZCE.RS', 'CZCE.WH',
              'DCE.bb', 'DCE.rr', 'CZCE.ZC', 'CZCE.CJ', "CFFEX.T", 'CFFEX.IM']

def get_symbol_list(api, exchange_id: list = ["SHFE", ], ins_class: str = 'contract',fitl:list=None)->tuple[list[str]]:
    '''全合约列表（排除不活跃合约）

    exchange_id
    ------------
        CFFEX : 中金所
        SHFE : 上期所
        DCE : 大商所
        CZCE : 郑商所

    ins_class
        contract : 主力合约
        cont : 主连
        index : 指数
    '''
    if exchange_id == 'all':
        exchange_id = ["SHFE", "DCE", "CZCE", "CFFEX"]
    contract_day = []
    contract_night = []
    if ins_class == 'contract':  # 主力合约
        for id in exchange_id:
            contract_day.append(api.query_cont_quotes(exchange_id=id))
            contract_night.append(
                api.query_cont_quotes(exchange_id=id, has_night=True))

    elif ins_class in ['cont', 'index']:  # 主连,指数
        ins_class = ins_class.upper()
        for id in exchange_id:
            contract_day.append(api.query_quotes(
                ins_class=ins_class, exchange_id=id))
            contract_night.append(api.query_quotes(
                ins_class=ins_class, exchange_id=id, has_night=True))

    day = [sent for sent in list(flatten(contract_day)) if not any(
        word in sent for word in FuturesDel)]
    night = [sent for sent in list(flatten(contract_night)) if not any(
        word in sent for word in FuturesDel)]
    
    if isinstance(fitl,list):
        if ins_class=='contract' and fitl:
            day=[y for x in fitl for y in day if x in y]
            night=[y for x in fitl for y in night if x in y]
            
    return day, night

def mkdir(file_name):
    file_path = f"./data/{file_name}"
    if not os.path.exists(file_path):
        os.mkdir(file_path)

#TA,MA,RM,jd,SA,fu,UR,SF,SM,PF,bu,lu,v,eb,pp,rb,b
#fu,SF,lu,v,eb,pp,rb
if __name__ == "__main__":
    file_format='csv'#'csv pkl
    assert file_format in ['pkl','csv']
    api = TqApi(TqKq(), auth=TqAuth("owenlovehellen", "owen2553832"))
    ins_class = 'contract'
    #fitl_contrace=['CZCE.SF','SHFE.fu','DCE.v','DCE.eb','DCE.pp','SHFE.rb','SHFE.sn','SHFE.ni']
    contrace, _ = get_symbol_list(api,exchange_id='all', ins_class=ins_class)#,fitl=fitl_contrace)
    print(contrace)
    cycle = 60
    file_name=f"{ins_class}_{cycle}"
    mkdir(file_name)
    length =1000
    for c in contrace:
        df = api.get_kline_serial(c, cycle, length)
        df.dropna(inplace=True)
        df.datetime = df.datetime.apply(time_to_datetime)
        quote = api.get_quote(c)
        df['price_tick'] = quote.price_tick
        columns=list(df.columns)
        symbol=df.symbol.iloc[0]
        c=''.join([c_ for c_ in c if not c_.isdigit()])
        path=f"./data/{file_name}/{c.replace('.','_')}.{file_format}"
        if os.path.exists(path):
            old_df=eval(f"read_{file_format}")(path)
            old_df.datetime=to_datetime(old_df.datetime)
            old_symbol=old_df.symbol.unique()
            if symbol not in old_symbol:
                columns1=columns.copy()
                columns1.pop(columns1.index('symbol'))
                df=merge(old_df,df,how='outer',on=columns1)
                df['symbol']=df.apply(lambda x :x['symbol_y'] if isna(x['symbol_x']) else x['symbol_x'],axis=1)
                df=df[columns]
            else:
                df=merge(old_df,df,how='outer',on=columns)
        if file_format=='pkl':
            to_pickle(df,path)
        elif file_format=='csv':
            df.to_csv(path,index=False)
    api.close()
