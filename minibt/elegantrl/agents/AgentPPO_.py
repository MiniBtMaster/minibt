import torch.nn as nn
import numpy as np
import torch as th
from torch import nn

from .AgentBase import AgentBase
from .AgentBase import build_mlp, layer_init_with_orthogonal
from ..train import Config, get_kwargs
import torch.nn.functional as F
from torch.nn.utils import clip_grad_norm_

TEN = th.Tensor

# https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/


class AgentPPO(AgentBase):
    """PPO algorithm + GAE
    “Proximal Policy Optimization Algorithms”. John Schulman. et al.. 2017.
    “Generalized Advantage Estimation”. John Schulman. et al..
    """

    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        self.if_off_policy = False

        # self.act = ActorPPO(net_dims=net_dims, state_dim=state_dim,
        #                     action_dim=action_dim).to(self.device)
        # self.cri = CriticPPO(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.act_optimizer = th.optim.AdamW(
        #     self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.AdamW(
        #     self.cri.parameters(), self.learning_rate)

        # `ratio.clamp(1 - clip, 1 + clip)`
        self.ratio_clip = getattr(args, "ratio_clip", 0.2)
        # self.lambda_gae_adv = getattr(args, "lambda_gae_adv", 0.95)  # could be 0.80~0.99
        # self.lambda_entropy = getattr(args, "lambda_entropy", 0.001)  # could be 0.00~0.10
        self.lambda_gae_adv = getattr(
            args, "lambda_gae_adv", 0.95)  # could be 0.80~0.99
        self.lambda_entropy = getattr(
            args, "lambda_entropy", 0.01)  # could be 0.00~0.10
        self.lambda_entropy = th.tensor(
            self.lambda_entropy, dtype=th.float32, device=self.device)
        # self.entropy_decay = 0.999  # 熵系数衰减率（每步更新衰减1%）
        # 新增：可配置的熵衰减率（默认不衰减，如需衰减通过args设置）
        self.entropy_decay = getattr(args, "entropy_decay", 1.0)  # 1.0表示不衰减
        self.if_use_v_trace = getattr(
            args, 'if_use_v_trace', False)  # V-trace默认关闭（PPO通常用GAE）
        self.cri_clip_grad = getattr(args, "cri_clip_grad", 0.5)

        # self.if_use_v_trace = getattr(args, 'if_use_v_trace', True)

        # 在__init__中主动调用组件初始化方法，确保对象可用
        self.initialize_components(net_dims, state_dim, action_dim, args)

    def initialize_components(self, net_dims, state_dim, action_dim, args: Config):
        if "Muon" in args.Optim.func.__name__:
            self._ismuon = True
            args._ismuon = self._ismuon
        if args.if_discrete:
            self.act = ActorDiscretePPO(
                net_dims=net_dims, state_dim=state_dim, action_dim=action_dim, args=args).to(self.device)
        else:
            self.act = ActorPPO(net_dims=net_dims, state_dim=state_dim,
                                action_dim=action_dim, args=args).to(self.device)
        self.cri = CriticPPO(
            net_dims=net_dims, state_dim=state_dim, action_dim=action_dim, args=args).to(self.device)
        self.criterion = args.Loss()
        # 提取优化器创建逻辑为辅助函数
        self.act_optimizer = self._create_optimizer(
            self.act.parameters(), args, self.act)
        self.cri_optimizer = self._create_optimizer(
            self.cri.parameters(), args, self.cri)
        self.if_lr_scheduler = args.LrScheduler is not None
        if self.if_lr_scheduler:
            self.act_scheduler = args.LrScheduler(self.act_optimizer)
            self.cri_scheduler = args.LrScheduler(self.cri_optimizer)
        # 提取SWA组件创建逻辑
        self._setup_swa_components(args)

    def _explore_one_env(self, env, horizon_len: int, if_random: bool = False) -> tuple[TEN, TEN, TEN, TEN, TEN, TEN]:
        """
        Collect trajectories through the actor-environment interaction for a **single** environment instance.

        env: RL training environment. env.reset() env.step(). It should be a vector env.
        horizon_len: collect horizon_len step while exploring to update networks
        return: `(states, actions, logprobs, rewards, undones, unmasks)` for on-policy
            num_envs == 1
            `states.shape == (horizon_len, num_envs, state_dim)`
            `actions.shape == (horizon_len, num_envs, action_dim)`
            `logprobs.shape == (horizon_len, num_envs, action_dim)`
            `rewards.shape == (horizon_len, num_envs)`
            `undones.shape == (horizon_len, num_envs)`
            `unmasks.shape == (horizon_len, num_envs)`
        """
        states = th.zeros((horizon_len, self.state_dim),
                          dtype=th.float32).to(self.device)
        actions = th.zeros((horizon_len, self.action_dim), dtype=th.float32).to(self.device) \
            if not self.if_discrete else th.zeros(horizon_len, dtype=th.int32).to(self.device)
        logprobs = th.zeros(horizon_len, dtype=th.float32).to(self.device)
        rewards = th.zeros(horizon_len, dtype=th.float32).to(self.device)
        terminals = th.zeros(horizon_len, dtype=th.bool).to(self.device)
        truncates = th.zeros(horizon_len, dtype=th.bool).to(self.device)

        state = self.last_state  # shape == (1, state_dim) for a single env.
        convert = self.act.convert_action_for_env
        for t in range(horizon_len):
            action, logprob = [t[0] for t in self.explore_action(state)]
            # 正确代码
            # action, logprob = self.explore_action(state)  # 直接解包元组

            states[t] = state
            actions[t] = action
            logprobs[t] = logprob

            ary_action = convert(action).detach().cpu().numpy()
            ary_state, reward, terminal, truncate, _ = env.step(ary_action)
            if terminal or truncate:
                ary_state, info_dict = env.reset()
            state = th.as_tensor(ary_state, dtype=th.float32,
                                 device=self.device).unsqueeze(0)

            rewards[t] = reward
            terminals[t] = terminal
            truncates[t] = truncate

        # state.shape == (1, state_dim) for a single env.
        self.last_state = state
        '''add dim1=1 below for workers buffer_items concat'''
        states = states.view((horizon_len, 1, self.state_dim))
        actions = actions.view((horizon_len, 1, self.action_dim)) \
            if not self.if_discrete else actions.view((horizon_len, 1))
        logprobs = logprobs.view((horizon_len, 1))
        rewards = (rewards * self.reward_scale).view((horizon_len, 1))
        undones = th.logical_not(terminals).view((horizon_len, 1))
        unmasks = th.logical_not(truncates).view((horizon_len, 1))
        return states, actions, logprobs, rewards, undones, unmasks

    def _explore_vec_env(self, env, horizon_len: int, if_random: bool = False) -> tuple[TEN, TEN, TEN, TEN, TEN, TEN]:
        """
        Collect trajectories through the actor-environment interaction for a **vectorized** environment instance.

        env: RL training environment. env.reset() env.step(). It should be a vector env.
        horizon_len: collect horizon_len step while exploring to update networks
        return: `(states, actions, logprobs, rewards, undones, unmasks)` for on-policy
            `states.shape == (horizon_len, num_envs, state_dim)`
            `actions.shape == (horizon_len, num_envs, action_dim)`
            `logprobs.shape == (horizon_len, num_envs, action_dim)`
            `rewards.shape == (horizon_len, num_envs)`
            `undones.shape == (horizon_len, num_envs)`
            `unmasks.shape == (horizon_len, num_envs)`
        """
        states = th.zeros((horizon_len, self.num_envs,
                          self.state_dim), dtype=th.float32).to(self.device)
        actions = th.zeros((horizon_len, self.num_envs, self.action_dim), dtype=th.float32).to(self.device) \
            if not self.if_discrete else th.zeros((horizon_len, self.num_envs), dtype=th.int32).to(self.device)
        logprobs = th.zeros((horizon_len, self.num_envs),
                            dtype=th.float32).to(self.device)
        rewards = th.zeros((horizon_len, self.num_envs),
                           dtype=th.float32).to(self.device)
        terminals = th.zeros((horizon_len, self.num_envs),
                             dtype=th.bool).to(self.device)
        truncates = th.zeros((horizon_len, self.num_envs),
                             dtype=th.bool).to(self.device)

        # shape == (num_envs, state_dim) for a vectorized env.
        state = self.last_state

        convert = self.act.convert_action_for_env
        for t in range(horizon_len):
            action, logprob = self.explore_action(state)

            states[t] = state
            actions[t] = action
            logprobs[t] = logprob

            state, reward, terminal, truncate, _ = env.step(
                convert(action))  # next_state

            rewards[t] = reward
            terminals[t] = terminal
            truncates[t] = truncate

        self.last_state = state
        rewards *= self.reward_scale
        undones = th.logical_not(terminals)
        unmasks = th.logical_not(truncates)
        return states, actions, logprobs, rewards, undones, unmasks

    def explore_action(self, state: TEN) -> tuple[TEN, TEN]:
        actions, logprobs = self.act.get_action(state)
        return actions, logprobs

    def update_net(self, buffer) -> tuple[float, float, float]:
        buffer_size = buffer[0].shape[0]

        '''get advantages reward_sums'''
        with th.no_grad():
            states, actions, logprobs, rewards, undones, unmasks = buffer
            # set a smaller 'batch_size' to avoid CUDA OOM
            bs = max(1, 2 ** 10 // self.num_envs)
            values = [self.cri(states[i:i + bs])
                      for i in range(0, buffer_size, bs)]
            # values.shape == (buffer_size, )
            values = th.cat(values, dim=0).squeeze(-1)

            advantages = self.get_advantages(
                states, rewards, undones, unmasks, values)  # shape == (buffer_size, )
            # reward_sums.shape == (buffer_size, )
            reward_sums = advantages + values
            del rewards, undones, values

            # advantages = (advantages - advantages.mean()) / \
            #     (advantages[::4, ::4].std() + 1e-5)  # avoid CUDA OOM
            # 优化后：
            adv_mean = advantages.mean()
            adv_std = advantages.std() + 1e-8  # 避免除以0
            advantages = (advantages - adv_mean) / adv_std

            assert logprobs.shape == advantages.shape == reward_sums.shape == (
                buffer_size, states.shape[1])
        buffer = states, actions, unmasks, logprobs, advantages, reward_sums

        '''update network'''
        obj_entropies = []
        obj_critics = []
        obj_actors = []

        th.set_grad_enabled(True)
        update_times = int(buffer_size * self.repeat_times / self.batch_size)
        assert update_times >= 1
        for update_t in range(update_times):
            obj_critic, obj_actor, obj_entropy = self.update_objectives(
                buffer, update_t)
            obj_entropies.append(obj_entropy)
            obj_critics.append(obj_critic)
            obj_actors.append(obj_actor)
        th.set_grad_enabled(False)
        ########################################################
        # 新增 SWA 更新逻辑（在此处添加）
        ########################################################
        self._update_swa_and_scheduler()  # 替代重复代码
        ########################################################

        obj_entropy_avg = np.array(
            obj_entropies).mean() if len(obj_entropies) else 0.0
        obj_critic_avg = np.array(
            obj_critics).mean() if len(obj_critics) else 0.0
        obj_actor_avg = np.array(obj_actors).mean() if len(obj_actors) else 0.0
        return obj_critic_avg, obj_actor_avg, obj_entropy_avg

    def update_objectives(self, buffer: tuple[TEN, ...], update_t: int) -> tuple[float, float, float]:
        states, actions, unmasks, logprobs, advantages, reward_sums = buffer

        sample_len = states.shape[0]
        num_seqs = states.shape[1]
        ids = th.randint(sample_len * num_seqs, size=(self.batch_size,),
                         requires_grad=False, device=self.device)
        ids0 = th.fmod(ids, sample_len)  # ids % sample_len
        # ids // sample_len
        ids1 = th.div(ids, sample_len, rounding_mode='floor')

        state = states[ids0, ids1]
        action = actions[ids0, ids1]
        unmask = unmasks[ids0, ids1]
        logprob = logprobs[ids0, ids1]
        advantage = advantages[ids0, ids1]
        reward_sum = reward_sums[ids0, ids1]

        # critic network predicts the reward_sum (Q value) of state
        value = self.cri(state).squeeze(1)
        obj_critic = (self.criterion(value, reward_sum) * unmask).mean()
        self.optimizer_backward(self.cri_optimizer, obj_critic)

        new_logprob, entropy = self.act.get_logprob_entropy(state, action)
        ratio = (new_logprob - logprob.detach()).exp()

        # surrogate1 = advantage * ratio
        # surrogate2 = advantage * ratio.clamp(1 - self.ratio_clip, 1 + self.ratio_clip)
        # surrogate = th.min(surrogate1, surrogate2)  # save as below
        # surrogate = advantage * ratio * \
        #     th.where(advantage.gt(0), 1 - self.ratio_clip, 1 + self.ratio_clip)
        # 优化后：
        surrogate1 = advantage * ratio  # 未截断优势
        surrogate2 = advantage * \
            ratio.clamp(1 - self.ratio_clip, 1 + self.ratio_clip)  # 截断优势
        surrogate = th.min(surrogate1, surrogate2)  # 取最小值，实现PPO截断

        self.lambda_entropy.data = self.lambda_entropy * self.entropy_decay  # 新增：熵系数衰减
        self.lambda_entropy.data = th.max(
            self.lambda_entropy, th.tensor(1e-5, device=self.device))  # 最低值

        obj_surrogate = (surrogate * unmask).mean()  # major actor objective
        obj_entropy = (entropy * unmask).mean()  # minor actor objective
        obj_actor_full = obj_surrogate - obj_entropy * self.lambda_entropy
        self.optimizer_backward(self.act_optimizer, -obj_actor_full)
        return obj_critic.item(), obj_surrogate.item(), obj_entropy.item()

    def get_advantages(self, states: TEN, rewards: TEN, undones: TEN, unmasks: TEN, values: TEN) -> TEN:
        advantages = th.empty_like(values)  # advantage value

        # update undones rewards when truncated
        truncated = th.logical_not(unmasks)
        if th.any(truncated):
            rewards[truncated] += self.cri(states[truncated]
                                           ).squeeze(1).detach()
            undones[truncated] = False

        masks = undones * self.gamma
        horizon_len = rewards.shape[0]

        next_state = self.last_state.clone()
        next_value = self.cri(next_state).detach().squeeze(-1)

        # last advantage value by GAE (Generalized Advantage Estimate)
        advantage = th.zeros_like(next_value)
        # get advantage value in reverse time series (V-trace)
        if self.if_use_v_trace:
            for t in range(horizon_len - 1, -1, -1):
                next_value = rewards[t] + masks[t] * next_value
                advantages[t] = advantage = next_value - values[t] + \
                    masks[t] * self.lambda_gae_adv * advantage
                next_value = values[t]
        else:  # get advantage value using the estimated value of critic network
            for t in range(horizon_len - 1, -1, -1):
                advantages[t] = rewards[t] - values[t] + masks[t] * advantage
                advantage = values[t] + self.lambda_gae_adv * advantages[t]
        return advantages

    # def update_avg_std_for_normalization(self, states: TEN):
    #     tau = self.state_value_tau
    #     if tau == 0:
    #         return

    #     state_avg = states.mean(dim=0, keepdim=True)
    #     state_std = states.std(dim=0, keepdim=True)
    #     self.act.state_avg[:] = self.act.state_avg * \
    #         (1 - tau) + state_avg * tau
    #     self.act.state_std[:] = (
    #         self.act.state_std * (1 - tau) + state_std * tau).clamp_min(1e-4)
    #     self.cri.state_avg[:] = self.act.state_avg
    #     self.cri.state_std[:] = self.act.state_std

    #     self.act_target.state_avg[:] = self.act.state_avg
    #     self.act_target.state_std[:] = self.act.state_std
    #     self.cri_target.state_avg[:] = self.cri.state_avg
    #     self.cri_target.state_std[:] = self.cri.state_std
    def update_avg_std_for_normalization(self, states: TEN):
        # 仅在训练模式下更新归一化统计量
        # if not self.training:
        #     return
        tau = self.state_value_tau * 0.1  # 原tau基础上再衰减10倍，减缓更新
        if tau == 0:
            return
        if self._ismuon:
            # 计算均值和标准差
            state_avg = states.mean(dim=0)
            state_std = states.std(dim=0) + 1e-6
        else:
            state_avg = states.mean(
                dim=0, keepdim=True).squeeze(0)  # 新增：按批次计算均值
            state_std = states.std(dim=0, keepdim=True).squeeze(
                0) + 1e-6  # 新增：按批次计算标准差

        # 仅用当前批次统计量缓慢更新，而非累积全量数据
        self.act.state_avg.data = self.act.state_avg * \
            (1 - tau) + state_avg * tau
        self.act.state_std.data = self.act.state_std * \
            (1 - tau) + state_std * tau
        # 同步Critic的归一化参数
        self.cri.state_avg.data = self.act.state_avg.data
        self.cri.state_std.data = self.act.state_std.data


class AgentA2C(AgentPPO):
    """A2C algorithm.
    “Asynchronous Methods for Deep Reinforcement Learning”. 2016.
    """

    def update_net(self, buffer) -> tuple[float, float, float]:
        buffer_size = buffer[0].shape[0]

        '''get advantages reward_sums'''
        with th.no_grad():
            states, actions, logprobs, rewards, undones, unmasks = buffer
            # set a smaller 'batch_size' to avoid CUDA OOM
            bs = max(1, 2 ** 10 // self.num_envs)
            values = [self.cri(states[i:i + bs])
                      for i in range(0, buffer_size, bs)]
            # values.shape == (buffer_size, )
            values = th.cat(values, dim=0).squeeze(-1)

            advantages = self.get_advantages(
                states, rewards, undones, unmasks, values)  # shape == (buffer_size, )
            # reward_sums.shape == (buffer_size, )
            reward_sums = advantages + values
            del rewards, undones, values

            advantages = (advantages - advantages.mean()) / \
                (advantages[::4, ::4].std() + 1e-5)  # avoid CUDA OOM
            assert logprobs.shape == advantages.shape == reward_sums.shape == (
                buffer_size, states.shape[1])
        buffer = states, actions, unmasks, logprobs, advantages, reward_sums

        '''update network'''
        obj_critics = []
        obj_actors = []

        th.set_grad_enabled(True)
        update_times = int(buffer_size * self.repeat_times / self.batch_size)
        assert update_times >= 1
        for update_t in range(update_times):
            obj_critic, obj_actor = self.update_objectives(buffer, update_t)
            obj_critics.append(obj_critic)
            obj_actors.append(obj_actor)
        th.set_grad_enabled(False)

        ########################################################
        # 新增 SWA 更新逻辑（在此处添加）
        ########################################################
        self._update_swa_and_scheduler()  # 替代重复代码
        ########################################################

        obj_critic_avg = np.array(
            obj_critics).mean() if len(obj_critics) else 0.0
        obj_actor_avg = np.array(obj_actors).mean() if len(obj_actors) else 0.0
        return obj_critic_avg, obj_actor_avg, 0

    def optimizer_backward(self, optimizer: th.optim.Optimizer, objective: TEN):
        optimizer.zero_grad()
        objective.backward()
        # 对Critic单独裁剪梯度（Actor依赖PPO截断，可省略）
        if optimizer == self.cri_optimizer and self.cri_clip_grad > 0:
            clip_grad_norm_(
                optimizer.param_groups[0]["params"], self.cri_clip_grad)
        optimizer.step()

    def update_objectives(self, buffer: tuple[TEN, ...], update_t: int) -> tuple[float, float]:
        states, actions, unmasks, logprobs, advantages, reward_sums = buffer

        buffer_size = states.shape[0]
        indices = th.randint(buffer_size, size=(
            self.batch_size,), requires_grad=False)
        state = states[indices]
        action = actions[indices]
        unmask = unmasks[indices]
        # logprob = logprobs[indices]
        advantage = advantages[indices]
        reward_sum = reward_sums[indices]

        # critic network predicts the reward_sum (Q value) of state
        value = self.cri(state).squeeze(1)
        obj_critic = (self.criterion(value, reward_sum) * unmask).mean()
        self.optimizer_backward(self.cri_optimizer, obj_critic)

        new_logprob, obj_entropy = self.act.get_logprob_entropy(state, action)
        # obj_actor without policy gradient clip
        obj_actor = (advantage * new_logprob).mean()
        self.optimizer_backward(self.act_optimizer, -obj_actor)
        return obj_critic.item(), obj_actor.item()


class AgentDiscretePPO(AgentPPO):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        # 强制设置离散动作标识，复用父类初始化逻辑
        args.if_discrete = True
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)
        # 子类无需重复初始化act/cri，由父类initialize_components统一创建
        # AgentPPO.__init__(self, net_dims, state_dim, action_dim, gpu_id, args)
        # self.if_off_policy = False

        # self.act = ActorDiscretePPO(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.cri = CriticPPO(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(
        #     self.cri.parameters(), self.learning_rate)

        # # `ratio.clamp(1 - clip, 1 + clip)`
        # self.ratio_clip = getattr(args, "ratio_clip", 0.25)
        # self.lambda_gae_adv = getattr(
        #     args, "lambda_gae_adv", 0.95)  # could be 0.80~0.99
        # self.lambda_entropy = getattr(
        #     args, "lambda_entropy", 0.01)  # could be 0.00~0.10
        # self.lambda_entropy = th.tensor(
        #     self.lambda_entropy, dtype=th.float32, device=self.device)

        # self.if_use_v_trace = getattr(args, 'if_use_v_trace', True)


class AgentDiscreteA2C(AgentDiscretePPO):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, gpu_id: int = 0, args: Config = Config()):
        args.if_discrete = True
        super().__init__(net_dims, state_dim, action_dim, gpu_id, args)  # 直接调用父类构造函数
        # AgentDiscretePPO.__init__(
        #     self, net_dims, state_dim, action_dim, gpu_id, args)
        # self.if_off_policy = False

        # self.act = ActorDiscretePPO(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.cri = CriticPPO(
        #     net_dims=net_dims, state_dim=state_dim, action_dim=action_dim).to(self.device)
        # self.act_optimizer = th.optim.Adam(
        #     self.act.parameters(), self.learning_rate)
        # self.cri_optimizer = th.optim.Adam(
        #     self.cri.parameters(), self.learning_rate)

        # self.if_use_v_trace = getattr(args, 'if_use_v_trace', True)


