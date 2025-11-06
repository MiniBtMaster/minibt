import os  # 导入操作系统相关模块，用于文件路径处理等
import numpy as np  # 导入numpy库，用于数值计算
import torch as th  # 导入PyTorch库，并重命名为th，用于深度学习计算
from torch import nn  # 导入PyTorch的神经网络模块
from torch.nn.utils import clip_grad_norm_  # 导入梯度裁剪工具，用于稳定训练
from typing import Union, Optional  # 导入类型提示工具，用于指定变量类型

# 从上级目录的train模块导入Config配置类和get_kwargs工具函数
from ..train import Config, get_kwargs
from ..train import ReplayBuffer  # 从上级目录的train模块导入经验回放缓冲区类

TEN = th.Tensor  # 定义类型别名TEN，代表PyTorch张量
try:
    # PyTorch 2.0+ 推荐用法
    from torch.amp import GradScaler
except ImportError:
    # 回退到旧版（PyTorch < 2.0）
    from torch.cuda.amp import GradScaler as _GradScaler

    def GradScaler(**kwargs):
        return _GradScaler(**kwargs) if th.cuda.is_available() else None


'''agent'''


class AgentBase:
    """
    优雅强化学习（ElegantRL）的基础智能体类
    所有具体智能体（如DQN、PPO等）的父类，实现通用功能

    net_dims: MLP（多层感知器）的中间层维度列表
    state_dim: 状态的维度（状态向量的特征数量）
    action_dim: 动作的维度（连续动作的特征数或离散动作的数量）
    gpu_id: 训练设备的GPU编号，当CUDA不可用时使用CPU
    args: 智能体训练的参数配置，`args = Config()`
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        self.if_discrete: bool = args.if_discrete  # 是否为离散动作空间
        self.if_off_policy: bool = args.if_off_policy  # 是否为离线策略算法

        self.net_dims = net_dims  # 每个网络层的维度列表
        self.state_dim = state_dim  # 状态的特征数量
        self.action_dim = action_dim  # 连续动作的特征数或离散动作的数量

        self.gamma = args.gamma  # 未来奖励的折扣因子
        self.max_step = args.max_step  # 智能体在一条轨迹中可执行的最大步数限制
        self.num_envs = args.num_envs  # 向量环境中子环境的数量，单环境时为1
        self.batch_size = args.batch_size  # 从经验回放缓冲区中采样的转移样本数量
        self.repeat_times = args.repeat_times  # 使用回放缓冲区中的样本重复更新网络的次数
        self.reward_scale = args.reward_scale  # 奖励的缩放因子，通常用于调整奖励量级
        self.learning_rate = args.learning_rate  # 网络更新的学习率
        self.if_off_policy = args.if_off_policy  # 再次确认是否为离线策略算法
        self.clip_grad_norm = args.clip_grad_norm  # 梯度归一化后的裁剪阈值
        self.soft_update_tau = args.soft_update_tau  # 软目标更新的系数，用于平滑更新目标网络
        self.state_value_tau = args.state_value_tau  # 状态价值归一化的系数
        self.buffer_init_size = args.buffer_init_size  # 离线策略中，开始训练前缓冲区需要的初始样本量

        self.explore_noise_std = getattr(
            args, 'explore_noise_std', 0.05)  # 探索噪声的标准差\
        self.explore_rate = getattr(args, "explore_rate", 0.985)  # 探索率衰减系数
        # 轨迹的最后一个状态，形状为(num_envs, state_dim)
        self.last_state: Optional[TEN] = None
        # 设备配置：优先使用指定GPU，否则使用CPU
        self.device = th.device(f"cuda:{gpu_id}" if (
            th.cuda.is_available() and (gpu_id >= 0)) else "cpu")

        '''network'''
        self.act = None  # 行为网络（Actor），用于生成动作
        self.cri = None  # 评价网络（Critic），用于评估动作价值
        self.act_target = self.act  # 行为目标网络，用于稳定训练
        self.cri_target = self.cri  # 评价目标网络，用于稳定训练

        '''optimizer'''
        self.act_optimizer: Optional[th.optim.Optimizer] = None  # 行为网络的优化器
        self.cri_optimizer: Optional[th.optim.Optimizer] = None  # 评价网络的优化器

        # 损失函数，默认为MSELoss（均方误差损失），不进行归约
        # self.criterion = getattr(
        #     args, 'criterion', th.nn.MSELoss(reduction="none"))
        # 损失函数（修复未初始化问题）
        self.criterion = None
        self.if_vec_env = self.num_envs > 1  # 是否使用向量环境（多子环境并行）
        self.if_use_per = getattr(args, 'if_use_per', False)  # 是否使用优先经验回放（PER）
        self.lambda_fit_cum_r = getattr(
            args, 'lambda_fit_cum_r', 0.0)  # 用于拟合累积奖励的系数
        self._ismuon = False

        """save and load"""
        # 需要保存和加载的属性名称集合
        self.save_attr_names = {
            'act', 'act_target', 'act_optimizer', 'cri', 'cri_target', 'cri_optimizer'}
        # 增加的探索率相关参数
        # self.explore_rate = getattr(args, "explore_rate", 0.985)  # 探索率的衰减速率
        self.if_swa = False  # 是否使用滑动平均权重（SWA）
        self.if_lr_scheduler = False  # 是否使用学习率调度器
        self.if_swap_swa_sgd = False  # 是否切换SWA和SGD优化器
        self.current_epoch_progress = 0.  # 当前训练周期的进度
        self.swa_start_epoch_progress = args.swa_start_epoch_progress  # 开始SWA的训练周期进度

        # AMP梯度缩放器（修复重复初始化问题）
        self.amp_scale = GradScaler() if self.device.type == "cuda" else None

    def _create_optimizer(self, params, args: Config, model=None):
        """创建优化器（支持SWA包装）"""
        # 从参数中获取学习率，默认使用类中的learning_rate
        lr = args.Optim.keywords.pop("lr", self.learning_rate)
        # 获取权重衰减系数，默认使用args中的weight_decay
        # weight_decay = args.Optim.keywords.pop(
        #     "weight_decay", args.weight_decay)
        # # 获取数值稳定性参数eps，默认使用args中的eps
        # eps = args.Optim.keywords.pop("eps", args.eps)
        # # 获取动量参数，默认使用args中的eps
        # momentum = args.Optim.keywords.pop("momentum", args.momentum)
        # # 获取优化器函数的参数列表
        # kwargs = get_kwargs(args.Optim.func)
        # new_kwargs = {}
        # # 筛选需要的参数（权重衰减、eps、动量）
        # for name in ["weight_decay", "eps", "momentum"]:
        #     if name in kwargs:
        #         new_kwargs.update({name: locals()[name]})
        # 若优化器为SWA（滑动平均），则先创建基础优化器再包装
        if args.Optim.func.__name__ == "SWA":
            base_optim = th.optim.SGD(
                params, lr)
            return args.Optim(base_optim)
        elif "Muon" in args.Optim.func.__name__:
            # 关键：不依赖model.body，直接从params中筛选参数
            # Muon处理：维度≥2且不含输入维度（210）的参数
            muon_params = [p for p in params if
                           p.ndim >= 2 and
                           args.state_dim not in p.shape]
            adamw_params = [p for p in params if
                            p.ndim < 2 or
                            args.state_dim in p.shape]
            return args.Optim(
                muon_params=muon_params,
                adamw_params=adamw_params,
                input_feature_dim=args.state_dim,  # 传入输入维度210
                lr=lr
            )
        return args.Optim(params, lr)
        #     try:
        #         return args.Optim(base_optim, **new_kwargs)
        #     except:
        #         return args.Optim(base_optim, *list(new_kwargs.values()))
        # # 创建普通优化器
        # try:
        #     return args.Optim(params, lr, ** new_kwargs)
        # except:
        #     return args.Optim(params, lr, *list(new_kwargs.values()))

    def _setup_swa_components(self, args: Config):
        """初始化SWA组件（适配Actor/Critic双网络）"""
        self.if_swa = args.SWALR is not None  # 根据配置判断是否使用SWA
        if self.if_swa:
            from torch.optim.swa_utils import AveragedModel  # 导入SWA平均模型工具
            # 为Actor和Critic分别创建SWA平均模型
            self.swa_model_act = AveragedModel(self.act)
            self.swa_model_cri = AveragedModel(self.cri)
            # 为Actor和Critic的优化器创建SWA学习率调度器
            self.swa_scheduler_act = args.SWALR(self.act_optimizer)
            self.swa_scheduler_cri = args.SWALR(self.cri_optimizer)
        # 检查是否支持SWA与SGD切换（仅当优化器有对应方法时）
        self.if_swap_swa_sgd = (hasattr(self.act_optimizer, "swap_swa_sgd")
                                and hasattr(self.cri_optimizer, "swap_swa_sgd")
                                and self.if_swa)

    def _update_swa_and_scheduler(self):
        """统一处理SWA模型更新、学习率调度及SWA/SGD切换（所有Agent共用逻辑）"""
        # 若启用SWA且当前进度超过开始SWA的进度，则更新SWA模型和调度器
        if self.if_swa and self.current_epoch_progress >= self.swa_start_epoch_progress:
            self.swa_model_act.update_parameters(self.act)  # 更新Actor的SWA模型
            self.swa_model_cri.update_parameters(self.cri)  # 更新Critic的SWA模型
            self.swa_scheduler_act.step()  # 执行Actor的SWA学习率调度
            self.swa_scheduler_cri.step()  # 执行Critic的SWA学习率调度
        else:
            # 非SWA阶段：使用普通学习率调度器
            if self.if_lr_scheduler:
                self.act_scheduler.step()  # 执行Actor的普通学习率调度
                self.cri_scheduler.step()  # 执行Critic的普通学习率调度
        # 若支持SWA与SGD切换，则执行切换（如训练后期使用SWA权重）
        if self.if_swap_swa_sgd:
            self.act_optimizer.swap_swa_sgd()
            self.cri_optimizer.swap_swa_sgd()

    def explore_env(self, env, horizon_len: int) -> tuple[TEN, TEN, TEN, TEN, TEN]:
        """根据环境类型（向量/单环境）调用对应的探索方法"""
        if self.if_vec_env:
            return self._explore_vec_env(env=env, horizon_len=horizon_len)
        else:
            return self._explore_one_env(env=env, horizon_len=horizon_len)

    def explore_action(self, state: TEN) -> TEN:
        """生成探索动作（加入噪声）"""
        return self.act.get_action(state, action_std=self.explore_noise_std)

    def _explore_one_env(self, env, horizon_len: int) -> tuple[TEN, TEN, TEN, TEN, TEN]:
        """
        在**单个**环境中通过智能体与环境交互收集轨迹数据

        env: RL训练环境，需支持env.reset()和env.step()方法
        horizon_len: 探索时收集的步数
        return: 轨迹数据(states, actions, rewards, undones, unmasks)
            num_envs == 1（单环境）
            states.shape == (horizon_len, num_envs, state_dim)
            actions.shape == (horizon_len, num_envs, action_dim)
            rewards.shape == (horizon_len, num_envs)
            undones.shape == (horizon_len, num_envs)  # 非终止标志（1-终止标志）
            unmasks.shape == (horizon_len, num_envs)  # 非截断标志（1-截断标志）
        """
        # 初始化存储轨迹数据的张量
        states = th.zeros((horizon_len, self.state_dim),
                          dtype=th.float32).to(self.device)
        # 根据动作类型（离散/连续）初始化动作张量
        actions = th.zeros((horizon_len, self.action_dim), dtype=th.float32).to(self.device) \
            if not self.if_discrete else th.zeros(horizon_len, dtype=th.int32).to(self.device)
        rewards = th.zeros(horizon_len, dtype=th.float32).to(self.device)  # 奖励
        terminals = th.zeros(horizon_len, dtype=th.bool).to(
            self.device)  # 终止标志
        truncates = th.zeros(horizon_len, dtype=th.bool).to(
            self.device)  # 截断标志

        state = self.last_state  # 获取上一步的最终状态
        for t in range(horizon_len):
            action = self.explore_action(state)[0]  # 生成探索动作

            states[t] = state  # 存储当前状态
            actions[t] = action  # 存储当前动作

            # 将动作转换为numpy数组，与环境交互
            ary_action = action.detach().cpu().numpy()
            ary_state, reward, terminal, truncate, _ = env.step(ary_action)
            # 若环境终止或截断，则重置环境
            if terminal or truncate:
                ary_state, info_dict = env.reset()
            # 将新状态转换为张量并添加批次维度
            state = th.as_tensor(ary_state, dtype=th.float32,
                                 device=self.device).unsqueeze(0)

            rewards[t] = reward  # 存储奖励
            terminals[t] = terminal  # 存储终止标志
            truncates[t] = truncate  # 存储截断标志

        self.last_state = state  # 更新最后状态
        # '''为了与多环境缓冲区拼接，增加维度1=1'''
        # states = states.view((horizon_len, 1, self.state_dim))  # 调整状态维度
        # # 调整动作维度（适应离散/连续动作）
        # actions = actions.view(
        #     (horizon_len, 1, self.action_dim if not self.if_discrete else 1))
        # actions = actions.view((horizon_len, 1, self.action_dim)) \
        #     if not self.if_discrete else actions.view((horizon_len, 1))
        # # 缩放奖励并调整维度
        # rewards = (rewards * self.reward_scale).view((horizon_len, 1))
        # undones = th.logical_not(terminals).view((horizon_len, 1))  # 计算非终止标志
        # unmasks = th.logical_not(truncates).view((horizon_len, 1))  # 计算非截断标志

        # 调整维度以匹配多环境格式 (horizon_len, 1, ...)
        states = states.unsqueeze(1)
        actions = actions.unsqueeze(1) if self.if_discrete else actions.view(
            horizon_len, 1, self.action_dim)
        rewards = (rewards * self.reward_scale).unsqueeze(1)
        undones = (~terminals).unsqueeze(1).float()  # 转为float类型
        unmasks = (~truncates).unsqueeze(1).float()
        return states, actions, rewards, undones, unmasks

    def _explore_vec_env(self, env, horizon_len: int) -> tuple[TEN, TEN, TEN, TEN, TEN]:
        """
        在**向量化**环境中通过智能体与环境交互收集轨迹数据

        env: RL训练环境，需支持env.reset()和env.step()方法，为向量环境
        horizon_len: 探索时收集的步数
        return: 轨迹数据(states, actions, rewards, undones, unmasks)
            num_envs > 1（多环境）
            states.shape == (horizon_len, num_envs, state_dim)
            actions.shape == (horizon_len, num_envs, action_dim)
            rewards.shape == (horizon_len, num_envs)
            undones.shape == (horizon_len, num_envs)  # 非终止标志（1-终止标志）
            unmasks.shape == (horizon_len, num_envs)  # 非截断标志（1-截断标志）
        """
        # 初始化存储轨迹数据的张量（多环境维度）
        states = th.zeros((horizon_len, self.num_envs,
                          self.state_dim), dtype=th.float32).to(self.device)
        # 根据动作类型（离散/连续）初始化动作张量
        actions = th.zeros((horizon_len, self.num_envs, self.action_dim), dtype=th.float32).to(self.device) \
            if not self.if_discrete else th.zeros((horizon_len, self.num_envs), dtype=th.int32).to(self.device)
        rewards = th.zeros((horizon_len, self.num_envs),
                           dtype=th.float32).to(self.device)  # 奖励
        terminals = th.zeros((horizon_len, self.num_envs),
                             dtype=th.bool).to(self.device)  # 终止标志
        truncates = th.zeros((horizon_len, self.num_envs),
                             dtype=th.bool).to(self.device)  # 截断标志

        state = self.last_state  # 获取上一步的最终状态（形状为(num_envs, state_dim)）
        for t in range(horizon_len):
            action = self.explore_action(state)  # 生成探索动作

            states[t] = state  # 存储当前状态
            actions[t] = action  # 存储当前动作

            # 与向量环境交互，获取新状态、奖励等
            state, reward, terminal, truncate, _ = env.step(action)

            rewards[t] = reward  # 存储奖励
            terminals[t] = terminal  # 存储终止标志
            truncates[t] = truncate  # 存储截断标志

        self.last_state = state  # 更新最后状态
        rewards *= self.reward_scale  # 缩放奖励
        undones = th.logical_not(terminals).float()  # 计算非终止标志
        unmasks = th.logical_not(truncates).float()  # 计算非截断标志
        return states, actions, rewards, undones, unmasks

    def update_net(self, buffer: Union[ReplayBuffer, tuple]) -> tuple[float, ...]:
        """更新网络（主方法），通过经验回放缓冲区中的样本训练网络"""
        objs_critic = []  # 存储评价网络的损失值
        objs_actor = []  # 存储行为网络的损失值

        # 若需要拟合累积奖励，则更新缓冲区中的累积奖励
        if self.lambda_fit_cum_r != 0:
            buffer.update_cum_rewards(
                get_cumulative_rewards=self.get_cumulative_rewards)

        th.set_grad_enabled(True)  # 启用梯度计算
        # 计算更新次数：根据缓冲区当前大小、重复更新次数和批次大小
        update_times = int(buffer.cur_size *
                           self.repeat_times / self.batch_size)
        for update_t in range(update_times):
            # 计算每次更新的目标函数值
            obj_critic, obj_actor = self.update_objectives(
                buffer=buffer, update_t=update_t)
            objs_critic.append(obj_critic)  # 记录评价网络损失
            # 记录行为网络损失（若为有效数值）
            objs_actor.append(obj_actor) if isinstance(
                obj_actor, float) else None
        th.set_grad_enabled(False)  # 禁用梯度计算

        # 新增：更新SWA和调度器（在每轮网络更新后执行）
        self._update_swa_and_scheduler()

        # 计算平均损失
        obj_avg_critic = np.nanmean(objs_critic) if objs_critic else 0.0
        obj_avg_actor = np.nanmean(objs_actor) if objs_actor else 0.0
        return obj_avg_critic, obj_avg_actor

    def update_objectives(self, buffer: ReplayBuffer, update_t: int) -> tuple[float, float]:
        """更新目标函数（单次更新），计算损失并反向传播"""
        assert isinstance(update_t, int)  # 确保update_t为整数
        with th.no_grad():  # 禁用梯度计算（目标值计算不需要梯度）
            if self.if_use_per:  # 若使用优先经验回放
                # 从缓冲区采样（包含优先级权重和索引）
                (state, action, reward, undone, unmask, next_state,
                 is_weight, is_index) = buffer.sample_for_per(self.batch_size)
            else:  # 普通经验回放
                state, action, reward, undone, unmask, next_state = buffer.sample(
                    self.batch_size)
                is_weight, is_index = None, None  # 无优先级权重和索引

            next_action = self.act(next_state)  # 用当前行为网络计算下一状态的动作（确定性策略）
            next_q = self.cri_target(
                next_state, next_action)  # 用目标评价网络计算下一状态的Q值

            # 计算目标Q值：即时奖励 + 折扣*下一状态Q值（仅当未终止时）
            q_label = reward + undone * self.gamma * next_q

        # 用当前评价网络计算Q值，并应用非截断掩码
        q_value = self.cri(state, action) * unmask
        # 计算TD误差（时间差分误差），应用非截断掩码
        td_error = self.criterion(q_value, q_label) * unmask
        if self.if_use_per:  # 优先经验回放时，用优先级权重加权损失
            obj_critic = (td_error * is_weight).mean()
            # 更新缓冲区中的优先级（基于TD误差）
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:  # 普通经验回放，直接计算平均TD误差
            obj_critic = td_error.mean()
        # 评价网络反向传播（优化器更新）
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        # 软更新评价目标网络
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 检查是否满足更新行为网络的条件（缓冲区样本量足够）
        if_update_act = bool(buffer.cur_size >= self.buffer_init_size)
        if if_update_act:
            action_pg = self.act(state)  # 用当前行为网络生成动作（用于策略梯度）
            # obj_actor = -self.cri(state, action_pg).mean()  # SAC通常直接最小化负Q值
            obj_actor = self.cri(state, action_pg).mean()  # 行为网络目标：最大化Q值
            # 行为网络反向传播（负号表示最大化，优化器默认最小化）
            self.optimizer_backward(self.act_optimizer, -obj_actor)
            # 软更新行为目标网络
            self.soft_update(self.act_target, self.act, self.soft_update_tau)
        else:
            obj_actor = th.tensor(th.nan)  # 不满足条件时，行为网络损失为NaN
        return obj_critic.item(), obj_actor.item()

    def get_cumulative_rewards(self, rewards: TEN, undones: TEN) -> TEN:
        """计算累积奖励（从后往前计算，考虑折扣因子）"""
        cum_rewards = th.empty_like(rewards)  # 初始化累积奖励张量

        masks = undones * self.gamma  # 计算掩码（未终止时的折扣因子）
        horizon_len = rewards.shape[0]  # 轨迹长度

        last_state = self.last_state  # 最后一个状态
        next_action = self.act_target(last_state)  # 目标行为网络生成的下一动作
        next_value = self.cri_target(
            last_state, next_action).detach()  # 目标评价网络的价值估计
        # 从后往前计算累积奖励
        for t in range(horizon_len - 1, -1, -1):
            cum_rewards[t] = next_value = rewards[t] + masks[t] * next_value
        return cum_rewards

    def optimizer_backward(self, optimizer: th.optim.Optimizer, objective: TEN):
        """通过优化器最小化目标函数（反向传播过程）"""
        optimizer.zero_grad()  # 清零梯度
        objective.backward()  # 反向传播计算梯度
        # 梯度裁剪：防止梯度爆炸
        clip_grad_norm_(
            parameters=optimizer.param_groups[0]["params"], max_norm=self.clip_grad_norm)
        optimizer.step()  # 优化器更新参数

    # automatic mixed precision
    def optimizer_backward_amp(self, optimizer: th.optim.Optimizer, objective: TEN):
        """使用自动混合精度（AMP）最小化目标函数（反向传播过程）"""
        # amp_scale = th.cuda.amp.GradScaler()  # 初始化AMP缩放器（在__init__中定义）
        if self.amp_scale is None:
            return self.optimizer_backward(optimizer, objective)

        optimizer.zero_grad()  # 清零梯度
        self.amp_scale.scale(objective).backward()  # 缩放目标函数并反向传播
        self.amp_scale.unscale_(optimizer)  # 取消优化器梯度的缩放（用于梯度裁剪）

        # 梯度裁剪：防止梯度爆炸
        clip_grad_norm_(
            parameters=optimizer.param_groups[0]["params"], max_norm=self.clip_grad_norm)
        self.amp_scale.step(optimizer)  # 优化器更新参数（考虑缩放）
        self.amp_scale.update()  # 更新AMP缩放器状态

    @staticmethod
    def soft_update(target_net: th.nn.Module, current_net: th.nn.Module, tau: float):
        """软更新目标网络参数

        target_net: 目标网络，通过当前网络更新以稳定训练
        current_net: 当前网络，通过优化器更新
        tau: 软更新系数：target_net = target_net * (1-tau) + current_net * tau
        """
        # 遍历目标网络和当前网络的参数，进行软更新
        for tar, cur in zip(target_net.parameters(), current_net.parameters()):
            tar.data.copy_(cur.data * tau + tar.data * (1.0 - tau))

    def save_or_load_agent(self, cwd: str, if_save: bool):
        """保存/加载智能体（添加异常处理）"""
        os.makedirs(cwd, exist_ok=True)
        for attr_name in self.save_attr_names:
            obj = getattr(self, attr_name, None)
            if obj is None:
                continue

            file_path = f"{cwd}/{attr_name}.pth"
            try:
                if if_save:
                    # 推荐保存state_dict而非整个对象
                    th.save(obj.state_dict(), file_path)
                else:
                    if os.path.exists(file_path):
                        obj.load_state_dict(
                            th.load(file_path, map_location=self.device, weights_only=True))
            except Exception as e:
                print(f"处理{attr_name}时出错: {e}")

        # SWA模型处理
        if if_save and self.if_swa:
            th.save(self.swa_model_act.state_dict(), f"{cwd}/swa_actor.pth")
            th.save(self.swa_model_cri.state_dict(), f"{cwd}/swa_critic.pth")

    # def save_or_load_agent(self, cwd: str, if_save: bool):
    #     """保存或加载智能体的训练文件

    #     cwd: 当前工作目录，ElegantRL在该目录下保存训练文件
    #     if_save: True表示保存文件，False表示加载文件
    #     """
    #     assert self.save_attr_names.issuperset(
    #         {'act', 'act_optimizer'})  # 验证必须保存的属性

    #     for attr_name in self.save_attr_names:
    #         file_path = f"{cwd}/{attr_name}.pth"  # 属性对应的文件路径

    #         if getattr(self, attr_name) is None:  # 跳过空属性
    #             continue

    #         if if_save:  # 保存属性到文件
    #             th.save(getattr(self, attr_name), file_path)
    #         elif os.path.isfile(file_path):  # 加载文件到属性（若文件存在）
    #             # try:
    #             setattr(self, attr_name, th.load(
    #                 file_path, map_location=self.device, weights_only=False))
    #             # except:
    #             #     ...
    #     # 若启用SWA，保存SWA模型
    #     if if_save and hasattr(self, "if_swa") and self.if_swa:
    #         th.save(self.swa_model_act, f"{cwd}/swa_actor.pth")
    #         th.save(self.swa_model_cri, f"{cwd}/swa_critic.pth")


