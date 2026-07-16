# -*- coding: utf-8 -*-
"""
Cognitive Diagnosis Service - 认知诊断服务

Implements simplified Bayesian Knowledge Tracing (BKT) and Elo-based rating
to estimate learner mastery from observed performance data.

Models:
1. BKT (Bayesian Knowledge Tracing): Estimates P(know) from correct/incorrect trials
2. Elo Rating: Dynamic difficulty estimation based on performance
3. Forgetting Curve: Time-decayed mastery adjustment

All models work on data from learner_mastery and learner_errors tables.
"""
from __future__ import annotations
import logging
import math
import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DiagnosisResult:
    """Output of cognitive diagnosis for one knowledge point."""
    kp_id: str
    kp_name: str = ""
    mastery_prob: float = 0.0  # P(know) from BKT
    confidence: float = 0.0
    elo_rating: float = 1500.0
    recommended_difficulty: float = 0.5
    struggling: bool = False
    forgotten: bool = False
    next_review_days: int = 1


class CognitiveDiagnosisService:
    """Cognitive diagnosis using BKT + Elo + forgetting curve."""

    # BKT default parameters
    P_INIT = 0.3       # P(know) at start
    P_TRANSIT = 0.15   # P(learn) per practice
    P_SLIP = 0.10      # P(slip) - know but wrong
    P_GUESS = 0.20     # P(guess) - don't know but correct

    def __init__(self):
        pass

    def estimate_mastery_bkt(self, correct_count: int, total_count: int,
                              mastery_history: List[Dict] = None) -> float:
        """Bayesian Knowledge Tracing estimation.

        Simplified single-KP BKT. Returns P(know) after observed trials.
        """
        if total_count == 0:
            return self.P_INIT

        # Start with prior
        p_know = self.P_INIT

        # Simulate each trial
        for i in range(total_count):
            # Before trial: P(know) = previous P(know) + P(not_know) * P_TRANSIT
            p_learned = (1 - p_know) * self.P_TRANSIT
            p_before = p_know + p_learned

            # After trial: update based on whether correct
            correct_ratio = correct_count / total_count
            # Simplified: use aggregate
            p_correct = p_before * (1 - self.P_SLIP) + (1 - p_before) * self.P_GUESS
            if correct_ratio > 0.5:
                # Evidence of correctness
                p_know = (p_before * (1 - self.P_SLIP)) / max(p_correct, 0.01)
            else:
                # Evidence of error
                p_know = (p_before * self.P_SLIP) / max(p_correct, 0.01)

        return max(0.01, min(0.99, p_know))

    def estimate_elo_change(self, learner_rating: float, kp_difficulty: float,
                             correct: bool, k_factor: int = 32) -> Tuple[float, float]:
        """Elo rating update for both learner and KP.
        Returns (new_learner_rating, new_kp_difficulty).
        """
        expected = 1.0 / (1.0 + math.pow(10, (kp_difficulty - learner_rating) / 400.0))
        score = 1.0 if correct else 0.0
        change = k_factor * (score - expected)
        return (learner_rating + change, kp_difficulty - change * 0.5)

    def apply_forgetting_curve(self, mastery: float, days_since_last_practice: float) -> float:
        """Ebbinghaus forgetting curve: mastery decays exponentially."""
        if days_since_last_practice <= 0:
            return mastery
        decay = math.exp(-0.1 * days_since_last_practice)
        retained = mastery * decay + 0.1 * (1 - decay)  # floor at 0.1
        return retained

    def estimate_next_review_days(self, mastery: float) -> int:
        """Estimate optimal days until next review."""
        if mastery < 0.3:
            return 1
        elif mastery < 0.6:
            return 3
        elif mastery < 0.8:
            return 7
        else:
            return 14

    def diagnose(self, kp_id: str, kp_name: str = "",
                 correct_count: int = 0, total_count: int = 0,
                 mastery_history: List[Dict] = None,
                 last_practiced_days: float = 999,
                 current_level: float = 0.0,
                 current_confidence: float = 0.0) -> DiagnosisResult:
        """Full diagnosis for one KP using all models."""
        # BKT mastery
        bkt_mastery = self.estimate_mastery_bkt(correct_count, total_count, mastery_history)

        # Apply forgetting curve if there's history
        if last_practiced_days < 999:
            effective_mastery = self.apply_forgetting_curve(bkt_mastery, last_practiced_days)
        else:
            effective_mastery = bkt_mastery

        # Blend with DB-stored level (weighted average)
        if total_count > 0:
            blended = 0.6 * effective_mastery + 0.4 * current_level
        else:
            blended = max(current_level, bkt_mastery)

        # Determine difficulty recommendation
        if blended < 0.3:
            rec_diff = 0.2  # very easy
            struggling = True
        elif blended < 0.6:
            rec_diff = 0.4  # easy
            struggling = True if current_level < 0.3 else False
        elif blended < 0.8:
            rec_diff = 0.6  # moderate
            struggling = False
        else:
            rec_diff = 0.8  # challenging
            struggling = False

        forgotten = (last_practiced_days > 14 and current_level > 0.5)

        return DiagnosisResult(
            kp_id=kp_id,
            kp_name=kp_name,
            mastery_prob=round(blended, 3),
            confidence=round(current_confidence + 0.1 * total_count, 3),
            recommended_difficulty=rec_diff,
            struggling=struggling,
            forgotten=forgotten,
            next_review_days=self.estimate_next_review_days(blended),
        )


# ── Singleton ──
_diagnosis_service: Optional[CognitiveDiagnosisService] = None


def get_diagnosis_service() -> CognitiveDiagnosisService:
    global _diagnosis_service
    if _diagnosis_service is None:
        _diagnosis_service = CognitiveDiagnosisService()
    return _diagnosis_service