# -*- coding: utf-8 -*-
"""
Evidence Tracker Service - 证据链追踪服务

Tracks the provenance of every claim made in generated content.
Each claim is linked to its source (KB document, knowledge point, rule).
Supports citation extraction, confidence scoring, and audit trail.

Usage:
    tracker = EvidenceTracker()
    tracker.add_claim(claim_text, source, confidence)
    report = tracker.generate_report()
"""
from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvidenceClaim:
    """A single claim with its evidence trail."""
    claim_id: str
    claim_text: str
    source_type: str  # kb_document / knowledge_point / rule / llm_generated
    source_id: str = ""
    source_name: str = ""
    confidence: str = "medium"  # high / medium / low
    verified: bool = False
    verification_method: str = ""
    created_at: str = ""


@dataclass
class EvidenceReport:
    """Complete evidence audit report for generated content."""
    content_id: str = ""
    content_title: str = ""
    total_claims: int = 0
    verified_claims: int = 0
    unverified_claims: int = 0
    claims: List[EvidenceClaim] = field(default_factory=list)
    overall_confidence: str = "medium"
    missing_sources: List[str] = field(default_factory=list)
    generated_at: str = ""


class EvidenceTracker:
    """Tracks evidence for all claims in generated content."""

    def __init__(self):
        self._claims: Dict[str, EvidenceClaim] = {}
        self._content_title: str = ""

    def start_tracking(self, content_id: str, title: str = "") -> None:
        """Start a new evidence tracking session."""
        self._claims = {}
        self._content_title = title or content_id

    def add_claim(self, claim_text: str, source_type: str = "llm_generated",
                  source_id: str = "", source_name: str = "",
                  confidence: str = "medium") -> str:
        """Add a claim with its evidence source. Returns claim_id."""
        cid = str(uuid.uuid4())[:8]
        claim = EvidenceClaim(
            claim_id=cid,
            claim_text=claim_text[:500],
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            confidence=confidence,
            created_at=datetime.now().isoformat(),
        )
        self._claims[cid] = claim
        return cid

    def verify_claim(self, claim_id: str, method: str = "auto") -> bool:
        """Mark a claim as verified."""
        if claim_id in self._claims:
            self._claims[claim_id].verified = True
            self._claims[claim_id].verification_method = method
            return True
        return False

    def generate_report(self, content_id: str = "") -> EvidenceReport:
        """Generate complete evidence report."""
        claims_list = list(self._claims.values())
        verified = [c for c in claims_list if c.verified]
        missing = [
            c.claim_text[:100]
            for c in claims_list
            if not c.verified and c.confidence == "high"
        ]

        # Overall confidence
        high_count = len([c for c in claims_list if c.confidence == "high"])
        if not claims_list:
            overall = "low"
        elif verified and len(verified) / len(claims_list) > 0.8:
            overall = "high" if high_count > len(claims_list) / 2 else "medium"
        elif len(verified) / len(claims_list) > 0.5:
            overall = "medium"
        else:
            overall = "low"

        return EvidenceReport(
            content_id=content_id,
            content_title=self._content_title,
            total_claims=len(claims_list),
            verified_claims=len(verified),
            unverified_claims=len(claims_list) - len(verified),
            claims=claims_list,
            overall_confidence=overall,
            missing_sources=missing,
            generated_at=datetime.now().isoformat(),
        )

    def track_content(self, content_data: Dict[str, Any],
                       evidence_map: List[Dict[str, Any]],
                       content_id: str = "") -> EvidenceReport:
        """Track evidence for a complete content item from its evidence_map."""
        title = content_data.get("title", "") if isinstance(content_data, dict) else ""
        self.start_tracking(content_id, title)

        # Add claims from evidence_map
        for em in evidence_map:
            cid = self.add_claim(
                claim_text=em.get("claim", ""),
                source_type=em.get("source_type", "kb_document"),
                source_id=em.get("source", ""),
                source_name=em.get("source_name", ""),
                confidence=em.get("confidence", "medium"),
            )
            if em.get("verified", False):
                self.verify_claim(cid)

        # Extract claims from content sections
        if isinstance(content_data, dict):
            for section in content_data.get("sections", []):
                body = section.get("body", "")
                # Check for citation markers [source:xxx]
                import re
                citations = re.findall(r'\[来源[:：]([^\]]+)\]', body)
                for src in citations:
                    self.add_claim(
                        claim_text=body[:100] + "...",
                        source_type="kb_document",
                        source_name=src.strip(),
                        confidence="high",
                    )

        return self.generate_report(content_id)


# ── Singleton ──
_evidence_tracker: Optional[EvidenceTracker] = None


def get_evidence_tracker() -> EvidenceTracker:
    global _evidence_tracker
    if _evidence_tracker is None:
        _evidence_tracker = EvidenceTracker()
    return _evidence_tracker