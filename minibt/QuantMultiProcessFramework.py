import os
import numpy as np
import multiprocessing as mp
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection
from typing import List, Dict, Callable, Any, Union, Tuple
import select

# 从独立模块导入函数
from test import calculate_indicator, backtest_strategy

# 确保Windows系统使用spawn启动方式
if os.name == 'nt':
    mp.set_start_method('spawn', force=True)

__all__ = ["QuantMultiProcessFramework", "QuantTask", "ReplayTask"]


class QuantTask:
    """量化任务基类 - 简化逻辑，移除输出"""

    def __init__(self, task_id: int, func: Callable, params: Dict = None, data: Any = None):
        self.task_id = task_id
        self.func = func
        self.params = params or {}
        self.data = data
        self.result = None

    def run(self) -> Dict:
        """执行任务 - 仅返回结果，无打印输出"""
        if self.data is not None:
            result = self.func(self.data, **self.params)
        else:
            result = self.func(** self.params)
        return self.task_id, result


class ReplayTask(QuantTask):
    """回测专用任务类 - 处理指标计算逻辑"""

    def run(self):
        params = self.params.copy()
        start_length = params.pop("start_length")
        ind_params = params.pop("ind_params")
        func_name = params.pop("func_name")
        myself = params.pop("myself")

        # 数据长度不足时返回NaN
        if len(self.data) < start_length:
            return self.task_id, np.nan

        # 调用指标函数（两种模式）
        if myself:
            _args = [self.data] + ind_params
            result = self.func(*_args, **params).values[-1]
        else:
            # 调用数据对象的ta属性中的指标方法
            result = getattr(getattr(self.data, "ta"), func_name)(
                *ind_params, **params).values[-1]

        return self.task_id, result


class WorkerProcess(Process):
    """工作进程"""

    def __init__(self, worker_id: int, task_pipe: Connection, result_pipe: Connection):
        super().__init__()
        self.worker_id = worker_id
        self.task_pipe = task_pipe
        self.result_pipe = result_pipe
        self.running = True

    def run(self) -> None:
        try:
            while self.running:
                # 增加超时机制，避免无限阻塞
                # if not self.task_pipe.poll():  # 1秒超时
                #     continue

                task: Union[QuantTask, None] = self.task_pipe.recv()
                if task is None:
                    self.running = False
                    break

                result = task.run()
                self.result_pipe.send(result)
        except:
            ...
        finally:
            # 确保管道关闭
            try:
                self.task_pipe.close()
                self.result_pipe.close()
            except Exception:
                pass


class CoordinatorProcess(Process):
    """协调进程"""

    def __init__(self, tasks: List[QuantTask],
                 task_pipes: List[Connection],
                 result_pipes: List[Connection],
                 result_send_pipe: Connection,
                 num_workers: int):
        super().__init__()
        self.tasks = tasks
        self.task_pipes = task_pipes
        self.result_pipes = result_pipes
        self.result_send_pipe = result_send_pipe
        self.num_workers = num_workers
        self.results = []

    def run(self) -> None:
        try:
            task_count = len(self.tasks)
            completed_tasks = 0
            task_index = 0

            # 初始分配任务
            for worker_id in range(min(self.num_workers, task_count)):
                self._assign_task(worker_id, task_index)
                task_index += 1

            # 处理结果并动态分配新任务
            while completed_tasks < task_count:
                for worker_id in range(self.num_workers):
                    if self.result_pipes[worker_id].poll():
                        result = self.result_pipes[worker_id].recv()
                        self.results.append(result)
                        completed_tasks += 1

                        if task_index < task_count:
                            self._assign_task(worker_id, task_index)
                            task_index += 1

            # 排序结果
            self.results.sort(key=lambda x: x['task_id'])
            # self.results = sorted(self.results, key=lambda x: x[0])
            # self.results = [value for _, value in self.results]

            # 关键修复：确保结果发送成功
            if not self.result_send_pipe.closed:
                # 发送结果前先确认主进程已准备好
                self.result_send_pipe.send(len(self.results))  # 先发送结果数量
                ack = self.result_send_pipe.recv()  # 等待主进程确认
                if ack == "ready":
                    self.result_send_pipe.send(self.results)  # 再发送实际结果

        except:
            if not self.result_send_pipe.closed:
                self.result_send_pipe.send([])
        finally:
            try:
                self.result_send_pipe.close()
            except Exception:
                pass

    def _assign_task(self, worker_id: int, task_index: int) -> None:
        self.task_pipes[worker_id].send(self.tasks[task_index])


