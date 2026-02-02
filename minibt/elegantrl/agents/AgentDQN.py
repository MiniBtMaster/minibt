import torch as th
from torch import nn
from copy import deepcopy
from typing import Tuple, List
import numpy as np

from .AgentBase import AgentBase
from .AgentBase import build_mlp, layer_init_with_orthogonal
from ..train import Config
from ..train import ReplayBuffer

TEN = th.Tensor


class AgentDQN(AgentBase):
    """Deep Q-Network algorithm.
    “Human-Level Control Through Deep Reinforcement Learning”. 2015.
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims=net_dims, state_dim=state_dim,
                         action_dim=action_dim, gpu_id=gpu_id, args=args)

        # self.act = QNetwork(net_dims=net_dims, state_dim=state_dim,
        #                     action_dim=action_dim).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)

        # self.cri = self.act
        # self.cri_target = self.act_target
        # self.cri_optimizer = self.act_optimizer

        # # set for `self.act.get_action()`
        # self.explore_rate = getattr(args, "explore_rate", 0.25)
        # the probability of choosing action randomly in epsilon-greedy
        #############################################################################
        # 扩展配置参数
        self.epsilon_start = getattr(args, "epsilon_start", 0.9)
        self.epsilon_end = getattr(args, "epsilon_end", 0.05)
        self.epsilon_decay = getattr(args, "epsilon_decay", 1000)
        self.clip_q_value = getattr(args, "clip_q_value", None)  # 新增Q值裁剪配置
        self.explore_step = 0  # 探索步数计数器

        # 基础参数初始化（非组件类）
        self.explore_rate = getattr(args, "explore_rate", 0.25)  # ε-贪婪策略的探索率
        self.lambda_fit_cum_r = getattr(
            args, "lambda_fit_cum_r", 0.0)  # 累积奖励拟合系数

        # 调用组件初始化函数（核心逻辑）
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """初始化DQN特有的网络、优化器、目标网络、调度器及SWA组件"""
        # 1. 验证参数合法性
        self._validate_components_args(net_dims, state_dim, action_dim, args)

        # 2. 根据Agent类型选择对应的Q网络（核心：适配不同DQN变种）
        self.act = self._build_q_network(
            net_dims, state_dim, action_dim, args).to(self.device)
        self.act_target = deepcopy(self.act)  # 目标网络（DQN核心组件）

        # 3. 评论网络与行为网络共享（DQN特性：Q网络同时作为act和cri）
        self.cri = self.act
        self.cri_target = self.act_target

        # 4. 损失函数（默认MSE，支持通过Config配置）
        self.criterion = args.Loss() if args.Loss is not None else nn.MSELoss(reduction="none")

        # 5. 优化器（act和cri共享优化器，DQN通常无需分开）
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self.act_optimizer  # 共享优化器

        # 6. 学习率调度器（可选）
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = self.act_scheduler  # 共享调度器

        # 7. SWA组件（随机权重平均，可选）
        self._setup_swa_components(args)

    def _build_q_network(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """根据当前Agent类型（基础DQN/双DQN/决斗DQN等）构建对应的Q网络"""
        # 判断当前Agent类型，选择对应的Q网络
        if isinstance(self, AgentDoubleDQN):
            # 双DQN：使用孪生Q网络
            return QNetTwin(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )
        elif isinstance(self, AgentDuelingDQN):
            # 决斗DQN：使用带优势值的Q网络
            return QNetDuel(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )
        elif isinstance(self, AgentD3QN):
            # D3QN（双决斗DQN）：孪生+决斗Q网络
            return QNetTwinDuel(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )
        else:
            # 基础DQN：标准Q网络
            return QNetwork(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )

    def _update_scheduler(self):
        """更新学习率调度器"""
        if self.if_lr_scheduler:
            self.act_scheduler.step()
            self.cri_scheduler.step()

    def _validate_components_args(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """验证输入参数合法性，提前规避错误"""
        if len(net_dims) < 1:
            raise ValueError(f"DQN网络至少需要1个隐藏层，当前net_dims={net_dims}")
        if state_dim <= 0 or action_dim <= 0:
            raise ValueError(f"状态维度（{state_dim}）和动作维度（{action_dim}）必须为正数")
        if args.Activation is None:
            raise ValueError("必须通过args.Activation指定激活函数（如nn.ReLU）")

    # def explore_action(self, state: TEN) -> TEN:
    #     return self.act.get_action(state, explore_rate=self.explore_rate)[:, 0]

    def explore_action(self, state: TEN) -> TEN:
        """优化探索策略：实现ε线性衰减"""
        self.explore_step += 1
        # 计算当前探索率（线性衰减）
        epsilon = self.epsilon_end + (self.epsilon_start - self.epsilon_end) * \
            np.exp(-1. * self.explore_step / self.epsilon_decay)
        return self.act.get_action(state, explore_rate=epsilon)[:, 0]

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

            next_q = self.cri_target.get_q_value(next_state).max(dim=1)[
                0]  # next q_values
            q_label = reward + undone * self.gamma * next_q

        # q_value = self.cri.get_q_value(
        #     state).squeeze(-1).gather(dim=1, index=action.long())
        # 关键修改：将action从1维扩展为2维（增加一个维度用于gather）
        q_value = self.cri.get_q_value(state).squeeze(-1).gather(
            dim=1,
            # 增加unsqueeze(1)，将形状从(batch_size,)变为(batch_size, 1)
            index=action.long().unsqueeze(1)
        )
        # 新增Q值裁剪，增强稳定性
        if self.clip_q_value is not None:
            q_value = q_value.clamp(*self.clip_q_value)
            q_label = q_label.clamp(*self.clip_q_value)

        td_error = self.criterion(q_value, q_label) * unmask
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()
        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean()
            obj_critic += self.criterion(cum_reward_mean,
                                         q_value.mean()) * self.lambda_fit_cum_r
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 学习率调度
        self._update_scheduler()

        obj_actor = q_value.detach().mean()
        return obj_critic.item(), obj_actor.item()

    def get_cumulative_rewards(self, rewards: TEN, undones: TEN) -> TEN:
        returns = th.empty_like(rewards)

        masks = undones * self.gamma
        horizon_len = rewards.shape[0]

        last_state = self.last_state
        next_value = self.act_target(last_state).argmax(
            dim=1).detach()  # actor is Q Network in DQN style
        for t in range(horizon_len - 1, -1, -1):
            returns[t] = next_value = rewards[t] + masks[t] * next_value
        return returns


class AgentDoubleDQN(AgentDQN):
    """
    Double Deep Q-Network algorithm. “Deep Reinforcement Learning with Double Q-learning”. 2015.
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 直接调用父类构造函数，由父类的initialize_components根据类型自动构建QNetTwin
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        ####################################################################
        # AgentBase.__init__(self, net_dims, state_dim,
        #                    action_dim, gpu_id=gpu_id, args=args)

        # self.act = QNetTwin(net_dims=net_dims, state_dim=state_dim,
        #                     action_dim=action_dim).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)

        # self.cri = self.act
        # self.cri_target = self.act_target
        # self.cri_optimizer = self.act_optimizer

        # # set for `self.act.get_action()`
        # self.explore_rate = getattr(args, "explore_rate", 0.25)
        # the probability of choosing action randomly in epsilon-greedy

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

            next_q = th.min(
                *self.cri_target.get_q1_q2(next_state)).max(dim=1)[0]
            q_label = reward + undone * self.gamma * next_q

        q_value1, q_value2 = [qs.gather(dim=1, index=action.unsqueeze(1).long()).squeeze(1)
                              for qs in self.cri.get_q1_q2(state)]
        # Q值裁剪
        if self.clip_q_value is not None:
            q_value1 = q_value1.clamp(*self.clip_q_value)
            q_value2 = q_value2.clamp(*self.clip_q_value)
            q_label = q_label.clamp(*self.clip_q_value)

        td_error = (self.criterion(q_value1, q_label) +
                    self.criterion(q_value2, q_label)) * unmask
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()

        # 新增双Q正则化项，减少两个Q网络差异
        obj_critic += 0.001 * th.mean((q_value1 - q_value2) ** 2)

        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean()
            obj_critic += (self.criterion(cum_reward_mean, q_value1.mean()) +
                           self.criterion(cum_reward_mean, q_value2.mean()))/2.
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 学习率调度
        self._update_scheduler()

        obj_actor = q_value1.detach().mean()
        return obj_critic.item(), obj_actor.item()


