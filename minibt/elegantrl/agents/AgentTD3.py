import numpy as np
import torch as th
from copy import deepcopy
from typing import Tuple, List

from .AgentBase import AgentBase
from .AgentBase import ActorBase, CriticBase
from .AgentBase import build_mlp, layer_init_with_orthogonal
from ..train import Config
from ..train import ReplayBuffer

TEN = th.Tensor


class AgentTD3(AgentBase):
    """Twin Delayed DDPG algorithm.
    Addressing Function Approximation Error in Actor-Critic Methods. 2018.
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        # self.update_freq = getattr(args, 'update_freq', 2)  # standard deviation of exploration noise
        # self.num_ensembles = getattr(args, 'num_ensembles', 8)  # the number of critic networks
        # self.policy_noise_std = getattr(args, 'policy_noise_std', 0.10)  # standard deviation of exploration noise
        # self.explore_noise_std = getattr(args, 'explore_noise_std', 0.05)  # standard deviation of exploration noise

        # self.act = Actor(net_dims, state_dim, action_dim).to(self.device)
        # self.cri = CriticTwin(net_dims, state_dim, action_dim, num_ensembles=self.num_ensembles).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.cri_target = deepcopy(self.cri)
        # self.act_optimizer = th.optim.Adam(self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(self.cri.parameters(), self.learning_rate)
        # TD3特有参数
        self.update_freq = getattr(args, 'update_freq', 2)  # Actor延迟更新频率
        self.num_ensembles = getattr(args, 'num_ensembles', 8)  # 评论家集成数量
        self.policy_noise_std = getattr(
            args, 'policy_noise_std', 0.10)  # 策略噪声标准差
        self.policy_noise_clip = getattr(
            args, 'policy_noise_clip', 0.5)  # 目标策略噪声裁剪范围 ,新增
        self.explore_noise_std = getattr(
            args, 'explore_noise_std', 0.05)  # 探索噪声标准差

        # 调用组件初始化核心逻辑
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """初始化TD3组件：网络、优化器、目标网络、调度器及SWA"""
        # 1. 参数合法性验证
        self._validate_td3_args(net_dims, state_dim, action_dim)

        # 2. 构建网络（Actor + 双评论家Critic）
        self.act = self._build_actor(
            net_dims, state_dim, action_dim, args).to(self.device)
        self.cri = self._build_critic(
            net_dims, state_dim, action_dim, args).to(self.device)

        # 3. 目标网络（TD3中Actor和Critic均需目标网络）
        self.act_target = deepcopy(self.act)
        self.cri_target = deepcopy(self.cri)
        # 新增
        for param in self.act_target.parameters():
            param.requires_grad = False
        for param in self.cri_target.parameters():
            param.requires_grad = False

        # 4. 损失函数（默认MSE，支持Huber等）
        self.criterion = args.Loss() if args.Loss is not None else th.nn.MSELoss(reduction="none")

        # 5. 优化器（Actor和Critic分离优化）
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self._create_optimizer(
            self.cri.parameters(), args)

        # 6. 学习率调度器（可选）
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = args.LrScheduler(self.cri_optimizer)

        # 7. SWA组件（适配双网络结构）
        self._setup_swa_components(args)

    def _build_actor(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """构建TD3的Actor网络（确定性策略）"""
        return Actor(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        )

    def _build_critic(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """构建TD3的双评论家网络（CriticTwin）"""
        return CriticTwin(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            num_ensembles=self.num_ensembles,
            args=args
        )

    # def _create_optimizer(self, params, args: Config) -> th.optim.Optimizer:
    #     """创建优化器（支持SWA包装）"""
    #     if args.Optim.func.__name__ == "SWA":
    #         lr = args.Optim.keywords.pop("lr", self.learning_rate)
    #         base_optim = th.optim.SGD(params, lr=lr)
    #         return args.Optim(base_optim)
    #     else:
    #         lr = args.Optim.keywords.pop("lr", self.learning_rate)
    #         return args.Optim(params, lr=lr)

    # def _setup_swa_components(self, args: Config):
    #     """初始化SWA组件（Actor和Critic分别维护）"""
    #     self.if_swa = args.SWALR is not None
    #     if self.if_swa:
    #         from torch.optim.swa_utils import AveragedModel, SWALR
    #         self.swa_model_act = AveragedModel(self.act)
    #         self.swa_model_cri = AveragedModel(self.cri)
    #         self.swa_scheduler_act = args.SWALR(self.act_optimizer)
    #         self.swa_scheduler_cri = args.SWALR(self.cri_optimizer)
    #     # 检查SWA与SGD切换支持
    #     self.if_swap_swa_sgd = (hasattr(self.act_optimizer, "swap_swa_sgd")
    #                             and hasattr(self.cri_optimizer, "swap_swa_sgd")
    #                             and self.if_swa)

    def _validate_td3_args(self, net_dims: List[int], state_dim: int, action_dim: int):
        """验证TD3参数合法性"""
        """验证TD3关键参数的合法性"""
        if len(self.net_dims) < 1:
            raise ValueError(f"TD3网络至少需要1个隐藏层，当前net_dims={self.net_dims}")
        if self.state_dim <= 0 or self.action_dim <= 0:
            raise ValueError(
                f"状态维度（{self.state_dim}）和动作维度（{self.action_dim}）必须为正数")
        if self.num_ensembles < 2:
            raise ValueError(
                f"TD3至少需要2个评论家网络（当前num_ensembles={self.num_ensembles}）")
        if self.update_freq < 1:
            raise ValueError(
                f"Actor更新频率必须为正数（当前update_freq={self.update_freq}）")
        if self.policy_noise_std < 0 or self.explore_noise_std < 0:
            raise ValueError("噪声标准差不能为负数")

    # 新增
    def explore_action(self, state: TEN) -> TEN:
        """生成带探索噪声的动作（用于与环境交互）"""
        with th.no_grad():
            action = self.act.get_action(
                state, action_std=self.explore_noise_std)
        return action

    def update_objectives(self, buffer: ReplayBuffer, update_t: int) -> Tuple[float, float]:
        assert isinstance(update_t, int)
        with th.no_grad():
            if self.if_use_per:
                (state, action, reward, undone, unmask, next_state,
                 is_weight, is_index) = buffer.sample_for_per(self.batch_size)
            else:
                state, action, reward, undone, unmask, next_state = buffer.sample(
                    self.batch_size)
                is_weight, is_index = None, None

            # next_action = self.act.get_action(
            #     next_state, action_std=self.policy_noise_std)  # deterministic policy
            # 新增
            # 目标动作添加噪声并裁剪（TD3核心改进1：目标策略平滑）
            next_action = self.act_target.get_action(
                next_state, action_std=self.policy_noise_std)
            next_action = th.clamp(
                next_action,
                -1.0 + 1e-6,  # 避免数值饱和
                1.0 - 1e-6
            )
            # 计算目标Q值（取最小Q值，TD3核心改进2：双评论家抑制过估计）
            next_q = self.cri_target.get_q_values(
                next_state, next_action).min(dim=1)[0]

            q_label = reward + undone * self.gamma * next_q

        # 更新Critic（每步更新）
        q_values = self.cri.get_q_values(state, action)
        q_labels = q_label.view((-1, 1)).repeat(1, q_values.shape[1])
        td_error = self.criterion(q_values, q_labels).mean(dim=1) * unmask
        # 计算Critic损失（支持PER权重）
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()
        # 累积奖励拟合（可选正则项）
        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean().repeat(q_values.shape[1])
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean(dim=0)).mean() * self.lambda_fit_cum_r
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)
        # 更新Actor（延迟更新，TD3核心改进3：双时标更新），新增
        obj_actor = th.tensor(float('nan'), device=self.device)

        if update_t % self.update_freq == 0:  # delay update
            action_pg = self.act(state)  # action to policy gradient
            obj_actor = self.cri(state, action_pg).mean()  # 用当前Critic评估
            self.optimizer_backward(self.act_optimizer, -obj_actor)  # 最大化Q值
            self.soft_update(self.act_target, self.act, self.soft_update_tau)
        else:
            obj_actor = th.tensor(th.nan)
        return obj_critic.item(), obj_actor.item()


class AgentDDPG(AgentBase):
    """DDPG(Deep Deterministic Policy Gradient)
    Continuous control with deep reinforcement learning. 2015.
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims=net_dims, state_dim=state_dim,
                         action_dim=action_dim, gpu_id=gpu_id, args=args)
        # self.explore_noise_std = getattr(args, 'explore_noise', 0.05)  # set for `self.get_policy_action()`

        # self.act = Actor(net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.cri = Critic(net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.cri_target = deepcopy(self.cri)
        # self.act_optimizer = th.optim.Adam(self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(self.cri.parameters(), self.learning_rate)
        #################################################################
        # DDPG特有参数
        self.explore_noise_std = getattr(args, 'explore_noise', 0.05)  # 探索噪声
        self.ou_noise = OrnsteinUhlenbeckNoise(size=action_dim) if getattr(
            args, "use_ou_noise", False) else None
        # 新增
        self.use_ou_noise = getattr(args, "use_ou_noise", False)  # 是否使用OU过程噪声
        self.ou_noise = OrnsteinUhlenbeckNoise(
            size=action_dim,
            theta=getattr(args, "ou_theta", 0.15),
            sigma=getattr(args, "ou_sigma", 0.3)
        ) if self.use_ou_noise else None

        # 调用组件初始化核心逻辑
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """初始化DDPG组件：网络、优化器、目标网络、调度器及SWA"""
        # 1. 参数合法性验证
        self._validate_ddpg_args(net_dims, state_dim, action_dim)

        # 2. 构建网络（Actor + 单评论家Critic）
        self.act = self._build_actor(
            net_dims, state_dim, action_dim, args).to(self.device)
        self.cri = self._build_critic(
            net_dims, state_dim, action_dim, args).to(self.device)

        # 3. 目标网络（DDPG中Actor和Critic均需目标网络）
        self.act_target = deepcopy(self.act)
        self.cri_target = deepcopy(self.cri)
        for param in self.act_target.parameters():
            param.requires_grad = False
        for param in self.cri_target.parameters():
            param.requires_grad = False

        # 4. 损失函数
        self.criterion = args.Loss() if args.Loss is not None else th.nn.MSELoss(reduction="none")

        # 5. 优化器
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self._create_optimizer(
            self.cri.parameters(), args)

        # 6. 学习率调度器
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = args.LrScheduler(self.cri_optimizer)

        # 7. SWA组件
        self._setup_swa_components(args)

    def _build_actor(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """构建DDPG的Actor网络"""
        return Actor(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        )

    def _build_critic(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """构建DDPG的单评论家网络"""
        return Critic(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        )

    # def _create_optimizer(self, params, args: Config) -> th.optim.Optimizer:
    #     """复用TD3的优化器创建逻辑"""
    #     if args.Optim.func.__name__ == "SWA":
    #         lr = args.Optim.keywords.pop("lr", self.learning_rate)
    #         base_optim = th.optim.SGD(params, lr=lr)
    #         return args.Optim(base_optim)
    #     else:
    #         lr = args.Optim.keywords.pop("lr", self.learning_rate)
    #         return args.Optim(params, lr=lr)

    # def _setup_swa_components(self, args: Config):
    #     """复用TD3的SWA初始化逻辑"""
    #     self.if_swa = args.SWALR is not None
    #     if self.if_swa:
    #         from torch.optim.swa_utils import AveragedModel, SWALR
    #         self.swa_model_act = AveragedModel(self.act)
    #         self.swa_model_cri = AveragedModel(self.cri)
    #         self.swa_scheduler_act = args.SWALR(self.act_optimizer)
    #         self.swa_scheduler_cri = args.SWALR(self.cri_optimizer)
    #     self.if_swap_swa_sgd = (hasattr(self.act_optimizer, "swap_swa_sgd")
    #                             and hasattr(self.cri_optimizer, "swap_swa_sgd")
    #                             and self.if_swa)

    def _validate_ddpg_args(self, net_dims, state_dim, action_dim):
        """验证DDPG参数合法性"""
        if len(net_dims) < 1:
            raise ValueError(f"DDPG网络至少需要1个隐藏层，当前net_dims={net_dims}")
        if state_dim <= 0 or action_dim <= 0:
            raise ValueError(
                f"状态维度（{state_dim}）和动作维度（{action_dim}）必须为正数")
        if self.explore_noise_std < 0:
            raise ValueError(f"探索噪声标准差不能为负数（当前{self.explore_noise_std}）")

    # 新增
    def explore_action(self, state: TEN) -> TEN:
        """生成探索动作（支持高斯噪声或OU过程噪声）"""
        with th.no_grad():
            action_deterministic = self.act(state)  # 确定性动作

            # 添加探索噪声
            if self.use_ou_noise and self.ou_noise is not None:
                # OU过程噪声（适用于惯性系统）
                noise = self.ou_noise()
                noise = th.tensor(noise, dtype=th.float32, device=self.device)
            else:
                # 高斯噪声（通用场景）
                noise = th.randn_like(
                    action_deterministic) * self.explore_noise_std

            action = action_deterministic + noise
            return action.clamp(-1.0, 1.0)  # 确保动作在合法范围

    def update_objectives(self, buffer: ReplayBuffer, update_t: int) -> Tuple[float, float]:
        """更新DDPG目标函数（Critic和Actor同步更新）"""
        with th.no_grad():
            if self.if_use_per:
                (state, action, reward, undone, unmask, next_state,
                 is_weight, is_index) = buffer.sample_for_per(self.batch_size)
            else:
                state, action, reward, undone, unmask, next_state = buffer.sample(
                    self.batch_size)
                is_weight, is_index = None, None

            # 目标动作（无噪声，DDPG与TD3的核心区别）
            next_action = self.act_target(next_state)
            next_q = self.cri_target(next_state, next_action).squeeze(1)
            q_label = reward + undone * self.gamma * next_q

        # 更新Critic
        q_values = self.cri(state, action)
        td_error = self.criterion(
            q_values, q_label.view(-1, 1)).squeeze(1) * unmask

        if self.if_use_per and is_weight is not None:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()

        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean()
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean()) * self.lambda_fit_cum_r

        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 更新Actor（每步更新，与TD3的延迟更新不同）
        action_pg = self.act(state)
        obj_actor = self.cri(state, action_pg).mean()
        self.optimizer_backward(self.act_optimizer, -obj_actor)
        self.soft_update(self.act_target, self.act, self.soft_update_tau)

        return obj_critic.item(), obj_actor.item()


class OrnsteinUhlenbeckNoise:
    def __init__(self, size: int, theta=0.15, sigma=0.3, ou_noise=0.0, dt=1e-2):
        """
        The noise of Ornstein-Uhlenbeck Process

        Source: https://github.com/slowbull/DDPG/blob/master/src/explorationnoise.py
        It makes Zero-mean Gaussian Noise more stable.
        It helps agent explore better in an inertial system.
        Don't abuse OU Process. OU process has too many hyperparameters and over fine-tuning make no sense.

        int size: the size of noise, shape = (-1, action_dim)
        float theta: related to the not independent of OU-noise
        float sigma: related to action noise std
        float ou_noise: initialize OU-noise
        float dt: derivative
        """
        self.theta = theta
        self.sigma = sigma
        self.ou_noise = ou_noise
        self.dt = dt
        self.size = size

    def __call__(self) -> float:
        """
        output a OU-noise

        return array ou_noise: a noise generated by Ornstein-Uhlenbeck Process
        """
        noise = self.sigma * np.sqrt(self.dt) * \
            np.random.normal(size=self.size)
        self.ou_noise -= self.theta * self.ou_noise * self.dt + noise
        return self.ou_noise


'''network'''


class Actor(ActorBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        self.net = build_mlp(
            dims=[state_dim, *net_dims, action_dim], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.1)

    def get_action(self, state: TEN, action_std: float) -> TEN:  # for exploration
        action_avg = self.net(state).tanh()
        dist = self.ActionDist(action_avg, action_std)
        action = dist.sample()
        return action.clip(-1.0, 1.0)


class Critic(CriticBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        self.net = build_mlp(
            dims=[state_dim + action_dim, *net_dims, 1], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.5)


class CriticTwin(CriticBase):  # shared parameter
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, num_ensembles: int = 2, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        self.net = build_mlp(
            dims=[state_dim + action_dim, *net_dims, num_ensembles], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.5)