'''network'''


class ActorPPO(th.nn.Module):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__()
        # self.net = build_mlp(dims=[state_dim, *net_dims, action_dim])
        self.net = build_mlp(
            dims=[state_dim, *net_dims, action_dim], args=args)
        layer_init_with_orthogonal(self.net[-1], std=0.1)

        self.action_std_log = nn.Parameter(
            th.zeros((1, action_dim)), requires_grad=True)  # trainable parameter
        self.ActionDist = th.distributions.normal.Normal
        self._ismuon = False
        if args._ismuon:
            self._ismuon = True
            self.state_avg = nn.Parameter(
                th.zeros(state_dim), requires_grad=False)
            self.state_std = nn.Parameter(
                th.ones(state_dim), requires_grad=False)
        else:
            self.state_avg = nn.Parameter(
                th.zeros((state_dim,)), requires_grad=False)
            self.state_std = nn.Parameter(
                th.ones((state_dim,)), requires_grad=False)
        # 新增
        self.norm = nn.LayerNorm(state_dim)  # 新增：层归一化
        self.param_noise_scale = getattr(
            args, "param_noise_scale", 0.0)  # 如0.01
        # self.if_train_norm = True  # 训练时更新归一化统计量，评估时关闭

    def state_norm(self, state):
        # 确保 state 和归一化参数维度匹配
        if self._ismuon:
            # 如果是批量数据，扩展归一化参数以匹配批量维度
            state_avg = self.state_avg.unsqueeze(0).expand(state.size(0), -1)
            state_std = self.state_std.unsqueeze(0).expand(state.size(0), -1)
        else:
            state_avg = self.state_avg
            state_std = self.state_std

        normalized = (state - state_avg) / (state_std + 1e-4)
        return normalized

    # def state_norm(self, state: TEN) -> TEN:
    #     return (state - self.state_avg) / (self.state_std + 1e-4)
    # def state_norm(self, state: TEN) -> TEN:
    #     # 先做全局归一化，再做层归一化
    #     normalized = (state - self.state_avg) / (self.state_std + 1e-4)
    #     return self.norm(normalized)  # 新增：通过LayerNorm稳定批次内分布

    # def state_norm(self, state: TEN) -> TEN:
    #     if not self.training:
    #         # 评估模式：使用训练阶段学到的标准差缩放（不减去均值，避免分布偏移）
    #         # 仅用标准差归一化，适合评估时输入分布与训练接近的场景
    #         normalized = state / (self.state_std + 1e-4)
    #     else:
    #         # 训练模式：使用动态更新的均值和标准差归一化
    #         normalized = (state - self.state_avg) / (self.state_std + 1e-4)
    #     # 无论训练/评估，都通过LayerNorm稳定批次内分布
    #     return self.norm(normalized)

    def forward(self, state: TEN) -> TEN:
        state = self.state_norm(state)
        action = self.net(state)
        return self.convert_action_for_env(action)

    # def get_action(self, state: TEN) -> tuple[TEN, TEN]:  # for exploration
    #     state = self.state_norm(state)
    #     action_avg = self.net(state)
    #     action_std = self.action_std_log.exp()

    #     # 新增：参数噪声（仅探索时添加）
    #     if self.training:  # 训练模式下启用
    #         param_noise = th.randn_like(action_avg) * 0.01  # 噪声强度0.01（可调整）
    #         action_avg = action_avg + param_noise

    #     dist = self.ActionDist(action_avg, action_std)
    #     action = dist.sample()
    #     logprob = dist.log_prob(action).sum(1)
    #     return action, logprob
    def get_action(self, state: TEN) -> tuple[TEN, TEN]:  # for exploration
        state = self.state_norm(state)
        action_avg = self.net(state)
        action_std = self.action_std_log.exp()

        # 优化：仅训练时且噪声强度>0才添加参数噪声
        if self.training and self.param_noise_scale > 0:
            param_noise = th.randn_like(action_avg) * self.param_noise_scale
            action_avg = action_avg + param_noise

        dist = self.ActionDist(action_avg, action_std)
        action = dist.sample()
        logprob = dist.log_prob(action).sum(1)
        return action, logprob

    def get_logprob_entropy(self, state: TEN, action: TEN) -> tuple[TEN, TEN]:
        state = self.state_norm(state)
        action_avg = self.net(state)
        action_std = self.action_std_log.exp()

        dist = self.ActionDist(action_avg, action_std)
        logprob = dist.log_prob(action).sum(1)
        entropy = dist.entropy().sum(1)
        return logprob, entropy

    @staticmethod
    def convert_action_for_env(action: TEN) -> TEN:
        return action.tanh()


