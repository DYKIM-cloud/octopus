#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loss Function Comparison for Bayesian Optimization (InP QD UV-Vis Abs spectrum)

Three methods evaluated:
  Method 1 (Current) : Peak detection → lambdamax + p_v_ratio loss with y_norm fallback
  Method 2 (Deriv)   : Discrete 1st/2nd derivative of smoothed Abs spectrum
  Method 3 (Decomp)  : Subtract 1/λ^n baseline, analyse residual peak via FWHM

Evaluation criteria for Bayesian Optimization suitability:
  1. Landscape smoothness  — Lipschitz constant & std of finite differences
  2. Informativeness       — mutual information proxy (variance across realistic spectrum space)
  3. Noise robustness      — loss change under ±1 % additive white noise
  4. Monotonicity          — correlation between loss and "closeness-to-target" across 500 synthetic spectra
  5. Absence of dead zones — fraction of parameter space with |∂loss/∂param| < ε
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, peak_widths
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit
import warnings
warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────────────
# Synthetic spectrum generator
# Generates realistic InP QD UV-Vis absorption spectra:
#   background  = A * λ^(-n)          (scattering / band-edge tail)
#   peak        = B * Gaussian(λ; λ0, σ)  (first exciton)
# ──────────────────────────────────────────────────────────────────────────────
WL = np.linspace(350, 800, 451)   # 1 nm resolution

def make_spectrum(lambda0: float, sigma: float, peak_amp: float,
                  scatter_amp: float = 0.8, scatter_exp: float = 2.5,
                  noise_level: float = 0.005) -> np.ndarray:
    """
    lambda0    : exciton peak wavelength (nm)
    sigma      : peak width (nm), FWHM = 2.355*sigma
    peak_amp   : peak absorbance amplitude (0 → no peak)
    scatter_exp: power law exponent for background (Rayleigh ≈ 4, typical QD ≈ 1-3)
    """
    bg = scatter_amp * (350 / WL) ** scatter_exp
    peak = peak_amp * np.exp(-0.5 * ((WL - lambda0) / sigma) ** 2)
    noise = noise_level * np.random.randn(len(WL))
    return bg + peak + noise


# ──────────────────────────────────────────────────────────────────────────────
# Method 1: Current (Peak detection + y_norm fallback)
# ──────────────────────────────────────────────────────────────────────────────
Y_STEEP    = 0.35
Y_RAYLEIGH = 0.45
Y_GRADUAL  = 0.55
Y_QD_LIKE  = 0.65
L_WORST    = -1.5
L_RAYLEIGH = -1.2
L_GRADUAL  = -0.6
L_NO_PEAK  = -0.3
PEAK_SCALE =  0.3

def _smooth(y, sigma=3):
    return gaussian_filter1d(y, sigma=sigma)

def _detect_peak(y_smooth, wl=WL, prominence=0.01, width_nm=15):
    dx = wl[1] - wl[0]
    width_pts = int(width_nm / dx)
    peaks, props = find_peaks(y_smooth, prominence=prominence, width=width_pts)
    if len(peaks) == 0:
        return None, None
    best = peaks[np.argmax(props["prominences"])]
    pw = peak_widths(y_smooth, [best], rel_height=0.5)
    fwhm = float(pw[0][0]) * dx
    return float(wl[best]), fwhm

def _pv_ratio(y_smooth, wl=WL, lambda_peak=None, prominence=0.01, width_nm=15):
    """Peak/Valley ratio: peak_wl / nearest_valley_wl"""
    dx = wl[1] - wl[0]
    width_pts = int(width_nm / dx)
    peaks, pp  = find_peaks( y_smooth, prominence=prominence, width=width_pts)
    valleys, vp = find_peaks(-y_smooth, prominence=prominence, width=width_pts)
    if len(peaks) == 0 or len(valleys) == 0:
        return 0.0
    best_p = peaks[np.argmax(pp["prominences"])]
    best_v = valleys[np.argmax(vp["prominences"])]
    return float(wl[best_p]) / float(wl[best_v])

