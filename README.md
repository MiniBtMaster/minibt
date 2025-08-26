# minibt：让量化交易更简单、更高效的一站式策略开发库
<center>
<img src="https://pica.zhimg.com/v2-d5438d7502600aafdeb46d83c76dc865_l.jpg" 
  alt="minibt" 
  width="200" 
  class="center-img">
</center>
&emsp;&emsp;无论是量化新手还是资深开发者，minibt 都能帮你轻松搞定从策略搭建到实盘交易的全流程 —— 以极简的代码实现复杂逻辑，用强大的工具链提升策略效果。

## 核心优势一目了然：



*   **极简编码体验**：告别繁琐的底层实现，用简洁语法快速定义交易逻辑，让你的精力聚焦于策略思想而非代码细节。

*   **丰富指标即插即用**：内置 pandas\_ta、talib 等主流指标库，均线、MACD、RSI 等常用指标一键调用，无需重复造轮子。

*   **直观可视化分析**：集成 Bokeh 可视化工具，策略回测结果、资金曲线、信号分布等数据一键生成交互式图表，趋势洞察更清晰。

*   **无缝对接实盘**：支持 TQSDK 实盘接口，策略在回测通过后可快速切换至实盘交易，从研究到落地零门槛。

*   **智能优化升级**：内置参数优化工具与强化学习模块，自动迭代策略参数、动态适应市场变化，助力提升策略稳定性与收益潜力。

&emsp;&emsp;minibt，让量化交易的门槛更低、效率更高，无论是快速验证想法还是部署实盘策略，都是你的得力助手。

# minibt 安装教程

## 一、环境要求

minibt 依赖以下基础环境，建议使用 Python 3.8 及以上版本（推荐 3.8 - 3.11 系列 ），可通过 `python --version` 检查当前环境版本 ：



*   **基础依赖**：`numpy`、`pandas` 用于数据处理；`PyQt5`（若使用可视化 UI 功能）、`qfluentwidgets`（UI 组件库 ）、`TA-Lib`/`pandas-ta`（指标计算相关 ）、`optuna`（参数优化 ）、`tqsdk`（若对接实盘 ）等。

## 二、安装方式

### （一）通过 pip 安装（推荐）



1.  **基础安装**

    打开终端（Windows 下为命令提示符或 PowerShell，Linux/Mac 下为终端 ），执行以下命令安装 minibt 核心包：



```python
pip install minibt
```

该命令会自动拉取 minibt 及其基础依赖（如 `numpy`、`pandas` 等 ），但部分特殊依赖（如 `TA-Lib` 需额外系统级依赖 ）需手动处理。



1.  **补充特殊依赖**

*   **TA-Lib**：

    TA-Lib 依赖系统级库，需先安装对应依赖再装 Python 包：


    *   **Windows**：

        从 [TA-Lib 官网](https://www.ta-lib.org/hdr_dll.html) 下载对应系统版本的 `ta_libc_cdr.dll` 等文件，放置到 Python 安装目录下的 `Lib\site-packages` ，或系统 `System32` 路径；然后执行：



```python
pip install ta-lib
```


*   **实盘对接（TQ 相关 ）**：

    若需对接 TQ 实盘，执行：



```python
pip install tqsdk
```



*   **可视化 UI 依赖**：

    若使用 `miniqt` 可视化界面，执行：



```python
pip install PyQt5 qfluentwidgets
```

### （二）从源码安装（适合开发 / 定制）



1.  **克隆源码**

    从项目仓库（示例地址 `https://github.com/MiniBtMaster/minibt` ，需替换为实际仓库 ）克隆代码，安装minibt的whl文件



```python
python -m pip install 文件名.whl
```



## 三、验证安装

安装完成后，打开 Python 交互环境（终端执行 `python` 或 `ipython` ），输入：



```python
import minibt
print(minibt.__version__)
```

若输出 `1.0.0`（或对应版本号 ），且无导入错误，说明安装成功。

## 四、常见问题



1.  **TA-Lib 导入报错**：

    确保按步骤安装了系统级依赖和 Python 包，若仍报错，检查 `ta-lib` 版本与系统兼容性，或尝试重新安装。

2.  **PyQt5 相关错误**：

    确认安装命令执行成功，若有 `QtCore` 等导入错误，尝试重新安装 `PyQt5`（`pip uninstall PyQt5 && pip install PyQt5` ）。

3.  **实盘对接问题**：

    使用 `tqsdk` 时，需正确配置 TQ 账号认证信息，若报错 “网络连接失败”，检查网络及 TQ 服务器状态。


## 五、知乎教程
知乎minibt量化交易专栏：`https://zhuanlan.zhihu.com/column/c_1942555756558783128`

