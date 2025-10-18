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


class AgentEmbedDQN(AgentBase):
    """Deep Q-Network algorithm. 
    “Human-Level Control Through Deep Reinforcement Learning”. 2015.

    DQN1 original:
    q_values = q_network(state)

    DQN2 modify by ElegantRL:
    q_values = q_critic(state, action)
    """

    def __init__(self, net_dims: [int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims=net_dims, state_dim=state_dim,
                         action_dim=action_dim, gpu_id=gpu_id, args=args)

        # self.act = QEmbedTwin(
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
        # 扩展探索策略参数（ε线性衰减）
        self.epsilon_start = getattr(args, "epsilon_start", 0.9)
        self.epsilon_end = getattr(args, "epsilon_end", 0.05)
        self.epsilon_decay = getattr(args, "epsilon_decay", 1000)
        self.explore_step = 0  # 探索步数计数器
        self.clip_q_value = getattr(args, "clip_q_value", None)  # Q值裁剪范围

        # 基础参数初始化
        self.explore_rate = getattr(args, "explore_rate", 0.25)
        self.lambda_fit_cum_r = getattr(args, "lambda_fit_cum_r", 0.0)
        self.num_ensembles = getattr(args, "num_ensembles", 8)  # 集成网络数量（默认8）

        # 调用组件初始化核心逻辑
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """初始化带动作嵌入的DQN组件：网络、优化器、目标网络、调度器及SWA"""
        # 1. 参数合法性验证
        self._validate_embed_dqn_args(net_dims, state_dim, action_dim, args)

        # 2. 构建带动作嵌入的Q网络（根据Agent类型动态选择）
        self.act = self._build_embed_q_network(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        ).to(self.device)
        self.act_target = deepcopy(self.act)  # 目标网络（DQN核心）

        # 3. 评论网络与行为网络共享（嵌入型DQN特性）
        self.cri = self.act
        self.cri_target = self.act_target

        # 4. 损失函数（支持Huber等自定义损失）
        self.criterion = args.Loss() if args.Loss is not None else nn.MSELoss(reduction="none")

        # 5. 优化器（act与cri共享，嵌入网络通常无需分离优化）
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self.act_optimizer  # 共享优化器

        # 6. 学习率调度器（可选）
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = self.act_scheduler  # 共享调度器

        # 7. SWA组件（随机权重平均，提升泛化性）
        self._setup_swa_components(args)

    def _build_embed_q_network(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """根据Agent类型构建对应的动作嵌入Q网络"""

        if isinstance(self, AgentEnsembleDQN):
            # 集成网络（多分支解码器）
            return QEmbedEnsemble(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                num_ensembles=self.num_ensembles,
                args=args
            )
        else:
            # 基础动作嵌入网络（孪生Q网络）
            return QEmbedTwin(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                num_ensembles=self.num_ensembles,
                args=args
            )

    def _validate_embed_dqn_args(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """验证嵌入型DQN的关键参数"""
        if len(net_dims) < 1:
            raise ValueError(f"嵌入DQN至少需要1个隐藏层，当前net_dims={net_dims}")
        if state_dim <= 0 or action_dim <= 0:
            raise ValueError(f"状态维度（{state_dim}）和动作维度（{action_dim}）必须为正数")
        if self.num_ensembles <= 0:
            raise ValueError(
                f"集成网络数量（num_ensembles={self.num_ensembles}）必须为正数")
        if args.Activation is None:
            raise ValueError("必须通过args.Activation指定激活函数（如nn.ReLU）")

    # def explore_action(self, state: TEN) -> TEN:
    #     return self.act.get_action(state, explore_rate=self.explore_rate)[:, 0]
    def explore_action(self, state: TEN) -> TEN:
        """优化探索策略：ε线性衰减（支持噪声网络）"""
        self.explore_step += 1
        # ε线性衰减计算
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

        q_values = self.cri.get_q_values(state, action_int=action.long())
        q_labels = q_label.view((-1, 1)).repeat(1, q_values.shape[1])
        # Q值裁剪（增强稳定性）
        if self.clip_q_value is not None:
            q_values = q_values.clamp(*self.clip_q_value)
            q_labels = q_labels.clamp(*self.clip_q_value)

        td_error = self.criterion(q_values, q_labels).mean(dim=1) * unmask
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()

        # 集成网络正则化（减少分支差异）
        if isinstance(self, AgentEnsembleDQN):
            q_var = q_values.var(dim=1).mean()  # 计算分支输出方差
            obj_critic += 0.01 * q_var  # 方差正则化

        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean().repeat(q_values.shape[1])
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean(dim=0)).mean() * self.lambda_fit_cum_r
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 学习率调度
        if self.if_lr_scheduler:
            self.act_scheduler.step()

        obj_actor = q_values.detach().mean()
        return obj_critic.item(), obj_actor.item()

    def get_cumulative_rewards(self, rewards: TEN, undones: TEN) -> TEN:
        returns = th.empty_like(rewards)

        masks = undones * self.gamma
        horizon_len = rewards.shape[0]

        last_state = self.last_state
        next_value = self.act_target.get_q_value(last_state).max(dim=1)[
            0].detach()  # next q_values
        for t in range(horizon_len - 1, -1, -1):
            returns[t] = next_value = rewards[t] + masks[t] * next_value
        return returns


class AgentEnsembleDQN(AgentEmbedDQN):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 集成网络默认数量为4（可通过args覆盖）
        args.num_ensembles = getattr(args, "num_ensembles", 4)
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        ###########################################################################
        # AgentBase.__init__(self, net_dims, state_dim,
        #                    action_dim, gpu_id=gpu_id, args=args)

        # self.act = QEmbedEnsemble(
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


class QEmbedBase(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        # build_mlp(net_dims=[state_dim + action_dim, *net_dims, 1])
        self.net = None

        self.embedding_dim = max(8, int(action_dim ** 0.5))
        self.action_emb = nn.Embedding(
            num_embeddings=action_dim, embedding_dim=self.embedding_dim)
        th.nn.init.orthogonal_(self.action_emb.weight, gain=0.5)

    def forward(self, state: TEN) -> TEN:
        # (batch, action_dim, num_ensembles)
        all_q_values = self.get_all_q_values(state=state)
        all_q_value = all_q_values.mean(dim=2)  # (batch, action_dim)
        return all_q_value.argmax(dim=1)  # index of max Q values

    def get_q_value(self, state: TEN) -> TEN:
        # (batch, action_dim, num_ensembles)
        all_q_values = self.get_all_q_values(state=state)
        all_q_value = all_q_values.mean(dim=2)  # (batch, action_dim)
        return all_q_value  # Q values

    def get_q_values(self, state: TEN, action_int: TEN) -> TEN:
        # Long: (batch, ) -> Float: (batch, embedding_dim)
        action = self.action_emb(action_int)
        # (batch, action_dim, state_dim+embedding)
        state_action = th.concat((state, action), dim=1)
        q_values = self.net(state_action)  # (batch, num_ensembles)
        return q_values

    # return the index List[int] of discrete action
    def get_action(self, state: TEN, explore_rate: float):
        if explore_rate < th.rand(1, device=state.device):
            action = self.get_q_value(state).argmax(dim=1, keepdim=True)
        else:
            action = th.randint(self.action_dim, size=(
                state.shape[0], 1), device=state.device)
        return action

    def get_all_q_values(self, state: TEN) -> TEN:
        batch_size = state.shape[0]
        device = state.device

        action_int = th.arange(
            self.action_dim, device=device)  # (action_dim, )
        all_action_int = action_int.unsqueeze(0).repeat(
            (batch_size, 1))  # (batch_size, action_dim)
        # (batch_size, action_dim, embedding_dim)
        all_action = self.action_emb(all_action_int)

        all_state = state.unsqueeze(1).repeat(
            (1, self.action_dim, 1))  # (batch, action_dim, state_dim)
        # (batch, action_dim, state_dim+embedding)
        all_state_action = th.concat((all_state, all_action), dim=2)
        # (batch, action_dim, num_ensembles)
        all_q_values = self.net(all_state_action)
        return all_q_values


class QEmbedTwin(QEmbedBase):  # shared parameter
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, num_ensembles: int = 8, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        self.net = build_mlp(
            dims=[state_dim + self.embedding_dim, *net_dims, num_ensembles], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.5)


class QEmbedEnsemble(QEmbedBase):  # ensemble networks
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, num_ensembles: int = 4, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # encoder of state and action
        self.encoder_sa = build_mlp(
            dims=[state_dim + self.embedding_dim, net_dims[0]], args=args)
        self.decoder_qs = nn.ModuleList()  # 用ModuleList管理，支持保存/加载
        for net_i in range(num_ensembles):
            decoder_q = build_mlp(dims=[*net_dims, 1], args=args)
            layer_init_with_orthogonal(decoder_q[-1], std=0.5)

            self.decoder_qs.append(decoder_q)
            setattr(self, f"decoder_q{net_i:02}", decoder_q)

    def get_q_values(self, state: TEN, action_int: TEN) -> TEN:
        # Long: (batch, ) -> Float: (batch, embedding_dim)
        action = self.action_emb(action_int)
        # (batch, action_dim, state_dim+embedding)
        state_action = th.concat((state, action), dim=1)

        tensor_sa = self.encoder_sa(state_action)
        q_values = th.concat([decoder_q(tensor_sa)
                             for decoder_q in self.decoder_qs], dim=-1)
        return q_values  # (batch, num_ensembles)

    def get_all_q_values(self, state: TEN) -> TEN:
        batch_size = state.shape[0]
        device = state.device

        action_int = th.arange(
            self.action_dim, device=device)  # (action_dim, )
        all_action_int = action_int.unsqueeze(0).repeat(
            (batch_size, 1))  # (batch_size, action_dim)
        # (batch_size, action_dim, embedding_dim)
        all_action = self.action_emb(all_action_int)

        all_state = state.unsqueeze(1).repeat(
            (1, self.action_dim, 1))  # (batch, action_dim, state_dim)
        # (batch, action_dim, state_dim+embedding)
        all_state_action = th.concat((all_state, all_action), dim=2)

        all_tensor_sa = self.encoder_sa(all_state_action)
        all_q_values = th.concat([decoder_q(all_tensor_sa)
                                 for decoder_q in self.decoder_qs], dim=-1)
        return all_q_values  # (batch, action_dim, num_ensembles)


"""
QR-DQN: Distributional Reinforcement Learning with Quantile Regression
IQN: Implicit Quantile Networks for Distributional Reinforcement Learning
"""
