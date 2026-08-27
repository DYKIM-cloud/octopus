"""
calculateUV_Data_clean_csv  vs  calculateUV_Data_clean_csv2  비교
────────────────────────────────────────────────────────────────────
각 샘플에 대해 1행 2열 그래프:
  Left  (csv ) : Boxcar→SavGol→Polyfit → analysisPickVelly
  Right (csv2) : Gaussian smooth → power-law BG fit → Gaussian peak fit

표시 항목
  · 보라/초록 실선  : 각 함수의 스무딩 곡선
  · 빨간 점선       : csv2의 power-law 배경
  · 파란 채움       : csv2의 잔류(배경 제거 스펙트럼)
  · 주황 점선       : csv2의 Gaussian peak fit
  · ▼ 마커         : 검출된 lambdamax (없으면 미검출)
  · 숫자 박스       : lambdamax, pv_ratio 결과값
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter1d

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
    selective_noise_correction, smooth_polyfit,
    analysisPickVelly,
    calculateUV_Data_clean_csv, calculateUV_Data_clean_csv2,
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

# ── csv 내부 파이프라인 재현 (중간 곡선 추출용) ───────────────────────────
def _run_csv_internals(wl_raw, ab_raw):
    order   = np.argsort(wl_raw)
    x_eval  = np.linspace(350, 950, 20000)
    trend   = np.interp(x_eval, wl_raw[order], ab_raw[order])
    raw     = np.array([x_eval, trend])

    smoothed  = smooth_Boxcar(raw, box_size=250)
    sliced    = getSliceSpectrum(smoothed, min_wl=360, max_wl=700)
    savgoled  = selective_noise_correction(sliced, noise_range=(360,700),
                                           window_length=51, polyorder=3)
    poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
    sliced2   = getSliceSpectrum((poly_wl, poly_ab), min_wl=420, max_wl=550)

    pv, lm = analysisPickVelly(rawSpectrum=sliced2,
                                prominence=0.0005, width_threshold=8)
    return {
        "x_eval":   x_eval,
        "raw":      trend,
        "poly_wl":  poly_wl,
        "poly_ab":  poly_ab,
        "sliced2":  sliced2,
        "pv":       pv,
        "lm":       lm,
    }

# ── csv2 내부 파이프라인 재현 (중간 곡선 추출용) ──────────────────────────
def _run_csv2_internals(wl_raw, ab_raw,
                        gauss_sigma_nm=3.0,
                        bg_wl_min=560.0, bg_wl_max=700.0,
                        peak_wl_min=420.0, peak_wl_max=510.0,
                        prominence=0.007):
    PTS_PER_NM = 20000 / 600.0
    order   = np.argsort(wl_raw)
    x_eval  = np.linspace(350, 950, 20000)
    y_interp = np.interp(x_eval, wl_raw[order], ab_raw[order])
    y_smooth = gaussian_filter1d(y_interp, sigma=gauss_sigma_nm * PTS_PER_NM)

    def _fit_bg(lo, hi, n_max=6.0):
        mask = (x_eval >= lo) & (x_eval <= hi)
        xb   = x_eval[mask]
        yb   = np.maximum(y_smooth[mask], 1e-9)
        ref  = float(xb[0])
        def pl(lam, a, n): return a * (ref/lam)**n
        try:
            p, _ = curve_fit(pl, xb, yb, p0=[float(yb[0]), 2.0],
                             bounds=([0,0.3],[20,n_max]), maxfev=3000)
            return np.maximum(pl(x_eval, *p), 0.0), float(yb.mean())
        except Exception:
            return None, 0.0

    bg_full, bg_mean = _fit_bg(bg_wl_min, bg_wl_max)
    if bg_full is None or bg_mean < 0.002:
        bg_full, bg_mean = _fit_bg(520.0, 640.0)
    if bg_full is None or bg_mean < 0.002:
        bg_full, _ = _fit_bg(peak_wl_min, peak_wl_max, n_max=4.0)
    if bg_full is None:
        bg_full = np.interp(x_eval, [x_eval[0],x_eval[-1]],
                            [y_smooth[0], y_smooth[-1]])

    resid_full = np.maximum(y_smooth - bg_full, 0.0)
    pk_mask    = (x_eval >= peak_wl_min) & (x_eval <= peak_wl_max)
    peaks_i, props = find_peaks(resid_full[pk_mask], prominence=prominence)

    lm, pv, gauss_curve = 0.0, 0.0, None
    amp_fit = ctr_fit = sig_fit = None

    if len(peaks_i) > 0:
        wl_pk    = x_eval[pk_mask]
        best_i   = peaks_i[int(np.argmax(props["prominences"]))]
        lm_rough = float(wl_pk[best_i])

        win = 40.0
        wm  = (x_eval >= lm_rough-win) & (x_eval <= lm_rough+win)
        def _gauss(l, amp, ctr, sig): return amp*np.exp(-0.5*((l-ctr)/sig)**2)
        try:
            p0 = [float(resid_full[wm].max()), lm_rough, 15.0]
            bd = ([0, lm_rough-25, 5],[2, lm_rough+25, 60])
            po, _ = curve_fit(_gauss, x_eval[wm], resid_full[wm],
                              p0=p0, bounds=bd, maxfev=2000)
            amp_fit, ctr_fit, sig_fit = po
            lm_cand = float(np.clip(ctr_fit, peak_wl_min, peak_wl_max))

            y_pred  = _gauss(x_eval[wm], *po)
            ss_res  = float(np.sum((resid_full[wm]-y_pred)**2))
            ss_tot  = float(np.sum((resid_full[wm]-resid_full[wm].mean())**2))
            gauss_r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else 0.0

            prom_best = float(props["prominences"][int(np.argmax(props["prominences"]))])
            neg_peaks, _ = find_peaks(-y_smooth[pk_mask], prominence=0.001)
            has_valley = any(wl_pk[v] < lm_cand for v in neg_peaks)
            quality_ok = (gauss_r2>0.85 and prom_best>0.010
                          and sig_fit>=8.0 and (has_valley or sig_fit<20.0))

            if quality_ok and lm_cand > peak_wl_min+1.5:
                lm = lm_cand
                idx_lm   = np.argmin(np.abs(x_eval - lm))
                peak_ab  = float(y_smooth[idx_lm])
                val_rng  = (x_eval >= lm-60) & (x_eval <= lm-10)
                valley_ab = float(y_smooth[val_rng].min()) if val_rng.sum()>0 else float(y_smooth[pk_mask][0])
                base_mask = (x_eval >= 540) & (x_eval <= 560)
                base_ab   = float(y_smooth[base_mask].mean())
                denom = valley_ab - base_ab
                if denom > 0:
                    pv_cand = (peak_ab - base_ab) / denom
                    pv = float(pv_cand) if pv_cand > 0 else 0.0
                gauss_curve = _gauss(x_eval, amp_fit, ctr_fit, sig_fit)
        except Exception:
            pass

    return {
        "x_eval":      x_eval,
        "raw":         y_interp,
        "y_smooth":    y_smooth,
        "bg_full":     bg_full,
        "resid_full":  resid_full,
        "gauss_curve": gauss_curve,
        "pv":          pv,
        "lm":          lm,
        "pk_mask":     pk_mask,
    }

# ── 공통 정규화 ────────────────────────────────────────────────────────────
def _norm(arr, mn, rng):
    return (arr - mn) / rng

# ── 단일 샘플 플롯 ─────────────────────────────────────────────────────────
def plot_sample(sample_idx, wl_raw, ab_raw, out_dir):
    A = _run_csv_internals(wl_raw, ab_raw)
    B = _run_csv2_internals(wl_raw, ab_raw)

    # 공통 정규화 기준: 360-700 nm 구간 raw 보간
    x_ref = A["x_eval"]
    y_ref = A["raw"]
    m_ref = (x_ref >= 360) & (x_ref <= 700)
    y_mn  = float(y_ref[m_ref].min())
    y_rng = float(y_ref[m_ref].max()) - y_mn
    if y_rng == 0: y_rng = 1.0
    def N(arr): return _norm(arr, y_mn, y_rng)

    VIEW = (x_ref >= 350) & (x_ref <= 720)
    xv   = x_ref[VIEW]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    fig.suptitle(
        f"Sample {sample_idx}  —  calculateUV_Data_clean_csv  vs  csv2",
        fontsize=13, y=1.02
    )

    # ── Left: csv ────────────────────────────────────────────────────────
    ax = axes[0]
    ax.set_title("calculateUV_Data_clean_csv\n"
                 "Boxcar(250) → SavGol(51) → Polyfit(19)\n"
                 "→ analysisPickVelly (420–550 nm)",
                 fontsize=9, pad=6)

    ax.plot(xv, N(A["raw"][VIEW]),
            color="#cccccc", lw=0.7, alpha=0.7, label="Interpolated (raw)")
    ax.plot(A["poly_wl"], N(A["poly_ab"]),
            color="#7b2d8b", lw=1.8, label="Polyfit deg=19")

    # 420-550 슬라이스 범위 표시
    ax.axvspan(420, 550, alpha=0.08, color="purple", label="Peak search 420-550 nm")

    # peak/valley 마커
    lm_A = A["lm"]; pv_A = A["pv"]
    if lm_A > 0:
        ax.axvline(lm_A, color="#c44e52", lw=1.2, ls=":")
        idx_lm = np.argmin(np.abs(A["poly_wl"] - lm_A))
        ax.scatter([lm_A], [N(A["poly_ab"][idx_lm])],
                   color="#c44e52", zorder=5, s=60, marker="v")

    result_txt = (f"λmax = {lm_A:.1f} nm\npv_ratio = {pv_A:.4f}"
                  if lm_A > 0 else "No peak detected")
    ax.text(0.03, 0.97, result_txt,
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="lavender", alpha=0.85))

    ax.set_xlim(350, 720); ax.set_ylim(-0.10, 1.20)
    ax.set_xlabel("Wavelength (nm)", fontsize=10)
    ax.set_ylabel("Absorbance (norm. 0–1)", fontsize=10)
    ax.legend(fontsize=7.5, loc="upper right")
    ax.grid(True, lw=0.35, alpha=0.4)

    # ── Right: csv2 ──────────────────────────────────────────────────────
    ax = axes[1]
    ax.set_title("calculateUV_Data_clean_csv2\n"
                 "Gaussian(3 nm) → power-law BG(560-700 nm)\n"
                 "→ Gaussian peak fit (420–510 nm)",
                 fontsize=9, pad=6)

    ax.plot(xv, N(B["raw"][VIEW]),
            color="#cccccc", lw=0.7, alpha=0.7, label="Interpolated (raw)")
    ax.plot(xv, N(B["y_smooth"][VIEW]),
            color="#1a6b3a", lw=1.6, label="Gaussian smooth (σ=3 nm)")
    ax.plot(xv, N(B["bg_full"][VIEW]),
            color="#e05c2a", lw=1.5, ls="--", label="BG fit (power-law, 560-700 nm)")

    # 잔류
    resid_n = np.maximum(N(B["y_smooth"][VIEW]) - N(B["bg_full"][VIEW]), 0.0)
    ax.fill_between(xv, 0, resid_n, color="#3a86ff", alpha=0.20)
    ax.plot(xv, resid_n, color="#3a86ff", lw=1.2, label="Residual (smoothed - BG)")

    # Gaussian peak fit
    if B["gauss_curve"] is not None:
        ax.plot(xv, N(B["gauss_curve"][VIEW]),
                color="#f4a261", lw=1.5, ls="-.",
                label="Gaussian peak fit")

    # 420-510 탐색 구간
    ax.axvspan(420, 510, alpha=0.08, color="steelblue", label="Peak search 420-510 nm")

    lm_B = B["lm"]; pv_B = B["pv"]
    if lm_B > 0:
        ax.axvline(lm_B, color="#c44e52", lw=1.2, ls=":")
        idx_lm = np.argmin(np.abs(B["x_eval"] - lm_B))
        ax.scatter([lm_B], [N(B["y_smooth"][idx_lm])],
                   color="#c44e52", zorder=5, s=60, marker="v")

    result_txt = (f"λmax = {lm_B:.1f} nm\npv_ratio = {pv_B:.4f}"
                  if lm_B > 0 else "No peak detected")
    ax.text(0.03, 0.97, result_txt,
            transform=ax.transAxes, fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.4", fc="honeydew", alpha=0.85))

    ax.set_xlim(350, 720)
    ax.set_xlabel("Wavelength (nm)", fontsize=10)
    ax.legend(fontsize=7.5, loc="upper right")
    ax.grid(True, lw=0.35, alpha=0.4)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"sample_{sample_idx:03d}_func_compare.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  saved: {out}")

# ── 메인 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    CSV_PATH    = "2508optimize/spectra_with_params_0407.csv"
    OUT_DIR     = "func_compare_results"
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
