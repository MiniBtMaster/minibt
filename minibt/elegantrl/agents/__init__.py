from .AgentBase import AgentBase

# DQN (off-policy)
from .AgentDQN import AgentDQN, AgentDuelingDQN
from .AgentDQN import AgentDoubleDQN, AgentD3QN
from .AgentEmbedDQN import AgentEmbedDQN, AgentEnsembleDQN

# off-policy
from .AgentTD3 import AgentTD3, AgentDDPG
from .AgentSAC import AgentSAC, AgentModSAC

# on-policy
from .AgentPPO import AgentPPO, AgentDiscretePPO
from .AgentPPO import AgentA2C, AgentDiscreteA2C

from ...other import Meta


class Agents(metaclass=Meta):
    AgentDQN = AgentDQN
    AgentDuelingDQN = AgentDuelingDQN
    AgentDoubleDQN = AgentDoubleDQN
    AgentD3QN = AgentD3QN
    AgentEmbedDQN = AgentEmbedDQN
    AgentEnsembleDQN = AgentEnsembleDQN

    AgentTD3 = AgentTD3
    AgentDDPG = AgentDDPG
    AgentSAC = AgentSAC
    AgentModSAC = AgentModSAC

    AgentPPO = AgentPPO
    AgentDiscretePPO = AgentDiscretePPO
    AgentA2C = AgentA2C
    AgentDiscreteA2C = AgentDiscreteA2C


class BestAgents(metaclass=Meta):
    AgentD3QN = AgentD3QN
    AgentDoubleDQN = AgentDoubleDQN
    AgentEmbedDQN = AgentEmbedDQN
    AgentEnsembleDQN = AgentEnsembleDQN
    AgentModSAC = AgentModSAC
    AgentDDPG = AgentDDPG
    AgentDiscretePPO = AgentDiscretePPO
    AgentDiscreteA2C = AgentDiscreteA2C


# class AgentOffPolicy(metaclass=Meta):
#     AgentDQN = AgentDQN
#     AgentDuelingDQN = AgentDuelingDQN
#     AgentDoubleDQN = AgentDoubleDQN
#     AgentD3QN = AgentD3QN
#     AgentEmbedDQN = AgentEmbedDQN
#     AgentEnsembleDQN = AgentEnsembleDQN

#     AgentTD3 = AgentTD3
#     AgentDDPG = AgentDDPG
#     AgentSAC = AgentSAC
#     AgentModSAC = AgentModSAC


# class AgentOnPolicy(metaclass=Meta):
#     AgentPPO = AgentPPO
#     AgentDiscretePPO = AgentDiscretePPO
#     AgentA2C = AgentA2C
#     AgentDiscreteA2C = AgentDiscreteA2C
