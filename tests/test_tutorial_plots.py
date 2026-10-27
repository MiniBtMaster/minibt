"""``tutorials/plots/`` 示例的冒烟测试。

两件事：

* 每个示例都能被 import（示例里的天勤登录只在 ``__main__`` 里，import 很安全）；
* 九合一那个示例（``11_all_nine_modes_cci.py``）把策略**真跑一遍**（回测、不出图）
  —— ``Config`` / ``LineStyle`` / ``run(...)`` 之类的 API 改动如果写坏了示例，
  这里会立刻失败（比“用户跑起来才发现”便宜得多）。

跑在子进程里：示例会往 ``sys.path`` 插仓库根、还会定义一堆策略类。
"""
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLOTS = ROOT / 'tutorials' / 'plots'

pytestmark = pytest.mark.skipif(
    not (ROOT / 'minibt').exists() or not PLOTS.is_dir(),
    reason='没有 tutorials/plots 或 minibt 包（跳过示例冒烟）',
)

# 注意：不要用 str.format（示例代码里有 f-string 的花括号）；用 __ROOT__ 占位替换。
CODE = r'''
import importlib.util
import pathlib
import sys

root = pathlib.Path(__ROOT__)
sys.path.insert(0, str(root))

from minibt import Bt, Strategy          # noqa: E402

files = sorted((root / 'tutorials' / 'plots').glob('*.py'))
skipped, bad = [], []
for path in files:
    name = f"tut_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except (ImportError, ModuleNotFoundError) as error:   # 缺可选依赖：跳过
        skipped.append(f"{path.name}: {error}")
        continue
    except Exception as error:                            # API 写坏：算失败
        bad.append(f"{path.name}: {type(error).__name__}: {error}")
        continue
    has_strategy = any(
        isinstance(getattr(module, attr), type)
        and issubclass(getattr(module, attr), Strategy)
        for attr in dir(module))
    if not has_strategy:
        bad.append(f"{path.name}: 没有定义 Strategy 子类")
    else:
        print(f"OK   {path.name}")

# 九合一示例：策略真跑一遍（回测、不出图）
nine = sys.modules.get("tut_11_all_nine_modes_cci")
assert nine is not None and hasattr(nine, "CCIStrategy"), "九合一示例没加载成功"
bt = Bt()
bt.addstrategy(nine.CCIStrategy)
bt.run(isplot=False)
print("NINE_MODES_STRATEGY_OK")

for line in skipped:
    print(f"SKIP {line}")
assert not bad, bad
print("TUTORIALS_SMOKE_OK")
'''


def test_tutorial_plots_import_and_nine_modes_backtest():
    env = dict(os.environ,
               PYTHONPATH=os.pathsep.join([str(ROOT),
                                           os.environ.get('PYTHONPATH', '')]))
    result = subprocess.run([sys.executable, '-c',
                             CODE.replace('__ROOT__', repr(str(ROOT)))],
                            cwd=str(ROOT), env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace',
                            timeout=900)
    assert result.returncode == 0, result.stderr[-2000:]
    assert 'TUTORIALS_SMOKE_OK' in result.stdout, result.stdout[-2000:]
    assert 'NINE_MODES_STRATEGY_OK' in result.stdout, result.stdout[-2000:]
