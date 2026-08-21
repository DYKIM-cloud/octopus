"""
배경 피팅 방식 3가지 비교 스크립트
────────────────────────────────────────────────────────────────
방식 A (현재):  calculateUV_Data_clean_csv
  - Boxcar → SavGol → polyfit(degree=19) → peak detection
  - 명시적 배경 제거 없음; 다항식 평활로 대체

방식 B (단파장):  power-law A(λ)=a·(λ_ref/λ)^n
  - 피팅 구간: 420–510 nm 만 (단파장, n ≤ 4 물리 제약)

방식 C (동시):  power-law 동시 피팅
  - 피팅 구간: 420–510 nm + 560–700 nm 결합
  - 두 구간의 잔류(residual) sum-of-squares 합산 최소화
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")           # 화면 없이 파일 저장
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit

from Analysis.AnalysisUV_poly import (
    calculateUV_Data_clean_csv,
    smooth_Boxcar, getSliceSpectrum, selective_noise_correction, smooth_polyfit,
    analysisPickVelly
)

# ─── CSV 로더 (self_bayesian_csv.py 와 동일) ────────────────────────────────

def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    param_dict = {}
    data_dict  = {}
    wavelength = df.iloc[4:, 0].astype(float).tolist()
    for col in range(1, df.shape[1]):
        col_name = f"Sample_{col}"
        keys   = df.iloc[0:4, 0].values
        values = df.iloc[0:4, col].values
        param_dict[col_name] = dict(zip(keys.astype(str), values))
        spectrum = df.iloc[4:, col].astype(float).tolist()
        data_dict[col_name] = {"Wavelength": wavelength, "RawSpectrum": spectrum}
    return param_dict, data_dict

# ─── 공통 전처리: 보간 + Gaussian 스무딩 ───────────────────────────────────

def _preprocess(uv_df):
    """DataFrame → (x_eval, y_smooth) on uniform 350-950 nm grid."""
    col = uv_df.columns[0]
    x = uv_df.index.values
    y = uv_df[col].values
    order  = np.argsort(x)
    x_eval = np.linspace(350.0, 950.0, 20000)
    y_interp = np.interp(x_eval, x[order], y[order])
    PTS_PER_NM = 20000 / 600.0
    y_smooth = gaussian_filter1d(y_interp, sigma=3.0 * PTS_PER_NM)
    return x_eval, y_interp, y_smooth

# ─── Power-law 배경 피팅 공통 함수 ─────────────────────────────────────────

def _powerlaw(lam, a, n, ref):
    return a * (ref / lam) ** n

def _fit_bg_single(x_eval, y_smooth, lo, hi, n_max=6.0):
    """단일 구간 power-law 피팅."""
    mask = (x_eval >= lo) & (x_eval <= hi)
    xb = x_eval[mask]
    yb = np.maximum(y_smooth[mask], 1e-9)
    ref = float(xb[0])
    try:
        p, pcov = curve_fit(
            lambda lam, a, n: _powerlaw(lam, a, n, ref),
            xb, yb,
            p0=[float(yb[0]), 2.0],
            bounds=([0.0, 0.3], [20.0, n_max]),
            maxfev=5000
        )
        bg = np.maximum(_powerlaw(x_eval, p[0], p[1], ref), 0.0)
        residuals = yb - _powerlaw(xb, p[0], p[1], ref)
        rmse = float(np.sqrt(np.mean(residuals**2)))
        r2   = float(1.0 - np.sum(residuals**2) / np.sum((yb - yb.mean())**2))
        return bg, rmse, r2, float(p[1])
    except Exception:
        return None, np.inf, 0.0, 0.0

def _fit_bg_joint(x_eval, y_smooth, lo1, hi1, lo2, hi2, n_max=6.0):
    """두 구간 동시 power-law 피팅 (단일 a, n 파라미터)."""
    mask1 = (x_eval >= lo1) & (x_eval <= hi1)
    mask2 = (x_eval >= lo2) & (x_eval <= hi2)
    xb = np.concatenate([x_eval[mask1], x_eval[mask2]])
    yb = np.maximum(np.concatenate([y_smooth[mask1], y_smooth[mask2]]), 1e-9)
    ref = float(x_eval[mask1][0]) if mask1.sum() > 0 else float(xb[0])
    try:
        p, _ = curve_fit(
            lambda lam, a, n: _powerlaw(lam, a, n, ref),
            xb, yb,
            p0=[float(yb[0]), 2.0],
            bounds=([0.0, 0.3], [20.0, n_max]),
            maxfev=5000
        )
        bg = np.maximum(_powerlaw(x_eval, p[0], p[1], ref), 0.0)
        residuals = yb - _powerlaw(xb, p[0], p[1], ref)
        rmse = float(np.sqrt(np.mean(residuals**2)))
        r2   = float(1.0 - np.sum(residuals**2) / np.sum((yb - yb.mean())**2))
        return bg, rmse, r2, float(p[1])
    except Exception:
        return None, np.inf, 0.0, 0.0

# ─── 방식 B: 단파장 배경 피팅 ──────────────────────────────────────────────

def method_B_short(uv_df,
                   peak_wl_min=420.0, peak_wl_max=510.0,
                   prominence=0.007):
    """Power-law 배경 피팅: 420–510 nm (단파장 전용, n ≤ 4)."""
    x_eval, y_interp, y_smooth = _preprocess(uv_df)

    bg, rmse, r2, n_val = _fit_bg_single(x_eval, y_smooth,
                                          peak_wl_min, peak_wl_max, n_max=4.0)
    if bg is None:
        return 0.0, 0.0, {"rmse": np.inf, "r2": 0.0, "n": 0.0, "bg": None}

    resid = np.maximum(y_smooth - bg, 0.0)
    pk_mask = (x_eval >= peak_wl_min) & (x_eval <= peak_wl_max)
    peaks_i, props = find_peaks(resid[pk_mask], prominence=prominence)

    if len(peaks_i) == 0:
        return 0.0, 0.0, {"rmse": rmse, "r2": r2, "n": n_val, "bg": bg,
                           "x_eval": x_eval, "y_smooth": y_smooth, "resid": resid}

    wl_pk = x_eval[pk_mask]
    best  = peaks_i[int(np.argmax(props["prominences"]))]
    lm_rough = float(wl_pk[best])

    # Gaussian 피팅으로 lambdamax 정밀화
    win = 40.0
    wm  = (x_eval >= lm_rough - win) & (x_eval <= lm_rough + win)
    try:
        p0 = [float(resid[wm].max()), lm_rough, 15.0]
        bd = ([0.0, lm_rough-25.0, 5.0], [2.0, lm_rough+25.0, 60.0])
        def _gauss(lam, amp, ctr, sig): return amp*np.exp(-0.5*((lam-ctr)/sig)**2)
        po, _ = curve_fit(_gauss, x_eval[wm], resid[wm], p0=p0, bounds=bd, maxfev=2000)
        amp_fit, ctr_fit, sig_fit = po
        lambdamax = float(np.clip(ctr_fit, peak_wl_min, peak_wl_max))
        # Gaussian R²
        y_pred = _gauss(x_eval[wm], *po)
        ss_res = float(np.sum((resid[wm]-y_pred)**2))
        ss_tot = float(np.sum((resid[wm]-resid[wm].mean())**2))
        gauss_r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else 0.0
    except Exception:
        lambdamax = lm_rough; gauss_r2 = 0.0; sig_fit = 15.0; amp_fit = float(resid[wm].max()); ctr_fit=lm_rough

    if lambdamax <= peak_wl_min + 1.5:
        return 0.0, 0.0, {"rmse": rmse, "r2": r2, "n": n_val, "bg": bg,
                           "x_eval": x_eval, "y_smooth": y_smooth, "resid": resid}

    idx_lm  = np.argmin(np.abs(x_eval - lambdamax))
    peak_ab = float(y_smooth[idx_lm])
    val_rng = (x_eval >= lambdamax-60.0) & (x_eval <= lambdamax-10.0)
    valley_ab = float(y_smooth[val_rng].min()) if val_rng.sum() > 0 else float(y_smooth[pk_mask][0])
    base_mask = (x_eval >= 540.0) & (x_eval <= 560.0)
    base_ab   = float(y_smooth[base_mask].mean())

    denom = valley_ab - base_ab
    if denom <= 0.0:
        pv = 0.0; lambdamax = 0.0
    else:
        pv = (peak_ab - base_ab) / denom
        if pv <= 0.0:
            pv = 0.0; lambdamax = 0.0

    return pv, lambdamax, {"rmse": rmse, "r2": r2, "n": n_val,
                            "gauss_r2": gauss_r2 if 'gauss_r2' in dir() else 0.0,
                            "bg": bg, "x_eval": x_eval,
                            "y_smooth": y_smooth, "resid": resid}

# ─── 방식 C: 단파장-장파장 동시 피팅 ──────────────────────────────────────

def method_C_joint(uv_df,
                   short_lo=420.0, short_hi=510.0,
                   long_lo=560.0,  long_hi=700.0,
                   peak_wl_min=420.0, peak_wl_max=510.0,
                   prominence=0.007):
    """Power-law 배경 동시 피팅: 420–510 nm + 560–700 nm."""
    x_eval, y_interp, y_smooth = _preprocess(uv_df)

    bg, rmse, r2, n_val = _fit_bg_joint(x_eval, y_smooth,
                                         short_lo, short_hi,
                                         long_lo,  long_hi)
    if bg is None:
        # fallback: 장파장만
        bg, rmse, r2, n_val = _fit_bg_single(x_eval, y_smooth, long_lo, long_hi)
    if bg is None:
        return 0.0, 0.0, {"rmse": np.inf, "r2": 0.0, "n": 0.0, "bg": None}

    resid = np.maximum(y_smooth - bg, 0.0)
    pk_mask = (x_eval >= peak_wl_min) & (x_eval <= peak_wl_max)
    peaks_i, props = find_peaks(resid[pk_mask], prominence=prominence)

    if len(peaks_i) == 0:
        return 0.0, 0.0, {"rmse": rmse, "r2": r2, "n": n_val, "bg": bg,
                           "x_eval": x_eval, "y_smooth": y_smooth, "resid": resid}

    wl_pk = x_eval[pk_mask]
    best  = peaks_i[int(np.argmax(props["prominences"]))]
    lm_rough = float(wl_pk[best])

    win = 40.0
    wm  = (x_eval >= lm_rough-win) & (x_eval <= lm_rough+win)
    try:
        p0 = [float(resid[wm].max()), lm_rough, 15.0]
        bd = ([0.0, lm_rough-25.0, 5.0], [2.0, lm_rough+25.0, 60.0])
        def _gauss(lam, amp, ctr, sig): return amp*np.exp(-0.5*((lam-ctr)/sig)**2)
        po, _ = curve_fit(_gauss, x_eval[wm], resid[wm], p0=p0, bounds=bd, maxfev=2000)
        amp_fit, ctr_fit, sig_fit = po
        lambdamax = float(np.clip(ctr_fit, peak_wl_min, peak_wl_max))
        y_pred = _gauss(x_eval[wm], *po)
        ss_res = float(np.sum((resid[wm]-y_pred)**2))
        ss_tot = float(np.sum((resid[wm]-resid[wm].mean())**2))
        gauss_r2 = 1.0 - ss_res/ss_tot if ss_tot > 0 else 0.0
    except Exception:
        lambdamax = lm_rough; gauss_r2 = 0.0; sig_fit = 15.0; amp_fit=float(resid[wm].max()); ctr_fit=lm_rough

    if lambdamax <= peak_wl_min + 1.5:
        return 0.0, 0.0, {"rmse": rmse, "r2": r2, "n": n_val, "bg": bg,
                           "x_eval": x_eval, "y_smooth": y_smooth, "resid": resid}

    idx_lm  = np.argmin(np.abs(x_eval - lambdamax))
    peak_ab = float(y_smooth[idx_lm])
    val_rng = (x_eval >= lambdamax-60.0) & (x_eval <= lambdamax-10.0)
    valley_ab = float(y_smooth[val_rng].min()) if val_rng.sum() > 0 else float(y_smooth[pk_mask][0])
    base_mask = (x_eval >= 540.0) & (x_eval <= 560.0)
    base_ab   = float(y_smooth[base_mask].mean())

    denom = valley_ab - base_ab
    if denom <= 0.0:
        pv = 0.0; lambdamax = 0.0
    else:
        pv = (peak_ab - base_ab) / denom
        if pv <= 0.0:
            pv = 0.0; lambdamax = 0.0

    return pv, lambdamax, {"rmse": rmse, "r2": r2, "n": n_val,
                            "gauss_r2": gauss_r2 if 'gauss_r2' in dir() else 0.0,
                            "bg": bg, "x_eval": x_eval,
                            "y_smooth": y_smooth, "resid": resid}

# ─── 비교 실행 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    CSV_PATH  = "2508optimize/spectra_with_params_0407.csv"
    N_SAMPLES = 152          # 비교할 샘플 수
    PLOT_SAMPLES = [1, 5, 10, 20, 50, 100]   # 상세 플롯할 샘플 번호
    OUT_DIR = "bg_comparison_results"
    os.makedirs(OUT_DIR, exist_ok=True)

    print("CSV 로드 중...")
    param_dict, data_dict = load_multisample_csv(CSV_PATH)

    records = []
    plot_data = {}   # {i: {A/B/C: {...}}}

    for j in range(N_SAMPLES):
        i = j + 1
        key = f"Sample_{i}"
        if key not in data_dict:
            continue

        uv = data_dict[key]
        wl = uv["Wavelength"]
        ab = uv["RawSpectrum"]
        data_df = pd.DataFrame(ab, index=wl, columns=[key])

        # ── 방식 A (현재) ────────────────────────────────────────────────
        try:
            pv_A, lm_A = calculateUV_Data_clean_csv(uv_df=data_df)
        except Exception as e:
            pv_A, lm_A = 0.0, 0.0

        # ── 방식 B (단파장) ──────────────────────────────────────────────
        try:
            pv_B, lm_B, info_B = method_B_short(uv_df=data_df)
        except Exception as e:
            pv_B, lm_B, info_B = 0.0, 0.0, {}

        # ── 방식 C (동시) ────────────────────────────────────────────────
        try:
            pv_C, lm_C, info_C = method_C_joint(uv_df=data_df)
        except Exception as e:
            pv_C, lm_C, info_C = 0.0, 0.0, {}

        records.append({
            "sample": i,
            "A_lambdamax": lm_A, "A_pv": pv_A,
            "B_lambdamax": lm_B, "B_pv": pv_B,
            "B_bg_r2": info_B.get("r2", np.nan),
            "B_bg_rmse": info_B.get("rmse", np.nan),
            "B_n": info_B.get("n", np.nan),
            "C_lambdamax": lm_C, "C_pv": pv_C,
            "C_bg_r2": info_C.get("r2", np.nan),
            "C_bg_rmse": info_C.get("rmse", np.nan),
            "C_n": info_C.get("n", np.nan),
        })

        # 상세 플롯용 데이터 저장
        if i in PLOT_SAMPLES:
            plot_data[i] = {
                "A": {"pv": pv_A, "lm": lm_A},
                "B": {"pv": pv_B, "lm": lm_B, **info_B},
                "C": {"pv": pv_C, "lm": lm_C, **info_C},
                "raw_wl": np.array(wl), "raw_ab": np.array(ab),
            }

        if (j+1) % 20 == 0:
            print(f"  {j+1}/{N_SAMPLES} 완료")

    df = pd.DataFrame(records)
    csv_out = os.path.join(OUT_DIR, "comparison_results.csv")
    df.to_csv(csv_out, index=False)
    print(f"\n결과 저장: {csv_out}")

    # ─── 통계 요약 ────────────────────────────────────────────────────────

    def _det_rate(col): return (df[col] > 0).mean() * 100.0
    def _lm_stats(col):
        v = df[col][df[col] > 0]
        return v.mean(), v.std()

    print("\n" + "="*62)
    print(f"{'지표':<26} {'방식A(현재)':>10} {'방식B(단파장)':>13} {'방식C(동시)':>12}")
    print("-"*62)
    dr_A = _det_rate("A_pv"); dr_B = _det_rate("B_pv"); dr_C = _det_rate("C_pv")
    print(f"{'피크 검출률 (%)':26} {dr_A:>10.1f} {dr_B:>13.1f} {dr_C:>12.1f}")

    ma,sa = _lm_stats("A_lambdamax"); mb,sb = _lm_stats("B_lambdamax"); mc,sc = _lm_stats("C_lambdamax")
    print(f"{'λmax 평균 (nm)':26} {ma:>10.1f} {mb:>13.1f} {mc:>12.1f}")
    print(f"{'λmax 표준편차 (nm)':26} {sa:>10.1f} {sb:>13.1f} {sc:>12.1f}")

    pvA = df["A_pv"][df["A_pv"]>0]; pvB = df["B_pv"][df["B_pv"]>0]; pvC = df["C_pv"][df["C_pv"]>0]
    print(f"{'pv_ratio 평균':26} {pvA.mean():>10.3f} {pvB.mean():>13.3f} {pvC.mean():>12.3f}")
    print(f"{'pv_ratio 표준편차':26} {pvA.std():>10.3f} {pvB.std():>13.3f} {pvC.std():>12.3f}")

    bgr2_B = df["B_bg_r2"].mean(); bgr2_C = df["C_bg_r2"].mean()
    bgrms_B = df["B_bg_rmse"].mean(); bgrms_C = df["C_bg_rmse"].mean()
    print(f"{'배경 피팅 R² (평균)':26} {'N/A':>10} {bgr2_B:>13.4f} {bgr2_C:>12.4f}")
    print(f"{'배경 피팅 RMSE (평균)':26} {'N/A':>10} {bgrms_B:>13.6f} {bgrms_C:>12.6f}")

    # 세 방법 모두 피크 검출한 샘플의 λmax 일치도
    both = df[(df["A_pv"]>0) & (df["B_pv"]>0) & (df["C_pv"]>0)]
    if len(both) > 0:
        diff_AB = np.abs(both["A_lambdamax"] - both["B_lambdamax"])
        diff_AC = np.abs(both["A_lambdamax"] - both["C_lambdamax"])
        diff_BC = np.abs(both["B_lambdamax"] - both["C_lambdamax"])
        print(f"\n공통 검출 샘플 수: {len(both)}")
        print(f"  |lA - lB| 평균: {diff_AB.mean():.2f} nm")
        print(f"  |lA - lC| 평균: {diff_AC.mean():.2f} nm")
        print(f"  |lB - lC| 평균: {diff_BC.mean():.2f} nm")

    print("="*62)

    # ─── 상세 플롯 (PLOT_SAMPLES 개) ──────────────────────────────────────
    for i, pd_info in plot_data.items():
        fig, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=False)

        raw_wl = pd_info["raw_wl"]
        raw_ab = pd_info["raw_ab"]

        # ── A 방식 (현재): 파이프라인 재현해 곡선 그리기 ──────────────
        ax = axes[0]
        ax.set_title(f"Sample {i} │ 방식 A (현재: polyfit)", fontsize=11)
        col_key = f"Sample_{i}"
        data_df_ = pd.DataFrame(raw_ab, index=raw_wl, columns=[col_key])
        # 재현 파이프라인
        _x = data_df_.index.values; _y = data_df_[col_key].values
        order = np.argsort(_x)
        x_ev = np.linspace(350, 950, 20000)
        y_int = np.interp(x_ev, _x[order], _y[order])
        raw_  = np.array([x_ev, y_int])
        sm = smooth_Boxcar(raw_, 250)
        sl = getSliceSpectrum(sm, 360, 700)
        sg = selective_noise_correction(sl, (360,700), 51, 3)
        p_wl, p_ab = smooth_polyfit(sg[0], sg[1], degree=19)
        sl2 = getSliceSpectrum((p_wl, p_ab), 420, 550)

        ax.plot(raw_wl, raw_ab, color="#aaa", lw=0.6, alpha=0.7, label="Raw")
        ax.plot(x_ev, y_int, color="#4c72b0", lw=0.9, alpha=0.6, label="Interpolated")
        ax.plot(sl2[0], sl2[1], color="#dd8452", lw=1.5, label="polyfit (420–550 nm)")
        ax.axvspan(420, 550, alpha=0.07, color="green")
        lm_A_ = pd_info["A"]["lm"]; pv_A_ = pd_info["A"]["pv"]
        if lm_A_ > 0:
            ax.axvline(lm_A_, color="red", lw=1, ls=":", label=f"λmax={lm_A_:.1f} nm  pv={pv_A_:.3f}")
        ax.set_xlim(380, 720); ax.set_ylabel("Absorbance"); ax.legend(fontsize=7)

        # ── B 방식 (단파장) ───────────────────────────────────────────
        ax = axes[1]
        ax.set_title(f"Sample {i} │ 방식 B (단파장 배경: 420–510 nm)", fontsize=11)
        if "x_eval" in pd_info["B"] and pd_info["B"]["x_eval"] is not None:
            xev = pd_info["B"]["x_eval"]; ysm = pd_info["B"]["y_smooth"]
            bg_B = pd_info["B"].get("bg", None); res_B = pd_info["B"].get("resid", None)
            ax.plot(raw_wl, raw_ab, color="#aaa", lw=0.6, alpha=0.6, label="Raw")
            ax.plot(xev, ysm, color="#4c72b0", lw=1.2, label="Gaussian smooth")
            if bg_B is not None:
                ax.plot(xev, bg_B, color="#dd8452", lw=1.2, ls="--",
                        label=f"BG fit (short, R²={pd_info['B'].get('r2',0):.3f})")
            ax.axvspan(420, 510, alpha=0.12, color="orange", label="Fitting region")
        lm_B_ = pd_info["B"]["lm"]; pv_B_ = pd_info["B"]["pv"]
        if lm_B_ > 0:
            ax.axvline(lm_B_, color="red", lw=1, ls=":", label=f"λmax={lm_B_:.1f} nm  pv={pv_B_:.3f}")
        ax.set_xlim(380, 720); ax.set_ylabel("Absorbance"); ax.legend(fontsize=7)

        # ── C 방식 (동시) ─────────────────────────────────────────────
        ax = axes[2]
        ax.set_title(f"Sample {i} │ 방식 C (동시 배경: 420–510+560–700 nm)", fontsize=11)
        if "x_eval" in pd_info["C"] and pd_info["C"]["x_eval"] is not None:
            xev = pd_info["C"]["x_eval"]; ysm = pd_info["C"]["y_smooth"]
            bg_C = pd_info["C"].get("bg", None)
            ax.plot(raw_wl, raw_ab, color="#aaa", lw=0.6, alpha=0.6, label="Raw")
            ax.plot(xev, ysm, color="#4c72b0", lw=1.2, label="Gaussian smooth")
            if bg_C is not None:
                ax.plot(xev, bg_C, color="#dd8452", lw=1.2, ls="--",
                        label=f"BG fit (joint, R²={pd_info['C'].get('r2',0):.3f})")
            ax.axvspan(420, 510, alpha=0.12, color="orange", label="Short fit region")
            ax.axvspan(560, 700, alpha=0.07, color="blue", label="Long fit region")
        lm_C_ = pd_info["C"]["lm"]; pv_C_ = pd_info["C"]["pv"]
        if lm_C_ > 0:
            ax.axvline(lm_C_, color="red", lw=1, ls=":", label=f"λmax={lm_C_:.1f} nm  pv={pv_C_:.3f}")
        ax.set_xlim(380, 720); ax.set_ylabel("Absorbance"); ax.set_xlabel("Wavelength (nm)")
        ax.legend(fontsize=7)

        plt.tight_layout()
        fig_path = os.path.join(OUT_DIR, f"sample_{i:03d}_comparison.png")
        plt.savefig(fig_path, dpi=120)
        plt.close()
        print(f"  그림 저장: {fig_path}")

    # ─── 전체 λmax 분포 비교 플롯 ─────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    colors = ["#4c72b0", "#dd8452", "#55a868"]
    for ax, col_lm, col_pv, label, color in zip(
            axes,
            ["A_lambdamax","B_lambdamax","C_lambdamax"],
            ["A_pv","B_pv","C_pv"],
            ["A 현재 (polyfit)","B 단파장 배경","C 동시 배경"],
            colors):
        vals = df[col_lm][df[col_lm]>0]
        ax.hist(vals, bins=20, color=color, alpha=0.7, edgecolor="white")
        ax.axvline(vals.mean(), color="red", lw=1.2, ls="--",
                   label=f"mean={vals.mean():.1f} nm")
        ax.set_title(f"λmax 분포: {label}\n검출률={_det_rate(col_pv):.1f}%", fontsize=10)
        ax.set_xlabel("λmax (nm)"); ax.set_ylabel("Count"); ax.legend(fontsize=8)
    plt.tight_layout()
    dist_path = os.path.join(OUT_DIR, "lambdamax_distribution.png")
    plt.savefig(dist_path, dpi=120)
    plt.close()
    print(f"\nλmax 분포 저장: {dist_path}")

    # ─── pv_ratio 산점도 (A vs B, A vs C, B vs C) ─────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    pairs = [("A_pv","B_pv","A vs B"), ("A_pv","C_pv","A vs C"), ("B_pv","C_pv","B vs C")]
    for ax, (cx, cy, ttl) in zip(axes, pairs):
        both_ = df[(df[cx]>0) & (df[cy]>0)]
        ax.scatter(both_[cx], both_[cy], alpha=0.5, s=20)
        if len(both_) > 1:
            lim = max(both_[cx].max(), both_[cy].max()) * 1.05
            ax.plot([0, lim], [0, lim], "r--", lw=1)
        ax.set_xlabel(f"pv_ratio {cx[:1]}"); ax.set_ylabel(f"pv_ratio {cy[:1]}")
        ax.set_title(f"pv_ratio: {ttl}  (n={len(both_)})", fontsize=10)
    plt.tight_layout()
    sc_path = os.path.join(OUT_DIR, "pv_ratio_scatter.png")
    plt.savefig(sc_path, dpi=120)
    plt.close()
    print(f"pv_ratio 산점도 저장: {sc_path}")

    print("\n완료.")
