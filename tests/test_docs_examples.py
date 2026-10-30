"""文档 ↔ 例子的一致性（「例子先行」的护栏）。

规则来自 ``minibt_docs/DOCS_PLAN.md`` 的六条铁律：

* **E1** 文档里引用的 ``tutorials/**.py`` 必须真实存在；
* **E2** ``tutorials/**.py`` 全部能通过 ``py_compile``（在
  ``test_minibt_packaging.py`` 里已有，这里不重复）；
* **E3** 文档里的 ``LocalDatas.<名字>`` 白名单（同上，已有）；
* **E4** **新章节**的例子必须被至少一篇文档引用（老例子不强制 —— 见
  ``STRICT_DIRS``，随章节落地逐步扩大）；
* **E5** 文档里引用的本地图片（``images/xxx.png``）必须存在；
* **E6** ``mkdocs.yml`` 的 nav 里列的每个 ``.md`` 都必须存在。

这些检查都很便宜（只读文件），适合放进 CI。
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
DOCS = REPO / 'minibt_docs' / 'docs'
TUTORIALS = REPO / 'tutorials'
MKDOCS = REPO / 'minibt_docs' / 'mkdocs.yml'

#: 要求「例子 ↔ 文档」双向齐全的教程子目录（新章节往里加）。
STRICT_DIRS = {'styles'}

#: 历史记录类页面不参与检查（里面会提到旧例子 / 旧图）。
SKIP_DOC_NAMES = {'changelog.md', 'changelog_cache.md', 'changelog_miniqt.md',
                  'changelog_minibt_cache.md', 'changelog_miniqt_cache.md'}

#: 正在改写的目录（文件名/编号会被重命名，链接暂时对不上）→ 这些目录不查。
SKIP_DOC_DIRS = {'minibt_miniqt'}

_EXAMPLE_REF = re.compile(r'tutorials/[A-Za-z0-9_\-./]+\.py')
_MD_IMAGE = re.compile(r'!\[[^\]]*\]\((?!https?://)([^)\s]+)\)')
_MD_LINK = re.compile(
    r'\[[^\]]*\]\((?!https?://|#|mailto:)([^)\s#]+)(#[^)\s]*)?\)')
_NAV_MD = re.compile(r':\s*([A-Za-z0-9_\-./]+\.md)\s*$')


def _doc_files():
    for path in DOCS.rglob('*.md'):
        if path.name in SKIP_DOC_NAMES:
            continue
        if SKIP_DOC_DIRS & set(path.relative_to(DOCS).parts):
            continue
        yield path


def _example_files():
    for path in TUTORIALS.rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        yield path


def _doc_texts():
    return {path: path.read_text(encoding='utf-8', errors='replace')
            for path in _doc_files()}


def test_e1_docs_reference_existing_examples():
    """文档里写的 ``tutorials/....py`` 都要真的存在（防止路径写错/例子被删）。"""
    missing = []
    for path, text in _doc_texts().items():
        for ref in set(_EXAMPLE_REF.findall(text)):
            if not (REPO / ref).exists():
                missing.append(f'{path.relative_to(REPO)} -> {ref}')
    assert not missing, '文档引用了不存在的例子：\n' + '\n'.join(missing)


def test_e4_strict_examples_are_linked_from_docs():
    """新章节（``STRICT_DIRS``）里的每个例子，都要在某篇文档里被引用。"""
    texts = '\n'.join(_doc_texts().values())
    unlinked = []
    for path in _example_files():
        rel = path.relative_to(REPO).as_posix()
        top = path.relative_to(TUTORIALS).parts[0]
        if top not in STRICT_DIRS:
            continue
        if rel not in texts:
            unlinked.append(rel)
    assert not unlinked, '这些例子还没有对应文档：\n' + '\n'.join(unlinked)


def test_e5_doc_images_exist():
    """文档里的本地图片要存在（截图统一放 ``<分类>/images/``）。"""
    missing = []
    for path, text in _doc_texts().items():
        for src in set(_MD_IMAGE.findall(text)):
            if src.startswith(('data:', '//')):
                continue
            target = (path.parent / src).resolve()
            if not target.exists():
                missing.append(f'{path.relative_to(REPO)} -> {src}')
    assert not missing, '文档引用了不存在的图片：\n' + '\n'.join(missing)


def test_e7_local_links_exist():
    """文档里的**本地链接**（``[文本](相对路径)``）目标要存在。

    （锚点不查：mkdocs 对缺失锚点只报 INFO；但文件不存在会报 WARNING，
    而本项目的验收口径是 ``mkdocs build`` 0 warning。）
    """
    missing = []
    for path, text in _doc_texts().items():
        for target, _anchor in _MD_LINK.findall(text):
            if target.startswith(('data:', '//', 'mailto:')):
                continue
            resolved = (path.parent / target).resolve()
            # 指向"正在改写的目录"的链接也跳过（那里的文件会被重命名/未创建）
            try:
                rel = resolved.relative_to(DOCS)
            except ValueError:
                rel = None
            if rel is not None and SKIP_DOC_DIRS & set(rel.parts):
                continue
            if not resolved.exists():
                missing.append(f'{path.relative_to(REPO)} -> {target}')
    assert not missing, '文档里有指向不存在文件的链接：\n' + '\n'.join(missing)


def test_e6_nav_files_exist():
    """``mkdocs.yml`` 的 nav 里不能指向不存在的文件（否则 build 直接挂）。"""
    text = MKDOCS.read_text(encoding='utf-8')
    missing = []
    for name in _NAV_MD.findall(text):
        if not (DOCS / name).exists():
            missing.append(name)
    assert not missing, 'nav 指向了不存在的页面：\n' + '\n'.join(missing)


def test_new_chapter_is_registered_in_nav():
    """新章节的页面必须挂进 nav（否则在站点里点不到）。"""
    nav = MKDOCS.read_text(encoding='utf-8')
    pages = sorted(p.name for p in (DOCS / 'minibt_styles').glob('*.md'))
    assert pages, 'minibt_styles 目录是空的'
    not_in_nav = [name for name in pages
                  if f'minibt_styles/{name}' not in nav]
    assert not not_in_nav, '这些页面没进 mkdocs nav：\n' + '\n'.join(not_in_nav)
