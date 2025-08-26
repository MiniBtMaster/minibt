import torch as th
from torch import nn
from copy import deepcopy
from typing import Tuple, List, Optional
import numpy as np

from .AgentBase import AgentBase, TEN
from .AgentBase import build_mlp, layer_init_with_orthogonal, NoisyLinear
from ..train import Config, ReplayBuffer


class AgentEmbedDQN(AgentBase):
    """带动作嵌入的DQN算法（优化版）"""

    def __init__(self, net_dims: [int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims=net_dims, state_dim=state_dim,
                         action_dim=action_dim, gpu_id=gpu_id, args=args)

        # 扩展探索策略参数（ε线性衰减）
        self.epsilon_start = getattr(args, "epsilon_start", 0.9)
        self.epsilon_end = getattr(args, "epsilon_end", 0.05)
        self.epsilon_decay = getattr(args, "epsilon_decay", 1000)
        self.explore_step = 0  # 探索步数计数器

        # 基础参数初始化
        self.explore_rate = getattr(args, "explore_rate", 0.25)  # 兼容旧版参数
        self.lambda_fit_cum_r = getattr(args, "lambda_fit_cum_r", 0.0)
        self.num_ensembles = getattr(args, "num_ensembles", 8)  # 集成网络数量
        self.clip_q_value = getattr(args, "clip_q_value", None)  # Q值裁剪范围

        # 调用组件初始化核心逻辑
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """初始化带动作嵌入的DQN组件"""
        self._validate_embed_dqn_args(net_dims, state_dim, action_dim, args)

        # 构建带动作嵌入的Q网络（支持噪声网络）
        self.act = self._build_embed_q_network(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        ).to(self.device)
        self.act_target = deepcopy(self.act)

        # 评论网络与行为网络共享
        self.cri = self.act
        self.cri_target = self.act_target

        # 损失函数（支持Huber损失等）
        self.criterion = args.Loss() if args.Loss is not None else nn.MSELoss(reduction="none")

        # 优化器
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self.act_optimizer

        # 学习率调度器
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = self.act_scheduler

        # SWA组件
        self._setup_swa_components(args)

    def _build_embed_q_network(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """构建动作嵌入Q网络（支持噪声网络）"""
        if isinstance(self, AgentEnsembleDQN):
            return QEmbedEnsemble(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                num_ensembles=self.num_ensembles,
                use_noisy=getattr(args, "use_noisy", False),  # 新增噪声网络支持
                args=args
            )
        else:
            return QEmbedTwin(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                num_ensembles=self.num_ensembles,
                use_noisy=getattr(args, "use_noisy", False),  # 新增噪声网络支持
                args=args
            )

    def _update_scheduler(self):
        """更新学习率调度器"""
        if self.if_lr_scheduler:
            self.act_scheduler.step()
            self.cri_scheduler.step()

    def _validate_embed_dqn_args(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config):
        """增强参数验证"""
        super()._validate_components_args(net_dims, state_dim, action_dim, args)  # 复用基础验证
        if self.num_ensembles <= 0 or self.num_ensembles > 32:
            raise ValueError(f"集成数量需在1-32之间，当前{self.num_ensembles}")
        if self.clip_q_value is not None and len(self.clip_q_value) != 2:
            raise ValueError(f"clip_q_value需为二元组，当前{self.clip_q_value}")

    def explore_action(self, state: TEN) -> TEN:
        """优化探索策略：ε线性衰减（支持噪声网络）"""
        self.explore_step += 1
        # 噪声网络模式下无需ε-贪婪
        if self.act.use_noisy:
            self.act.reset_noise()  # 重置噪声
            return self.act.get_action(state, explore_rate=0.0)[:, 0]

        # ε线性衰减计算
        epsilon = self.epsilon_end + (self.epsilon_start - self.epsilon_end) * \
            np.exp(-1. * self.explore_step / self.epsilon_decay)
        return self.act.get_action(state, explore_rate=epsilon)[:, 0]

    def update_objectives(self, buffer: ReplayBuffer, update_t: int) -> Tuple[float, float]:
        assert isinstance(update_t, int)

        with th.no_grad():
            # 采样数据
            if self.if_use_per:
                (state, action, reward, undone, unmask, next_state,
                 is_weight, is_index) = buffer.sample_for_per(self.batch_size)
            else:
                state, action, reward, undone, unmask, next_state = buffer.sample(
                    self.batch_size)
                is_weight, is_index = None, None

            # 计算目标Q值
            next_q = self.cri_target.get_q_value(next_state).max(dim=1)[0]
            q_label = reward + undone * self.gamma * next_q

        # 获取当前Q值（多集成分支）
        q_values = self.cri.get_q_values(state, action_int=action.long())
        q_labels = q_label.view((-1, 1)).repeat(1, q_values.shape[1])

        # Q值裁剪（增强稳定性）
        if self.clip_q_value is not None:
            q_values = q_values.clamp(*self.clip_q_value)
            q_labels = q_labels.clamp(*self.clip_q_value)

        # 计算损失（支持PER权重）
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

        # 累积奖励拟合
        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean()
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean()) * self.lambda_fit_cum_r

        # 反向传播与目标网络更新
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        # 学习率调度
        if self.if_lr_scheduler:
            self._update_scheduler()

        obj_actor = q_values.detach().mean()
        return obj_critic.item(), obj_actor.item()

    def get_cumulative_rewards(self, rewards: TEN, undones: TEN) -> TEN:
        returns = th.empty_like(rewards)
        masks = undones * self.gamma
        horizon_len = rewards.shape[0]

        last_state = self.last_state
        next_value = self.act_target.get_q_value(
            last_state).max(dim=1)[0].detach()
        for t in range(horizon_len - 1, -1, -1):
            returns[t] = next_value = rewards[t] + masks[t] * next_value
        return returns


class AgentEnsembleDQN(AgentEmbedDQN):
    """集成动作嵌入DQN（优化版）"""

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        args.num_ensembles = getattr(args, "num_ensembles", 4)  # 集成数量默认4
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)


