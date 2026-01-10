"""Shared rating generation logic for agents."""

import random
from typing import Literal


def generate_rating_value(
    dna_factor: float, factor_type: Literal["behavior_factor", "service_quality"]
) -> int:
    """Generate rating value based on DNA quality factor using Gaussian distribution."""
    if dna_factor < 0.3:
        mean = 3.5
        std_dev = 0.9 if factor_type == "service_quality" else 0.8
    elif dna_factor < 0.7:
        mean = 4.2
        std_dev = 0.7 if factor_type == "service_quality" else 0.6
    else:
        mean = 4.5 if factor_type == "service_quality" else 4.7
        std_dev = 0.5 if factor_type == "service_quality" else 0.4

    rating = int(round(random.gauss(mean, std_dev)))
    return max(1, min(5, rating))


def should_submit_rating(rating_value: int) -> bool:
    """Determine if rating should be submitted based on value."""
    is_exceptional = rating_value <= 2 or rating_value == 5
    threshold = 0.85 if is_exceptional else 0.60
    return random.random() < threshold
