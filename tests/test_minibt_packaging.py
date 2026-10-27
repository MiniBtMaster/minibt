"""打包前检查：版本一致性 / 依赖一致性 / 文档与教程只用内置数据 ✓。

内置数据只有三个：``pp2609_60`` / ``l2609_60`` / ``test`` ✓
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]

#: ``LocalDatas`` 的方法/占位名（不是数据集 ✓）
_NOT_DATASETS = {
    'get', 'get_dataframe', 'get_path', 'get_IndFrame', 'import_package_data',
    'rewrite', 'keep', 'rename', 'deleter', 'update', 'add',
    'my_data', 'xxx',            # 文档里的占位写法 ✓
}


def _read(*parts):
    return REPO.joinpath(*parts).read_text(encoding='utf-8')


def test_version_consistent_across_package_files():
    """``__init__.__version__`` / ``pyproject.toml`` / README 徽章要一致 ✓"""
    from minibt import __version__, __version_info__

    pyproject = _read('minibt', 'pyproject.toml')
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    assert m, 'pyproject.toml 里找不到 version ✗'
    assert m.group(1) == __version__, (m.group(1), __version__)
    assert '.'.join(str(x) for x in __version_info__) == __version__

    readme = _read('minibt', 'README.md')
    assert f'version-{__version__}-green' in readme, 'README 徽章没跟上 ✗'
    assert f'v{__version__} 更新亮点' in readme, 'README 更新亮点标题没跟上 ✗'
    # 代码里的版本说明
    init = _read('minibt', '__init__.py')
    assert f'版本信息: v{__version__}' in init
    assert f'__version_info__ = {tuple(int(x) for x in __version__.split("."))}' in init


def test_requirements_matches_pyproject_dependencies():
    """``requirements.txt`` 必须与 ``pyproject.toml`` 的依赖**集合**一致 ✓

    （``pyproject`` 里多出来的 build/setuptools/wheel/cython/lint 是打包与开发
    工具，``requirements.txt`` 里是注释掉的 ✓ —— 允许这种差异 ✓）
    """
    def names(text: str) -> set:
        out = set()
        for line in text.splitlines():
            line = line.split('#')[0].strip().rstrip(',').strip('"\'')
            m = re.match(r'^([A-Za-z0-9_.\-]+)([<>=!~].*)?$', line)
            if m:
                out.add(m.group(1).lower().replace('_', '-'))
        return out

    pj = names(pyproject_dependencies(_read('minibt', 'pyproject.toml')))
    rq = names(_read('minibt', 'requirements.txt'))
    dev_only = {'build', 'setuptools', 'wheel', 'cython', 'autopep8', 'pylint',
                'pipdeptree'}
    missing = rq - pj
    assert not missing, f'requirements 里有 pyproject 没声明的依赖 ✗ {missing}'
    extra = pj - rq - dev_only
    assert not extra, f'pyproject 有依赖但 requirements 里没写 ✗ {extra}'


def test_docs_and_tutorials_only_use_builtin_datasets():
    """文档/教程里的 ``LocalDatas.<名字>`` 必须是内置的三个之一 ✓

    （用户把内置数据精简成 ``pp2609_60`` / ``l2609_60`` / ``test`` 三个之后，
    旧文档里还留着 ``v2509_60`` / ``cu`` / ``rb`` 之类的引用 ✗ —— 直接照抄
    示例会报错 ✗。）
    """
    builtin = {'pp2609_60', 'l2609_60', 'test'}
    pattern = re.compile(r'LocalDatas\.([A-Za-z_][A-Za-z0-9_]*)')
    bad = []
    for root in ('minibt_docs', 'tutorials'):
        for path in (REPO / root).rglob('*'):
            if path.suffix not in ('.md', '.py'):
                continue
            if path.name == 'changelog.md':       # 历史记录，保持原样 ✓
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except Exception:                                     # noqa: BLE001
                continue
            for name in pattern.findall(text):
                if name not in builtin and name not in _NOT_DATASETS:
                    bad.append(f'{path.relative_to(REPO)}: LocalDatas.{name}')
    assert not bad, '文档/教程引用了不存在的数据集 ✗\n' + '\n'.join(bad)


def test_tutorials_compile():
    """所有教程都要能通过语法编译 ✓（打包前例行检查）"""
    import py_compile
    bad = []
    for path in (REPO / 'tutorials').rglob('*.py'):
        if '__pycache__' in str(path):
            continue
        try:
            py_compile.compile(str(path), cfile=None, doraise=True)
        except Exception as error:                                # noqa: BLE001
            bad.append(f'{path.name}: {error}')
    assert not bad, bad


# --------------------------------------------------------------------------- #
# 打包布局（实测踩到的两个坑，都必须守住 ✓）
# --------------------------------------------------------------------------- #
def _pyproject() -> str:
    return _read('minibt', 'pyproject.toml')


def pyproject_dependencies(text: str) -> str:
    """只取 ``dependencies = [...]`` 那一块 ✓

    （``packages = [...]`` 里的包名（如 ``minibt.data``）长得也像依赖名 ✗，
    混进来就会误报“pyproject 有依赖但 requirements 里没写”✗）
    """
    return text.split('dependencies = [', 1)[1].split(']', 1)[0]


def test_all_subpackages_are_declared():
    """★ 回归：``项目根 == 包目录`` 的布局下 ``packages`` 必须显式列全 ✓

    以前写的是 ``[tool.setuptools.packages.find] include = ["minibt", "minibt.*"]``
    —— 它要去找**子目录** ``minibt/`` ✗，而项目根**就是** ``minibt/``（没有更深一层）
    → **一个包都发现不了** ✗ → 打出来的 wheel 里只有 5 个 ``.pyd`` 扩展、
    **没有任何 .py 模块、没有 data/** ✗（实测踩到）。所以：显式 ``packages`` +
    ``package-dir = {"minibt": "."}``，并且不能再用 ``packages.find``。
    """
    data = _pyproject()
    assert 'package-dir = { "minibt" = "." }' in data, \
        '缺少 package-dir 映射（项目根 == 包目录时必需）✗'
    # 只看**没被注释掉**的行（上面说明里会提到 packages.find ✓）
    active = '\n'.join(line for line in data.splitlines()
                       if not line.lstrip().startswith('#'))
    assert 'packages.find' not in active, '又用回 packages.find 了（找不到包 ✗）'
    block = data.split('packages = [')[1].split(']')[0]
    declared = set(re.findall(r'"([\w.]+)"', block))
    assert 'minibt' in declared

    root = REPO / 'minibt'
    real = {'minibt'}
    for path in root.rglob('__init__.py'):
        rel = path.parent.relative_to(root)
        if not rel.parts:
            continue
        if any(x in ('build', '__pycache__', '.git') for x in rel.parts):
            continue
        real.add('minibt.' + '.'.join(rel.parts))
    missing = sorted(real - declared)
    assert not missing, f'pyproject.toml 的 packages 漏了这些子包 ✗: {missing}'


def test_extension_sources_use_absolute_paths():
    """★ 回归：``.pyx`` 必须用**绝对路径** ✓

    ``setup.py`` 就住在包里（``minibt/setup.py``），而 setuptools 把
    ``Extension.sources`` 的**相对路径按“项目根”**解析 —— 也就是说
    ``cd minibt && python -m build --wheel``（pyproject.toml 里写的标准做法）
    会把 ``minibt/cython_functions/xx.pyx`` 找成
    ``minibt/minibt/cython_functions/xx.pyx`` → 直接报
    ``ValueError: '...pyx' doesn't match any files``，**根本打不出包** ✗（实测）。
    """
    src = _read('minibt', 'setup.py')
    assert 'os.path.join(_HERE, "cython_functions")' in src
    assert 'os.path.join(_HERE, "zigzag")' in src
    assert '"minibt/cython_functions"' not in src
    assert '"minibt/zigzag"' not in src
