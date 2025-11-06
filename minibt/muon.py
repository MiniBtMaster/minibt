import os
import torch
import torch.distributed as dist
from typing import List, Optional, Tuple

# 完全禁用 torch.compile
os.environ["TORCHDYNAMO_DISABLE"] = "1"


def zeropower_via_newtonschulz5(G: torch.Tensor, steps: int) -> torch.Tensor:
    """
    Newton-Schulz iteration to compute the zeroth power / orthogonalization of G.

    Args:
        G: Input matrix to orthogonalize
        steps: Number of Newton-Schulz iterations

    Returns:
        Orthogonalized matrix
    """
    assert len(G.shape) == 2, "Input must be a 2D matrix"
    a, b, c = (3.4445, -4.7750, 2.0315)

    # 使用与输入相同的设备类型
    X = G.clone()
    if G.size(0) > G.size(1):
        X = X.T

    # 确保谱范数不超过1，添加更安全的归一化
    norm_val = X.norm()
    if norm_val > 0:
        X = X / (norm_val + 1e-12)  # 更小的 epsilon 以提高数值稳定性
    else:
        X = X / 1e-12  # 避免除零错误

    # 执行 NS 迭代
    for _ in range(steps):
        A = X @ X.T
        B = b * A + c * A @ A
        X = a * X + B @ X

    if G.size(0) > G.size(1):
        X = X.T

    return X


