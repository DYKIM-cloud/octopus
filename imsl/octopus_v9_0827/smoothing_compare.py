"""
calculateUV_Data_clean_csv 스무딩 파이프라인 비교
─────────────────────────────────────────────────────────────────────
Pipeline A  (AnalysisUV_poly.py   — 현재):
  1) 보간 350-950nm 20000pts
  2) Boxcar  box_size=250  (~7.5 nm)
  3) 절삭 360-700nm
  4) SavGol  window=51 pts (~1.5 nm), polyorder=3
  5) Polyfit degree=19  → 최종 스무딩 곡선

Pipeline B  (AnalysisUV_poly copy.py — 구버전):
  1) 보간 350-950nm 20000pts
  2) Boxcar  box_size=199  (~6.0 nm)
  3) 절삭 360-700nm
  4) SavGol  window=11 pts (~0.33 nm), polyorder=3
  5) Polyfit degree=19  → 최종 스무딩 곡선
  6) 절삭 420-550nm → 축 교환(sliced3) → analysisPickVelly
     ※ sliced3 = 흡광도 0-1 범위만 남기는 축 교환 트릭 (흡광도>1 구간 삭제)

비교 항목
  ① 각 단계별 중간 결과 (보간→Boxcar→SavGol→Polyfit)
  ② 최종 스무딩 결과 A vs B 오버레이
  ③ sliced2(420-550nm), sliced3(A 기준) 비교
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

try:
    from matplotlib import font_manager
    _fonts = [f.name for f in font_manager.fontManager.ttflist]
    _kor = next((f for f in ["Malgun Gothic","NanumGothic","AppleGothic"] if f in _fonts), None)
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

# ── Pipeline A (poly.py 현재) ──────────────────────────────────────────────
def pipeline_A(wl_raw, ab_raw):
    order  = np.argsort(wl_raw)
    x_eval = np.linspace(350, 950, 20000)
    trend  = np.interp(x_eval, wl_raw[order], ab_raw[order])
    raw    = np.array([x_eval, trend], dtype=float)

    smoothed  = smooth_Boxcar(rawSpectrum=raw, box_size=250)          # ~7.5 nm
    sliced    = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)
    savgoled  = selective_noise_correction(sliced, noise_range=(360,700),
                                           window_length=51, polyorder=3)  # ~1.5 nm
    poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
    sliced2   = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)

    return {
        "interp":   (x_eval,       trend),
        "boxcar":   (smoothed[0],  smoothed[1]),
        "savgol":   (savgoled[0],  savgoled[1]),
        "polyfit":  (poly_wl,      poly_ab),
        "sliced2":  (sliced2[0],   sliced2[1]),
    }

# ── Pipeline B (poly copy.py 구버전) ──────────────────────────────────────
def pipeline_B(wl_raw, ab_raw):
    order  = np.argsort(wl_raw)
    x_eval = np.linspace(350, 950, 20000)
    trend  = np.interp(x_eval, wl_raw[order], ab_raw[order])
    raw    = np.array([x_eval, trend], dtype=float)

    smoothed  = smooth_Boxcar(rawSpectrum=raw, box_size=199)          # ~6.0 nm
    sliced    = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)
    savgoled  = selective_noise_correction(sliced, noise_range=(360,700),
                                           window_length=11, polyorder=3)  # ~0.33 nm
    poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
    sliced2   = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)
    # 구버전 축 교환 트릭: 흡광도를 x축으로, 파장을 y축으로 → 0~1 구간만 남김
    sliced3   = getSliceSpectrum(rawSpectrum=(sliced2[1], sliced2[0]), min_wl=0, max_wl=1)

    return {
        "interp":   (x_eval,       trend),
        "boxcar":   (smoothed[0],  smoothed[1]),
        "savgol":   (savgoled[0],  savgoled[1]),
        "polyfit":  (poly_wl,      poly_ab),
        "sliced2":  (sliced2[0],   sliced2[1]),
        "sliced3_wl": sliced3[1],   # 파장 (원래 y → 복원)
        "sliced3_ab": sliced3[0],   # 흡광도 (원래 x → 복원)
    }

# ── 정규화 헬퍼 ───────────────────────────────────────────────────────────
def norm01(y):
    mn, mx = np.nanmin(y), np.nanmax(y)
    return (y - mn) / (mx - mn) if mx != mn else np.zeros_like(y)

# ── 단계별 비교 플롯 ───────────────────────────────────────────────────────
STEP_COLORS = {
    "interp":  ("#aaaaaa", 0.6, 0.7, "Interpolated"),
    "boxcar":  ("#f4a261", 1.0, 1.0, None),   # 레이블은 아래에서 지정
    "savgol":  ("#2a9d8f", 1.2, 1.0, None),
    "polyfit": ("#e63946", 1.5, 1.0, None),
}

def plot_sample(sample_idx, wl_raw, ab_raw, out_dir):
    A = pipeline_A(wl_raw, ab_raw)
    B = pipeline_B(wl_raw, ab_raw)

    # ── Figure: 2행 4열 ──────────────────────────────────────────────────
    # Row 0: Pipeline A 단계별  |  Row 1: Pipeline B 단계별
    # Col 0: 전체(360-700nm)    Col 1: 피크 구간(420-550nm)
    # Col 2: A vs B 최종 오버레이  Col 3: sliced2/sliced3 비교
    fig, axes = plt.subplots(2, 4, figsize=(22, 10))
    fig.suptitle(
        f"Sample {sample_idx}  —  Pipeline A (poly.py) vs Pipeline B (poly copy.py)",
        fontsize=13, y=1.01
    )

    for row, (pipe, pipe_label, bc_size, sg_win) in enumerate([
        (A, "Pipeline A  (Boxcar=250, SavGol=51)", 250, 51),
        (B, "Pipeline B  (Boxcar=199, SavGol=11)", 199, 11),
    ]):
        # ── Col 0: 전체 단계별 (360-700 nm) ──────────────────────────────
        ax = axes[row][0]
        x_i, y_i = pipe["interp"]
        mask_full = (x_i >= 360) & (x_i <= 700)

        # interp
        ax.plot(x_i[mask_full], norm01(y_i[mask_full]),
                color="#aaaaaa", lw=0.7, alpha=0.7, label="Interpolated")
        # boxcar
        xb, yb = pipe["boxcar"]
        ax.plot(xb, norm01(yb),
                color="#f4a261", lw=1.0, label=f"Boxcar (box={bc_size})")
        # savgol
        xs, ys = pipe["savgol"]
        ax.plot(xs, norm01(ys),
                color="#2a9d8f", lw=1.2, label=f"SavGol (win={sg_win})")
        # polyfit
        xp, yp = pipe["polyfit"]
        mask_p = (xp >= 360) & (xp <= 700)
        ax.plot(xp[mask_p], norm01(yp[mask_p]),
                color="#e63946", lw=1.5, label="Polyfit deg=19")

        ax.set_xlim(360, 700)
        ax.set_ylim(-0.05, 1.10)
        ax.set_xlabel("Wavelength (nm)", fontsize=9)
        ax.set_ylabel(f"{pipe_label}\nAbsorbance (norm.)", fontsize=8)
        ax.set_title("Step-by-step (360-700 nm)", fontsize=10)
        ax.legend(fontsize=7.5, loc="upper right")
        ax.grid(True, lw=0.35, alpha=0.4)

        # ── Col 1: 피크 구간 단계별 (420-550 nm) ─────────────────────────
        ax = axes[row][1]
        mask_pk = (x_i >= 420) & (x_i <= 550)

        ax.plot(x_i[mask_pk], norm01(y_i[mask_pk]),
                color="#aaaaaa", lw=0.7, alpha=0.7, label="Interpolated")
        xb_m = (xb >= 420) & (xb <= 550)
        ax.plot(xb[xb_m], norm01(yb[xb_m]),
                color="#f4a261", lw=1.0, label=f"Boxcar (box={bc_size})")
        xs_m = (xs >= 420) & (xs <= 550)
        ax.plot(xs[xs_m], norm01(ys[xs_m]),
                color="#2a9d8f", lw=1.2, label=f"SavGol (win={sg_win})")
        xp2, yp2 = pipe["sliced2"]
        ax.plot(xp2, norm01(yp2),
                color="#e63946", lw=1.5, label="Polyfit deg=19 (420-550)")

        ax.set_xlim(420, 550)
        ax.set_ylim(-0.05, 1.10)
        ax.set_xlabel("Wavelength (nm)", fontsize=9)
        ax.set_title("Step-by-step (420-550 nm)", fontsize=10)
        ax.legend(fontsize=7.5, loc="upper right")
        ax.grid(True, lw=0.35, alpha=0.4)

    # ── Col 2: A vs B 최종 polyfit 오버레이 (전체 360-700 nm) ─────────────
    for row in range(2):
        ax = axes[row][2]
        pipe = A if row == 0 else B
        other = B if row == 0 else A
        other_label = "B (copy)" if row == 0 else "A (current)"
        self_label  = "A (current)" if row == 0 else "B (copy)"

        # raw interp (공통)
        x_i, y_i = pipe["interp"]
        mask_full = (x_i >= 360) & (x_i <= 700)
        ax.plot(x_i[mask_full], norm01(y_i[mask_full]),
                color="#cccccc", lw=0.7, alpha=0.6, label="Interpolated (raw)")

        # self polyfit
        xp, yp = pipe["polyfit"]
        mp = (xp >= 360) & (xp <= 700)
        ax.plot(xp[mp], norm01(yp[mp]),
                color="#e63946", lw=2.0, label=f"Polyfit {self_label}")

        # other polyfit (norm 기준은 self 와 같게 하기 위해 raw 기준)
        xo, yo = other["polyfit"]
        mo = (xo >= 360) & (xo <= 700)
        # 공통 y_min/y_max: 보간된 360-700 범위
        y_mn = float(y_i[mask_full].min()); y_mx = float(y_i[mask_full].max())
        y_rng = y_mx - y_mn if y_mx != y_mn else 1.0
        def N(arr): return (arr - y_mn) / y_rng

        ax.plot(x_i[mask_full], N(y_i[mask_full]),
                color="#cccccc", lw=0.7, alpha=0.0)   # invisible, just to set scale
        ax.plot(xp[mp], N(yp[mp]),
                color="#e63946", lw=2.0)
        ax.plot(xo[mo], N(yo[mo]),
                color="#3a86ff", lw=1.5, ls="--", label=f"Polyfit {other_label}")
        ax.plot(x_i[mask_full], N(y_i[mask_full]),
                color="#cccccc", lw=0.7, alpha=0.6)

        ax.set_xlim(360, 700)
        ax.set_ylim(-0.05, 1.10)
        ax.set_xlabel("Wavelength (nm)", fontsize=9)
        ax.set_title("A vs B: Final polyfit overlay\n(360-700 nm)", fontsize=10)
        ax.legend(fontsize=7.5, loc="upper right")
        ax.grid(True, lw=0.35, alpha=0.4)

    # ── Col 3: sliced2 (A) vs sliced2 (B) vs sliced3 (B) — 공통 기준 정규화 ──
    # 공통 정규화 기준: 420-550 nm 구간 raw 보간값
    x_i_ref, y_i_ref = A["interp"]
    mask_ref = (x_i_ref >= 420) & (x_i_ref <= 550)
    y_ref_mn  = float(y_i_ref[mask_ref].min())
    y_ref_mx  = float(y_i_ref[mask_ref].max())
    y_ref_rng = y_ref_mx - y_ref_mn if y_ref_mx != y_ref_mn else 1.0
    def Nref(arr): return (arr - y_ref_mn) / y_ref_rng

    for row in range(2):
        ax = axes[row][3]

        # raw 보간 (공통 기준선)
        ax.plot(x_i_ref[mask_ref], Nref(y_i_ref[mask_ref]),
                color="#cccccc", lw=0.8, alpha=0.7, label="Interpolated (raw)")

        # sliced2 A
        xA2, yA2 = A["sliced2"]
        ax.plot(xA2, Nref(yA2),
                color="#e63946", lw=1.8, label="sliced2  A (Boxcar=250, SavGol=51)")

        # sliced2 B
        xB2, yB2 = B["sliced2"]
        ax.plot(xB2, Nref(yB2),
                color="#3a86ff", lw=1.2, ls="--",
                label="sliced2  B (Boxcar=199, SavGol=11)")

        # sliced3 B (축교환으로 흡광도>1 구간 삭제된 결과)
        if "sliced3_wl" in B:
            wl3 = B["sliced3_wl"]; ab3 = B["sliced3_ab"]
            ax.plot(wl3, Nref(ab3),
                    color="#f4a261", lw=1.2, ls=":",
                    label="sliced3  B (abs≤1 only, B 구버전)")

        ax.set_xlim(410, 560)
        ax.set_xlabel("Wavelength (nm)", fontsize=9)
        ax.set_title("sliced2 A vs B (공통 scale)\n(+ sliced3 of B)", fontsize=10)
        ax.legend(fontsize=7.5, loc="upper right")
        ax.grid(True, lw=0.35, alpha=0.4)

    # Col 3 y축: 두 행 공통으로 raw 기준 범위 맞춤
    all_col3 = np.concatenate([
        Nref(A["sliced2"][1]), Nref(B["sliced2"][1]),
        Nref(B["sliced3_ab"]) if "sliced3_ab" in B else np.array([0.0])
    ])
    c3_min = min(-0.05, float(all_col3.min()) - 0.05)
    c3_max = float(all_col3.max()) + 0.08
    for row in range(2):
        axes[row][3].set_ylim(c3_min, c3_max)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"sample_{sample_idx:03d}_smoothing_compare.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  saved: {out}")

# ── 메인 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    CSV_PATH    = "2508optimize/spectra_with_params_0407.csv"
    OUT_DIR     = "smoothing_compare_results"
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