class ActorDiscretePPO(ActorPPO):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__(net_dims=net_dims, state_dim=state_dim,
                         action_dim=action_dim, args=args)
        self.ActionDist = th.distributions.Categorical
        self.soft_max = nn.Softmax(dim=-1)

    def forward(self, state: TEN) -> TEN:
        state = self.state_norm(state)
        a_prob = self.net(state)  # action_prob without softmax
        return a_prob.argmax(dim=1)  # get the indices of discrete action

    def get_action(self, state: TEN) -> tuple[TEN, TEN]:
        state = self.state_norm(state)
        a_prob = self.soft_max(self.net(state))
        a_dist = self.ActionDist(a_prob)
        action = a_dist.sample()
        logprob = a_dist.log_prob(action)
        return action, logprob

    # def get_logprob_entropy(self, state: TEN, action: TEN) -> tuple[TEN, TEN]:
    #     state = self.state_norm(state)
    #     # action.shape == (batch_size, 1), action.dtype = th.int
    #     a_prob = self.soft_max(self.net(state))
    #     dist = self.ActionDist(a_prob)
    #     logprob = dist.log_prob(action)
    #     entropy = dist.entropy()
    #     return logprob, entropy

    def get_logprob_entropy(self, state: TEN, action: TEN) -> tuple[TEN, TEN]:
        state = self.state_norm(state)
        a_logit = self.net(state)
        # 新增：softmax添加epsilon避免数值下溢
        a_prob = self.soft_max(a_logit) + 1e-8  # 避免prob=0导致log(0)
        dist = self.ActionDist(a_prob)
        logprob = dist.log_prob(action)
        entropy = dist.entropy()
        return logprob, entropy

    @staticmethod
    def convert_action_for_env(action: TEN) -> TEN:
        return action.long()