'''add dueling q network'''


class AgentDuelingDQN(AgentDQN):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 直接调用父类构造函数，由父类的initialize_components根据类型自动构建QNetTwin
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        ####################################################################
        # AgentBase.__init__(self, net_dims, state_dim,
        #                    action_dim, gpu_id=gpu_id, args=args)

        # self.act = QNetDuel(net_dims=net_dims, state_dim=state_dim,
        #                     action_dim=action_dim).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)

        # self.cri = self.act
        # self.cri_target = self.act_target
        # self.cri_optimizer = self.act_optimizer

        # # set for `self.act.get_action()`
        # self.explore_rate = getattr(args, "explore_rate", 0.25)
        # # the probability of choosing action randomly in epsilon-greedy


class AgentD3QN(AgentDoubleDQN):  # Dueling Double Deep Q Network. (D3QN)
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 直接调用父类构造函数，由父类的initialize_components根据类型自动构建QNetTwin
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        ####################################################################
        # AgentBase.__init__(self, net_dims, state_dim,
        #                    action_dim, gpu_id=gpu_id, args=args)

        # self.act = QNetTwinDuel(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)

        # self.cri = self.act
        # self.cri_target = self.act_target
        # self.cri_optimizer = self.act_optimizer

        # # set for `self.act.get_action()`
        # self.explore_rate = getattr(args, "explore_rate", 0.25)
        # # the probability of choosing action randomly in epsilon-greedy