'''网络类优化'''


class QEmbedBase(nn.Module):
    """动作嵌入网络基类（优化版）"""

    def __init__(self, state_dim: int, action_dim: int, use_noisy: bool = False):
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.use_noisy = use_noisy  # 噪声网络开关

        # 动作嵌入层（支持噪声）
        self.embedding_dim = max(8, int(action_dim ** 0.5))  # 嵌入维度自适应
        self.action_emb = nn.Embedding(
            num_embeddings=action_dim, embedding_dim=self.embedding_dim
        )
        layer_init_with_orthogonal(self.action_emb.weight, gain=0.5)  # 优化初始化

    def forward(self, state: TEN) -> TEN:
        # (batch, action_dim, num_ensembles)
        all_q_values = self.get_all_q_values(state=state)
        all_q_value = all_q_values.mean(dim=2)  # 集成平均
        return all_q_value.argmax(dim=1)

    def get_q_value(self, state: TEN) -> TEN:
        all_q_values = self.get_all_q_values(state=state)
        return all_q_values.mean(dim=2)  # 集成平均Q值

    def get_q_values(self, state: TEN, action_int: TEN) -> TEN:
        action = self.action_emb(action_int)  # (batch, embedding_dim)
        state_action = th.concat((state, action), dim=1)  # 状态+动作嵌入
        return self.net(state_action)  # (batch, num_ensembles)

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

        # 生成所有可能动作的嵌入
        action_int = th.arange(
            self.action_dim, device=device)  # (action_dim, )
        all_action_int = action_int.unsqueeze(0).repeat(
            (batch_size, 1))  # (batch, action_dim)
        # (batch, action_dim, embedding_dim)
        all_action = self.action_emb(all_action_int)

        # 拼接状态与所有动作嵌入
        all_state = state.unsqueeze(1).repeat(
            (1, self.action_dim, 1))  # (batch, action_dim, state_dim)
        # (batch, action_dim, state_dim+embedding)
        all_state_action = th.concat((all_state, all_action), dim=2)

        return self.net(all_state_action)  # (batch, action_dim, num_ensembles)

    def reset_noise(self):
        """重置噪声层（噪声网络用）"""
        if self.use_noisy:
            for module in self.modules():
                if hasattr(module, 'reset_noise'):
                    module.reset_noise()


class QEmbedTwin(QEmbedBase):
    """孪生动作嵌入网络（优化版）"""

    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int,
                 num_ensembles: int = 8, use_noisy: bool = False, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim, use_noisy=use_noisy)
        # 构建共享网络（支持噪声层）
        self.net = build_mlp(
            dims=[state_dim + self.embedding_dim, *net_dims, num_ensembles],
            args=args
        )
        # 替换输出层为噪声层（若启用）
        if use_noisy and isinstance(self.net[-1], nn.Linear):
            in_feat = self.net[-1].in_features
            out_feat = self.net[-1].out_features
            self.net[-1] = NoisyLinear(in_feat, out_feat)
        else:
            layer_init_with_orthogonal(self.net[-1], std=0.5)


class QEmbedEnsemble(QEmbedBase):
    """集成动作嵌入网络（优化版）"""

    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int,
                 num_ensembles: int = 4, use_noisy: bool = False, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim, use_noisy=use_noisy)

        # 共享编码器
        self.encoder_sa = build_mlp(
            dims=[state_dim + self.embedding_dim, net_dims[0]],
            args=args
        )
        layer_init_with_orthogonal(self.encoder_sa[-1], std=0.5)

        # 多分支解码器（集成）
        self.decoder_qs = nn.ModuleList()  # 用ModuleList管理，支持保存/加载
        for _ in range(num_ensembles):
            decoder_q = build_mlp(dims=[*net_dims, 1], args=args)
            # 解码器输出层替换为噪声层（若启用）
            if use_noisy and isinstance(decoder_q[-1], nn.Linear):
                in_feat = decoder_q[-1].in_features
                out_feat = decoder_q[-1].out_features
                decoder_q[-1] = NoisyLinear(in_feat, out_feat)
            else:
                layer_init_with_orthogonal(decoder_q[-1], std=0.5)
            self.decoder_qs.append(decoder_q)

    def get_q_values(self, state: TEN, action_int: TEN) -> TEN:
        action = self.action_emb(action_int)
        state_action = th.concat((state, action), dim=1)
        tensor_sa = self.encoder_sa(state_action)  # 共享编码
        # 集成分支输出拼接
        q_values = th.concat([decoder_q(tensor_sa)
                             for decoder_q in self.decoder_qs], dim=-1)
        return q_values  # (batch, num_ensembles)

    def get_all_q_values(self, state: TEN) -> TEN:
        batch_size = state.shape[0]
        device = state.device

        # 生成所有动作嵌入
        action_int = th.arange(self.action_dim, device=device)
        all_action_int = action_int.unsqueeze(0).repeat((batch_size, 1))
        all_action = self.action_emb(all_action_int)

        # 拼接状态与所有动作
        all_state = state.unsqueeze(1).repeat((1, self.action_dim, 1))
        all_state_action = th.concat((all_state, all_action), dim=2)
        all_tensor_sa = self.encoder_sa(all_state_action)  # 共享编码

        # 集成分支输出
        all_q_values = th.concat([decoder_q(all_tensor_sa).unsqueeze(2)
                                 for decoder_q in self.decoder_qs], dim=2)
        return all_q_values  # (batch, action_dim, num_ensembles)