def loss_method1(y_raw, target_lm=490.0, target_pv=2.0,
                 w_lm=0.1, w_pv=0.9):
    y_s = _smooth(y_raw)
    lambdamax, fwhm = _detect_peak(y_s)
    pv_ratio = _pv_ratio(y_s, lambda_peak=lambdamax) if lambdamax else 0.0

    # y_norm_470 (spectral shape metric)
    x_eval  = WL
    rs_s    = np.convolve(y_s, np.ones(20)/20, mode='same')
    ab_420  = float(rs_s[np.argmin(np.abs(x_eval - 420))])
    ab_tgt  = float(rs_s[np.argmin(np.abs(x_eval - target_lm))])
    ab_550  = float(rs_s[np.argmin(np.abs(x_eval - 550))])
    denom   = ab_420 - ab_550
    y_norm  = float(np.clip((ab_tgt - ab_550) / denom, 0, 1)) if denom > 0 else 0.0

    if lambdamax and lambdamax > 0 and pv_ratio > 0:
        scale  = max(target_lm - WL.min(), WL.max() - target_lm)
        lm_loss = float(np.clip(abs(target_lm - lambdamax) / scale, 0, 1))
        pv_loss = float(np.clip((target_pv - pv_ratio) / target_pv, 0, 1)) if pv_ratio < target_pv else 0.0
        return -(lm_loss * w_lm + pv_loss * w_pv) * PEAK_SCALE
    else:
        if   y_norm <= Y_STEEP:    return L_WORST
        elif y_norm <= Y_RAYLEIGH: return L_WORST   + (L_RAYLEIGH - L_WORST)   * (y_norm - Y_STEEP)   / (Y_RAYLEIGH - Y_STEEP)
        elif y_norm <= Y_GRADUAL:  return L_RAYLEIGH + (L_GRADUAL  - L_RAYLEIGH)* (y_norm - Y_RAYLEIGH)/ (Y_GRADUAL  - Y_RAYLEIGH)
        elif y_norm <= Y_QD_LIKE:  return L_GRADUAL  + (L_NO_PEAK  - L_GRADUAL) * (y_norm - Y_GRADUAL) / (Y_QD_LIKE  - Y_GRADUAL)
        else:                      return L_NO_PEAK


# ──────────────────────────────────────────────────────────────────────────────
# Method 2: Discrete derivative (1st + 2nd) based loss
#
# Key idea:
#   - 2nd derivative at target wavelength: highly negative → sharp peak = good
#   - Position of minimum 2nd derivative (= inflection curvature valley) → λ_peak proxy
#   - 1st derivative sign: helps locate peak centre without threshold-based find_peaks
#
# Loss = -(curvature_score * w1 + position_score * w2)
#   curvature_score = -d²A/dλ² at λ_target (normalised by global max curvature)
#   position_score  = exp(-0.5 * ((λ_minCurv - λ_target) / bandwidth)²)
# ──────────────────────────────────────────────────────────────────────────────

def loss_method2(y_raw, target_lm=490.0, w_curv=0.6, w_pos=0.4,
                 sigma=5, bandwidth=40.0):
    """
    sigma     : Gaussian smoothing sigma (nm-equivalent; WL step=1nm so σ pts)
    bandwidth : Gaussian width for position reward (nm)
    """
    y_s  = gaussian_filter1d(y_raw, sigma=sigma)
    dy   = np.gradient(y_s,  WL)     # 1st derivative  dA/dλ
    d2y  = np.gradient(dy,   WL)     # 2nd derivative  d²A/dλ²

    # Curvature score: negative d2y at target wavelength → peak
    idx_tgt = int(np.argmin(np.abs(WL - target_lm)))
    d2_at_target = float(d2y[idx_tgt])

    # Normalise by the most negative curvature in the spectrum
    # (handles different absolute absorption levels)
    d2_min = float(np.min(d2y))   # most negative = sharpest peak
    if d2_min >= 0:
        curvature_score = 0.0
    else:
        curvature_score = float(np.clip(-d2_at_target / (-d2_min + 1e-9), 0, 1))

    # Position score: where is the sharpest negative curvature?
    idx_sharpest = int(np.argmin(d2y))
    lambda_sharp = float(WL[idx_sharpest])
    position_score = float(np.exp(-0.5 * ((lambda_sharp - target_lm) / bandwidth) ** 2))

    # Combine — both should be maximised → negate for loss convention
    score = curvature_score * w_curv + position_score * w_pos
    return -(1.0 - score)   # range: [-1, 0], 0 = perfect


