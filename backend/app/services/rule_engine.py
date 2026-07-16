# -*- coding: utf-8 -*-
"""
Rule Engine - 规则推断引擎

Defines and evaluates explicit rules for content quality, prerequisite compliance,
cognitive load bounds, and normative constraints. Each rule produces a typed result
with severity, explanation, and suggested fix.

Usage:
    engine = RuleEngine()
    results = engine.evaluate("content_quality", content=content, learner=learner)
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class RuleResult:
    """Single rule evaluation result."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str = "minor"  # critical / major / minor
    message: str = ""
    suggestion: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    """A single checkable rule."""
    rule_id: str
    name: str
    category: str  # prerequisite / load / quality / normative / coverage
    description: str
    severity: str
    enabled: bool = True

    def __post_init__(self):
        self._check_fn: Optional[Callable] = None

    def set_check(self, fn: Callable) -> None:
        self._check_fn = fn

    async def evaluate(self, **context) -> RuleResult:
        if not self._check_fn:
            return RuleResult(self.rule_id, self.name, True, self.severity, "未实现检查")
        try:
            return await self._check_fn(**context)
        except Exception as e:
            logger.exception("Rule %s error: %s", self.rule_id, e)
            return RuleResult(self.rule_id, self.name, False, "critical",
                              f"规则检查异常: {e}")


# ── Rule Engine ──────────────────────────────────────────────────────