def get_optim_param(optimizer: th.optim) -> list:  # backup
    """获取优化器中的参数（备份用）"""
    params_list = []
    # 遍历优化器状态中的参数
    for params_dict in optimizer.state_dict()["state"].values():
        params_list.extend([t for t in params_dict.values()
                           if isinstance(t, th.Tensor)])
    return params_list


'''network'''


class ActorBase(nn.Module):
    """行为网络（Actor）基类，用于生成动作"""

    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        # 网络结构：MLP，输入为状态，输出为动作（需在子类中具体实现）
        # build_mlp(net_dims=[state_dim, *net_dims, action_dim])
        self.net = None

        self.state_dim = state_dim  # 状态维度
        self.action_dim = action_dim  # 动作维度
        self.explore_noise_std = None  # 探索噪声的标准差
        self.ActionDist = th.distributions.normal.Normal  # 动作分布（默认正态分布）

    def forward(self, state: TEN) -> TEN:
        """前向传播：输入状态，输出动作（通过tanh限制范围）"""
        return self.net(state).tanh()

    # def get_action(self, state: TEN, action_std: float = 0.0) -> TEN:
    #     """生成带噪声的动作（SAC需重写为分布采样）"""
    #     action_mean = self.forward(state)
    #     if action_std > 0:
    #         action = self.ActionDist(action_mean, action_std).sample()
    #         return action.clamp(-1.0, 1.0)  # 确保在合法范围
    #     return action_mean