'''network'''


class QNetBase(nn.Module):  # nn.Module is a standard PyTorch Network
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        # build_mlp(net_dims=[state_dim + action_dim, *net_dims, 1])
        self.net = None
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.use_noisy = False  # 支持噪声网络

    def forward(self, state):
        q_value = self.get_q_value(state)
        return q_value.argmax(dim=1)  # index of max Q values

    def get_q_value(self, state: TEN) -> TEN:
        q_value = self.net(state)
        return q_value

    # return the index List[int] of discrete action
    # def get_action(self, state: TEN, explore_rate: float):
    #     if explore_rate < th.rand(1):
    #         action = self.get_q_value(state).argmax(dim=1, keepdim=True)
    #     else:
    #         action = th.randint(self.action_dim, size=(state.shape[0], 1))
    #     return action

    def get_action(self, state: TEN, explore_rate: float):
        """优化探索逻辑，支持ε-贪婪和噪声网络"""
        if self.use_noisy:
            # 噪声网络模式：直接使用带噪声的Q值输出
            q_value = self.get_q_value(state)
            return q_value.argmax(dim=1, keepdim=True)
        else:
            # ε-贪婪模式
            if explore_rate < th.rand(1, device=state.device):
                action = self.get_q_value(state).argmax(dim=1, keepdim=True)
            else:
                action = th.randint(self.action_dim, size=(
                    state.shape[0], 1), device=state.device)
            return action

    def reset_noise(self):
        """重置噪声参数（噪声网络使用）"""
        if self.use_noisy:
            for module in self.modules():
                if hasattr(module, 'reset_noise'):
                    module.reset_noise()