class CriticPPO(th.nn.Module):
    def __init__(self, net_dims: list[int], state_dim: int, action_dim: int, args: Config = None):
        super().__init__()
        # assert isinstance(action_dim, int)
        # self.net = build_mlp(dims=[state_dim, *net_dims, 1])
        self.net = build_mlp(dims=[state_dim, *net_dims, 1], args=args)

        layer_init_with_orthogonal(self.net[-1], std=0.5)
        self._ismuon = False
        if args._ismuon:
            self._ismuon = True
            self.state_avg = nn.Parameter(
                th.zeros(state_dim), requires_grad=False)
            self.state_std = nn.Parameter(
                th.ones(state_dim), requires_grad=False)
        else:
            self.state_avg = nn.Parameter(
                th.zeros((state_dim,)), requires_grad=False)
            self.state_std = nn.Parameter(
                th.ones((state_dim,)), requires_grad=False)
        self.norm = nn.LayerNorm(state_dim)  # 新增

    def forward(self, state: TEN) -> TEN:
        state = self.state_norm(state)
        value = self.net(state)
        return value  # advantage value

    # def state_norm(self, state: TEN) -> TEN:
    #     return (state - self.state_avg) / (self.state_std + 1e-4)

    # def state_norm(self, state: TEN) -> TEN:
    #     normalized = (state - self.state_avg) / (self.state_std + 1e-4)
    #     return self.norm(normalized)  # 新增

    def state_norm(self, state):
        # 确保 state 和归一化参数维度匹配
        if self._ismuon:
            # 如果是批量数据，扩展归一化参数以匹配批量维度
            state_avg = self.state_avg.unsqueeze(0).expand(state.size(0), -1)
            state_std = self.state_std.unsqueeze(0).expand(state.size(0), -1)
        else:
            state_avg = self.state_avg
            state_std = self.state_std

        normalized = (state - state_avg) / (state_std + 1e-4)
        return normalized