class CriticBase(nn.Module):
    """评价网络（Critic）基类，用于评估动作价值（Q值）"""

    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.state_dim = state_dim  # 状态维度
        self.action_dim = action_dim  # 动作维度
        # 网络结构：MLP，输入为状态+动作，输出为Q值（需在子类中具体实现）
        # build_mlp(net_dims=[state_dim + action_dim, *net_dims, 1])
        self.net = None

    def forward(self, state: TEN, action: TEN) -> TEN:
        """前向传播：输入状态和动作，输出Q值（平均多个Q值估计）"""
        values = self.get_q_values(state=state, action=action)
        value = values.mean(dim=-1, keepdim=True)  # 平均多个Q值估计
        return value  # Q值

    def get_q_values(self, state: TEN, action: TEN) -> TEN:
        """获取Q值估计：拼接状态和动作作为输入，通过网络计算"""
        values = self.net(th.cat((state, action), dim=1))
        return values  # Q值估计

    # def get_q_values(self, state: TEN, action: TEN) -> TEN:
    #     """获取所有Q值估计"""
    #     x = th.cat((state, action), dim=1)
    #     return th.cat([net(x) for net in self.nets], dim=-1)  # (batch_size, num_q)


"""utils"""


def build_mlp(
    dims: list[int],
    output_activation: bool = False,
    args: Config = None
) -> nn.Sequential:
    """
    构建多层感知器(MLP)，支持添加激活函数、层归一化、Dropout等组件

    参数:
        dims: 网络维度列表，例如[输入_dim, 隐藏层1_dim, ..., 输出_dim]
        activation: 隐藏层激活函数类型（如nn.ReLU, nn.GELU），默认使用nn.Tanh
        output_activation: 是否为输出层添加激活函数（默认不添加）
        add_layer_norm: 是否在隐藏层后添加LayerNorm（输出层前不添加）
        dropout_rate: Dropout概率（0~1），0表示不使用Dropout
        bias: 线性层是否使用偏置项

    返回:
        构建好的MLP网络（nn.Sequential）
    """
    activation = args.Activation or nn.Tanh  # 激活函数类型
    norm = args.Norm
    dropout_rate = args.dropout_rate       # Dropout概率，0表示不使用
    bias = args.bias                # 线性层是否使用偏置
    # 输入验证：确保维度列表有效
    if len(dims) < 2:
        raise ValueError(f"dims列表长度必须至少为2（输入+输出），当前为{len(dims)}")
    if not all(isinstance(d, int) and d > 0 for d in dims):
        raise ValueError(f"dims必须包含正整数，当前为{dims}")
    if dropout_rate < 0. or dropout_rate >= 1.:
        raise ValueError(f"dropout_rate必须在[0, 1)范围内，当前为{dropout_rate}")
    net_list = []  # 存储网络层的列表
    num_layers = len(dims) - 1  # 总层数（线性层数量）
    for i in range(num_layers):
        # 添加线性层（输入维度dims[i]，输出维度dims[i+1]）
        net_list.append(nn.Linear(dims[i], dims[i+1], bias=bias))
        # 处理隐藏层（除输出层外）
        if i < num_layers - 1:
            # 添加激活函数
            net_list.append(activation())
            # 若启用，添加层归一化
            if norm is not None:
                net_list.append(norm(dims[i+1]))
            # 若启用，添加Dropout
            if dropout_rate > 0.:
                net_list.append(nn.Dropout(dropout_rate))
        # 处理输出层
        else:
            # 若需要，为输出层添加激活函数
            if output_activation:
                net_list.append(activation())
    # 组合所有层为Sequential网络
    return nn.Sequential(*net_list)


