from __future__ import annotations

from cogames.policy.aligner_agent import AlignerPolicyImpl, AlignerState, SharedMap
from cogames.policy.starter_agent import StarterCogPolicyImpl, StarterCogState
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy
from mettagrid.policy.policy_env_interface import PolicyEnvInterface


class MachinaRolesPolicy(MultiAgentPolicy):
    short_names = ["machina_roles", "machina_mixed"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int = 2,
        aligner_ids: str = "0,5",
    ):
        super().__init__(policy_env_info, device=device)
        parsed_aligner_ids = tuple(
            int(part.strip()) for part in aligner_ids.split(",") if part.strip()
        )
        if parsed_aligner_ids:
            self._aligner_ids = frozenset(parsed_aligner_ids)
        else:
            self._aligner_ids = frozenset(range(num_aligners))
        self._agent_policies: dict[int, StatefulAgentPolicy[AlignerState | StarterCogState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[AlignerState | StarterCogState]:
        if agent_id not in self._agent_policies:
            if agent_id in self._aligner_ids:
                impl = AlignerPolicyImpl(self._policy_env_info, agent_id)
            else:
                impl = StarterCogPolicyImpl(self._policy_env_info, agent_id, preferred_gear="miner")
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]


class FourAlignersPolicy(MultiAgentPolicy):
    """4 independent scripted aligners, no SharedMap, no miners.

    Each agent acts completely independently. Useful for testing whether
    parallel alignment (4 agents × 1 junction each) beats 1 aligner + 3 miners.
    """
    short_names = ["four_aligners"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
    ):
        super().__init__(policy_env_info, device=device)
        self._agent_policies: dict[int, StatefulAgentPolicy[AlignerState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[AlignerState]:
        if agent_id not in self._agent_policies:
            impl = AlignerPolicyImpl(self._policy_env_info, agent_id)  # no SharedMap
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]


class PartitionedMachinaRolesPolicy(MultiAgentPolicy):
    """Scripted aligner policy with spatial partitioning for improved coverage.

    Each aligner is assigned a map quadrant (NW/NE/SW/SE) to explore preferentially.
    Agents also use a shared map for collective map knowledge and optionally apply
    a repulsion field to avoid clustering near teammates.

    Quadrant assignment (4 agents):
      agent 0 -> NW (row<0, col<0)
      agent 1 -> NE (row<0, col>0)
      agent 2 -> SW (row>0, col<0)
      agent 3 -> SE (row>0, col>0)

    With repulsion_radius > 0, agents prefer frontier cells at least that far from teammates.
    """
    short_names = ["partitioned_machina_roles"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int | str = 4,
        quadrant_assign: bool | str = False,
        repulsion_radius: int | str = 0,
        share_move_blocked: bool | str = True,
        share_terrain: bool | str = True,
    ):
        super().__init__(policy_env_info, device=device)
        self._num_aligners = int(num_aligners)
        self._quadrant_assign = str(quadrant_assign).lower() in ("true", "1", "yes")
        self._repulsion_radius = int(repulsion_radius)
        # share_move_blocked=True by default: shared BFS map improves navigation for all agents
        # Consistent with LLMAlignerPolicyImpl which also defaults to share_move_blocked=True
        self._share_move_blocked = str(share_move_blocked).lower() in ("true", "1", "yes")
        # share_terrain=True by default: shared terrain enables faster BFS for all agents
        self._share_terrain = str(share_terrain).lower() in ("true", "1", "yes")
        self._shared_map = SharedMap()
        self._agent_policies: dict[int, StatefulAgentPolicy[AlignerState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[AlignerState]:
        if agent_id not in self._agent_policies:
            if self._quadrant_assign and agent_id < self._num_aligners:
                # Assign quadrant based on agent rank: 0=NW, 1=NE, 2=SW, 3=SE (cycles if >4)
                quadrant = agent_id % 4
            else:
                quadrant = None
            impl = AlignerPolicyImpl(
                self._policy_env_info,
                agent_id,
                shared_map=self._shared_map,
                quadrant_bias=quadrant,
                repulsion_radius=self._repulsion_radius,
                share_move_blocked=self._share_move_blocked,
                share_terrain=self._share_terrain,
            )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]
