## 可用的 Agent 分类

### 第一梯队：最适合 bandit 范式

#### 1. AgentEnsembleDQN（最接近 Thompson Sampling）
- 集成多个 Q 网络，每个网络独立对 `Q(s,a)` 做估计
- 决策时用集成的**方差**衡量不确定性——方差大说明不确定，方差小说明确定
- **天然等价于 Thompson Sampling**：对每个 action 有独立的置信度估计
- 适合小样本、不确定性高的场景

#### 2. AgentDuelingDQN
- 把 Q(s,a) 拆成 V(s) + A(s,a)：状态价值 + 动作优势
- 在 bandit 场景下：V(s) 预测「这个 state 总体好不好」，A(s,a) 预测「哪个 action 最优」
- 比纯 DQN 样本利用率高，适合小数据

#### 3. AgentDQN / AgentDoubleDQN / AgentD3QN
- 标准离散动作 Q-learning，off-policy 可重复利用样本
- 每步 (state, action, reward) 独立训练，**天然匹配 bandit**
- Double/D3QN 减少 Q 值过估计，更稳

### 第二梯队：可以用但不是最优

#### 4. AgentDiscretePPO
- on-policy，每批样本只用一次，**样本利用率低**
- 在 bandit 范式下能跑，但比 DQN 多需要 3-5 倍样本才能收敛
- 优势：实现最简单，已集成好

#### 5. AgentDiscreteA2C
- PPO 的简化版（没有 clip），训练更稳定
- 同样 on-policy，样本利用率低

### 第三梯队：不适合

- AgentTD3 / AgentDDPG / AgentSAC / AgentModSAC：**连续动作**算法，你的 action 是离散的 1-6，不匹配

## 推荐组合（针对期货小样本场景）

```
首选: AgentEnsembleDQN  →  集成不确定性 ≈ Thompson Sampling，最像 bandit
次选: AgentDuelingDQN   →  V(s) + A(s,a) 拆分，样本利用率高
基线: AgentDiscretePPO  →  你当前用的，可作为对照
```

## 与 bandit 算法的对应关系

| Bandit 算法       | 对应的 ElegantRL Agent               |
| ----------------- | ------------------------------------ |
| LinUCB            | AgentDQN（线性 Q 网络 + ε-greedy）   |
| Neural Bandit     | AgentDuelingDQN（神经网络 Q 值）     |
| Thompson Sampling | **AgentEnsembleDQN**（集成不确定性） |
| ε-greedy Bandit   | AgentDQN / AgentDiscretePPO          |