def layer_init_with_orthogonal(layer, std=1.0, bias_const=1e-6):
    """用正交初始化方法初始化层的权重和偏置"""
    th.nn.init.orthogonal_(layer.weight, std)  # 正交初始化权重
    th.nn.init.constant_(layer.bias, bias_const)  # 偏置初始化为常数


class NnReshape(nn.Module):
    """自定义的Reshape层，用于调整张量形状"""

    def __init__(self, *args):
        super().__init__()
        self.args = args  # 目标形状

    def forward(self, x):
        """前向传播：将输入张量调整为指定形状（保留批次维度）"""
        return x.view((x.size(0),) + self.args)


class DenseNet(nn.Module):  # 计划作为超参数：层数
    """密集连接网络（DenseNet），用于特征提取"""

    def __init__(self, lay_dim):
        super().__init__()
        # 第一层密集连接：输入维度lay_dim*1，输出维度lay_dim*1，激活函数Hardswish
        self.dense1 = nn.Sequential(
            nn.Linear(lay_dim * 1, lay_dim * 1), nn.Hardswish())
        # 第二层密集连接：输入维度lay_dim*2，输出维度lay_dim*2，激活函数Hardswish
        self.dense2 = nn.Sequential(
            nn.Linear(lay_dim * 2, lay_dim * 2), nn.Hardswish())
        self.inp_dim = lay_dim  # 输入维度
        self.out_dim = lay_dim * 4  # 输出维度

    def forward(self, x1):  # x1.shape==(-1, lay_dim*1)
        """前向传播：通过密集连接组合特征"""
        x2 = th.cat((x1, self.dense1(x1)), dim=1)  # 拼接输入和第一层输出
        return th.cat(
            (x2, self.dense2(x2)), dim=1
        )  # 拼接x2和第二层输出，得到最终特征