class QNetwork(QNetBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # self.net = build_mlp(dims=[state_dim, *net_dims, action_dim])
        ####################################################################
        self.net = build_mlp(
            dims=[state_dim, *net_dims, action_dim], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.1)
        # 支持噪声网络
        self.use_noisy = getattr(args, "use_noisy", False)
        if self.use_noisy:
            self._replace_with_noisy_layers()

    def _replace_with_noisy_layers(self):
        """将最后一层替换为噪声层（NoisyNet）"""
        for i, module in enumerate(self.net):
            if isinstance(module, nn.Linear) and i == len(self.net) - 1:
                in_features = module.in_features
                out_features = module.out_features
                self.net[i] = NoisyLinear(in_features, out_features)


class QNetDuel(QNetBase):  # Dueling DQN
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # self.net_state = build_mlp(dims=[state_dim, *net_dims])
        # self.net_adv = build_mlp(dims=[net_dims[-1], 1])  # advantage value
        # self.net_val = build_mlp(dims=[net_dims[-1], action_dim])  # Q value
        ###################################################################
        self.net_state = build_mlp(dims=[state_dim, *net_dims], args=args)
        self.net_adv = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # advantage value
        self.net_val = build_mlp(
            dims=[net_dims[-1], 1], args=args)  # Q value

        layer_init_with_orthogonal(self.net_adv[-1], std=0.1)
        layer_init_with_orthogonal(self.net_val[-1], std=0.1)

        # 支持噪声网络
        self.use_noisy = getattr(args, "use_noisy", False)
        if self.use_noisy:
            self._replace_with_noisy_layers()

    def forward(self, state):
        s_enc = self.net_state(state)  # encoded state
        q_val = self.net_val(s_enc)  # q value
        q_adv = self.net_adv(s_enc)  # advantage value
        value = q_val - q_val.mean(dim=1, keepdim=True) + \
            q_adv  # dueling Q value
        return value.argmax(dim=1)  # index of max Q values

    # def get_q_value(self, state: TEN) -> TEN:
    #     s_enc = self.net_state(state)  # encoded state
    #     q_value = self.net_val(s_enc)
    #     return q_value

    def get_q_value(self, state: TEN) -> TEN:
        # s_enc = self.net(state)
        s_enc = self.net_state(state)  # 编码状态

        q_val = self.net_val(s_enc)  # 状态价值 V(s)
        q_adv = self.net_adv(s_enc)  # 优势价值 A(s,a)

        # 计算Q值：Q(s,a) = V(s) + (A(s,a) - mean(A(s,a)))
        return q_val + (q_adv - q_adv.mean(dim=1, keepdim=True))

    def _replace_with_noisy_layers(self):
        """将输出层替换为噪声层"""
        if self.net_adv[-1]:
            in_features = self.net_adv[-1].in_features
            out_features = self.net_adv[-1].out_features
            self.net_adv[-1] = NoisyLinear(in_features, out_features)

        if self.net_val[-1]:
            in_features = self.net_val[-1].in_features
            out_features = self.net_val[-1].out_features
            self.net_val[-1] = NoisyLinear(in_features, out_features)


class QNetTwin(QNetBase):  # Double DQN
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # self.net_state = build_mlp(dims=[state_dim, *net_dims])
        # self.net_val1 = build_mlp(dims=[net_dims[-1], action_dim])  # Q value 1
        # self.net_val2 = build_mlp(dims=[net_dims[-1], action_dim])  # Q value 2
        ########################################################
        self.net_state = build_mlp(dims=[state_dim, *net_dims], args=args)
        self.net_val1 = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # Q value 1
        self.net_val2 = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # Q value 2
        self.soft_max = nn.Softmax(dim=-1)

        layer_init_with_orthogonal(self.net_val1[-1], std=0.1)
        layer_init_with_orthogonal(self.net_val2[-1], std=0.1)

        # 支持噪声网络
        self.use_noisy = getattr(args, "use_noisy", False)
        if self.use_noisy:
            self._replace_with_noisy_layers()

    def get_q_value(self, state: TEN) -> TEN:
        s_enc = self.net_state(state)  # encoded state
        q_value = self.net_val1(s_enc)  # q value
        return q_value

    # def get_q1_q2(self, state):
    #     s_enc = self.net_state(state)  # encoded state
    #     q_val1 = self.net_val1(s_enc)  # q value 1
    #     q_val2 = self.net_val2(s_enc)  # q value 2
    #     return q_val1, q_val2  # two groups of Q values

    def get_q1_q2(self, state):
        # s_enc = self.net(state)
        s_enc = self.net_state(state)  # 编码状态
        q_val1 = self.net_val1(s_enc)  # Q网络1输出
        q_val2 = self.net_val2(s_enc)  # Q网络2输出
        return q_val1, q_val2

    def _replace_with_noisy_layers(self):
        """将输出层替换为噪声层"""
        if self.net_val1[-1]:
            in_features = self.net_val1[-1].in_features
            out_features = self.net_val1[-1].out_features
            self.net_val1[-1] = NoisyLinear(in_features, out_features)

        if self.net_val2[-1]:
            in_features = self.net_val2[-1].in_features
            out_features = self.net_val2[-1].out_features
            self.net_val2[-1] = NoisyLinear(in_features, out_features)


class QNetTwinDuel(QNetTwin):  # D3QN: Dueling Double DQN
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        QNetBase.__init__(self, state_dim=state_dim, action_dim=action_dim)
        # self.net_state = build_mlp(dims=[state_dim, *net_dims])
        # self.net_adv1 = build_mlp(dims=[net_dims[-1], 1])  # advantage value 1
        # self.net_val1 = build_mlp(dims=[net_dims[-1], action_dim])  # Q value 1
        # self.net_adv2 = build_mlp(dims=[net_dims[-1], 1])  # advantage value 2
        # self.net_val2 = build_mlp(dims=[net_dims[-1], action_dim])  # Q value 2
        #############################################################################
        self.net_state = build_mlp(dims=[state_dim, *net_dims], args=args)
        self.net_adv1 = build_mlp(
            dims=[net_dims[-1], 1], args=args)  # advantage value 1
        self.net_val1 = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # Q value 1
        self.net_adv2 = build_mlp(
            dims=[net_dims[-1], 1], args=args)  # advantage value 2
        self.net_val2 = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # Q value 2
        self.soft_max = nn.Softmax(dim=1)

        layer_init_with_orthogonal(self.net_adv1[-1], std=0.1)
        layer_init_with_orthogonal(self.net_val1[-1], std=0.1)
        layer_init_with_orthogonal(self.net_adv2[-1], std=0.1)
        layer_init_with_orthogonal(self.net_val2[-1], std=0.1)

        # 支持噪声网络
        self.use_noisy = getattr(args, "use_noisy", False)
        if self.use_noisy:
            self._replace_with_noisy_layers()

    # def get_q_value(self, state):
    #     s_enc = self.net_state(state)  # encoded state
    #     q_val = self.net_val1(s_enc)  # q value
    #     q_adv = self.net_adv1(s_enc)  # advantage value
    #     # one dueling Q value
    #     q_value = q_val - q_val.mean(dim=1, keepdim=True) + q_adv
    #     return q_value

    # def get_q1_q2(self, state):
    #     s_enc = self.net_state(state)  # encoded state

    #     q_val1 = self.net_val1(s_enc)  # q value 1
    #     q_adv1 = self.net_adv1(s_enc)  # advantage value 1
    #     q_duel1 = q_val1 - q_val1.mean(dim=1, keepdim=True) + q_adv1

    #     q_val2 = self.net_val2(s_enc)  # q value 2
    #     q_adv2 = self.net_adv2(s_enc)  # advantage value 2
    #     q_duel2 = q_val2 - q_val2.mean(dim=1, keepdim=True) + q_adv2
    #     return q_duel1, q_duel2  # two dueling Q values

    def get_q_value(self, state):
        # s_enc = self.feature_extractor(state)
        s_enc = self.net_state(state)  # 编码状态

        q_val1 = self.net_val1(s_enc)  # 状态价值1
        q_adv1 = self.net_adv1(s_enc)  # 优势价值1
        return q_val1 + (q_adv1 - q_adv1.mean(dim=1, keepdim=True))  # 决斗Q值1

    def get_q1_q2(self, state):
        # s_enc = self.net(state)
        s_enc = self.net_state(state)  # 编码状态

        # 计算第一个决斗Q值
        q_val1 = self.net_val1(s_enc)
        q_adv1 = self.net_adv1(s_enc)
        q_duel1 = q_val1 + (q_adv1 - q_adv1.mean(dim=1, keepdim=True))

        # 计算第二个决斗Q值
        q_val2 = self.net_val2(s_enc)
        q_adv2 = self.net_adv2(s_enc)
        q_duel2 = q_val2 + (q_adv2 - q_adv2.mean(dim=1, keepdim=True))

        return q_duel1, q_duel2

    def _replace_with_noisy_layers(self):
        """将输出层替换为噪声层"""
        # 替换第一个Q网络的层
        if self.net_adv1[-1]:
            self.net_adv1[-1] = NoisyLinear(self.net_adv1[-1].in_features,
                                            self.net_adv1[-1].out_features)
        if self.net_val1[-1]:
            self.net_val1[-1] = NoisyLinear(self.net_val1[-1].in_features,
                                            self.net_val1[-1].out_features)

        # 替换第二个Q网络的层
        if self.net_adv2[-1]:
            self.net_adv2[-1] = NoisyLinear(self.net_adv2[-1].in_features,
                                            self.net_adv2[-1].out_features)
        if self.net_val2[-1]:
            self.net_val2[-1] = NoisyLinear(self.net_val2[-1].in_features,
                                            self.net_val2[-1].out_features)


class NoisyLinear(nn.Module):
    """噪声线性层，用于NoisyNet实现，替代ε-贪婪探索"""

    def __init__(self, in_features: int, out_features: int, sigma_init: float = 0.017):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features

        # 权重和偏置
        self.weight_mu = nn.Parameter(th.Tensor(out_features, in_features))
        self.weight_sigma = nn.Parameter(th.Tensor(out_features, in_features))
        self.bias_mu = nn.Parameter(th.Tensor(out_features))
        self.bias_sigma = nn.Parameter(th.Tensor(out_features))

        # 噪声参数
        self.register_buffer(
            'weight_epsilon', th.Tensor(out_features, in_features))
        self.register_buffer('bias_epsilon', th.Tensor(out_features))

        # 初始化
        nn.init.kaiming_uniform_(self.weight_mu, a=np.sqrt(5))
        nn.init.constant_(self.weight_sigma, sigma_init)
        nn.init.zeros_(self.bias_mu)
        nn.init.constant_(self.bias_sigma, sigma_init)

        self.reset_noise()

    def reset_noise(self):
        """重置噪声"""
        with th.no_grad():
            epsilon_in = self._scale_noise(self.in_features)
            epsilon_out = self._scale_noise(self.out_features)
            self.weight_epsilon.copy_(epsilon_out.outer(epsilon_in))
            self.bias_epsilon.copy_(epsilon_out)

    def _scale_noise(self, size: int) -> TEN:
        """生成缩放的噪声"""
        x = th.randn(size)
        return x.sign().mul(x.abs().sqrt())

    def forward(self, input: TEN) -> TEN:
        """前向传播，添加噪声"""
        if self.training:
            return nn.functional.linear(
                input,
                self.weight_mu + self.weight_sigma * self.weight_epsilon,
                self.bias_mu + self.bias_sigma * self.bias_epsilon
            )
        else:
            # 测试时不添加噪声
            return nn.functional.linear(input, self.weight_mu, self.bias_mu)
