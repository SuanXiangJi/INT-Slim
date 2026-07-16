"""
Ebbinghaus Forgetting Curve Service
R(t) = e^(-t/S) where S is memory strength (retention half-life)
"""
import math

# Standard Ebbinghaus review intervals (in hours from first study)
REVIEW_INTERVALS = [
    (0, 1.0),     # Just learned
    (1, 0.58),    # 1 hour
    (24, 0.44),   # 1 day
    (72, 0.36),   # 3 days
    (168, 0.29),  # 7 days
    (336, 0.23),  # 14 days
    (720, 0.17),  # 30 days
]

# Optimal review schedule (in hours after last review)
OPTIMAL_REVIEW_HOURS = [24, 72, 168, 336, 720]  # 1h, 1d, 3d, 7d, 14d, 30d

# Memory strength S in hours - larger = slower forgetting
# Base S=24 means e^(-24/24)≈37% retention after 1 day (classic Ebbinghaus)
REVIEW_BOOST = {
    0: 24.0,    # Initial study (base 24h half-life)
    1: 36.0,    # After 1st review (1.5x)
    2: 54.0,    # After 2nd review (2.25x)
    3: 81.0,    # After 3rd review (3.375x)
    4: 120.0,   # After 4th review (5x)
    5: 168.0,   # After 5th review (7x - ~1 week half-life)
}


def retention_at(t_hours: float, study_count: int = 1, last_review_hours: float = 0) -> float:
    """Calculate retention rate at time t_hours since first study.
    
    Args:
        t_hours: Hours since first study
        study_count: Number of reviews completed
        last_review_hours: Hours since last review
    
    Returns:
        Retention rate (0.0 to 1.0)
    """
    # Memory strength increases with each review
    S = REVIEW_BOOST.get(study_count, 24.0)
    
    # Calculate retention using Ebbinghaus formula
    # R = e^(-t/S) where t is time since LAST review
    if last_review_hours >= 0 and study_count > 0:
        retention = math.exp(-last_review_hours / S)
    else:
        retention = math.exp(-t_hours / S)
    
    return max(0.0, min(1.0, retention))