class AdaMuon(torch.optim.Optimizer):
    """
    Muon - MomentUm Orthogonalized by Newton-schulz

    Muon internally runs standard SGD-momentum, and then performs an orthogonalization post-
    processing step, in which each 2D parameter's update is replaced with the nearest orthogonal
    matrix. To efficiently orthogonalize each update, we use a Newton-Schulz iteration.

    Arguments:
        muon_params: The parameters to be optimized by Muon.
        lr: The learning rate. The updates will have spectral norm of `lr`. (0.02 is a good default)
        momentum: The momentum used by the internal SGD. (0.95 is a good default)
        beta2: The beta2 for gradient norm EMA.
        nesterov: Whether to use Nesterov-style momentum in the internal SGD. (recommended)
        ns_steps: The number of Newton-Schulz iterations to run. (6 is probably always enough)
        adamw_params: The parameters to be optimized by AdamW.
        adamw_lr: The learning rate for the internal AdamW.
        adamw_betas: The betas for the internal AdamW.
        adamw_eps: The epsilon for the internal AdamW.
        adamw_wd: The weight decay for the internal AdamW.
        input_feature_dim: The dimension of the input features (e.g., state_dim). If provided, parameters
        containing this dimension in their shape will be excluded from Muon optimization.
        debug_mode: Whether to enable debug logging.
    """

    def __init__(self, muon_params: List[torch.Tensor], lr: float = 0.02, momentum: float = 0.95,
                 beta2: float = 0.995, nesterov: bool = True, ns_steps: int = 6,
                 adamw_params: Optional[List[torch.Tensor]] = None, adamw_lr: float = 3e-4,
                 adamw_betas: Tuple[float, float] = (0.95, 0.95), adamw_eps: float = 1e-8,
                 adamw_wd: float = 0, input_feature_dim: Optional[int] = None,
                 debug_mode: bool = False):

        defaults = dict(
            lr=lr, momentum=momentum, beta2=beta2, nesterov=nesterov, ns_steps=ns_steps,
            adamw_lr_ratio=adamw_lr/lr, adamw_betas=adamw_betas,
            adamw_eps=adamw_eps, adamw_wd=adamw_wd
        )

        params = list(muon_params)
        adamw_params = list(adamw_params) if adamw_params is not None else []
        params.extend(adamw_params)
        super().__init__(params, defaults)

        # 初始化步数计数器
        self.step_count = 0
        self.debug_mode = debug_mode

        # 将参数分类为使用 Muon 或不使用 Muon
        for p in muon_params:
            # 使用 Muon 的参数：维度≥2且不包含输入特征维度
            if p.ndim >= 2 and (input_feature_dim is None or all(s != input_feature_dim for s in p.shape)):
                self.state[p]['use_muon'] = True
            else:
                self.state[p]['use_muon'] = False

        for p in adamw_params:
            # 不使用 Muon 的参数
            self.state[p]['use_muon'] = False

        # 分布式训练设置
        if 'WORLD_SIZE' in os.environ:
            self.world_size = int(os.environ['WORLD_SIZE'])
            self.rank = int(os.environ['RANK'])
        else:
            self.world_size = 1
            self.rank = 0

    def step(self, closure=None):
        """Perform a single optimization step.

        Args:
            closure (Callable, optional): A closure that reevaluates the model
                and returns the loss.
        """
        try:
            loss = None
            if closure is not None:
                with torch.enable_grad():
                    loss = closure()

            # 更新步数计数器
            self.step_count += 1

            # 记录优化器状态
            # if self.debug_mode and self.rank == 0 and self.step_count % 100 == 0:
            #     self._log_optimizer_state()

            for group in self.param_groups:
                # 处理 Muon 参数
                self._process_muon_params(group)

                # 处理 AdamW 参数
                self._process_adamw_params(group)

            return loss

        except Exception as e:
            # 错误处理
            print(f"Error in AdaMuon step {self.step_count}: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            # 回退到标准 SGD 优化
            return self._fallback_step(closure)

    def _process_muon_params(self, group):
        """处理使用 Muon 优化的参数"""
        params = [p for p in group['params']
                  if self.state[p].get('use_muon', False)]
        if not params:
            return

        device = params[0].device
        lr = group['lr']
        momentum = group['momentum']
        beta2 = group['beta2']
        ns_steps = group['ns_steps']
        nesterov = group['nesterov']

        # 预计算所有需要的梯度
        grads = []
        param_info = []  # 存储参数索引和大小信息
        total_size = 0

        for i, p in enumerate(params):
            if i % self.world_size != self.rank:
                continue

            g = p.grad
            if g is None:
                continue

            # 处理高维参数
            if g.ndim > 2:
                g = g.view(g.size(0), -1)

            grads.append(g)
            param_info.append((i, p.numel(), p.shape))
            total_size += p.numel()

        # 如果没有梯度需要处理，直接返回
        if not grads:
            return

        # 根据设备类型选择合适的数据类型
        dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
        updates_flat = torch.zeros(total_size, device=device, dtype=dtype)
        curr_idx = 0

        for (i, p_numel, p_shape), g in zip(param_info, grads):
            state = self.state[params[i]]

            # 初始化状态
            if 'momentum_buffer' not in state:
                state['momentum_buffer'] = torch.zeros_like(g)
                state['grad_norm_ema'] = torch.zeros(1, device=device)

            buf = state['momentum_buffer']
            buf.mul_(momentum).add_(g)

            # 应用 Nesterov 动量
            if nesterov:
                g_update = g.add(buf, alpha=momentum)
            else:
                g_update = buf.clone()

            # 计算梯度范数
            og_norm = g_update.norm()
            grad_norm_ema = state['grad_norm_ema']
            grad_norm_ema.lerp_(og_norm**2, 1 - beta2)

            # 正交化处理
            try:
                g_ortho = zeropower_via_newtonschulz5(g_update, steps=ns_steps)
            except Exception as e:
                if self.debug_mode:
                    print(f"NS iteration failed: {e}")
                g_ortho = g_update  # 失败时回退到原始梯度

            # 保持梯度范数
            ortho_norm = g_ortho.norm()
            if ortho_norm > 1e-12:  # 避免除零错误
                g_ortho = g_ortho * (og_norm / ortho_norm)

            # 应用梯度归一化
            if grad_norm_ema > 0:
                g_ortho = g_ortho / (torch.sqrt(grad_norm_ema) + 1e-12)

            # 存储更新
            updates_flat[curr_idx:curr_idx + p_numel] = g_ortho.flatten()
            curr_idx += p_numel

        # 分布式同步
        if self.world_size > 1:
            dist.all_reduce(updates_flat, op=dist.ReduceOp.SUM)

        # 应用更新
        curr_idx = 0
        for i, p_numel, p_shape in param_info:
            g_update = updates_flat[curr_idx:curr_idx + p_numel].view(p_shape)
            params[i].data.add_(g_update.type_as(params[i].data), alpha=-lr)
            curr_idx += p_numel

    def _process_adamw_params(self, group):
        """处理使用 AdamW 优化的参数"""
        params = [p for p in group['params']
                  if not self.state[p].get('use_muon', True)]
        if not params:
            return

        lr = group['adamw_lr_ratio'] * group['lr']  # 考虑学习率调度
        beta1, beta2 = group['adamw_betas']
        eps = group['adamw_eps']
        weight_decay = group['adamw_wd']

        for p in params:
            g = p.grad
            if g is None:
                continue

            state = self.state[p]

            # 初始化状态
            if 'step' not in state:
                state['step'] = 0
                state['moment1'] = torch.zeros_like(g)
                state['moment2'] = torch.zeros_like(g)

            state['step'] += 1
            step = state['step']
            buf1 = state['moment1']
            buf2 = state['moment2']

            # 更新动量
            buf1.lerp_(g, 1 - beta1)
            buf2.lerp_(g.square(), 1 - beta2)

            # 计算更新
            g_update = buf1 / (eps + buf2.sqrt())

            # 偏差校正
            bias_correction1 = 1 - beta1 ** step
            bias_correction2 = 1 - beta2 ** step
            scale = bias_correction1 / (bias_correction2 ** 0.5 + 1e-12)

            # 应用权重衰减
            p.data.mul_(1 - lr * weight_decay)

            # 应用更新
            p.data.add_(g_update, alpha=-lr / scale)

    def _log_optimizer_state(self):
        """记录优化器状态用于调试"""
        muon_params = sum(1 for p in self.param_groups[0]['params']
                          if self.state[p].get('use_muon', False))
        adamw_params = sum(1 for p in self.param_groups[0]['params']
                           if not self.state[p].get('use_muon', True))

        print(
            f"AdaMuon step {self.step_count}: {muon_params} Muon params, {adamw_params} AdamW params")

    def _fallback_step(self, closure=None):
        """回退到标准 SGD 优化"""
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group['lr']
            momentum = group['momentum']
            nesterov = group['nesterov']

            for p in group['params']:
                if p.grad is None:
                    continue

                d_p = p.grad

                # 应用动量
                state = self.state[p]
                if 'momentum_buffer' not in state:
                    state['momentum_buffer'] = torch.zeros_like(d_p)

                buf = state['momentum_buffer']
                buf.mul_(momentum).add_(d_p)

                # 应用 Nesterov 动量
                if nesterov:
                    d_p = d_p.add(buf, alpha=momentum)
                else:
                    d_p = buf

                # 应用更新
                p.data.add_(d_p, alpha=-lr)

        return loss


def gradwhiten(grad: torch.Tensor, ns_steps: int = 6, beta: float = 0.5) -> torch.Tensor:
    """
    Implements the GradWhitening operator as described in Algorithm 2.

    Args:
        grad: Input matrix G of shape (m x n) where m <= n
        ns_steps: Number of Newton-Schulz iterations (default: 6)
        beta: Step size for Newton-Schulz iterations (default: 0.5)

    Returns:
        Whitened gradient ZG where Z approximates (GG^T)^(-1/2)
    """
    # 确保输入是2D矩阵
    if grad.ndim != 2:
        raise ValueError("grad must be a 2D matrix")

    # 初始化
    norm_val = grad.norm()
    if norm_val > 0:
        grad = grad / (norm_val + 1e-12)  # 更安全的归一化
    else:
        grad = grad / 1e-12  # 避免除零错误

    Y = grad @ grad.T
    Z = torch.eye(Y.size(0), device=grad.device, dtype=grad.dtype)
    I3 = 3 * Z

    # Newton-Schulz 迭代
    for _ in range(ns_steps):
        ZY = Z @ Y
        I3_minus_ZY = I3 - ZY
        Y = beta * (Y @ I3_minus_ZY)
        Z = beta * (I3_minus_ZY @ Z)

    return Z


class MomMuon(torch.optim.Optimizer):
    """
    Muon - MomentUm Orthogonalized by Newton-schulz

    Muon internally runs standard SGD-momentum, and then performs an orthogonalization post-
    processing step, in which each 2D parameter's update is replaced with the nearest orthogonal
    matrix. To efficiently orthogonalize each update, we use a Newton-Schulz iteration.

    Arguments:
        muon_params: The parameters to be optimized by Muon.
        lr: The learning rate. The updates will have spectral norm of `lr`. (0.02 is a good default)
        momentum: The momentum used by the internal SGD. (0.95 is a good default)
        beta2: The beta2 for gradient norm EMA.
        ns_beta: Beta parameter for preconditioner EMA.
        ns_every: Apply NS iteration every N steps.
        nesterov: Whether to use Nesterov-style momentum in the internal SGD. (recommended)
        ns_steps: The number of Newton-Schulz iterations to run. (6 is probably always enough)
        adamw_params: The parameters to be optimized by AdamW.
        adamw_lr: The learning rate for the internal AdamW.
        adamw_betas: The betas for the internal AdamW.
        adamw_eps: The epsilon for the internal AdamW.
        adamw_wd: The weight decay for the internal AdamW.
        input_feature_dim: The dimension of the input features (e.g., state_dim). If provided, parameters
        containing this dimension in their shape will be excluded from Muon optimization.
        debug_mode: Whether to enable debug logging.
    """

    def __init__(self, muon_params: List[torch.Tensor], lr: float = 0.02, momentum: float = 0.95,
                 beta2: float = 0.995, ns_beta: float = 0.9, ns_every: int = 1, nesterov: bool = True,
                 ns_steps: int = 15, adamw_params: Optional[List[torch.Tensor]] = None,
                 adamw_lr: float = 3e-4, adamw_betas: Tuple[float, float] = (0.95, 0.95),
                 adamw_eps: float = 1e-8, adamw_wd: float = 0,
                 input_feature_dim: Optional[int] = None, debug_mode: bool = False):

        defaults = dict(
            lr=lr, momentum=momentum, beta2=beta2, ns_beta=ns_beta, ns_every=ns_every,
            nesterov=nesterov, ns_steps=ns_steps,
            adamw_lr_ratio=adamw_lr/lr, adamw_betas=adamw_betas,
            adamw_eps=adamw_eps, adamw_wd=adamw_wd
        )

        params = list(muon_params)
        adamw_params = list(adamw_params) if adamw_params is not None else []
        params.extend(adamw_params)
        super().__init__(params, defaults)

        # 初始化步数计数器
        self.step_count = 0
        self.debug_mode = debug_mode

        # 将参数分类为使用 Muon 或不使用 Muon
        for p in muon_params:
            # 使用 Muon 的参数：维度≥2且不包含输入特征维度
            if p.ndim >= 2 and (input_feature_dim is None or all(s != input_feature_dim for s in p.shape)):
                self.state[p]['use_muon'] = True
            else:
                self.state[p]['use_muon'] = False

        for p in adamw_params:
            # 不使用 Muon 的参数
            self.state[p]['use_muon'] = False

        # 分布式训练设置
        if 'WORLD_SIZE' in os.environ:
            self.world_size = int(os.environ['WORLD_SIZE'])
            self.rank = int(os.environ['RANK'])
        else:
            self.world_size = 1
            self.rank = 0

    def step(self, closure=None):
        """Perform a single optimization step.

        Args:
            closure (Callable, optional): A closure that reevaluates the model
                and returns the loss.
        """
        try:
            loss = None
            if closure is not None:
                with torch.enable_grad():
                    loss = closure()

            # 更新步数计数器
            self.step_count += 1

            # 记录优化器状态
            # if self.debug_mode and self.rank == 0 and self.step_count % 100 == 0:
            #     self._log_optimizer_state()

            for group in self.param_groups:
                # 处理 Muon 参数
                self._process_muon_params(group)

                # 处理 AdamW 参数
                self._process_adamw_params(group)

            return loss

        except Exception as e:
            # 错误处理
            print(f"Error in MomMuon step {self.step_count}: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            # 回退到标准 SGD 优化
            return self._fallback_step(closure)

    def _process_muon_params(self, group):
        """处理使用 Muon 优化的参数"""
        params = [p for p in group['params']
                  if self.state[p].get('use_muon', False)]
        if not params:
            return

        device = params[0].device
        lr = group['lr']
        momentum = group['momentum']
        ns_beta = group['ns_beta']
        ns_every = group['ns_every']
        ns_steps = group['ns_steps']
        nesterov = group['nesterov']

        # 预计算所有需要的梯度
        grads = []
        param_info = []  # 存储参数索引和大小信息
        total_size = 0

        for i, p in enumerate(params):
            if i % self.world_size != self.rank:
                continue

            g = p.grad
            if g is None:
                continue

            # 处理高维参数
            if g.ndim > 2:
                g = g.view(g.size(0), -1)

            grads.append(g)
            param_info.append((i, p.numel(), p.shape))
            total_size += p.numel()

        # 如果没有梯度需要处理，直接返回
        if not grads:
            return

        # 根据设备类型选择合适的数据类型
        dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
        updates_flat = torch.zeros(total_size, device=device, dtype=dtype)
        curr_idx = 0

        for (i, p_numel, p_shape), g in zip(param_info, grads):
            state = self.state[params[i]]

            # 初始化状态
            if 'step' not in state:
                state['step'] = 0
            if 'momentum_buffer' not in state:
                state['momentum_buffer'] = torch.zeros_like(g)

            buf = state['momentum_buffer']
            buf.mul_(momentum).add_(g)

            # 应用 Nesterov 动量
            if nesterov:
                g_update = g.add(buf, alpha=momentum)
            else:
                g_update = buf.clone()

            # 应用 NS 预处理
            if (ns_every > 0 and state['step'] % ns_every == 0) or state['step'] == 0:
                try:
                    precond = gradwhiten(g_update, ns_steps=ns_steps)
                except Exception as e:
                    if self.debug_mode:
                        print(f"GradWhitening failed: {e}")
                    precond = torch.eye(g_update.size(
                        0), device=device, dtype=g_update.dtype)

                # 初始化或更新预处理指数平均值
                if "precond_exp_avg" not in state:
                    state["precond_exp_avg"] = precond
                else:
                    state["precond_exp_avg"].lerp_(precond, 1 - ns_beta)

            # 应用预处理
            g_processed = state["precond_exp_avg"] @ g_update

            # 缩放因子
            scaling_factor = max(1, g_processed.size(
                0) / g_processed.size(1)) ** 0.5
            g_processed = g_processed * scaling_factor

            # 存储更新
            updates_flat[curr_idx:curr_idx + p_numel] = g_processed.flatten()
            curr_idx += p_numel

            # 更新步数
            state['step'] += 1

        # 分布式同步
        if self.world_size > 1:
            dist.all_reduce(updates_flat, op=dist.ReduceOp.SUM)

        # 应用更新
        curr_idx = 0
        for i, p_numel, p_shape in param_info:
            g_update = updates_flat[curr_idx:curr_idx + p_numel].view(p_shape)
            params[i].data.add_(g_update.type_as(params[i].data), alpha=-lr)
            curr_idx += p_numel

    def _process_adamw_params(self, group):
        """处理使用 AdamW 优化的参数"""
        params = [p for p in group['params']
                  if not self.state[p].get('use_muon', True)]
        if not params:
            return

        lr = group['adamw_lr_ratio'] * group['lr']  # 考虑学习率调度
        beta1, beta2 = group['adamw_betas']
        eps = group['adamw_eps']
        weight_decay = group['adamw_wd']

        for p in params:
            g = p.grad
            if g is None:
                continue

            state = self.state[p]

            # 初始化状态
            if 'step' not in state:
                state['step'] = 0
                state['moment1'] = torch.zeros_like(g)
                state['moment2'] = torch.zeros_like(g)

            state['step'] += 1
            step = state['step']
            buf1 = state['moment1']
            buf2 = state['moment2']

            # 更新动量
            buf1.lerp_(g, 1 - beta1)
            buf2.lerp_(g.square(), 1 - beta2)

            # 计算更新
            g_update = buf1 / (eps + buf2.sqrt())

            # 偏差校正
            bias_correction1 = 1 - beta1 ** step
            bias_correction2 = 1 - beta2 ** step
            scale = bias_correction1 / (bias_correction2 ** 0.5 + 1e-12)

            # 应用权重衰减
            p.data.mul_(1 - lr * weight_decay)

            # 应用更新
            p.data.add_(g_update, alpha=-lr / scale)

    def _log_optimizer_state(self):
        """记录优化器状态用于调试"""
        muon_params = sum(1 for p in self.param_groups[0]['params']
                          if self.state[p].get('use_muon', False))
        adamw_params = sum(1 for p in self.param_groups[0]['params']
                           if not self.state[p].get('use_muon', True))

        print(
            f"MomMuon step {self.step_count}: {muon_params} Muon params, {adamw_params} AdamW params")

    def _fallback_step(self, closure=None):
        """回退到标准 SGD 优化"""
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group['lr']
            momentum = group['momentum']
            nesterov = group['nesterov']

            for p in group['params']:
                if p.grad is None:
                    continue

                d_p = p.grad

                # 应用动量
                state = self.state[p]
                if 'momentum_buffer' not in state:
                    state['momentum_buffer'] = torch.zeros_like(d_p)

                buf = state['momentum_buffer']
                buf.mul_(momentum).add_(d_p)

                # 应用 Nesterov 动量
                if nesterov:
                    d_p = d_p.add(buf, alpha=momentum)
                else:
                    d_p = buf

                # 应用更新
                p.data.add_(d_p, alpha=-lr)

        return loss


def zeropower_via_newtonschulz5(G: torch.Tensor, steps: int) -> torch.Tensor:
    """
    Newton-Schulz iteration to compute the zeroth power / orthogonalization of G.

    Args:
        G: Input matrix to orthogonalize
        steps: Number of Newton-Schulz iterations

    Returns:
        Orthogonalized matrix
    """
    assert len(G.shape) == 2, "Input must be a 2D matrix"
    a, b, c = (3.4445, -4.7750, 2.0315)

    # 使用与输入相同的设备类型
    X = G.clone()
    if G.size(0) > G.size(1):
        X = X.T

    # 确保谱范数不超过1，添加更安全的归一化
    norm_val = X.norm()
    if norm_val > 0:
        X = X / (norm_val + 1e-12)  # 更小的 epsilon 以提高数值稳定性
    else:
        X = X / 1e-12  # 避免除零错误

    # 执行 NS 迭代
    for _ in range(steps):
        A = X @ X.T
        B = b * A + c * A @ A
        X = a * X + B @ X

    if G.size(0) > G.size(1):
        X = X.T

    return X


class OGSignMuon(torch.optim.Optimizer):
    """
    Muon - MomentUm Orthogonalized by Newton-schulz with Sign Preservation

    Muon internally runs standard SGD-momentum, and then performs an orthogonalization post-
    processing step, in which each 2D parameter's update is replaced with the nearest orthogonal
    matrix. To efficiently orthogonalize each update, we use a Newton-Schulz iteration.

    Arguments:
        muon_params: The parameters to be optimized by Muon.
        lr: The learning rate. The updates will have spectral norm of `lr`. (0.02 is a good default)
        momentum: The momentum used by the internal SGD. (0.95 is a good default)
        nesterov: Whether to use Nesterov-style momentum in the internal SGD. (recommended)
        ns_steps: The number of Newton-Schulz iterations to run. (6 is probably always enough)
        adamw_params: The parameters to be optimized by AdamW.
        adamw_lr: The learning rate for the internal AdamW.
        adamw_betas: The betas for the internal AdamW.
        adamw_eps: The epsilon for the internal AdamW.
        adamw_wd: The weight decay for the internal AdamW.
        input_feature_dim: The dimension of the input features (e.g., state_dim). If provided, parameters
        containing this dimension in their shape will be excluded from Muon optimization.
        debug_mode: Whether to enable debug logging.
    """

    def __init__(self, muon_params: List[torch.Tensor], lr: float = 0.02, momentum: float = 0.95,
                 nesterov: bool = True, ns_steps: int = 6, adamw_params: Optional[List[torch.Tensor]] = None,
                 adamw_lr: float = 3e-4, adamw_betas: Tuple[float, float] = (0.95, 0.95),
                 adamw_eps: float = 1e-8, adamw_wd: float = 0,
                 input_feature_dim: Optional[int] = None, debug_mode: bool = False):

        defaults = dict(
            lr=lr, momentum=momentum, nesterov=nesterov, ns_steps=ns_steps,
            adamw_lr_ratio=adamw_lr/lr, adamw_betas=adamw_betas,
            adamw_eps=adamw_eps, adamw_wd=adamw_wd
        )

        params = list(muon_params)
        adamw_params = list(adamw_params) if adamw_params is not None else []
        params.extend(adamw_params)
        super().__init__(params, defaults)

        # 初始化步数计数器
        self.step_count = 0
        self.debug_mode = debug_mode

        # 将参数分类为使用 Muon 或不使用 Muon
        for p in muon_params:
            # 使用 Muon 的参数：维度≥2且不包含输入特征维度
            if p.ndim >= 2 and (input_feature_dim is None or all(s != input_feature_dim for s in p.shape)):
                self.state[p]['use_muon'] = True
            else:
                self.state[p]['use_muon'] = False

        for p in adamw_params:
            # 不使用 Muon 的参数
            self.state[p]['use_muon'] = False

        # 分布式训练设置
        if 'WORLD_SIZE' in os.environ:
            self.world_size = int(os.environ['WORLD_SIZE'])
            self.rank = int(os.environ['RANK'])
        else:
            self.world_size = 1
            self.rank = 0

    def step(self, closure=None):
        """Perform a single optimization step.

        Args:
            closure (Callable, optional): A closure that reevaluates the model
                and returns the loss.
        """
        try:
            loss = None
            if closure is not None:
                with torch.enable_grad():
                    loss = closure()

            # 更新步数计数器
            self.step_count += 1

            # 记录优化器状态
            if self.debug_mode and self.rank == 0 and self.step_count % 100 == 0:
                self._log_optimizer_state()

            for group in self.param_groups:
                # 处理 Muon 参数
                self._process_muon_params(group)

                # 处理 AdamW 参数
                self._process_adamw_params(group)

            return loss

        except Exception as e:
            # 错误处理
            print(f"Error in OGSignMuon step {self.step_count}: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            # 回退到标准 SGD 优化
            return self._fallback_step(closure)

    def _process_muon_params(self, group):
        """处理使用 Muon 优化的参数"""
        params = [p for p in group['params']
                  if self.state[p].get('use_muon', False)]
        if not params:
            return

        device = params[0].device
        lr = group['lr']
        momentum = group['momentum']
        ns_steps = group['ns_steps']
        nesterov = group['nesterov']

        # 预计算所有需要的梯度
        grads = []
        param_info = []  # 存储参数索引和大小信息
        total_size = 0

        for i, p in enumerate(params):
            if i % self.world_size != self.rank:
                continue

            g = p.grad
            if g is None:
                continue

            # 处理高维参数
            if g.ndim > 2:
                g = g.view(g.size(0), -1)

            grads.append(g)
            param_info.append((i, p.numel(), p.shape))
            total_size += p.numel()

        # 如果没有梯度需要处理，直接返回
        if not grads:
            return

        # 根据设备类型选择合适的数据类型
        dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
        updates_flat = torch.zeros(total_size, device=device, dtype=dtype)
        curr_idx = 0

        for (i, p_numel, p_shape), g in zip(param_info, grads):
            state = self.state[params[i]]

            # 初始化状态
            if 'momentum_buffer' not in state:
                state['momentum_buffer'] = torch.zeros_like(g)

            buf = state['momentum_buffer']
            buf.mul_(momentum).add_(g)

            # 应用 Nesterov 动量
            if nesterov:
                g_update = g.add(buf, alpha=momentum)
            else:
                g_update = buf.clone()

            # 保存符号信息
            sign_mask = g_update.sign()

            # 应用 NS 正交化
            try:
                g_ortho = zeropower_via_newtonschulz5(g_update, steps=ns_steps)
            except Exception as e:
                if self.debug_mode:
                    print(f"NS iteration failed: {e}")
                g_ortho = g_update  # 失败时回退到原始梯度

            # 恢复符号信息
            g_processed = g_ortho.abs() * sign_mask

            # 缩放因子
            scaling_factor = max(1, g_processed.size(
                0) / g_processed.size(1)) ** 0.5
            g_processed = g_processed * scaling_factor

            # 存储更新
            updates_flat[curr_idx:curr_idx + p_numel] = g_processed.flatten()
            curr_idx += p_numel

        # 分布式同步
        if self.world_size > 1:
            dist.all_reduce(updates_flat, op=dist.ReduceOp.SUM)

        # 应用更新
        curr_idx = 0
        for i, p_numel, p_shape in param_info:
            g_update = updates_flat[curr_idx:curr_idx + p_numel].view(p_shape)
            params[i].data.add_(g_update.type_as(params[i].data), alpha=-lr)
            curr_idx += p_numel

    def _process_adamw_params(self, group):
        """处理使用 AdamW 优化的参数"""
        params = [p for p in group['params']
                  if not self.state[p].get('use_muon', True)]
        if not params:
            return

        lr = group['adamw_lr_ratio'] * group['lr']  # 考虑学习率调度
        beta1, beta2 = group['adamw_betas']
        eps = group['adamw_eps']
        weight_decay = group['adamw_wd']

        for p in params:
            g = p.grad
            if g is None:
                continue

            state = self.state[p]

            # 初始化状态
            if 'step' not in state:
                state['step'] = 0
                state['moment1'] = torch.zeros_like(g)
                state['moment2'] = torch.zeros_like(g)

            state['step'] += 1
            step = state['step']
            buf1 = state['moment1']
            buf2 = state['moment2']

            # 更新动量
            buf1.lerp_(g, 1 - beta1)
            buf2.lerp_(g.square(), 1 - beta2)

            # 计算更新
            g_update = buf1 / (eps + buf2.sqrt())

            # 偏差校正
            bias_correction1 = 1 - beta1 ** step
            bias_correction2 = 1 - beta2 ** step
            scale = bias_correction1 / (bias_correction2 ** 0.5 + 1e-12)

            # 应用权重衰减
            p.data.mul_(1 - lr * weight_decay)

            # 应用更新
            p.data.add_(g_update, alpha=-lr / scale)

    def _log_optimizer_state(self):
        """记录优化器状态用于调试"""
        muon_params = sum(1 for p in self.param_groups[0]['params']
                          if self.state[p].get('use_muon', False))
        adamw_params = sum(1 for p in self.param_groups[0]['params']
                           if not self.state[p].get('use_muon', True))

        print(
            f"OGSignMuon step {self.step_count}: {muon_params} Muon params, {adamw_params} AdamW params")

    def _fallback_step(self, closure=None):
        """回退到标准 SGD 优化"""
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group['lr']
            momentum = group['momentum']
            nesterov = group['nesterov']

            for p in group['params']:
                if p.grad is None:
                    continue

                d_p = p.grad

                # 应用动量
                state = self.state[p]
                if 'momentum_buffer' not in state:
                    state['momentum_buffer'] = torch.zeros_like(d_p)

                buf = state['momentum_buffer']
                buf.mul_(momentum).add_(d_p)

                # 应用 Nesterov 动量
                if nesterov:
                    d_p = d_p.add(buf, alpha=momentum)
                else:
                    d_p = buf

                # 应用更新
                p.data.add_(d_p, alpha=-lr)

        return loss