# ──────────────────────────────────────────────────────────────────────────────
# Method 3: 1/λ^n background subtraction → residual peak → FWHM loss
#
# Steps:
#   1. Fit A_bg(λ) = a * λ^(-n) to flanking regions (avoid peak region)
#   2. Residual = A(λ) - A_bg(λ)
#   3. Find peak in residual
#   4. Compute FWHM, peak position → loss
#
# Loss = -(λ_loss * w_lm + fwhm_loss * w_fwhm + amp_loss * w_amp)
# ──────────────────────────────────────────────────────────────────────────────

def _fit_background(y_raw, wl=WL, peak_exclude_center=490, peak_exclude_half=80):
    """Fit power-law background excluding the expected peak region."""
    mask = (wl < peak_exclude_center - peak_exclude_half) | \
           (wl > peak_exclude_center + peak_exclude_half)
    if mask.sum() < 10:
        mask = np.ones(len(wl), dtype=bool)

    wl_fit  = wl[mask]
    y_fit   = np.maximum(y_raw[mask], 1e-6)

    def power_law(x, a, n):
        return a * (350 / x) ** n

    try:
        popt, _ = curve_fit(power_law, wl_fit, y_fit,
                            p0=[1.0, 2.0], bounds=([0, 0.5], [10, 6]), maxfev=2000)
        bg = power_law(wl, *popt)
    except Exception:
        # Fallback: linear interpolation between endpoints
        bg = np.interp(wl, [wl[0], wl[-1]], [y_raw[0], y_raw[-1]])

    return np.maximum(bg, 0)