class RuleEngine:
    """Central rule engine - manages and evaluates all rules."""

    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Register built-in rules with their check functions."""
        # ── Prerequisite rules ──
        prereq_covered = Rule(
            "prereq_covered", "前置知识覆盖检查", "prerequisite",
            "目标知识点的前置技能必须已掌握（level >= 0.3）", "major")
        prereq_covered.set_check(self._check_prereq_covered)
        self.register(prereq_covered)

        # ── Load rules ──
        load_ok = Rule(
            "load_ok", "认知负荷检查", "load",
            "学习计划总难度不应超过学员认知负荷阈值", "critical")
        load_ok.set_check(self._check_load)
        self.register(load_ok)

        # ── Quality rules ──
        evidence_required = Rule(
            "evidence_required", "证据引用检查", "quality",
            "教学内容中的关键主张应引用知识库证据", "major")
        evidence_required.set_check(self._check_evidence)
        self.register(evidence_required)

        has_structure = Rule(
            "has_structure", "内容结构完整性检查", "quality",
            "讲义应包含标题、正文和小节结构", "minor")
        has_structure.set_check(self._check_structure)
        self.register(has_structure)

        # ── Coverage rules ──
        kp_coverage = Rule(
            "kp_coverage", "知识点覆盖检查", "coverage",
            "生成的内容应覆盖目标知识点的核心描述", "major")
        kp_coverage.set_check(self._check_kp_coverage)
        self.register(kp_coverage)

    def register(self, rule: Rule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule '{rule.rule_id}' already registered")
        self._rules[rule.rule_id] = rule
        logger.info("Rule registered: %s (%s)", rule.rule_id, rule.name)

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)

    def list_rules(self, category: Optional[str] = None) -> List[Rule]:
        if category:
            return [r for r in self._rules.values()
                    if r.category == category and r.enabled]
        return [r for r in self._rules.values() if r.enabled]

    async def evaluate(self, category: str = "all",
                       **context) -> List[RuleResult]:
        """Evaluate all enabled rules in a category. Returns list of RuleResults."""
        target_rules = self.list_rules(category) if category != "all" else self.list_rules()
        results = []
        for rule in target_rules:
            result = await rule.evaluate(**context)
            results.append(result)
            if not result.passed:
                logger.info("Rule FAILED: %s - %s", rule.rule_id, result.message)
        return results

    async def evaluate_all(self, **context) -> List[RuleResult]:
        """Evaluate ALL enabled rules across all categories."""
        return await self.evaluate("all", **context)

    # ── Check function implementations ──

    async def _check_prereq_covered(self, **ctx) -> RuleResult:
        """Check that prerequisites for target KP are at minimal mastery level."""
        mastery = ctx.get("mastery", {})
        target_kp = ctx.get("target_kp", "")
        prereqs = ctx.get("prerequisites", [])

        uncovered = []
        for p in prereqs:
            p_id = p if isinstance(p, str) else p.get("id", "")
            if p_id and mastery.get(p_id, {}).get("level", 0) < 0.3:
                uncovered.append(p_id)

        if uncovered:
            return RuleResult(
                "prereq_covered", "前置知识覆盖检查", False, "major",
                f"前置知识点未达标: {uncovered}",
                "建议先巩固前置知识点",
                {"uncovered": uncovered})
        return RuleResult("prereq_covered", "前置知识覆盖检查", True, "major", "前置知识全部达标")

    async def _check_load(self, **ctx) -> RuleResult:
        """Check cognitive load threshold."""
        current_load = ctx.get("cognitive_load", 0.0)
        threshold = ctx.get("load_threshold", 0.8)
        plan_difficulty = ctx.get("plan_difficulty", 0.5)

        estimated = current_load + plan_difficulty * 0.3
        if estimated > threshold:
            return RuleResult(
                "load_ok", "认知负荷检查", False, "critical",
                f"预计总负荷 {estimated:.2f} 超过阈值 {threshold:.2f}",
                "建议降低难度或将学习计划分散到多天",
                {"current_load": current_load, "estimated": estimated, "threshold": threshold})
        return RuleResult("load_ok", "认知负荷检查", True, "critical", "负荷在安全范围")

    async def _check_evidence(self, **ctx) -> RuleResult:
        """Check that content cites evidence sources."""
        content = ctx.get("content", {})
        evidence_map = content.get("evidence_map", []) if isinstance(content, dict) else []

        if not evidence_map:
            return RuleResult(
                "evidence_required", "证据引用检查", False, "major",
                "内容没有引用任何知识来源",
                "请补充证据引用，标注每个主张的知识来源")
        low_conf = [e for e in evidence_map if e.get("confidence") == "low"]
        if low_conf:
            return RuleResult(
                "evidence_required", "证据引用检查", True, "minor",
                f"有 {len(low_conf)} 条低置信度引用，建议核实",
                details={"low_confidence": low_conf})
        return RuleResult("evidence_required", "证据引用检查", True, "major",
                          f"已引用 {len(evidence_map)} 条证据")

    async def _check_structure(self, **ctx) -> RuleResult:
        """Check content has minimum structure."""
        content = ctx.get("content", {})
        if isinstance(content, dict):
            sections = content.get("sections", []) if "sections" in content else []
            if not sections and not content.get("steps"):
                return RuleResult(
                    "has_structure", "内容结构完整性检查", False, "minor",
                    "内容缺少分段结构",
                    "建议添加章节标题和分段正文")
        return RuleResult("has_structure", "内容结构完整性检查", True, "minor", "结构完整")

    async def _check_kp_coverage(self, **ctx) -> RuleResult:
        """Check content covers target KP's key concepts."""
        content = ctx.get("content", {})
        kp = ctx.get("kp", {})

        kp_desc = (kp.get("description", "") if isinstance(kp, dict) else "")
        content_str = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)

        if kp_desc and len(kp_desc) > 10:
            keywords = [w.strip() for w in kp_desc[:200].replace(",", " ").split() if len(w.strip()) > 1]
            covered = [kw for kw in keywords[:5] if kw.lower() in content_str.lower()]
            if len(covered) < min(3, len(keywords[:5])):
                return RuleResult(
                    "kp_coverage", "知识点覆盖检查", False, "major",
                    f"内容未充分覆盖知识点关键词 ({len(covered)}/{min(5, len(keywords))})",
                    "请确保涵盖知识点的核心概念")
        return RuleResult("kp_coverage", "知识点覆盖检查", True, "major", "覆盖良好")


# ── Singleton ──
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine