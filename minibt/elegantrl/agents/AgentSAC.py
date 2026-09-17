import math
import numpy as np
import torch as th
from torch import nn
from copy import deepcopy
from typing import Tuple, List

from .AgentBase import AgentBase
from .AgentBase import ActorBase, CriticBase
from .AgentBase import build_mlp, layer_init_with_orthogonal
from ..train import Config
from ..train import ReplayBuffer

TEN = th.Tensor


class AgentSAC(AgentBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        # self.num_ensembles = getattr(args, 'num_ensembles', 4)  # the number of critic networks

        # self.act = ActorSAC(net_dims, state_dim, action_dim).to(self.device)
        # self.cri = CriticEnsemble(net_dims, state_dim, action_dim, num_ensembles=self.num_ensembles).to(self.device)
        # # self.act_target = deepcopy(self.act)
        # self.cri_target = deepcopy(self.cri)
        # self.act_optimizer = th.optim.Adam(self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(self.cri.parameters(), self.learning_rate)

        # self.alpha_log = th.tensor((-1,), dtype=th.float32, requires_grad=True, device=self.device)  # trainable var
        # self.alpha_optim = th.optim.Adam((self.alpha_log,), lr=args.learning_rate)
        # self.target_entropy = np.log(action_dim)

        # 基础参数初始化
        self.num_ensembles = getattr(args, "num_ensembles", 4)  # 集成评论家网络数量
        self.target_entropy = getattr(
            args, "target_entropy", -np.log(action_dim))  # 目标熵
        # self.target_entropy = getattr(
        #     args, "target_entropy", np.log(action_dim))  # 目标熵
        self.alpha_log = None  # 温度参数（延迟初始化）

        # 调用组件初始化核心逻辑
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """初始化SAC特有的组件：Actor/Critic网络、优化器、温度参数、调度器及SWA"""
        # 1. 参数合法性验证
        self._validate_sac_args(net_dims, state_dim, action_dim, args)

        # 2. 构建Actor和Critic网络（根据SAC变种动态选择）
        self.act = self._build_actor_network(
            net_dims, state_dim, action_dim, args).to(self.device)
        self.cri = self._build_critic_network(
            net_dims, state_dim, action_dim, args).to(self.device)

        # 3. 目标网络（SAC中Critic需要目标网络，Actor可选）
        self.cri_target = deepcopy(self.cri)
        self.act_target = deepcopy(self.act) if isinstance(
            self, AgentModSAC) else self.act  # ModSAC需要Actor目标网络

        # 4. 损失函数（默认MSE，支持Huber等）
        self.criterion = args.Loss() if args.Loss is not None else nn.MSELoss(reduction="none")

        # 5. 优化器（Actor/Critic/温度参数分别优化）
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args)
        self.cri_optimizer = self._create_optimizer(
            self.cri.parameters(), args)
        self._init_alpha_optimizer(args)  # 初始化温度参数优化器

        # 6. 学习率调度器（可选）
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = args.LrScheduler(self.cri_optimizer)
            self.alpha_scheduler = args.LrScheduler(
                self.alpha_optim) if hasattr(self, "alpha_optim") else None

        # 7. SWA组件（适配双网络结构）
        self._setup_swa_components(args)

        # 确保目标网络参数不参与梯度计算
        for param in self.cri_target.parameters():
            param.requires_grad = False

    def _build_actor_network(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """根据SAC变种构建Actor网络"""
        if isinstance(self, AgentModSAC):
            # 改进版SAC使用固定结构的Actor
            return ActorFixSAC(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )
        else:
            # 基础SAC使用标准Actor
            return ActorSAC(
                net_dims=net_dims,
                state_dim=state_dim,
                action_dim=action_dim,
                args=args
            )

    def _build_critic_network(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """构建集成评论家网络（Critic Ensemble）"""
        return CriticEnsemble(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            num_ensembles=self.num_ensembles,
            args=args
        )

    def _init_alpha_optimizer(self, args: Config):
        """初始化温度参数（alpha）及对应的优化器"""
        self.alpha_log = th.tensor(
            (-1.0,),  # 初始值
            dtype=th.float32,
            requires_grad=True,
            device=self.device
        )
        # 温度参数优化器（单独优化，学习率与主优化器一致）
        self.alpha_optim = th.optim.Adam(
            (self.alpha_log,),
            lr=args.learning_rate
        )

    def _create_optimizer(self, params, args: Config) -> th.optim.Optimizer:
        """创建优化器（支持SWA包装）"""
        if args.Optim.func.__name__ == "SWA":
            lr = args.Optim.keywords.pop("lr", self.learning_rate)
            base_optim = th.optim.SGD(params, lr=lr)
            return args.Optim(base_optim)
        else:
            lr = args.Optim.keywords.pop("lr", self.learning_rate)
            return args.Optim(params, lr=lr)

    def _setup_swa_components(self, args: Config):
        """初始化SWA组件（适配Actor/Critic双网络）"""
        self.if_swa = args.SWALR is not None
        if self.if_swa:
            from torch.optim.swa_utils import AveragedModel, SWALR
            # SWA模型：Actor和Critic分别维护
            self.swa_model_act = AveragedModel(self.act)
            self.swa_model_cri = AveragedModel(self.cri)
            # SWA学习率调度器
            self.swa_scheduler_act = args.SWALR(self.act_optimizer)
            self.swa_scheduler_cri = args.SWALR(self.cri_optimizer)
        # 检查是否支持SWA与SGD切换（仅当优化器支持时）
        self.if_swap_swa_sgd = (hasattr(self.act_optimizer, "swap_swa_sgd")
                                and hasattr(self.cri_optimizer, "swap_swa_sgd")
                                and self.if_swa)

    def _validate_sac_args(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """验证SAC特有的参数合法性"""
        if len(net_dims) < 1:
            raise ValueError(f"SAC网络至少需要1个隐藏层，当前net_dims={net_dims}")
        if state_dim <= 0 or action_dim <= 0:
            raise ValueError(f"状态维度（{state_dim}）和动作维度（{action_dim}）必须为正数")
        if self.num_ensembles <= 0:
            raise ValueError(
                f"集成评论家数量（num_ensembles={self.num_ensembles}）必须为正数")
        if args.Activation is None:
            raise ValueError("必须通过args.Activation指定激活函数（如nn.ReLU）")

    def explore_action(self, state: TEN) -> TEN:
        return self.act.get_action(state)

    def _explore_one_action(self, state: TEN) -> TEN:
        return self.act.get_action(state.unsqueeze(0))[0]

    def _explore_vec_action(self, state: TEN) -> TEN:
        return self.act.get_action(state)

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

            next_action, next_logprob = self.act.get_action_logprob(
                next_state)  # stochastic policy
            next_q = th.min(self.cri_target.get_q_values(
                next_state, next_action), dim=1)[0]
            alpha = self.alpha_log.exp()
            q_label = reward + undone * self.gamma * \
                (next_q - next_logprob * alpha)

        '''objective of critic (loss function of critic)'''
        q_values = self.cri.get_q_values(state, action)
        q_labels = q_label.view((-1, 1)).repeat(1, q_values.shape[1])
        td_error = self.criterion(q_values, q_labels).mean(dim=1) * unmask
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()
        if self.lambda_fit_cum_r:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean().repeat(q_values.shape[1])
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean(dim=0)).mean() * self.lambda_fit_cum_r
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        '''objective of alpha (temperature parameter automatic adjustment)'''
        action_pg, logprob = self.act.get_action_logprob(
            state)  # policy gradient
        obj_alpha = (self.alpha_log *
                     (self.target_entropy - logprob).detach()).mean()
        self.optimizer_backward(self.alpha_optim, obj_alpha)

        # 限制alpha范围，增强稳定性
        with th.no_grad():
            self.alpha_log.clamp_(-16, 2)  # 使用in-place操作更高效

        '''objective of actor'''
        alpha = self.alpha_log.exp().detach()
        q_value_pg = self.cri_target(state, action_pg).mean()
        obj_actor = (q_value_pg - logprob * alpha).mean()
        self.optimizer_backward(self.act_optimizer, -obj_actor)  # 最大化目标，所以取负
        # self.soft_update(self.act_target, self.act, self.soft_update_tau)
        return obj_critic.item(), obj_actor.item()


# Modified SAC using reliable_lambda and Two Time-scale Update Rule
class AgentModSAC(AgentSAC):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 改进版SAC特有的参数（如目标熵、评论家tau）
        args.target_entropy = getattr(
            args, "target_entropy", -np.log(action_dim))
        self.critic_tau = getattr(args, "critic_tau", 0.995)
        self.critic_value = 1.0
        self.update_a = 0
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        ######################################################
        # AgentBase.__init__(self, net_dims, state_dim, action_dim, gpu_id, args)
        # # the number of critic networks
        # self.num_ensembles = getattr(args, 'num_ensembles', 8)

        # self.act = ActorFixSAC(net_dims, state_dim, action_dim).to(self.device)
        # self.cri = CriticEnsemble(
        #     net_dims, state_dim, action_dim, num_ensembles=self.num_ensembles).to(self.device)
        # self.act_target = deepcopy(self.act)
        # self.cri_target = deepcopy(self.cri)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(
        #     self.cri.parameters(), self.learning_rate)

        # self.alpha_log = th.tensor(
        #     (-1,), dtype=th.float32, requires_grad=True, device=self.device)  # trainable var
        # self.alpha_optim = th.optim.Adam(
        #     (self.alpha_log,), lr=args.learning_rate)
        # self.target_entropy = getattr(
        #     args, 'target_entropy', -np.log(action_dim))

        # # for reliable_lambda
        # self.critic_tau = getattr(args, 'critic_tau', 0.995)
        # self.critic_value = 1.0  # for reliable_lambda
        # self.update_a = 0  # the counter of update actor

    def _build_actor_network(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config) -> nn.Module:
        """改进版SAC使用固定结构的Actor"""
        return ActorFixSAC(
            net_dims=net_dims,
            state_dim=state_dim,
            action_dim=action_dim,
            args=args
        )

    def initialize_components(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config):
        """重写初始化方法，为改进版SAC添加Actor目标网络"""
        super().initialize_components(net_dims, state_dim, action_dim, args)
        # 改进版SAC需要Actor目标网络
        self.act_target = deepcopy(self.act).to(self.device)
        for param in self.act_target.parameters():
            param.requires_grad = False

    def update_objectives(self, buffer: ReplayBuffer, update_t: int) -> Tuple[float, float]:
        with th.no_grad():
            if self.if_use_per:
                (state, action, reward, undone, unmask, next_state,
                 is_weight, is_index) = buffer.sample_for_per(self.batch_size)
            else:
                state, action, reward, undone, unmask, next_state = buffer.sample(
                    self.batch_size)
                is_weight, is_index = None, None

            next_action, next_logprob = self.act.get_action_logprob(
                next_state)  # stochastic policy
            next_q = th.min(self.cri_target.get_q_values(
                next_state, next_action), dim=1)[0]
            alpha = self.alpha_log.exp()
            q_label = reward + undone * self.gamma * \
                (next_q - next_logprob * alpha)

        '''objective of critic (loss function of critic)'''
        q_values = self.cri.get_q_values(state, action)
        q_labels = q_label.view((-1, 1)).repeat(1, q_values.shape[1])
        td_error = self.criterion(q_values, q_labels).mean(dim=1) * unmask
        if self.if_use_per:
            obj_critic = (td_error * is_weight).mean()
            buffer.td_error_update_for_per(
                is_index.detach(), td_error.detach())
        else:
            obj_critic = td_error.mean()
        if self.lambda_fit_cum_r != 0:
            cum_reward_mean = buffer.cum_rewards[buffer.ids0, buffer.ids1].detach_(
            ).mean().repeat(q_values.shape[1])
            obj_critic += self.criterion(cum_reward_mean,
                                         q_values.mean(dim=0)).mean() * self.lambda_fit_cum_r
        self.optimizer_backward(self.cri_optimizer, obj_critic)
        self.soft_update(self.cri_target, self.cri, self.soft_update_tau)

        '''objective of alpha (temperature parameter automatic adjustment)'''
        action_pg, logprob = self.act.get_action_logprob(
            state)  # policy gradient
        obj_alpha = (self.alpha_log *
                     (self.target_entropy - logprob).detach()).mean()
        self.optimizer_backward(self.alpha_optim, obj_alpha)

        '''objective of actor'''

        with th.no_grad():
            self.alpha_log[:] = self.alpha_log.clamp(-16, 2)
        alpha = self.alpha_log.exp().detach()
        # for reliable_lambda
        reliable_lambda = math.exp(-self.critic_value ** 2)
        # reset update_a to 0 when update_t is 0
        self.update_a = 0 if update_t == 0 else self.update_a
        if (self.update_a / (update_t + 1)) < (1 / (2 - reliable_lambda)):  # auto Two-time update rule
            self.update_a += 1

            q_value_pg = self.cri_target(state, action_pg).mean()
            obj_actor = (q_value_pg - logprob * alpha).mean()
            self.optimizer_backward(self.act_optimizer, -obj_actor)
            self.soft_update(self.act_target, self.act, self.soft_update_tau)
        else:
            obj_actor = th.tensor(th.nan)
        return obj_critic.item(), obj_actor.item()


'''network'''


class ActorSAC(ActorBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # network of encoded state
        self.net_s = build_mlp(
            dims=[state_dim, *net_dims], output_activation=True, args=args)
        # the average and log_std of action
        self.net_a = build_mlp(dims=[net_dims[-1], action_dim * 2], args=args)
        layer_init_with_orthogonal(self.net_a[-1], std=0.1)

    def forward(self, state):
        """前向传播，返回确定性动作（用于评估）"""
        s_enc = self.net_s(state)  # encoded state
        a_avg = self.net_a(s_enc)[:, :self.action_dim]
        return a_avg.tanh()  # action

    def get_action(self, state):
        """生成带探索噪声的动作（用于与环境交互）"""
        s_enc = self.net_s(state)  # encoded state
        a_avg, a_std_log = self.net_a(s_enc).chunk(2, dim=1)
        a_std = a_std_log.clamp(-16, 2).exp()

        dist = self.ActionDist(a_avg, a_std)
        return dist.rsample().tanh()  # action (re-parameterize)

    def get_action_logprob(self, state):
        """生成动作并计算其对数概率（用于训练）"""
        s_enc = self.net_s(state)  # encoded state
        a_avg, a_std_log = self.net_a(s_enc).chunk(2, dim=1)
        a_std = a_std_log.clamp(-16, 2).exp()

        dist = self.ActionDist(a_avg, a_std)
        action = dist.rsample()

        action_tanh = action.tanh()
        logprob = dist.log_prob(a_avg)
        # fix logprob using the derivative of action.tanh()
        logprob -= (-action_tanh.pow(2) + 1.000001).log()
        return action_tanh, logprob.sum(1)
        # # 计算对数概率，并修正tanh的导数影响
        # logprob -= (-action_tanh.pow(2) + 1.000001).log().sum(1, keepdim=True)

        # return action_tanh, logprob.squeeze(1)


class ActorFixSAC(ActorBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        self.encoder_s = build_mlp(
            dims=[state_dim, *net_dims], args=args)  # encoder of state
        self.decoder_a_avg = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # decoder of action mean
        self.decoder_a_std = build_mlp(
            dims=[net_dims[-1], action_dim], args=args)  # decoder of action log_std
        self.soft_plus = nn.Softplus()

        layer_init_with_orthogonal(self.decoder_a_avg[-1], std=0.1)
        layer_init_with_orthogonal(self.decoder_a_std[-1], std=0.1)

    def forward(self, state: TEN) -> TEN:
        """前向传播，返回确定性动作"""
        state_tmp = self.encoder_s(state)  # temporary tensor of state
        return self.decoder_a_avg(state_tmp).tanh()  # action

    def get_action(self, state: TEN, **_kwargs) -> TEN:  # for exploration
        """生成带探索噪声的动作"""
        state_tmp = self.encoder_s(state)  # temporary tensor of state
        action_avg = self.decoder_a_avg(state_tmp)
        action_std = self.decoder_a_std(state_tmp).clamp(-20, 2).exp()

        noise = th.randn_like(action_avg, requires_grad=True)
        action = action_avg + action_std * noise
        return action.tanh()  # action (re-parameterize)

    def get_action_logprob(self, state: TEN) -> Tuple[TEN, TEN]:
        """生成动作并计算其对数概率"""
        state_tmp = self.encoder_s(state)  # temporary tensor of state
        action_log_std = self.decoder_a_std(state_tmp).clamp(-20, 2)
        action_std = action_log_std.exp()
        action_avg = self.decoder_a_avg(state_tmp)

        noise = th.randn_like(action_avg, requires_grad=True)
        action = action_avg + action_std * noise
        # 计算对数概率
        logprob = -action_log_std - \
            noise.pow(2) * 0.5 - np.log(np.sqrt(2 * np.pi))
        # 修正tanh的导数影响
        logprob -= (np.log(2.) - action - self.soft_plus(-2. * action)) * 2.
        # logprob = -action_log_std - \
        #     noise.pow(2) * 0.5 - np.log(np.sqrt(2 * np.pi))
        # # dist = self.Normal(action_avg, action_std)
        # # action = dist.sample()
        # # logprob = dist.log_prob(action)

        # '''fix logprob by adding the derivative of y=tanh(x)'''
        # logprob -= (np.log(2.) - action - self.soft_plus(-2. *
        #             action)) * 2.  # better than below
        # logprob -= (1.000001 - action.tanh().pow(2)).log()
        return action.tanh(), logprob.sum(1)


class CriticEnsemble(CriticBase):
    def __init__(self, net_dims: List[int], state_dim: int, action_dim: int, num_ensembles: int = 4, args: Config = None):
        super().__init__(state_dim=state_dim, action_dim=action_dim)
        # encoder of state and action
        self.encoder_sa = build_mlp(
            dims=[state_dim + action_dim, net_dims[0]], args=args)
        self.decoder_qs = nn.ModuleList()
        for net_i in range(num_ensembles):
            decoder_q = build_mlp(dims=[*net_dims, 1], args=args)
            layer_init_with_orthogonal(decoder_q[-1], std=0.5)

            self.decoder_qs.append(decoder_q)
            setattr(self, f"decoder_q{net_i:02}", decoder_q)

    def get_q_values(self, state: TEN, action: TEN) -> TEN:
        tensor_sa = self.encoder_sa(th.cat((state, action), dim=1))
        values = th.concat([decoder_q(tensor_sa)
                           for decoder_q in self.decoder_qs], dim=-1)
        return values  # Q values