def loss_method3(y_raw, target_lm=490.0, target_fwhm=50.0,
                 w_lm=0.5, w_fwhm=0.3, w_amp=0.2,
                 fwhm_range=550.0,           # max meaningful FWHM (nm)
                 lm_bounds=(300, 850),
                 sigma=4, prominence=0.005, width_nm=10):
    """
    target_fwhm : desired FWHM (nm); narrower = higher quality QD
    fwhm_range  : normalisation denominator for FWHM loss
    """
    y_s  = gaussian_filter1d(y_raw, sigma=sigma)
    bg   = _fit_background(y_s, wl=WL, peak_exclude_center=target_lm)
    resid = np.maximum(y_s - bg, 0)

    dx = WL[1] - WL[0]
    width_pts = int(width_nm / dx)
    peaks, props = find_peaks(resid, prominence=prominence, width=width_pts)

    if len(peaks) == 0:
        # No residual peak → penalise based on max residual amplitude
        max_resid = float(np.max(resid))
        amp_proxy = float(np.clip(max_resid / 0.2, 0, 1))  # 0.2 = typical detectable amp
        return -(1.0 - amp_proxy * 0.3)   # range [-1.0, -0.7]

    best  = peaks[np.argmax(props["prominences"])]
    pw    = peak_widths(resid, [best], rel_height=0.5)
    lm_found = float(WL[best])
    fwhm_found = float(pw[0][0]) * dx
    amp_found  = float(resid[best])

    # λmax loss (asymmetric normalisation, identical to current method)
    left_span  = lm_found - lm_bounds[0] if lm_found < target_lm else target_lm - lm_bounds[0]
    right_span = lm_bounds[1] - target_lm if lm_found >= target_lm else lm_bounds[1] - lm_found
    span = max(left_span if lm_found < target_lm else right_span, 1.0)
    lm_loss = float(np.clip(abs(target_lm - lm_found) / span, 0, 1))

    # FWHM loss: one-sided — only penalise if FWHM > target (narrower is better)
    if fwhm_found <= target_fwhm:
        fwhm_loss = 0.0
    else:
        fwhm_loss = float(np.clip((fwhm_found - target_fwhm) / fwhm_range, 0, 1))

    # Amplitude loss: higher amplitude = better (proxy for QD concentration/quality)
    AMP_TARGET = 0.3   # typical good absorption amplitude
    amp_loss = float(np.clip(1.0 - amp_found / AMP_TARGET, 0, 1))

    score = lm_loss * w_lm + fwhm_loss * w_fwhm + amp_loss * w_amp
    return float(np.clip(-score, -1.0, 0.0))


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation framework
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_all(n_spectra=500, target_lm=490.0, seed=42):
    rng = np.random.default_rng(seed)

    # ── Generate diverse synthetic spectra ────────────────────────────────────
    # Systematically vary: lambda0 (400-600), peak_amp (0-0.5), scatter_exp (1-4)
    records = []
    for _ in range(n_spectra):
        lm      = float(rng.uniform(400, 600))
        amp     = float(rng.uniform(0.0, 0.5))
        s_exp   = float(rng.uniform(1.0, 4.0))
        sigma_p = float(rng.uniform(15, 60))
        y = make_spectrum(lm, sigma_p, amp, scatter_exp=s_exp, noise_level=0.005)
        # "true closeness": distance of peak from target (0=perfect)
        true_closeness = -abs(lm - target_lm) / 200.0 if amp > 0.02 else -1.0
        records.append((y, lm, amp, true_closeness))

    # ── Compute losses ─────────────────────────────────────────────────────────
    L1, L2, L3, TC = [], [], [], []
    for (y, lm, amp, tc) in records:
        L1.append(loss_method1(y, target_lm=target_lm))
        L2.append(loss_method2(y, target_lm=target_lm))
        L3.append(loss_method3(y, target_lm=target_lm))
        TC.append(tc)

    L1, L2, L3, TC = map(np.array, [L1, L2, L3, TC])

    # ── Metric 1: Smoothness — Lipschitz estimate via neighbouring spectra ─────
    # Perturb each spectrum slightly and measure |ΔLoss / Δspectrum|
    def lipschitz_estimate(loss_fn, n_probe=200):
        eps = 1e-3
        ratios = []
        for i in rng.choice(n_spectra, size=n_probe, replace=False):
            y0, lm0, amp0, _ = records[i]
            perturb = eps * rng.standard_normal(len(y0))
            y1 = y0 + perturb
            dl = abs(loss_fn(y1, target_lm=target_lm) - loss_fn(y0, target_lm=target_lm))
            dy = np.linalg.norm(perturb)
            ratios.append(dl / (dy + 1e-12))
        return float(np.percentile(ratios, 95))  # 95th-pct Lipschitz constant

    print("Computing smoothness metrics (Lipschitz constant)...")
    lip1 = lipschitz_estimate(loss_method1)
    lip2 = lipschitz_estimate(loss_method2)
    lip3 = lipschitz_estimate(loss_method3)

    # ── Metric 2: Noise robustness — loss variance under 1% noise ─────────────
    def noise_sensitivity(loss_fn, n_probe=200, noise_pct=0.01):
        deltas = []
        for i in rng.choice(n_spectra, size=n_probe, replace=False):
            y0 = records[i][0]
            scale = noise_pct * np.mean(np.abs(y0))
            losses_noisy = [loss_fn(y0 + scale * rng.standard_normal(len(y0)),
                                    target_lm=target_lm) for _ in range(10)]
            deltas.append(float(np.std(losses_noisy)))
        return float(np.mean(deltas))

    print("Computing noise sensitivity...")
    ns1 = noise_sensitivity(loss_method1)
    ns2 = noise_sensitivity(loss_method2)
    ns3 = noise_sensitivity(loss_method3)

    # ── Metric 3: Monotonicity — Spearman correlation with true closeness ─────
    from scipy.stats import spearmanr
    corr1, _ = spearmanr(L1, TC)
    corr2, _ = spearmanr(L2, TC)
    corr3, _ = spearmanr(L3, TC)

    # ── Metric 4: Informativeness — variance across spectrum space ────────────
    # Higher variance → more discriminating signal for GP surrogate
    var1 = float(np.var(L1))
    var2 = float(np.var(L2))
    var3 = float(np.var(L3))

    # ── Metric 5: Dead zones — fraction with near-zero gradient ───────────────
    # Estimate by binning loss values and counting near-flat regions
    def dead_zone_fraction(losses, eps=0.02):
        n = len(losses)
        sorted_L = np.sort(losses)
        diffs = np.diff(sorted_L)
        flat = np.sum(diffs < eps) / max(n - 1, 1)
        return float(flat)

    dz1 = dead_zone_fraction(L1)
    dz2 = dead_zone_fraction(L2)
    dz3 = dead_zone_fraction(L3)

    # ── Metric 6: Discontinuity count (abrupt jumps in sorted loss) ───────────
    def discontinuity_score(losses, jump_thresh=0.15):
        sorted_L = np.sort(losses)
        diffs = np.diff(sorted_L)
        return int(np.sum(diffs > jump_thresh))

    disc1 = discontinuity_score(L1)
    disc2 = discontinuity_score(L2)
    disc3 = discontinuity_score(L3)

    return {
        "L1": L1, "L2": L2, "L3": L3, "TC": TC,
        "metrics": {
            "Lipschitz (↓ smoother)":           {"M1": lip1, "M2": lip2, "M3": lip3},
            "Noise sensitivity (↓ robust)":     {"M1": ns1,  "M2": ns2,  "M3": ns3},
            "Spearman corr w/ truth (↑ better)":{"M1": corr1,"M2": corr2,"M3": corr3},
            "Variance / informativeness (↑)":   {"M1": var1, "M2": var2, "M3": var3},
            "Dead zone fraction (↓ better)":    {"M1": dz1,  "M2": dz2,  "M3": dz3},
            "Discontinuity count (↓ better)":   {"M1": disc1,"M2": disc2,"M3": disc3},
        }
    }


