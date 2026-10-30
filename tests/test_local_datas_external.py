"""外部数据登记到 `LocalDatas`（单个 CSV / 整个文件夹）✓"""
from __future__ import annotations

import pathlib

from minibt.data import tools as T

HEADER = 'datetime,open,high,low,close,volume\n'
ROWS = '2024-01-01 00:00:00,1,2,0.5,1.5,10\n' \
       '2024-01-01 00:01:00,2,3,1.5,2.5,12\n'


def _make(tmp: pathlib.Path):
    folder = tmp / 'bar_data'
    folder.mkdir()
    single = tmp / 'one.csv'
    for path in (folder / 'a.csv', folder / 'b.csv', single):
        path.write_text(HEADER + ROWS, encoding='utf-8')
    # 缺 `volume` → 不符合 `FILED.ALL`，应被跳过 ✓
    (folder / 'bad.csv').write_text(
        'datetime,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n',
        encoding='utf-8')
    return folder, single


def test_add_single_csv_and_folder(tmp_path, monkeypatch):
    folder, single = _make(tmp_path)
    monkeypatch.setattr(T, 'EXTERNAL_FILE', str(tmp_path / 'ext.json'))
    # ① 单个 CSV
    assert T.add_external(str(single), rewrite=False)
    # ② 文件夹（非法 CSV 被跳过）
    assert T.add_external(str(folder), rewrite=False)
    names = {name for name, _path in T.external_items()}
    assert names == {'one', 'a', 'b'}, names          # `bad` 不登记 ✓
    assert T.get_csv_path('a').endswith('a.csv')
    assert T.get_csv_path('one').endswith('one.csv')
    assert 'a' in T.list_csv_names()
    # 取消登记（不删文件 ✓）
    T.remove_external(str(folder), rewrite=False)
    assert (folder / 'a.csv').exists()
    assert {name for name, _ in T.external_items()} == {'one'}


def test_remove_and_missing_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(T, 'EXTERNAL_FILE', str(tmp_path / 'ext.json'))
    missing = tmp_path / 'nope'
    assert T.add_external(str(missing), rewrite=False) == []
    assert '路径不存在' in capsys.readouterr().out
    assert T.external_items() == []


def test_local_datas_has_add_api():
    from minibt.data.utils import LocalDatas
    for name in ('add', 'remove', 'externals'):
        assert callable(getattr(LocalDatas, name))
    assert 'add_external' in T.__all__


def test_filed_all_header_validation(tmp_path, monkeypatch):
    """表头必须是 `FILED.ALL`（含 volume），且**只读前 10 行** ✓"""
    monkeypatch.setattr(T, 'EXTERNAL_FILE', str(tmp_path / 'ext.json'))
    good = tmp_path / 'good.csv'
    good.write_text(HEADER + ROWS, encoding='utf-8')
    no_vol = tmp_path / 'novol.csv'
    no_vol.write_text(
        'datetime,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n',
        encoding='utf-8')
    empty = tmp_path / 'empty.csv'
    empty.write_text('', encoding='utf-8')
    assert T._valid_csv(str(good)) is True
    assert T._valid_csv(str(no_vol)) is False          # 少 volume ✗
    assert T._valid_csv(str(empty)) is False
    assert T.PROBE_LINES == 10                         # 只读前 10 行 ✓
    # 登记时非法文件被跳过
    assert T.add_external(str(no_vol), rewrite=False) == []


def test_desk_merges_localdatas_externals(tmp_path, monkeypatch):
    """desk 启动时并入 `LocalDatas` 登记的外部路径（重开 desk 自动读到 ✓）"""
    source = (pathlib.Path(__file__).resolve().parents[1]
              / 'minibt' / 'desk' / 'local_data.py').read_text(encoding='utf-8')
    assert 'from ..data.tools import external_paths' in source
    assert 'if os.path.isfile(folder):' in source
    assert 'add_external(folder, rewrite=True)' in source
