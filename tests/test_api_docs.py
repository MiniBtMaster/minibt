"""API 参考文档的覆盖率护栏（P2-3）。

* 用 ``scripts/gen_minibt_api_docs.py`` 的 ``check()`` 保证：
  ``minibt.__all__`` 里的每个公开类都分配了页面，且页面的 AUTO 区没有过期；
* 保证 ``api/`` 的 8 个页面 + ``_coverage.md`` 都在 ``mkdocs.yml`` 的 nav 里
  （否则站点里点不到）。
"""
from __future__ import annotations

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'scripts' / 'gen_minibt_api_docs.py'
DOCS = REPO / 'minibt_docs' / 'docs' / 'api'
MKDOCS = REPO / 'minibt_docs' / 'mkdocs.yml'


def _load_generator():
    spec = importlib.util.spec_from_file_location('gen_minibt_api_docs', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # type: ignore[union-attr]
    return module


def test_api_docs_are_up_to_date(capsys):
    gen = _load_generator()
    minibt = gen._load_minibt()
    rc = gen.check(minibt)
    output = capsys.readouterr().out
    assert rc == 0, output


def test_api_pages_exist_and_are_in_nav():
    nav = MKDOCS.read_text(encoding='utf-8')
    pages = sorted(p.name for p in DOCS.glob('*.md'))
    assert pages, 'api/ 目录是空的'
    missing = [name for name in pages if f'api/{name}' not in nav]
    assert not missing, '这些 API 页面没进 mkdocs nav：\n' + '\n'.join(missing)


def test_every_public_class_is_assigned():
    gen = _load_generator()
    minibt = gen._load_minibt()
    assigned = {name for names in gen.PAGES.values() for name in names}
    unassigned = []
    for name in gen._class_names(minibt):
        import inspect
        obj = getattr(minibt, name, None)
        if inspect.isclass(obj) and name not in assigned:
            unassigned.append(name)
    assert not unassigned, '这些公开类没有分配 API 页面：\n' + '\n'.join(unassigned)
