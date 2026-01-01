from __future__ import annotations
from minibt import *
from tqsdk import TqApi, TqAuth, TqKq


def get_contract(exchange_id: str, contracts: list[str], has_night=None):
    global api
    target_prefixes: list[str] = [
        f"{exchange_id}.{cont}" for cont in contracts]
    all_contracts: list[str] = api.query_cont_quotes(
        exchange_id, has_night=has_night)

    return [
        contract for contract in all_contracts
        for prefix in target_prefixes
        if contract.startswith(prefix) and contract[len(prefix):].isdigit()
    ]


class owen(Strategy):
    params = dict(symbol="DCE.v2601")

    def __init__(self) -> None:
        self.data = self.get_kline(self.params.symbol, 60, 1000)
        self.data.height = 300
        self.ma = self.data.tradingview.G_Channels()
        self.pmax = self.data.close.btind.pmax3()
        self.macd = self.data.close.macd()
        self.data1 = self.get_kline(self.params.symbol, 60*5, 1000, height=400)
        self.ha = self.data1.ha()
        self.ha.overlap = False


if __name__ == "__main__":
    api = TqApi(TqKq(), auth=TqAuth(
        "天勤账号", "天勤密码"))
    bt = Bt(auto=False, live=True)
    bt.addTqapi(api=api)

    contracts_dict = {
        "DCE": ["v", "pp", "m", "l", "jd", "eg", "eb", "b"],
        "CZCE": ["TA", "SR", "SM", "RM", "PX", "PF", "MA"]
    }
    # , "a"
    # , "PK"
    name = "策略"
    i = 0
    for k, v in contracts_dict.items():
        contracts = get_contract(k, v)
        for contract in contracts:
            i += 1
            bt.addstrategy(
                owen.copy(name=f"{name}{i}", params=dict(symbol=contract)))

    bt.run()