class ConvNet(nn.Module):  # 像素级状态编码器
    """卷积网络（ConvNet），用于处理像素级状态（如图像）"""

    def __init__(self, inp_dim, out_dim, image_size=224):
        super().__init__()
        if image_size == 224:  # 输入图像大小为224x224
            self.net = nn.Sequential(  # 网络结构：卷积层+激活函数+全连接层
                nn.Conv2d(inp_dim, 32, (5, 5), stride=(
                    2, 2), bias=False),  # 卷积层1
                nn.ReLU(inplace=True),  # 激活函数，输出大小110x110
                nn.Conv2d(32, 48, (3, 3), stride=(2, 2)),  # 卷积层2
                nn.ReLU(inplace=True),  # 激活函数，输出大小54x54
                nn.Conv2d(48, 64, (3, 3), stride=(2, 2)),  # 卷积层3
                nn.ReLU(inplace=True),  # 激活函数，输出大小26x26
                nn.Conv2d(64, 96, (3, 3), stride=(2, 2)),  # 卷积层4
                nn.ReLU(inplace=True),  # 激活函数，输出大小12x12
                nn.Conv2d(96, 128, (3, 3), stride=(2, 2)),  # 卷积层5
                nn.ReLU(inplace=True),  # 激活函数，输出大小5x5
                nn.Conv2d(128, 192, (5, 5), stride=(1, 1)),  # 卷积层6
                nn.ReLU(inplace=True),  # 激活函数，输出大小1x1
                NnReshape(-1),  # 展平为一维张量（batch_size, 192）
                nn.Linear(192, out_dim),  # 全连接层，输出指定维度
            )
        elif image_size == 112:  # 输入图像大小为112x112
            self.net = nn.Sequential(  # 网络结构：卷积层+激活函数+全连接层
                nn.Conv2d(inp_dim, 32, (5, 5), stride=(
                    2, 2), bias=False),  # 卷积层1
                nn.ReLU(inplace=True),  # 激活函数，输出大小54x54
                nn.Conv2d(32, 48, (3, 3), stride=(2, 2)),  # 卷积层2
                nn.ReLU(inplace=True),  # 激活函数，输出大小26x26
                nn.Conv2d(48, 64, (3, 3), stride=(2, 2)),  # 卷积层3
                nn.ReLU(inplace=True),  # 激活函数，输出大小12x12
                nn.Conv2d(64, 96, (3, 3), stride=(2, 2)),  # 卷积层4
                nn.ReLU(inplace=True),  # 激活函数，输出大小5x5
                nn.Conv2d(96, 128, (5, 5), stride=(1, 1)),  # 卷积层5
                nn.ReLU(inplace=True),  # 激活函数，输出大小1x1
                NnReshape(-1),  # 展平为一维张量（batch_size, 128）
                nn.Linear(128, out_dim),  # 全连接层，输出指定维度
            )
        else:
            assert image_size in {224, 112}  # 仅支持224和112两种图像大小

    def forward(self, x):
        """前向传播：处理输入图像，输出特征向量"""
        # 调整通道维度位置（HWC -> CHW）
        x = x.permute(0, 3, 1, 2)
        x = x / 128.0 - 1.0  # 归一化到[-1, 1]范围
        return self.net(x)  # 通过网络计算输出

    @staticmethod
    def check():
        """检查ConvNet的正确性（测试用）"""
        inp_dim = 3  # 输入通道数（如RGB图像）
        out_dim = 32  # 输出特征维度
        batch_size = 2  # 批次大小
        image_size = [224, 112][1]  # 选择图像大小（测试用112）
        net = ConvNet(inp_dim, out_dim, image_size)  # 创建网络实例

        # 创建测试输入（随机图像）
        image = th.ones((batch_size, image_size, image_size,
                        inp_dim), dtype=th.uint8) * 255
        print(image.shape)  # 打印输入形状
        output = net(image)  # 前向传播
        print(output.shape)  # 打印输出形状（应符合预期）
