from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align
from rich.traceback import install as install_traceback
from enum import Enum
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from .utils import BtAccount, pd, qs_stats, os, BASE_DIR
from .strategy.strategy import Strategy

__all__ = ["Logger", "LogLevel", "get_logger"]


class LogLevel(Enum):
    """## 日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"
    TRADE = "TRADE"


class Logger:
    """
    ## 基于 Rich 的交易日志库
    """

    def __init__(
        self,
        name: str = "minibt",
        log_to_file: bool = True,
        log_dir: str = "logs",
        log_level: LogLevel = LogLevel.INFO,
        enable_traceback: bool = True,
        auto_clean_days: int = 15,  # 自动清理天数，0表示不清理
        clean_frequency_hours: int = 24  # 新增：清理频率，默认24小时一次
    ):
        self.name = name
        self.log_to_file = log_to_file
        self.log_dir = Path(BASE_DIR, log_dir)
        self.log_level = log_level
        self.console = Console()
        self._header_printed = False
        self.auto_clean_days = auto_clean_days  # 保存清理天数设置
        self.clean_frequency_hours = clean_frequency_hours  # 清理频率
        self.clean_state_file = self.log_dir / ".clean_state"  # 清理状态记录文件
        # os.path.join(
        #     self.log_dir, ".clean_state")  # 清理状态记录文件

        # 日志缓冲区
        self._log_buffer: List[str] = []
        self._trade_buffer: List[str] = []

        # 启用更好的错误追踪
        if enable_traceback:
            install_traceback(show_locals=True)

        # 创建日志目录
        if log_to_file:
            self.log_dir.mkdir(exist_ok=True)
            self.log_file = self.log_dir / \
                f"{name}_log_{datetime.now().strftime('%Y-%m-%d')}.log"
            self.trade_log_file = self.log_dir / \
                f"{self.name}_trades_{datetime.now().strftime('%Y-%m-%d')}.log"

            # 如果这两个文件不存在，则创建两个空文件
            self._ensure_log_files_exist()

            # 自动清理旧日志文件（根据频率控制）
            if self.auto_clean_days > 0:
                self._clean_old_logs_if_needed()

        # 交易统计
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "start_time": datetime.now(),
            "failed_trades": 0,
            "insufficient_cash_errors": 0
        }

        # 交易记录
        self.trade_history: List[Dict] = []

        # 性能监控
        self.performance_data: Dict[str, List[float]] = {
            "response_times": [],
            "trade_durations": []
        }

    def set_params(self,
                   log_to_file: bool = True,
                   auto_clean_days: int = 30):
        self.log_to_file = log_to_file
        self.auto_clean_days = auto_clean_days

    def _get_clean_state(self):
        """获取清理状态"""
        try:
            if self.clean_state_file.exists():
                with open(self.clean_state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    return state.get("last_clean_time", 0)
            return 0
        except Exception:
            return 0

    def _set_clean_state(self):
        """设置清理状态"""
        try:
            state = {
                "last_clean_time": time.time(),
                "last_clean_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.clean_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.debug(f"保存清理状态失败: {e}")

    def _clean_old_logs_if_needed(self):
        """根据频率控制自动清理旧日志文件"""
        try:
            current_time = time.time()
            last_clean_time = self._get_clean_state()

            # 检查是否到了清理时间
            hours_since_last_clean = (current_time - last_clean_time) / 3600

            if hours_since_last_clean >= self.clean_frequency_hours:
                self._clean_old_logs()
                self._set_clean_state()
            else:
                next_clean_in = self.clean_frequency_hours - hours_since_last_clean
                # self.debug(f"距离下次清理还有 {next_clean_in:.1f} 小时")

        except Exception as e:
            ...
            # self.error(f"检查清理状态失败: {e}")

    def _clean_old_logs(self):
        """自动清理指定天数前的日志文件"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.auto_clean_days)
            deleted_count = 0

            # 遍历日志目录中的所有文件，但跳过状态文件
            for file_path in self.log_dir.glob("*"):
                if file_path.is_file() and file_path != self.clean_state_file:
                    # 获取文件修改时间
                    file_mtime = datetime.fromtimestamp(
                        file_path.stat().st_mtime)

                    # 如果文件早于截止时间，则删除
                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        # self.debug(f"已删除旧日志文件: {file_path.name}")

            # if deleted_count > 0:
            #     self.info(
            #         f"自动清理完成，删除了 {deleted_count} 个 {self.auto_clean_days} 天前的日志文件")
            # else:
            #     self.debug(f"无需清理，没有找到 {self.auto_clean_days} 天前的日志文件")

        except Exception as e:
            ...
            # self.error(f"自动清理日志文件失败: {e}")

    def _add_to_buffer(self, level: str, message: str, operation: str = ""):
        """添加日志到缓冲区"""
        if not self.log_to_file:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} | {level:8} | {operation:6} | {message}"

        self._log_buffer.append(log_entry)

    def _ensure_log_files_exist(self):
        """确保日志文件存在，如果不存在则创建空文件"""
        try:
            # 创建主日志文件
            # if not os.path.exists(self.log_file):
            with open(self.log_file, os.path.exists(self.log_file) and "a" or "w", encoding='utf-8') as f:
                f.write(
                    f"\n #################### {self.name} 日志文件创建于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ####################\n")
                # f.write(f"# 日志级别: {self.log_level.value}\n\n")
            # self.debug(f"创建日志文件: {self.log_file}")

            # 创建交易日志文件
            # if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, os.path.exists(self.trade_log_file) and "a" or "w", encoding='utf-8') as f:
                f.write(
                    f"\n #################### {self.name} 交易日志文件创建于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ####################\n")
            # self.debug(f"创建交易日志文件: {self.trade_log_file}")

        except Exception as e:
            ...
            # self.console.print(f"[red]创建日志文件失败: {e}[/red]")

    def close_logger(self):
        """## 关闭日志器，保存所有缓冲的日志到文件"""
        if self.log_to_file:

            # 保存普通日志
            if self._log_buffer:
                try:
                    with open(self.log_file, 'a', encoding='utf-8') as f:  # 使用 'a' 追加模式
                        for log_entry in self._log_buffer:
                            f.write(f"{log_entry}\n")
                    # self.debug(
                    #     f"已保存 {len(self._log_buffer)} 条日志到 {self.log_file}")
                except Exception as e:
                    # self.console.print(f"[red]保存日志失败: {e}[/red]")
                    ...
            # else:
            #     self.debug("普通日志缓冲区为空，无需保存")

            # 保存交易日志
            if self._trade_buffer:
                try:
                    with open(self.trade_log_file, 'a', encoding='utf-8') as f:  # 使用 'a' 追加模式
                        for trade_entry in self._trade_buffer:
                            f.write(f"{trade_entry}\n")
                    # self.debug(
                    #     f"已保存 {len(self._trade_buffer)} 条交易日志到 {self.trade_log_file}")
                except Exception as e:
                    ...
            #         self.console.print(f"[red]保存交易日志失败: {e}[/red]")
            # else:
            #     self.debug("交易日志缓冲区为空，无需保存")

            self.clear_buffer()
            # self.info("日志器已关闭，所有日志已保存到文件")

    def get_buffer_size(self):
        """## 获取当前缓冲区大小"""
        return len(self._log_buffer)

    def get_trade_buffer_size(self):
        """## 获取交易缓冲区大小"""
        return len(self._trade_buffer)

    def clear_buffer(self):
        """## 清空缓冲区（谨慎使用）"""
        self._log_buffer.clear()
        self._trade_buffer.clear()
        # self.info("日志缓冲区已清空")

    def _update_stats(self, operation: str, pnl: float = 0.0):
        """更新交易统计"""
        if operation in ["平多", "平空", "减多", "减空"]:
            self.stats["total_trades"] += 1
            self.stats["total_pnl"] += pnl

            if pnl > 0:
                self.stats["winning_trades"] += 1
                self.stats["max_profit"] = max(self.stats["max_profit"], pnl)
            elif pnl < 0:
                self.stats["losing_trades"] += 1
                self.stats["max_loss"] = min(self.stats["max_loss"], pnl)
        elif operation == "失败":
            self.stats["failed_trades"] += 1
        elif operation == "错误":
            self.stats["insufficient_cash_errors"] += 1

    def print_header(self):
        """## 打印日志头信息（确保只打印一次）"""
        if not self._header_printed:
            header = Panel(
                Align.center(f"🎯 {self.name} 交易日志系统 🎯\n"
                             f"启动时间: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}"),
                style="bold cyan",
                box=box.DOUBLE_EDGE
            )
            self.console.print(header)
            self._header_printed = True

    def _get_level_style(self, level: LogLevel) -> str:
        """根据日志级别返回样式"""
        style_map = {
            LogLevel.DEBUG: "dim blue",
            LogLevel.INFO: "bold blue",
            LogLevel.WARNING: "bold yellow",
            LogLevel.ERROR: "bold red",
            LogLevel.CRITICAL: "bold magenta",
            LogLevel.SUCCESS: "bold green",
            LogLevel.TRADE: "bold cyan"
        }
        return style_map.get(level, "white")

    def _get_level_emoji(self, level: LogLevel) -> str:
        """根据日志级别返回表情符号"""
        emoji_map = {
            LogLevel.DEBUG: "🐛",
            LogLevel.INFO: "ℹ️",
            LogLevel.WARNING: "⚠️",
            LogLevel.ERROR: "❌",
            LogLevel.CRITICAL: "💥",
            LogLevel.SUCCESS: "✅",
            LogLevel.TRADE: "💰"
        }
        return emoji_map.get(level, "📝")

    def _get_operation_style(self, operation: str, pnl: float = 0.0) -> str:
        """## 根据操作类型和盈亏返回样式"""
        if operation in ["开多", "开空", "创建", "加多", "加空"]:
            return "bold yellow"
        elif operation in ["平多", "平空", "减多", "减空"]:
            return "bold green" if pnl >= 0 else "bold red"
        elif operation in ["失败", "错误"]:
            return "bold red"
        elif operation in ["警告"]:
            return "bold yellow"
        else:
            return "bold white"

    def _get_operation_emoji(self, operation: str, pnl: float = 0.0) -> str:
        """## 根据操作类型返回表情符号"""
        emoji_map = {
            "开多": "📈 ",
            "加多": "📈↑",
            "开空": "📉 ",
            "加空": "📉↑",
            "平多": "💰 " if pnl >= 0 else "💸 ",
            "减多": "💰↓" if pnl >= 0 else "💸↓",
            "平空": "💰 " if pnl >= 0 else "💸 ",
            "减空": "💰↓" if pnl >= 0 else "💸↓",
            "创建": "🔄 ",
            "失败": "🚫 ",
            "错误": "❌ ",
            "警告": "⚠️ "
        }
        return emoji_map.get(operation, "📝")

    def _should_log(self, level: LogLevel) -> bool:
        """## 检查是否应该记录该级别的日志"""
        level_priority = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.SUCCESS: 25,
            LogLevel.TRADE: 27,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50
        }
        current_priority = level_priority.get(self.log_level, 20)
        message_priority = level_priority.get(level, 20)
        return message_priority >= current_priority

    def _update_stats(self, operation: str, pnl: float = 0.0):
        """## 更新交易统计"""
        if operation in ["平多", "平空", "减多", "减空"]:
            self.stats["total_trades"] += 1
            self.stats["total_pnl"] += pnl

            if pnl > 0:
                self.stats["winning_trades"] += 1
                self.stats["max_profit"] = max(self.stats["max_profit"], pnl)
            elif pnl < 0:
                self.stats["losing_trades"] += 1
                self.stats["max_loss"] = min(self.stats["max_loss"], pnl)
        elif operation == "失败":
            self.stats["failed_trades"] += 1
        elif operation == "错误":
            self.stats["insufficient_cash_errors"] += 1

    def set_log_level(self, level: LogLevel):
        """## 设置日志级别"""
        self.log_level = level
        self.info(f"日志级别设置为: {level.value}")

    # ========== 通用日志方法 ==========
    def log(self, level: LogLevel, message: str, *args, **kwargs):
        """## 通用日志方法"""
        if not self._should_log(level):
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        emoji = self._get_level_emoji(level)
        style = self._get_level_style(level)

        # 格式化消息
        if args:
            message = message.format(*args)

        # 创建富文本
        text = Text()
        text.append(f"{timestamp} ", style="dim")
        text.append(f"{emoji} {level.value:^16}", style=style)
        text.append(f" | {message}", style="white")

        self.console.print(text)
        self._add_to_buffer(level.value, message)

    def debug(self, message: str, *args, **kwargs):
        """### 调试日志"""
        self.log(LogLevel.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """### 信息日志"""
        self.log(LogLevel.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """### 警告日志"""
        self.log(LogLevel.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """### 错误日志"""
        self.log(LogLevel.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """### 严重错误日志"""
        self.log(LogLevel.CRITICAL, message, *args, **kwargs)

    def success(self, message: str, *args, **kwargs):
        """### 成功日志"""
        self.log(LogLevel.SUCCESS, message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        """### 异常日志（自动包含堆栈跟踪）"""
        self.error(f"{message}", *args, **kwargs)
        # 这里可以添加堆栈跟踪，但Rich的traceback已经在初始化时安装

    # ========== 交易错误和警告方法 ==========
    def log_insufficient_cash(self, datetime: str, details: str = ""):
        """## 账户现金不足，交易失败"""
        message = f"账户现金不足，交易失败!"
        if details:
            message += f" {details}"

        self.log_operation("错误", datetime, message)
        self.stats["insufficient_cash_errors"] += 1

    def log_trade_failed(self, datetime: str, reason: str, details: str = ""):
        """## 交易失败"""
        message = f"交易失败: {reason}"
        if details:
            message += f" | {details}"

        self.log_operation("失败", datetime, message)
        self.stats["failed_trades"] += 1

    def log_market_warning(self, datetime: str, warning: str, details: str = ""):
        """## 市场警告"""
        message = f"市场警告: {warning}"
        if details:
            message += f" | {details}"

        self.log_operation("警告", datetime, message)

    # ========== 性能监控方法 ==========
    def time_it(self, func: Callable) -> Callable:
        """## 装饰器：测量函数执行时间"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000  # 毫秒
                self.performance_data["response_times"].append(execution_time)
                self.debug(f"函数 {func.__name__} 执行时间: {execution_time:.2f}ms")
                return result
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                self.error(
                    f"函数 {func.__name__} 执行失败，耗时: {execution_time:.2f}ms, 错误: {e}")
                raise
        return wrapper

    def show_performance(self):
        """## 显示性能统计"""
        if not self.performance_data["response_times"]:
            self.info("暂无性能数据")
            return

        times = self.performance_data["response_times"]
        table = Table(title="📊 性能统计", show_header=True,
                      header_style="bold cyan")
        table.add_column("指标", style="green")
        table.add_column("数值", style="white")

        table.add_row("调用次数", str(len(times)))
        table.add_row("平均响应时间", f"{sum(times)/len(times):.2f}ms")
        table.add_row("最快响应", f"{min(times):.2f}ms")
        table.add_row("最慢响应", f"{max(times):.2f}ms")
        table.add_row("95%分位", f"{sorted(times)[int(len(times)*0.95)]:.2f}ms")

        self.console.print(table)

    # ========== 交易操作日志 ==========
    def log_operation(self, operation: str, datetime: str, message: str, pnl: float = 0.0, **kwargs):
        """## 通用交易操作日志"""
        emoji = self._get_operation_emoji(operation, pnl)
        style = self._get_operation_style(operation, pnl)

        # 创建富文本
        text = Text()
        text.append(f"{datetime} ", style="dim")
        text.append(f"{emoji} {operation:6}", style=style)
        text.append(f" | {message}", style="white")

        # 如果有盈亏，特别标注
        if pnl != 0:
            pnl_style = "green" if pnl > 0 else "red" if pnl < 0 else "white"
            text.append(f" | 盈亏: ", style="white")
            text.append(f"{pnl:+.1f}", style=pnl_style)

        self.console.print(text)
        # 构建文件日志消息
        file_message = f"{message}"
        if pnl != 0:
            file_message += f" | 盈亏：{pnl:+.1f}"

        self._update_stats(operation, pnl)

        # 同时记录到交易缓冲区
        trade_entry = f"{datetime} | {operation} | {file_message}"
        self._trade_buffer.append(trade_entry)

    def message(self, sname: str, cont: str, price: float, quantity: int, fee: float, capital: float) -> str:
        """## 生成标准消息格式"""
        return f"策略：{sname:^16} | 合约：{cont:^16} | 价格: {price}, 数量: {quantity}, 手续费: {fee}, 资金: {capital}"

    # 具体的交易操作方法
    def operation_msg(self, operation: str, pnl: Optional[float] = None, *args):
        """## 统一操作消息处理"""
        if pnl is None:
            return self.open(operation, *args)
        return self.close(operation, pnl, *args)

    def open(self, operation: str, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 开仓操作"""
        self.log_operation(operation, datetime, self.message(
            sname, cont, price, quantity, fee, capital))

    def close(self, operation: str, pnl: float, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 平仓操作"""
        self.log_operation(operation, datetime, self.message(
            sname, cont, price, quantity, fee, capital), pnl)
        self._record_trade(operation, sname, cont, datetime,
                           price, quantity, pnl, capital)

    # 具体的交易方法
    def open_long(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 开多操作"""
        self.open("开多", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def add_long(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 加多操作"""
        self.open("加多", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def open_short(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 开空操作"""
        self.open("开空", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def add_short(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 加空操作"""
        self.open("加空", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def close_long(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, pnl: float, capital: float, **kwargs):
        """平多操作"""
        self.close("平多", pnl, sname, cont, datetime, price,
                   quantity, fee, capital, **kwargs)

    def close_short(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, pnl: float, capital: float, **kwargs):
        """## 平空操作"""
        self.close("平空", pnl, sname, cont, datetime, price,
                   quantity, fee, capital, **kwargs)

    def create_long(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 创建多头委托"""
        self.open("创建", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def create_short(self, sname: str, cont: str, datetime: str, price: float, quantity: int, fee: float, capital: float, **kwargs):
        """## 创建空头委托"""
        self.open("创建", sname, cont, datetime, price,
                  quantity, fee, capital, **kwargs)

    def _record_trade(self, operation: str, sname: str, cont: str, datetime: str, price: float, quantity: int, pnl: float, capital: float):
        """## 记录交易到历史"""
        trade = {
            "strategy_name": sname,
            "contract": cont,
            "timestamp": datetime,
            "operation": operation,
            "price": price,
            "quantity": quantity,
            "pnl": pnl,
            "capital": capital
        }
        self.trade_history.append(trade)
        self.debug(f"记录交易: {operation} 价格{price} 盈亏{pnl}")

    def show_stats(self):
        """## 显示交易统计"""
        if self.stats["total_trades"] == 0 and self.stats["failed_trades"] == 0:
            self.info("暂无交易统计")
            return

        table = Table(title="📊 交易统计", show_header=True,
                      header_style="bold magenta")
        table.add_column("指标", style="cyan", width=20)
        table.add_column("数值", style="white", width=15)
        table.add_column("备注", style="dim", width=30)

        # 基本交易统计
        if self.stats["total_trades"] > 0:
            win_rate = (self.stats["winning_trades"] /
                        self.stats["total_trades"]) * 100
            run_time = datetime.now() - self.stats["start_time"]
            hours = run_time.total_seconds() / 3600
            trades_per_hour = self.stats["total_trades"] / \
                hours if hours > 0 else 0

            table.add_row("总交易次数", str(self.stats["total_trades"]), "所有平仓交易")
            table.add_row("盈利次数", str(
                self.stats["winning_trades"]), f"胜率: {win_rate:.1f}%")
            table.add_row("亏损次数", str(
                self.stats["losing_trades"]), f"败率: {100-win_rate:.1f}%")
            table.add_row("总盈亏", f"{self.stats['total_pnl']:+.2f}",
                          "green" if self.stats['total_pnl'] >= 0 else "red")
            table.add_row("最大盈利", f"{self.stats['max_profit']:+.2f}", "单笔最大盈利")
            table.add_row("最大亏损", f"{self.stats['max_loss']:+.2f}", "单笔最大亏损")
            table.add_row(
                "交易频率", f"{trades_per_hour:.1f}次/小时", f"运行{hours:.1f}小时")

        # 错误统计
        if self.stats["failed_trades"] > 0 or self.stats["insufficient_cash_errors"] > 0:
            table.add_row("失败交易", str(self.stats["failed_trades"]), "交易失败次数")
            table.add_row("资金不足", str(
                self.stats["insufficient_cash_errors"]), "现金不足错误次数")

        self.console.print(table)

    def show_recent_trades(self, count: int = 10):
        """## 显示最近交易"""
        if not self.trade_history:
            self.info("暂无交易记录")
            return

        recent_trades = self.trade_history[-count:]

        table = Table(title=f"📋 最近 {len(recent_trades)} 笔交易",
                      show_header=True, header_style="bold blue")
        table.add_column("时间", style="dim", width=16)
        table.add_column("操作", style="cyan", width=6)
        table.add_column("价格", style="white", width=10)
        table.add_column("数量", style="white", width=6)
        table.add_column("盈亏", style="white", width=12)
        table.add_column("资金", style="white", width=12)

        for trade in recent_trades:
            pnl_style = "green" if trade['pnl'] > 0 else "red" if trade['pnl'] < 0 else "white"
            table.add_row(
                trade['timestamp'].strftime('%m-%d %H:%M'),
                trade['operation'],
                f"{trade['price']:.2f}",
                str(trade['quantity']),
                f"[{pnl_style}]{trade['pnl']:+.2f}[/{pnl_style}]",
                f"{trade['capital']:.2f}"
            )

        self.console.print(table)

    # 旧格式日志解析（保持不变）
    def parse_legacy_logs(self, log_lines: List[str]):
        """## 解析旧格式日志"""
        self.info("开始解析旧格式日志")
        # ... 原有的解析代码保持不变

    def print_account(self, account: BtAccount):
        """## 美观化账户信息打印"""
        self.print_header()
        # 创建主面板
        main_panel = Panel(
            self._create_account_content(account),
            title="💰 账户信息",
            title_align="center",
            style="bold cyan",
            box=box.DOUBLE_EDGE
        )

        self.console.print(main_panel)

        # 如果有持仓，显示持仓详情
        if any(not broker.mpsc.empty() for broker in account.brokers):
            self.console.print(self._create_positions_table(account))

    def _create_account_content(self, account: BtAccount) -> str:
        """## 创建账户内容"""
        # 计算收益率
        initial_balance = account.cash  # 假设初始资金为100万，你可以根据实际情况调整
        total_return = ((account.balance - initial_balance) /
                        initial_balance) * 100

        # 确定颜色样式
        balance_style = "green" if account.balance >= initial_balance else "red"
        profit_style = "green" if account.total_profit >= 0 else "red"
        return_style = "green" if total_return >= 0 else "red"

        content = f"""
    [bold]账户权益:[/bold] [{balance_style}]{account.balance:,.2f}[/{balance_style}]
    [bold]可用现金:[/bold] {account.available:,.2f}
    [bold]累计手续费:[/bold] {account.total_commission:,.2f}
    [bold]累计收益:[/bold] [{profit_style}]{account.total_profit:+,.2f}[/{profit_style}]
    [bold]总收益率:[/bold] [{return_style}]{total_return:+.2f}%[/{return_style}]
    """
        # [bold]持仓合约数:[/bold] {sum(len(broker.mpsc.queue) for broker in account.brokers if not broker.mpsc.empty())}
        # [bold]活跃Broker数:[/bold] {sum(1 for broker in account.brokers if not broker.mpsc.empty())}
        return content

    def _create_positions_table(self, account: BtAccount) -> Table:
        """## 创建持仓表格"""
        table = Table(
            title="📊 最后持仓详情",
            show_header=True,
            header_style="bold magenta",
            box=box.ROUNDED
        )

        # 添加表头
        table.add_column("合约", style="cyan", width=12)
        table.add_column("序号", style="dim", width=4)
        table.add_column("保证金", style="yellow", width=12)
        table.add_column("成交价", style="green", width=12)
        table.add_column("手数", style="blue", width=8)
        table.add_column("手续费", style="red", width=12)
        table.add_column("持仓价值", style="white", width=15)

        # 添加持仓数据
        broker_index = 0
        for broker in account.brokers:
            if not broker.mpsc.empty():
                position_index = 0
                for position in broker.mpsc.queue:
                    margin, price, size, commission = position
                    position_value = price * size

                    table.add_row(
                        f"{broker.symbol}",
                        str(position_index + 1),
                        f"{margin:,.2f}",
                        f"{price:,.2f}",
                        f"{size:,}",
                        f"{commission:,.2f}",
                        f"{position_value / broker.margin_rate:,.2f}"
                    )
                    position_index += 1
                broker_index += 1

        return table

    def print_account_simple(self, account: BtAccount):
        """## 简洁版账户信息打印（兼容旧格式）"""
        # 收集所有broker的mpsc数据
        mpsc_data = []
        for broker in account.brokers:
            if broker.mpsc.empty():
                mpsc_data.append([])
            else:
                mpsc_data.append(broker.mpsc.queue)

        # 创建账户信息字典
        account_info = {
            "账户权益": account.balance,
            "现金": account.available,
            "手续费": account.total_commission,
            "收益": account.total_profit,
            "mpsc": mpsc_data
        }

        # 使用Rich的语法高亮显示字典
        from rich.syntax import Syntax
        account_str = str(account_info)
        syntax = Syntax(account_str, "python",
                        theme="monokai", line_numbers=False)

        panel = Panel(
            syntax,
            title="📋 账户信息 (原始格式)",
            style="bold blue"
        )
        self.console.print(panel)

    #
    def print_strategy(self, strategy: Strategy):
        """## 美观化策略回测报告打印"""
        self.print_header()
        if not hasattr(strategy, "profits") or strategy.profits is None:
            self.warning("策略无收益数据，无法生成报告")
            return

        # 计算策略指标
        profits = pd.Series(strategy.profits).diff()
        profits.iloc[0] = 0.
        returns = strategy._net_worth

        if len(profits.unique()) <= 1:
            self.warning("收益数据无波动，无法计算有效指标")
            return

        # 计算所有指标
        final_return = profits.sum()
        comm = strategy._account._total_commission
        compounded = qs_stats.comp(returns)
        sharpe = qs_stats.sharpe(returns)
        max_dd = qs_stats.max_drawdown(returns)
        value_at_risk = qs_stats.value_at_risk(returns)
        risk_return_ratio = qs_stats.risk_return_ratio(returns)
        profit_factor = qs_stats.profit_factor(returns)
        profit_ratio = qs_stats.profit_ratio(returns)
        win_rate = qs_stats.win_rate(returns)
        wins = len(profits[profits > 0.])
        losses = len(profits[profits < 0.])
        avg_return = qs_stats.avg_return(profits)
        avg_win = qs_stats.avg_win(profits)
        avg_loss = qs_stats.avg_loss(profits)

        # 创建主面板
        self.console.print(
            Panel(
                self._create_strategy_header(
                    strategy, final_return, compounded, wins, losses),
                title=f"📈 {strategy.__class__.__name__} 策略回测报告",
                title_align="center",
                style="bold cyan",
                box=box.DOUBLE_EDGE
            )
        )

        # 创建指标表格
        self.console.print(self._create_metrics_table(
            final_return, comm, compounded, sharpe, value_at_risk,
            risk_return_ratio, max_dd, profit_factor, profit_ratio,
            win_rate, wins, losses, avg_return, avg_win, avg_loss
        ))

        # 创建性能评估面板
        if strategy.config.performance:
            self.console.print(self._create_performance_assessment(
                sharpe, win_rate, profit_factor, max_dd
            ))

    def _create_strategy_header(self, strategy: Strategy, final_return, compounded, wins, losses) -> str:
        """## 创建策略报告头部信息"""
        total_trades = wins + losses
        win_rate_percent = (wins / total_trades *
                            100) if total_trades > 0 else 0

        # 确定颜色样式
        return_style = "green" if final_return >= 0 else "red"
        compounded_style = "green" if compounded >= 0 else "red"
        win_rate_style = "green" if win_rate_percent >= 50 else "yellow"
        start, end = strategy._start_end_datetime()

        header = f"""
    [bold]策略名称:[/bold] {strategy.__class__.__name__}
    [bold]回测周期:[/bold] {start} 至 {end}
    [bold]总交易次数:[/bold] {total_trades} ([{win_rate_style}]{win_rate_percent:.1f}%[/{win_rate_style}] 胜率)
    [bold]最终收益:[/bold] [{return_style}]{final_return:+,.2f}[/{return_style}] ([{compounded_style}]{compounded:+.2%}[/{compounded_style}])
    """
        return header

    def _create_metrics_table(self, final_return, comm, compounded, sharpe, value_at_risk,
                              risk_return_ratio, max_dd, profit_factor, profit_ratio,
                              win_rate, wins, losses, avg_return, avg_win, avg_loss) -> Table:
        """## 创建指标表格"""
        table = Table(show_header=True,
                      header_style="bold magenta", box=box.ROUNDED)

        # 添加三列
        table.add_column("收益指标", style="cyan", width=20)
        table.add_column("风险指标", style="yellow", width=20)
        table.add_column("交易指标", style="green", width=20)

        # 收益指标行
        return_style = "green" if final_return >= 0 else "red"
        compounded_style = "green" if compounded >= 0 else "red"
        profit_factor_style = "green" if profit_factor > 1 else "red"

        table.add_row(
            f"最终收益: [{return_style}]{final_return:+,.2f}[/{return_style}]",
            f"夏普比率: {sharpe:.4f}",
            f"胜率: {win_rate:.2%}"
        )

        table.add_row(
            f"累计收益率: [{compounded_style}]{compounded:+.2%}[/{compounded_style}]",
            f"最大回撤: {abs(max_dd):.2%}",
            f"盈利次数: {wins}"
        )

        table.add_row(
            f"总手续费: {comm:.2f}",
            f"风险价值(VaR): {value_at_risk:.4f}",
            f"亏损次数: {losses}"
        )

        table.add_row(
            f"盈亏比: [{profit_factor_style}]{profit_factor:.4f}[/{profit_factor_style}]",
            f"风险收益比: {risk_return_ratio:.4f}",
            f"收益比率: {profit_ratio:.4f}"
        )

        table.add_row(
            f"平均收益: {avg_return:.6f}",
            "",
            f"交易次数: {wins + losses}"
        )

        table.add_row(
            f"平均盈利: {avg_win:.6f}",
            "",
            f"平均亏损: {avg_loss:.6f}"
        )

        return table

    def _create_performance_assessment(self, sharpe, win_rate, profit_factor, max_dd) -> Panel:
        """## 创建性能评估面板"""
        assessments = []

        # 夏普比率评估
        if sharpe > 1.5:
            sharpe_assess = "[green]优秀[/green] (>1.5)"
        elif sharpe > 0.5:
            sharpe_assess = "[yellow]良好[/yellow] (0.5-1.5)"
        elif sharpe > 0:
            sharpe_assess = "[blue]一般[/blue] (0-0.5)"
        else:
            sharpe_assess = "[red]较差[/red] (<0)"

        # 胜率评估
        if win_rate > 0.6:
            win_rate_assess = "[green]优秀[/green] (>60%)"
        elif win_rate > 0.5:
            win_rate_assess = "[yellow]良好[/yellow] (50%-60%)"
        elif win_rate > 0.4:
            win_rate_assess = "[blue]一般[/blue] (40%-50%)"
        else:
            win_rate_assess = "[red]较差[/red] (<40%)"

        # 盈亏比评估
        if profit_factor > 1.5:
            pf_assess = "[green]优秀[/green] (>1.5)"
        elif profit_factor > 1.1:
            pf_assess = "[yellow]良好[/yellow] (1.1-1.5)"
        elif profit_factor > 1.0:
            pf_assess = "[blue]一般[/blue] (1.0-1.1)"
        else:
            pf_assess = "[red]较差[/red] (<1.0)"

        # 最大回撤评估
        max_dd_abs = abs(max_dd)
        if max_dd_abs < 0.1:
            dd_assess = "[green]优秀[/green] (<10%)"
        elif max_dd_abs < 0.2:
            dd_assess = "[yellow]良好[/yellow] (10%-20%)"
        elif max_dd_abs < 0.3:
            dd_assess = "[blue]一般[/blue] (20%-30%)"
        else:
            dd_assess = "[red]较差[/red] (>30%)"

        assessment_content = f"""
    [b]性能评估:[/b]

    [b]夏普比率:[/b] {sharpe_assess}
    [b]胜率:[/b] {win_rate_assess}  
    [b]盈亏比:[/b] {pf_assess}
    [b]最大回撤:[/b] {dd_assess}

    [dim]注: 评估基于行业标准，具体标准可能因策略类型而异[/dim]
    """

        return Panel(assessment_content, title="🎯 性能评估", style="bold blue")

    def print_strategy_simple(self, strategy: Strategy):
        """## 简洁版策略报告（保持原格式）"""
        if not hasattr(strategy, "pprint"):
            self.warning("策略对象没有pprint方法")
            return

        # 使用原策略的pprint方法
        strategy.pprint


# 全局日志器实例
_global_logger = None


def get_logger(name: str = "minibt", **kwargs) -> Logger:
    """## 获取全局日志器实例"""
    global _global_logger
    if _global_logger is None:
        kwargs.setdefault('enable_traceback', False)
        _global_logger = Logger(name, **kwargs)
    return _global_logger

# # 使用示例
# if __name__ == "__main__":
#     # 创建日志器
#     logger = Logger("minibt", log_level=LogLevel.DEBUG)

#     # 测试通用日志
#     logger.debug("这是一条调试信息")
#     logger.info("这是一条普通信息")
#     logger.warning("这是一条警告信息")
#     logger.error("这是一条错误信息")
#     logger.success("这是一条成功信息")

#     # 测试交易日志
#     current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     logger.open_long(current_time, 4678.0, 1, 0.0, 998475.0)
#     logger.close_short(current_time, 4664.0, 1, 0.0, -45.0, 998475.0)

#     # 测试错误和警告日志
#     logger.log_insufficient_cash(current_time, "当前资金: 1000, 所需资金: 1500")
#     logger.log_trade_failed(current_time, "网络超时", "重试3次后仍失败")
#     logger.log_market_warning(current_time, "市场波动剧烈", "建议降低仓位")

#     # 测试性能监控
#     @logger.time_it
#     def test_function():
#         time.sleep(0.1)
#         return "完成"

#     test_function()

#     # 显示统计
#     logger.show_stats()
#     logger.show_performance()