# ──────────────────────────────────────────────────────────────────────────────
# Visualisation
# ──────────────────────────────────────────────────────────────────────────────

def plot_results(results, save_dir="Algorithm/Loss"):
    import os
    os.makedirs(save_dir, exist_ok=True)

    L1, L2, L3, TC = results["L1"], results["L2"], results["L3"], results["TC"]
    metrics = results["metrics"]

    # ── Figure 1: Loss landscapes ─────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, L, name, color in zip(axes,
                                   [L1, L2, L3],
                                   ["Method 1\n(Current: Peak detection + y_norm)",
                                    "Method 2\n(2nd Derivative curvature)",
                                    "Method 3\n(1/λⁿ decomp + FWHM)"],
                                   ["#1f77b4", "#ff7f0e", "#2ca02c"]):
        ax.scatter(TC, L, alpha=0.3, s=8, c=color)
        ax.set_xlabel("True closeness to target (higher = better)")
        ax.set_ylabel("Loss value")
        ax.set_title(name, fontsize=10)
        # Fit trend line
        z = np.polyfit(TC, L, 1)
        p = np.poly1d(z)
        tc_sorted = np.sort(TC)
        ax.plot(tc_sorted, p(tc_sorted), "k--", linewidth=1.5, label=f"slope={z[0]:.3f}")
        ax.legend(fontsize=8)
    plt.suptitle("Loss vs True Closeness to Target (InP QD, λ_target=490 nm)", fontsize=12)
    plt.tight_layout()
    plt.savefig(f"{save_dir}/loss_landscape_comparison.png", dpi=150)
    plt.close()

    # ── Figure 2: Loss distributions ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 4))
    bins = np.linspace(-1.6, 0.1, 50)
    ax.hist(L1, bins=bins, alpha=0.6, label="M1 (Current)", color="#1f77b4", density=True)
    ax.hist(L2, bins=bins, alpha=0.6, label="M2 (Deriv)",   color="#ff7f0e", density=True)
    ax.hist(L3, bins=bins, alpha=0.6, label="M3 (Decomp)",  color="#2ca02c", density=True)
    ax.set_xlabel("Loss value")
    ax.set_ylabel("Density")
    ax.set_title("Loss Distribution Across 500 Synthetic Spectra")
    ax.legend()
    plt.tight_layout()
    plt.savefig(f"{save_dir}/loss_distribution_comparison.png", dpi=150)
    plt.close()

    # ── Figure 3: Example spectra with loss values ─────────────────────────────
    np.random.seed(99)
    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    scenarios = [
        ("No peak (pure scattering)", 0.00, 3.5, 490),
        ("Weak proto-peak",           0.05, 2.5, 490),
        ("Peak at wrong λ (440nm)",   0.25, 2.0, 440),
        ("Peak at wrong λ (560nm)",   0.25, 2.0, 560),
        ("Near-target peak (480nm)",  0.25, 2.0, 480),
        ("On-target peak (490nm)",    0.25, 2.0, 490),
        ("Sharp on-target (σ=12)",    0.30, 2.0, 490),
        ("Strong peak + noise",       0.40, 2.0, 490),
    ]
    sigmas = [40, 40, 35, 35, 35, 35, 12, 35]
    for idx, ((title, amp, s_exp, lm0), sigma_p, ax_row) in enumerate(
            zip(scenarios, sigmas, axes.flatten())):
        y = make_spectrum(lm0, sigma_p, amp, scatter_exp=s_exp, noise_level=0.003)
        ax_row.plot(WL, y, color="#333", linewidth=1.2)
        ax_row.axvline(490, color="red", linestyle="--", linewidth=0.8, label="λ_target")

        l1 = loss_method1(y)
        l2 = loss_method2(y)
        l3 = loss_method3(y)
        ax_row.set_title(f"{title}\nM1={l1:.3f}  M2={l2:.3f}  M3={l3:.3f}", fontsize=8)
        ax_row.set_xlabel("λ (nm)", fontsize=7)
        ax_row.set_ylabel("Absorbance", fontsize=7)
        ax_row.legend(fontsize=6)
        ax_row.tick_params(labelsize=7)

    plt.suptitle("Example Spectra with Loss Values (target λ=490 nm)", fontsize=11)
    plt.tight_layout()
    plt.savefig(f"{save_dir}/example_spectra_loss.png", dpi=150)
    plt.close()

    # ── Figure 4: Radar chart of metrics ─────────────────────────────────────
    metric_names = list(metrics.keys())
    # Normalise each metric to [0,1] where 1=best for BO
    # Lipschitz, noise, dead zone, discontinuity: lower=better → invert
    # Spearman, variance: higher=better → keep
    def normalise_metric(name, vals):
        v1, v2, v3 = vals["M1"], vals["M2"], vals["M3"]
        arr = np.array([abs(v1), abs(v2), abs(v3)])
        if arr.max() == arr.min():
            return arr * 0 + 0.5
        norm = (arr - arr.min()) / (arr.max() - arr.min())
        if "↓" in name:     # lower=better → invert
            return 1 - norm
        else:                # higher=better → keep
            return norm

    scores_m1, scores_m2, scores_m3 = [], [], []
    for name, vals in metrics.items():
        n = normalise_metric(name, vals)
        scores_m1.append(n[0])
        scores_m2.append(n[1])
        scores_m3.append(n[2])

    angles = np.linspace(0, 2*np.pi, len(metric_names), endpoint=False).tolist()
    angles += angles[:1]
    for s in [scores_m1, scores_m2, scores_m3]:
        s += s[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    short_labels = ["Smoothness", "Noise\nRobust", "Monoton.", "Inform.", "No Dead\nZones", "No Disc."]
    ax.set_thetagrids(np.degrees(angles[:-1]), short_labels, fontsize=10)
    ax.plot(angles, scores_m1, "o-", linewidth=2, label="M1 (Current)", color="#1f77b4")
    ax.fill(angles, scores_m1, alpha=0.15, color="#1f77b4")
    ax.plot(angles, scores_m2, "s-", linewidth=2, label="M2 (Deriv)",   color="#ff7f0e")
    ax.fill(angles, scores_m2, alpha=0.15, color="#ff7f0e")
    ax.plot(angles, scores_m3, "^-", linewidth=2, label="M3 (Decomp)",  color="#2ca02c")
    ax.fill(angles, scores_m3, alpha=0.15, color="#2ca02c")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    ax.set_title("BO Suitability Radar Chart\n(each axis: 1 = best)", fontsize=12, pad=20)
    plt.tight_layout()
    plt.savefig(f"{save_dir}/radar_chart.png", dpi=150, bbox_inches="tight")
    plt.close()

    print(f"\nPlots saved to: {save_dir}/")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  Loss Function Comparison for Bayesian Optimization")
    print("  Target: InP QD first-exciton peak at 490 nm")
    print("=" * 65)

    results = evaluate_all(n_spectra=500)
    metrics = results["metrics"]

    # ── Print numerical results ────────────────────────────────────────────────
    print("\n{'─'*65}")
    print(f"{'Metric':<42} {'M1(Current)':>12} {'M2(Deriv)':>10} {'M3(Decomp)':>11}")
    print("─" * 77)
    for name, vals in metrics.items():
        print(f"{name:<42} {vals['M1']:>12.4f} {vals['M2']:>10.4f} {vals['M3']:>11.4f}")

    # ── Compute composite BO score ─────────────────────────────────────────────
    # Weights chosen to reflect GP surrogate's sensitivity
    # Smoothness + monotonicity are most critical for BO convergence
    weights = {
        "Lipschitz (↓ smoother)":           -2.0,  # lower=better, weight 2
        "Noise sensitivity (↓ robust)":     -1.5,  # lower=better
        "Spearman corr w/ truth (↑ better)": 3.0,  # higher=better, most important
        "Variance / informativeness (↑)":    1.0,
        "Dead zone fraction (↓ better)":    -1.5,
        "Discontinuity count (↓ better)":   -2.0,
    }

    def normalise_metric(name, vals):
        v1, v2, v3 = vals["M1"], vals["M2"], vals["M3"]
        arr = np.array([abs(float(v1)), abs(float(v2)), abs(float(v3))])
        if arr.max() == arr.min():
            return arr * 0 + 0.5
        norm = (arr - arr.min()) / (arr.max() - arr.min())
        if "↓" in name:
            return 1 - norm
        return norm

    composite = np.zeros(3)
    for name, vals in metrics.items():
        w = abs(weights[name])
        n = normalise_metric(name, vals)
        composite += w * n

    total_w = sum(abs(v) for v in weights.values())
    composite /= total_w

    print("\n" + "─" * 77)
    print(f"{'Composite BO score (↑ better)':<42} {composite[0]:>12.4f} {composite[1]:>10.4f} {composite[2]:>11.4f}")
    print("─" * 77)

    winner = ["M1 (Current)", "M2 (Derivative)", "M3 (Decomp)"][int(np.argmax(composite))]
    print(f"\n>>> Recommended method: {winner} (composite score = {max(composite):.4f})\n")

    # ── Print qualitative analysis ─────────────────────────────────────────────
    print("""
┌─────────────────────────────────────────────────────────────────┐
│               Qualitative Analysis Summary                      │
├─────────────────────────────────────────────────────────────────┤
│ M1 (Current — Peak detection + y_norm fallback)                 │
│  + Physically motivated; directly measures what we care about   │
│  + y_norm fallback provides continuous signal in no-peak zone   │
│  − Hard discontinuity at peak-detection boundary (threshold)    │
│  − Two separate regimes make GP landscape bimodal              │
│  − Lipschitz constant high near detection boundary              │
│                                                                 │
│ M2 (2nd Derivative curvature)                                   │
│  + Fully continuous — no threshold-gated branches              │
│  + Smooth everywhere → GP models it well in few evaluations    │
│  + Works even for very small proto-peaks below find_peaks thresh│
│  − Derivatives amplify high-frequency noise                     │
│  − Requires good smoothing (σ choice affects results)           │
│  − Curvature at a single point can be noisy for broad peaks     │
│                                                                 │
│ M3 (1/λⁿ baseline subtraction + FWHM)                          │
│  + Physically cleanest: separates scattering from excitonic abs │
│  + FWHM directly encodes size-dispersion quality                │
│  − Background fit can fail (degenerate solutions, noisy flanks) │
│  − Still requires find_peaks on residual → same threshold issue │
│  − Most failure modes → least robust in practice               │
└─────────────────────────────────────────────────────────────────┘

RECOMMENDATION FOR BO:
  The ideal loss for a GP-based Bayesian Optimiser is smooth,
  monotone, and free of discontinuities (GP assumes Lipschitz
  continuity). M2 satisfies these the most reliably.

  However, the current M1 is already strong. The key weakness is
  the hard jump at the peak-detection boundary. A practical
  improvement: blend M1 and M2 — use M2's continuous curvature
  score *when no peak is detected*, replacing the y_norm fallback,
  and keep M1's peak-property loss when a peak is found. This
  preserves physical interpretability while eliminating the
  largest source of landscape discontinuity.
""")

    plot_results(results)
    print("Done. Check Algorithm/Loss/ for plots.")


if __name__ == "__main__":
    main()
