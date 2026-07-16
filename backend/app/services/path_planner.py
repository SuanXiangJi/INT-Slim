# -*- coding: utf-8 -*-
"""
Adaptive Path Planner - 自适应学习路径规划服务

Generates optimized learning paths based on:
1. Knowledge graph (prerequisite chains)
2. Learner mastery (known vs unknown KPs)
3. Cognitive load constraints
4. Goal decomposition
5. Time budget

Uses topological sort + constraint satisfaction for path optimization.
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class PathNode:
    """A single node in the learning path."""
    kp_id: str
    kp_name: str
    difficulty: float = 0.5
    estimated_hours: float = 2.0
    mastery_before: float = 0.0
    expected_gain: float = 0.3
    priority: int = 0  # higher = more important
    status: str = "pending"  # pending / ready / learning / completed


@dataclass
class LearningPath:
    """Complete learning path."""
    goal: str = ""
    nodes: List[PathNode] = field(default_factory=list)
    total_hours: float = 0.0
    weekly_schedule: str = ""
    path_summary: str = ""


class PathPlanner:
    """Adaptive learning path planner."""

    def __init__(self):
        pass

    def plan(self, goal: str,
             available_kps: List[Dict[str, Any]],
             prerequisite_map: Dict[str, List[str]],
             learner_mastery: Dict[str, Dict[str, Any]],
             cognitive_load: float = 0.0,
             load_threshold: float = 0.8,
             max_weekly_hours: int = 10,
             focus_areas: List[str] = None) -> LearningPath:
        """Generate optimized learning path.

        Args:
            goal: Learning goal description
            available_kps: All available knowledge points [{id, name, difficulty, description}]
            prerequisite_map: {kp_id: [prerequisite_kp_ids]}
            learner_mastery: {kp_id: {level, confidence, last_assessed}}
            cognitive_load: Current cognitive load estimate
            load_threshold: Max allowed load
            max_weekly_hours: Maximum study hours per week
            focus_areas: Areas learner should focus on

        Returns:
            LearningPath with ordered nodes
        """
        # Build ID->KP map
        kp_map = {k["id"]: k for k in available_kps}
        target_ids = set(kp_map.keys())

        # 1. Get unmastered KPs
        unmastered = set()
        for kid in target_ids:
            mastery = learner_mastery.get(kid, {}).get("level", 0)
            if mastery < 0.7:  # Not yet mastered
                unmastered.add(kid)

        # If none unmastered, all are available
        if not unmastered:
            unmastered = target_ids.copy()

        # 2. Filter by focus areas
        if focus_areas:
            focused = set()
            for kid in unmastered:
                kp = kp_map.get(kid, {})
                kp_name = kp.get("name", "").lower()
                cat = kp.get("category", "").lower()
                if any(fa.lower() in kp_name or fa.lower() in cat for fa in focus_areas):
                    focused.add(kid)
            if focused:
                unmastered = focused

        # 3. Find prerequisites for unmastered KPs
        all_needed = set(unmastered)
        queue = deque(unmastered)
        while queue:
            kid = queue.popleft()
            prereqs = prerequisite_map.get(kid, [])
            for p in prereqs:
                if p not in all_needed and p in kp_map:
                    mastery = learner_mastery.get(p, {}).get("level", 0)
                    if mastery < 0.7:
                        all_needed.add(p)
                        queue.append(p)

        # 4. Topological sort for learning order
        sorted_nodes = self._topological_sort(all_needed, prerequisite_map, kp_map)

        # 5. Assign estimated hours and adjust for load
        load_budget = max(1, (load_threshold - cognitive_load) * max_weekly_hours)
        total_hours = 0

        path_nodes = []
        for i, (kid, depth) in enumerate(sorted_nodes):
            kp = kp_map.get(kid, {})
            difficulty = kp.get("difficulty", 0.5)
            base_hours = 1.0 + difficulty * 3  # harder KPs take longer
            # Adjust for learner mastery
            mastery = learner_mastery.get(kid, {}).get("level", 0)
            if mastery > 0.3:
                base_hours *= max(0.5, 1.0 - mastery * 0.5)

            # Cap to load budget for first week
            if i < 3:  # first few KPs
                base_hours = min(base_hours, load_budget / max(1, 3 - i))

            total_hours += base_hours
            path_nodes.append(PathNode(
                kp_id=kid,
                kp_name=kp.get("name", kid),
                difficulty=difficulty,
                estimated_hours=round(base_hours, 1),
                mastery_before=mastery,
                expected_gain=round(0.5 - mastery * 0.3, 2),
                priority=len(sorted_nodes) - i,  # later in chain = higher priority
                status="ready" if i == 0 else "pending",
            ))

        # 6. Generate schedule
        weeks = max(1, math.ceil(total_hours / max_weekly_hours))
        schedule = []
        for w in range(weeks):
            start = w * max_weekly_hours
            end = min((w + 1) * max_weekly_hours, total_hours)
            week_hours = end - start
            week_nodes = [n.kp_name for n in path_nodes
                          if sum(n2.estimated_hours for n2 in path_nodes[:path_nodes.index(n)]) < end
                          and sum(n2.estimated_hours for n2 in path_nodes[:path_nodes.index(n)]) >= start]
            if week_nodes:
                schedule.append(f"第{w+1}周 ({week_hours:.0f}小时): {' → '.join(week_nodes)}")

        path_summary = (f"学习路径规划完成: {len(path_nodes)} 个知识点, "
                       f"预计 {total_hours:.0f} 小时, {weeks} 周完成")

        return LearningPath(
            goal=goal,
            nodes=path_nodes,
            total_hours=round(total_hours, 1),
            weekly_schedule="\n".join(schedule[:8]),
            path_summary=path_summary,
        )

    def _topological_sort(self, kp_ids: Set[str],
                           prerequisite_map: Dict[str, List[str]],
                           kp_map: Dict[str, Dict]) -> List[tuple]:
        """Topological sort with depth tracking. Returns [(kp_id, depth), ...]."""
        in_degree = defaultdict(int)
        children = defaultdict(list)

        for kid in kp_ids:
            if kid not in in_degree:
                in_degree[kid] = 0
            for prereq in prerequisite_map.get(kid, []):
                if prereq in kp_ids:
                    in_degree[kid] = in_degree.get(kid, 0) + 1
                    children[prereq].append(kid)

        # Kahn's algorithm with depth
        queue = deque()
        depths = {}
        for kid in kp_ids:
            if in_degree.get(kid, 0) == 0:
                queue.append(kid)
                depths[kid] = 0

        result = []
        while queue:
            kid = queue.popleft()
            result.append((kid, depths.get(kid, 0)))
            for child in children.get(kid, []):
                in_degree[child] -= 1
                depths[child] = max(depths.get(child, 0), depths.get(kid, 0) + 1)
                if in_degree[child] == 0:
                    queue.append(child)

        # Add any remaining (cycles in graph)
        for kid in kp_ids:
            if kid not in {r[0] for r in result}:
                result.append((kid, 99))

        return result

    def recommend_next_kp(self, path: LearningPath,
                           learner_mastery: Dict[str, Dict]) -> Optional[str]:
        """Recommend the next KP to study based on current progress."""
        for node in path.nodes:
            if node.status == "ready":
                return node.kp_id
            elif node.status == "learning":
                # Check if prerequisites met
                mastery = learner_mastery.get(node.kp_id, {}).get("level", 0)
                if mastery > 0.3:
                    return node.kp_id
        return None


# ── Singleton ──
_path_planner: Optional[PathPlanner] = None


def get_path_planner() -> PathPlanner:
    global _path_planner
    if _path_planner is None:
        _path_planner = PathPlanner()
    return _path_planner