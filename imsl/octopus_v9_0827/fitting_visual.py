"""
Polyfit 데이터 기반 배경 피팅 방식 3가지 비교
────────────────────────────────────────────────────────────────
스무딩: Boxcar(250) + SavGol(51, poly=3) + Polyfit(deg=19)  [고정]

[열] 배경 피팅 방식 — power-law  A(λ) = a·(λ_ref/λ)^n
  Method 1  단파장만   360–400 nm
  Method 2  장파장만   560–700 nm
  Method 3  단+장 동시  360–400 nm  +  560–700 nm  (joint fit)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

try:
    from matplotlib import font_manager
    _fonts = [f.name for f in font_manager.fontManager.ttflist]
    _kor   = next((f for f in ["Malgun Gothic","NanumGothic","AppleGothic"] if f in _fonts), None)
    if _kor:
        matplotlib.rcParams["font.family"] = _kor
except Exception:
    pass
matplotlib.rcParams["axes.unicode_minus"] = False

from Analysis.AnalysisUV_poly import (
    smooth_Boxcar, getSliceSpectrum,
    selective_noise_correction, smooth_polyfit
)

# ── CSV 로더 ───────────────────────────────────────────────────────────────
def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    data_dict = {}
    wavelength = df.iloc[4:, 0].astype(float).tolist()
    for col in range(1, df.shape[1]):
        name = f"Sample_{col}"
        spectrum = df.iloc[4:, col].astype(float).tolist()
        data_dict[name] = {"Wavelength": wavelength, "RawSpectrum": spectrum}
    return data_dict

# ── 표시 그리드 ────────────────────────────────────────────────────────────
VIEW_X = np.linspace(350.0, 720.0, 15000)

def _to_view(x_src, y_src):
    return np.interp(VIEW_X, x_src, y_src,
                     left=float(y_src[0]), right=float(y_src[-1]))

# ── Polyfit 파이프라인 ──────────────────────────────────────────────────────
def get_polyfit(wl_raw, ab_raw):
    """Boxcar(250) + SavGol(51) + Polyfit(deg=19) → VIEW_X 기준 곡선."""
    order   = np.argsort(wl_raw)
    x_inner = np.linspace(350.0, 950.0, 20000)
    y_inner = np.interp(x_inner, wl_raw[order], ab_raw[order])

    smoothed = smooth_Boxcar(np.array([x_inner, y_inner]), box_size=250)
    sliced   = getSliceSpectrum(smoothed, min_wl=360, max_wl=700)
    savgoled = selective_noise_correction(sliced, noise_range=(360,700),
                                          window_length=51, polyorder=3)
    poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)

    y_interp = np.interp(VIEW_X, wl_raw[order], ab_raw[order])
    y_poly   = _to_view(poly_wl, poly_ab)
    return y_interp, y_poly

# ── Power-law 배경 피팅 ────────────────────────────────────────────────────
def _pl(lam, a, n, ref):
    return a * (ref / lam) ** n

def fit_single(y_poly, lo, hi, n_max=8.0):
    """단일 구간 power-law 피팅."""
    mask = (VIEW_X >= lo) & (VIEW_X <= hi)
    xb, yb = VIEW_X[mask], np.maximum(y_poly[mask], 1e-9)
    ref = float(xb[0])
    try:
        p, _ = curve_fit(lambda l,a,n: _pl(l,a,n,ref), xb, yb,
                         p0=[float(yb.mean()), 2.0],
                         bounds=([0,0.1],[20,n_max]), maxfev=8000)
        bg = np.maximum(_pl(VIEW_X, p[0], p[1], ref), 0.0)
        lbl = f"n={p[1]:.2f}, a={p[0]:.3f}"
    except Exception:
        bg  = np.interp(VIEW_X, [VIEW_X[0],VIEW_X[-1]],
                        [float(y_poly[0]),float(y_poly[-1])])
        lbl = "fallback"
    return bg, lbl

def fit_joint(y_poly, lo1, hi1, lo2, hi2, n_max=8.0):
    """단파장+장파장 동시 power-law 피팅 (공통 a, n)."""
    m1 = (VIEW_X >= lo1) & (VIEW_X <= hi1)
    m2 = (VIEW_X >= lo2) & (VIEW_X <= hi2)
    xb = np.concatenate([VIEW_X[m1], VIEW_X[m2]])
    yb = np.maximum(np.concatenate([y_poly[m1], y_poly[m2]]), 1e-9)
    ref = float(VIEW_X[m1][0])
    try:
        p, _ = curve_fit(lambda l,a,n: _pl(l,a,n,ref), xb, yb,
                         p0=[float(yb.mean()), 2.0],
                         bounds=([0,0.1],[20,n_max]), maxfev=8000)
        bg  = np.maximum(_pl(VIEW_X, p[0], p[1], ref), 0.0)
        lbl = f"n={p[1]:.2f}, a={p[0]:.3f}"
    except Exception:
        bg  = np.interp(VIEW_X, [VIEW_X[0],VIEW_X[-1]],
                        [float(y_poly[0]),float(y_poly[-1])])
        lbl = "fallback"
    return bg, lbl

# ── 플롯 ───────────────────────────────────────────────────────────────────
def plot_sample(sample_idx, wl_raw, ab_raw, out_dir):
    y_interp, y_poly = get_polyfit(wl_raw, ab_raw)

    # 정규화 기준: 360–700 nm 내 polyfit
    v = (VIEW_X >= 360) & (VIEW_X <= 700)
    y_mn  = float(y_poly[v].min())
    y_rng = float(y_poly[v].max()) - y_mn
    if y_rng == 0: y_rng = 1.0
    def N(arr): return (arr - y_mn) / y_rng

    # 세 방식 피팅
    bg1, lbl1 = fit_single(y_poly, lo=360, hi=400)
    bg2, lbl2 = fit_single(y_poly, lo=560, hi=700)
    bg3, lbl3 = fit_joint (y_poly, lo1=360, hi1=400, lo2=560, hi2=700)

    methods = [
        (bg1, lbl1, [(360,400)],          "Method 1: power-law short\n(fit: 360-400 nm)"),
        (bg3, lbl3, [(360,400),(560,700)],"Method 2: joint fit\n(360-400 + 560-700 nm)"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    fig.suptitle(
        f"Sample {sample_idx}  —  Background separation on Polyfit(deg=19) data",
        fontsize=13, y=1.02
    )

    span_colors = ["tomato", "steelblue"]

    for ax, (bg, lbl, spans, title) in zip(axes, methods):
        resid_n = np.maximum(N(y_poly) - N(bg), 0.0)

        ax.plot(VIEW_X, N(y_interp),
                color="#cccccc", lw=0.7, alpha=0.7, label="Interpolated (raw)")
        ax.plot(VIEW_X, N(y_poly),
                color="#7b2d8b", lw=1.8, label="Polyfit (deg=19)")
        ax.plot(VIEW_X, N(bg),
                color="#e05c2a", lw=1.6, ls="--", label=f"BG fit  {lbl}")
        ax.fill_between(VIEW_X, 0, resid_n, color="#3a86ff", alpha=0.22)
        ax.plot(VIEW_X, resid_n,
                color="#3a86ff", lw=1.5, label="Residual (peak)")

        for (lo_s, hi_s), sc in zip(spans, span_colors):
            ax.axvspan(lo_s, hi_s, alpha=0.12, color=sc,
                       label=f"Fit region {lo_s}-{hi_s} nm")

        ax.set_xlim(350, 720)
        ax.set_ylim(-0.08, 1.18)
        ax.set_xlabel("Wavelength (nm)", fontsize=10)
        ax.set_title(title, fontsize=11, pad=6)
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, lw=0.35, alpha=0.4)

    axes[0].set_ylabel("Absorbance (norm. 0–1)", fontsize=10)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"sample_{sample_idx:03d}_fitting.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  saved: {out}")

# ── 메인 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    CSV_PATH    = "2508optimize/spectra_with_params_0407.csv"
    OUT_DIR     = "fitting_visual_results"
    SAMPLE_LIST = [1, 2, 3, 5, 8, 10, 20, 34, 49, 50, 100, 120]

    print("CSV 로드 중...")
    data_dict = load_multisample_csv(CSV_PATH)

    for i in SAMPLE_LIST:
        key = f"Sample_{i}"
        if key not in data_dict:
            print(f"  [skip] {key} 없음")
            continue
        uv   = data_dict[key]
        wl_r = np.array(uv["Wavelength"], dtype=float)
        ab_r = np.array(uv["RawSpectrum"], dtype=float)
        plot_sample(i, wl_r, ab_r, OUT_DIR)

    print("완료.")
