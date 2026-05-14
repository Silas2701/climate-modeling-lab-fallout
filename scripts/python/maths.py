"""Module for math related formulas."""

import numpy as np
from scipy.stats import norm

DEFAULT_CENTRAL_MASS: float = 0.66
"""The default probability mass that should be distributed across the central 50%."""

DEFAULT_N_BINS: int = 10
"""The default number of bins to be used for the gaussian distribution."""

def _sigma_from_symmetric_interval(mu, a, b, central_mass):
    """
    Compute sigma for a normal distribution N(mu, sigma^2) such that
    P(a <= X <= b) = central_mass, assuming the interval is symmetric
    around mu.

    Args:
        mu (float): Mean of the distribution.
        a (float): Lower interval bound (must be symmetric around mu).
        b (float): Upper interval bound (must be symmetric around mu).
        central_mass (float): Desired probability mass in [a, b].

    Returns
        float: The value for sigma.
    """

    # 1. Check symmetry (important for correctness)
    if not np.isclose(mu - a, b - mu):
        raise ValueError("Interval [a, b] must be symmetric around mu")

    # 2. Half-width of the interval
    half_width = b - mu   # same as mu - a

    # 3. Convert central mass → one-sided cumulative probability
    # central_mass = P(|Z| <= k) = 2Φ(k) - 1
    # ⇒ Φ(k) = (1 + central_mass) / 2
    target_cdf = (1 + central_mass) / 2

    # 4. Convert to z-score
    z = norm.ppf(target_cdf)

    # 5. Map back to sigma
    sigma = half_width / z

    return sigma

def gaussian_bin_probs(n_bins: int = DEFAULT_N_BINS, central_mass: float = DEFAULT_CENTRAL_MASS) -> np.ndarray:
    """Compute gaussian bin probabilities based on central mass.
    
    Args:
        central_mass (float): Probability mass that should be spread in the central 50%. 
        n_bins (int): Number of bins to use for distributing the probabilities.

    Returns:
        np.ndarray: Binned probabilities.
    """
    edges = np.linspace(0, 1, n_bins + 1)

    mu = np.mean(edges)
    a, b = [0.25, 0.75]
    sigma = _sigma_from_symmetric_interval(mu, a, b, central_mass)

    # raw bin probabilities
    probs = norm.cdf(edges[1:], mu, sigma) - norm.cdf(edges[:-1], mu, sigma)

    # normalize to sum to 1
    probs /= probs.sum()

    return probs
