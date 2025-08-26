from tinydb import TinyDB, Query
from .indicators import pd, datetime, Optional, partial, FILED


class TinydbStorage(object):

    def __init__(self, db_path="./minibt/data/data.json"):
        self.db = TinyDB(db_path)
        self.timetostr_func = partial(
            datetime.strftime, format="%Y-%m-%d %H:%M:%S")

    @property
    def tables(self) -> list[str]:
        return list(self.db.tables())

    def get(self, table_name, start: Optional[str] = None, end: Optional[str] = None, length: Optional[int] = None) -> pd.DataFrame:
        result = None
        if table_name in self.tables:
            table = self.db.table(table_name)

            if isinstance(start, str) and start:
                element = Query()
                if isinstance(end, str) and end:
                    result = table.search((element.datetime >= start) & (
                        element.datetime <= end))
                else:
                    result = table.search(element.datetime >= start)
            elif isinstance(length, int) and length > 0:
                value = table.all()
                if value:
                    last_id = table.all()[-1].doc_id
                    start_id = max(last_id-length, 1)
                    doc_id = list(range(start_id, last_id+1))
                    result = table.get(doc_id=doc_id)
            else:
                value = table.all()
                if value:
                    result = value
        return pd.DataFrame(result)

    def set(self, table_name, df: pd.DataFrame) -> None:
        if not df.empty:
            values = None
            df.datetime = df.datetime.apply(self.timetostr_func)
            df = df[FILED.Quote]
            table = self.db.table(table_name)
            data = table.all()
            if data:
                datetime_ = df.datetime
                last_datetime = data[-1]['datetime']
                if last_datetime != datetime_.iloc[-1]:
                    if last_datetime in datetime_.iloc[:-1]:
                        element = Query()
                        table.remove(element.datetime == last_datetime)
                        df = df[df.datetime >= last_datetime]
                    values = df.to_dict(orient='records')
            else:
                values = df.to_dict(orient='records')
            if values:
                table.insert_multiple(values)

    def close(self):
        self.db.close()

    def drop_table(self, table_name: str):
        if table_name in self.tables:
            self.db.drop_table(table_name)

    def drop_tables(self):
        self.db.drop_tables()