class QuantMultiProcessFramework:
    """量化多进程计算框架"""

    def __init__(self, num_workers: int = None):
        self.num_workers = num_workers or min(mp.cpu_count(), 32)
        self.workers = []
        self.coordinator = None
        self.result_recv_pipe = None

    def run_tasks(self, tasks: List[QuantTask]) -> List[Dict]:
        if not tasks:
            return []

        # 创建通信管道（主进程与协调进程使用双向管道）
        main_result_recv, coord_result_send = Pipe(duplex=True)
        self.result_recv_pipe = main_result_recv

        # 工作进程与协调进程的管道
        task_pipes = []
        worker_task_pipes = []
        result_pipes = []
        worker_result_pipes = []

        for _ in range(self.num_workers):
            w_task_recv, c_task_send = Pipe(duplex=False)
            worker_task_pipes.append(w_task_recv)
            task_pipes.append(c_task_send)

            c_result_recv, w_result_send = Pipe(duplex=False)
            result_pipes.append(c_result_recv)
            worker_result_pipes.append(w_result_send)

        # 启动工作进程
        for i in range(self.num_workers):
            worker = WorkerProcess(
                worker_id=i,
                task_pipe=worker_task_pipes[i],
                result_pipe=worker_result_pipes[i]
            )
            self.workers.append(worker)
            worker.start()

        # 启动协调进程
        self.coordinator = CoordinatorProcess(
            tasks=tasks,
            task_pipes=task_pipes,
            result_pipes=result_pipes,
            result_send_pipe=coord_result_send,
            num_workers=self.num_workers
        )
        self.coordinator.start()

        # 关键修复：安全接收结果
        results = []
        try:
            # 先接收结果数量
            result_count = self.result_recv_pipe.recv()
            if result_count > 0:
                self.result_recv_pipe.send("ready")  # 发送确认
                results = self.result_recv_pipe.recv()  # 接收实际结果
        except:
            results = []

        # 关键修复：先关闭管道再join进程，避免死锁
        try:
            coord_result_send.close()
            main_result_recv.close()
        except Exception:
            pass
        # 清理工作进程管道
        for pipe in task_pipes + result_pipes + worker_task_pipes + worker_result_pipes:
            try:
                pipe.close()
            except Exception:
                pass

        # 等待进程结束
        self.coordinator.join()
        for worker in self.workers:
            worker.join()

        return results

    @classmethod
    def create_tasks_from_params(cls, func: Callable, params_list: List[Dict], data: Any = None, task_class: QuantTask = None) -> List[QuantTask]:
        task_class = task_class or QuantTask
        return [task_class(task_id=i, func=func, params=params, data=data) for i, params in enumerate(params_list)]

    @classmethod
    def create_tasks_from_datas(cls, func: Callable, data_list: List[Any], params: Dict = None, task_class: QuantTask = None) -> List[QuantTask]:
        task_class = task_class or QuantTask
        return [task_class(task_id=i, func=func, params=params, data=data) for i, data in enumerate(data_list)]


# 测试代码（无输出）
if __name__ == "__main__":
    np.random.seed(42)
    price_data = np.cumsum(np.random.randn(10000)) + 100

    # 场景1：固定数据源，不同参数
    framework = QuantMultiProcessFramework(num_workers=4)
    params_list = [
        {'window': 10, 'indicator_type': 'sma'},
        {'window': 20, 'indicator_type': 'sma'},
        {'window': 14, 'indicator_type': 'rsi'},
        {'window': 21, 'indicator_type': 'rsi'}
    ]
    tasks = QuantMultiProcessFramework.create_tasks_from_params(
        func=calculate_indicator,
        params_list=params_list,
        data=price_data
    )
    results = framework.run_tasks(tasks)

    # 场景2：固定参数，不同数据源
    data_list = [
        {'symbol': 'AAPL', 'close': np.cumsum(np.random.randn(10000)) + 150},
        {'symbol': 'MSFT', 'close': np.cumsum(np.random.randn(10000)) + 250},
        {'symbol': 'GOOG', 'close': np.cumsum(np.random.randn(10000)) + 2800},
        {'symbol': 'AMZN', 'close': np.cumsum(np.random.randn(10000)) + 130}
    ]
    fixed_params = {'initial_capital': 10000}
    tasks = QuantMultiProcessFramework.create_tasks_from_datas(
        func=backtest_strategy,
        data_list=data_list,
        params=fixed_params
    )
    results = framework.run_tasks(tasks)
