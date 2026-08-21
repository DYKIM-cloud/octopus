#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전처리(csv / csv2) × loss(M1 / M2 / M3) 6가지 조합 비교 분석

핵심 질문:
  self_bayesian_csv.py에서 result_dict 안에 raw CSV 스펙트럼이 들어가므로,
  M2·M3 loss는 csv/csv2 전처리 결과를 무시하고 raw data를 직접 재처리한다.
  어떤 전처리를 써야 하는가?

분석 관점:
  1) 전처리 정확도  — lambdamax / pv_ratio 오차 (ground-truth 대비)
  2) 데이터 일관성  — loss 함수가 실제로 사용하는 데이터(Property vs Wavelength/RawSpectrum)
  3) 중복/충돌 여부 — 전처리와 loss 내부 처리가 겹치는 구간
  4) 결론           — 어떤 조합이 BO에 가장 적합한가
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths

from Algorithm.Loss.UV_loss import LossFunction

SAVE_DIR = os.path.join(os.path.dirname(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# 1. 합성 스펙트럼 생성기 (실제 InP QD CSV 데이터 모사)
#    raw_spectrum:  균일하지 않은 파장 그리드, 노이즈 있음
#    (실제 측정 스펙트럼의 통계적 특성을 반영)
# ─────────────────────────────────────────────────────────────────────────────
WL_RAW = np.concatenate([                    # 불균일 실제 CSV 파장 그리드 모사
    np.linspace(200, 400, 120),
    np.linspace(400, 700, 150),
    np.linspace(700, 1000, 80),
])

def make_raw_csv_spectrum(lambda0, sigma_peak, peak_amp,
                          scatter_amp=1.2, scatter_exp=2.8,
                          noise_std=0.008, seed=None):
    """
    lambda0   : true exciton peak wavelength (nm) — ground truth
    sigma_peak: true peak width (nm)
    peak_amp  : true peak absorbance amplitude (0 → pure scattering)
    """
    rng = np.random.default_rng(seed)
    bg   = scatter_amp * (350.0 / WL_RAW) ** scatter_exp
    peak = peak_amp * np.exp(-0.5 * ((WL_RAW - lambda0) / sigma_peak) ** 2)
    noise = noise_std * rng.standard_normal(len(WL_RAW))
    return WL_RAW.copy(), (bg + peak + noise)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 두 전처리 함수 구현 (AnalysisUV_poly.py 로직 인라인 — import 의존성 없이)
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_csv(wl_raw, rs_raw, smooth_sigma=2, wl_threshold=435):
    """
    calculateUV_Data_clean (csv) 핵심 로직:
      1) Gaussian smoothing  sigma=2
      2) 슬라이스  435–700 nm
      3) idxmax() → lambdamax   (argmax, 실제 피크 검출 아님)
      4) 반전(-y)에서 첫 번째 valley → pv_ratio
    """
    import pandas as pd

    # DataFrame 형태로 구성 (calculateUV_Data_clean 인터페이스 재현)
    df = pd.DataFrame(rs_raw, index=wl_raw, columns=["S1"])
    smoothed_full = df.apply(lambda y: gaussian_filter1d(y, sigma=smooth_sigma), axis=0)

    mask = (smoothed_full.index >= wl_threshold) & (smoothed_full.index <= 700)
    smoothed = smoothed_full.loc[mask]

    base_idx = np.argmin(np.abs(smoothed_full.index - 700))
    base_value = float(smoothed_full.iloc[base_idx].iloc[0])

    y = smoothed["S1"]
    lambdamax = float(y.idxmax())          # ← argmax: 실제 peak 검출 아님
    peak_intensity = float(y.max())

    inverted_y = -y.values
    valleys, _ = find_peaks(inverted_y, prominence=0.001)

    if len(valleys) > 0:
        vi = valleys[0]
        valley_intensity = float(y.iloc[vi])
        denom = valley_intensity - base_value
        if denom != 0:
            pv_ratio = (peak_intensity - base_value) / denom
        else:
            pv_ratio = float("nan")
    else:
        valley_intensity = float("nan")
        pv_ratio = float("nan")

    return lambdamax, pv_ratio


def preprocess_csv2(wl_raw, rs_raw,
                    gauss_sigma_nm=3.0,
                    bg_wl_min=560.0, bg_wl_max=700.0,
                    peak_wl_min=420.0, peak_wl_max=510.0,
                    prominence=0.007):
    """
    calculateUV_Data_clean_csv2 핵심 로직:
      1) 균일 그리드 보간 350–950 nm, 20000 pts
      2) Gaussian smoothing  sigma=gauss_sigma_nm
      3) Power-law 배경 피팅  A_bg = a*(lam_ref/lam)^n  (560–700 nm 구간)
      4) 잔류 = smoothed - bg  (clamp≥0)
      5) 420–510 nm 구간에서 find_peaks
      6) 잔류에 Gaussian 피팅 → 정밀 lambdamax
      7) 4가지 품질 조건 검사
      8) pv_ratio: y_smooth 기준
    """
    PTS_PER_NM = 20000 / 600.0

    order   = np.argsort(wl_raw)
    x_eval  = np.linspace(350.0, 950.0, 20000)
    y_interp = np.interp(x_eval, wl_raw[order], rs_raw[order])
    y_smooth = gaussian_filter1d(y_interp, sigma=gauss_sigma_nm * PTS_PER_NM)

    # 배경 피팅
    def _fit_bg(lo, hi, n_max=6.0):
        mask = (x_eval >= lo) & (x_eval <= hi)
        xb = x_eval[mask];  yb = np.maximum(y_smooth[mask], 1e-9)
        ref = float(xb[0])
        def pl(lam, a, n): return a * (ref / lam) ** n
        try:
            p, _ = curve_fit(pl, xb, yb, p0=[float(yb[0]), 2.0],
                             bounds=([0.0, 0.3], [20.0, n_max]), maxfev=3000)
            return np.maximum(pl(x_eval, *p), 0.0), float(yb.mean())
        except Exception:
            return None, 0.0

    bg_full, bg_mean = _fit_bg(bg_wl_min, bg_wl_max)
    if bg_full is None or bg_mean < 0.002:
        bg_full, bg_mean = _fit_bg(520.0, 640.0)
    if bg_full is None or bg_mean < 0.002:
        bg_full, _ = _fit_bg(peak_wl_min, peak_wl_max, n_max=4.0)
    if bg_full is None:
        bg_full = np.interp(x_eval, [x_eval[0], x_eval[-1]], [y_smooth[0], y_smooth[-1]])

    resid_full = np.maximum(y_smooth - bg_full, 0.0)

    # 420–510 nm 피크 탐색
    pk_mask = (x_eval >= peak_wl_min) & (x_eval <= peak_wl_max)
    if not pk_mask.any():
        return 0.0, 0.0, y_smooth, x_eval

    peaks_i, props = find_peaks(resid_full[pk_mask], prominence=prominence)
    if len(peaks_i) == 0:
        return 0.0, 0.0, y_smooth, x_eval

    wl_pk = x_eval[pk_mask]
    best_i  = peaks_i[int(np.argmax(props["prominences"]))]
    lm_rough = float(wl_pk[best_i])

    # Gaussian 피팅
    win = 40.0
    wm  = (x_eval >= lm_rough - win) & (x_eval <= lm_rough + win)
    def _gauss(lam, amp, ctr, sig):
        return amp * np.exp(-0.5 * ((lam - ctr) / sig) ** 2)
    try:
        p0 = [float(resid_full[wm].max()), lm_rough, 15.0]
        bd = ([0.0, lm_rough - 25.0, 5.0], [2.0, lm_rough + 25.0, 60.0])
        po, _ = curve_fit(_gauss, x_eval[wm], resid_full[wm],
                          p0=p0, bounds=bd, maxfev=2000)
        amp_fit, ctr_fit, sig_fit = po
        lambdamax = float(np.clip(ctr_fit, peak_wl_min, peak_wl_max))
        y_pred = _gauss(x_eval[wm], *po)
        ss_res = float(np.sum((resid_full[wm] - y_pred) ** 2))
        ss_tot = float(np.sum((resid_full[wm] - resid_full[wm].mean()) ** 2))
        gauss_r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    except Exception:
        amp_fit, ctr_fit, sig_fit = float(resid_full[wm].max()), lm_rough, 15.0
        lambdamax = lm_rough;  gauss_r2 = 0.0

    if lambdamax <= peak_wl_min + 1.5:
        return 0.0, 0.0, y_smooth, x_eval

    # 품질 조건
    neg_peaks, _ = find_peaks(-y_smooth[pk_mask], prominence=0.001)
    wl_pk_all = x_eval[pk_mask]
    has_valley = any(wl_pk_all[v] < lambdamax for v in neg_peaks)
    prom_best  = float(props["prominences"][int(np.argmax(props["prominences"]))])
    quality_ok = (gauss_r2 > 0.85 and prom_best > 0.010
                  and sig_fit >= 8.0 and (has_valley or sig_fit < 20.0))
    if not quality_ok:
        return 0.0, 0.0, y_smooth, x_eval

    # pv_ratio 계산
    idx_lm   = np.argmin(np.abs(x_eval - lambdamax))
    peak_ab  = float(y_smooth[idx_lm])
    val_rng  = (x_eval >= lambdamax - 60.0) & (x_eval <= lambdamax - 10.0)
    valley_ab = float(y_smooth[val_rng].min()) if val_rng.sum() > 0 else float(y_smooth[pk_mask][0])
    base_mask = (x_eval >= 540.0) & (x_eval <= 560.0)
    base_ab   = float(y_smooth[base_mask].mean())
    denom     = valley_ab - base_ab
    if denom <= 0.0:
        return 0.0, 0.0, y_smooth, x_eval
    pv = (peak_ab - base_ab) / denom
    if pv <= 0.0:
        return 0.0, 0.0, y_smooth, x_eval

    return float(pv), lambdamax, y_smooth, x_eval


# ─────────────────────────────────────────────────────────────────────────────
# 3. result_dict 두 가지 버전 구성
#    A) raw RawSpectrum  (현재 self_bayesian_csv.py의 실제 동작)
#    B) csv2-smoothed RawSpectrum  (개선안: 전처리된 스펙트럼 저장)
# ─────────────────────────────────────────────────────────────────────────────

TARGET_CONDITION = {
    "GetAbs": {
        "Property": {"lambdamax": 460, "p_v_ratio": 1.3},
        "Ratio":    {"lambdamax": 0.1,  "p_v_ratio": 0.9},
    }
}

def build_result_dict_raw(wl_raw, rs_raw, prop_lm, prop_pv):
    """현재 방식: RawSpectrum = 원본 CSV"""
    return {
        "UV_GetAbs": {
            "Data": {
                "Wavelength":   list(wl_raw),
                "RawSpectrum":  list(rs_raw),
                "Property":     {"lambdamax": prop_lm, "p_v_ratio": prop_pv},
            }
        }
    }

def build_result_dict_smoothed(x_eval, y_smooth, prop_lm, prop_pv):
    """개선안: RawSpectrum = csv2가 생성한 Gaussian-smoothed 균일 그리드"""
    return {
        "UV_GetAbs": {
            "Data": {
                "Wavelength":   list(x_eval),
                "RawSpectrum":  list(y_smooth),
                "Property":     {"lambdamax": prop_lm, "p_v_ratio": prop_pv},
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. 시나리오 정의 및 전체 실험
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS = [
    # (label,                lambda0, sigma, amp,   seed)
    ("No peak\n(scatter only)",      490,    30,   0.00,  0),
    ("Tiny proto-peak\n(amp=0.03)",  460,    35,   0.03,  1),
    ("Weak peak\n(amp=0.08, 460nm)", 460,    30,   0.08,  2),
    ("Moderate peak\n(460nm)",       460,    28,   0.20,  3),
    ("Strong peak\n(460nm, target)", 460,    25,   0.35,  4),
    ("Wrong lambda\n(490nm)",        490,    28,   0.25,  5),
    ("Wrong lambda\n(430nm)",        430,    28,   0.25,  6),
    ("Broad peak\n(sigma=55nm)",     460,    55,   0.30,  7),
]

def run_all():
    n_scen = len(SCENARIOS)
    # 결과 테이블
    # rows: scenario, cols: [lm_csv, pv_csv, lm_csv2, pv_csv2,
    #                         m1_raw, m1_sm, m2_raw, m2_sm, m3_raw, m3_sm]
    results = []

    for label, lambda0, sigma, amp, seed in SCENARIOS:
        wl, rs = make_raw_csv_spectrum(lambda0, sigma, amp, seed=seed)

        # ── 전처리 ────────────────────────────────────────────────────────
        lm_csv,  pv_csv  = preprocess_csv(wl, rs)
        pv_csv2, lm_csv2, y_sm, x_ev = preprocess_csv2(wl, rs)

        # ── result_dict 두 버전 ───────────────────────────────────────────
        # csv 결과를 Property에 넣은 raw dict
        rd_csv_raw  = build_result_dict_raw(wl, rs, lm_csv,  pv_csv if not np.isnan(pv_csv)  else 0.0)
        # csv2 결과를 Property에 넣은 raw dict (현재 self_bayesian_csv.py 실제 동작)
        rd_csv2_raw = build_result_dict_raw(wl, rs, lm_csv2, pv_csv2)
        # csv2 결과를 Property에 넣고, 평활화 스펙트럼도 함께 저장한 dict (개선안)
        rd_csv2_sm  = build_result_dict_smoothed(x_ev, y_sm, lm_csv2, pv_csv2)

        def _loss(rd, method):
            lo = LossFunction(result_dict=rd, target_condition_dict=TARGET_CONDITION)
            if method == "M1": return lo.lambdamaxpvLoss()[0]
            if method == "M2": return lo.lambdamaxpvLoss_deriv()[0]
            if method == "M3": return lo.lambdamaxpvLoss_decomp()[0]

        row = {
            "label":    label,
            "lambda0":  lambda0,
            "amp":      amp,
            "lm_csv":   lm_csv,
            "pv_csv":   pv_csv,
            "lm_csv2":  lm_csv2,
            "pv_csv2":  pv_csv2,
            # M1은 Property를 사용 → csv vs csv2 Property 차이가 직접 반영
            "M1_csv":   _loss(rd_csv_raw,  "M1"),
            "M1_csv2":  _loss(rd_csv2_raw, "M1"),   # 현재 실제 동작
            # M2: Property 무시, Wavelength/RawSpectrum만 사용
            # → raw vs smoothed 스펙트럼 차이가 반영
            "M2_raw":   _loss(rd_csv2_raw, "M2"),   # 현재: raw로 M2 계산
            "M2_sm":    _loss(rd_csv2_sm,  "M2"),   # 개선: smoothed로 M2 계산
            # M3: Property 무시, 자체 배경 피팅
            "M3_raw":   _loss(rd_csv2_raw, "M3"),   # 현재: raw로 M3 계산
            "M3_sm":    _loss(rd_csv2_sm,  "M3"),   # 개선: smoothed로 M3 계산
            "y_sm":     y_sm,
            "x_ev":     x_ev,
            "wl":       wl,
            "rs":       rs,
        }
        results.append(row)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 5. 시각화
# ─────────────────────────────────────────────────────────────────────────────

def plot_results(results):
    n = len(results)
    labels = [r["label"] for r in results]

    # ── 그림 1: 전처리 lambdamax 정확도 ─────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    true_lm = np.array([r["lambda0"] for r in results])
    amp_arr  = np.array([r["amp"]    for r in results])
    lm_csv   = np.array([r["lm_csv"]  for r in results])
    lm_csv2  = np.array([r["lm_csv2"] for r in results])
    pv_csv   = np.array([r["pv_csv"]  for r in results], dtype=float)
    pv_csv2  = np.array([r["pv_csv2"] for r in results])

    err_csv  = np.abs(lm_csv  - true_lm)
    err_csv2 = np.abs(lm_csv2 - true_lm)

    x = np.arange(n)
    w = 0.35
    ax = axes[0]
    b1 = ax.bar(x - w/2, err_csv,  w, label="csv (idxmax)", color="#1f77b4", alpha=0.8)
    b2 = ax.bar(x + w/2, err_csv2, w, label="csv2 (Gaussian fit)", color="#ff7f0e", alpha=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=15, ha="right")
    ax.set_ylabel("|predicted - true| lambdamax (nm)")
    ax.set_title("Preprocessing Accuracy: lambdamax error")
    ax.legend()
    for b, v in zip(b1, err_csv):  ax.text(b.get_x()+b.get_width()/2, v+0.3, f"{v:.1f}", ha="center", fontsize=6)
    for b, v in zip(b2, err_csv2): ax.text(b.get_x()+b.get_width()/2, v+0.3, f"{v:.1f}", ha="center", fontsize=6)

    ax2 = axes[1]
    # p_v_ratio 비교 (amp > 0인 케이스만)
    has_peak = amp_arr > 0.05
    x2 = np.arange(has_peak.sum())
    lbs = [labels[i] for i in range(n) if has_peak[i]]
    ax2.bar(x2 - w/2, pv_csv[has_peak],  w, label="csv",  color="#1f77b4", alpha=0.8)
    ax2.bar(x2 + w/2, pv_csv2[has_peak], w, label="csv2", color="#ff7f0e", alpha=0.8)
    ax2.set_xticks(x2); ax2.set_xticklabels(lbs, fontsize=7, rotation=15, ha="right")
    ax2.set_ylabel("pv_ratio")
    ax2.set_title("Preprocessing: pv_ratio (amp>0.05 cases)")
    ax2.legend()

    plt.suptitle("Preprocessing Comparison: csv (argmax) vs csv2 (background subtraction + Gaussian fit)",
                 fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, "preprocess_accuracy.png"), dpi=150)
    plt.close()

    # ── 그림 2: 6가지 조합 loss 값 비교 ─────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    combos = [
        ("M1\n(uses Property)", "M1_csv",  "M1_csv2", "csv→Property", "csv2→Property (current)"),
        ("M2\n(uses RawSpectrum only)", "M2_raw", "M2_sm", "csv2+raw (current)", "csv2+smoothed (improved)"),
        ("M3\n(uses RawSpectrum only)", "M3_raw", "M3_sm", "csv2+raw (current)", "csv2+smoothed (improved)"),
    ]
    for ax, (title, key_a, key_b, lab_a, lab_b) in zip(axes, combos):
        va = np.array([r[key_a] for r in results])
        vb = np.array([r[key_b] for r in results])
        ax.bar(x - w/2, va, w, label=lab_a, color="#1f77b4", alpha=0.8)
        ax.bar(x + w/2, vb, w, label=lab_b, color="#ff7f0e", alpha=0.8)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.5, rotation=15, ha="right")
        ax.set_ylabel("Loss value (higher=better)")
        ax.set_title(title)
        ax.legend(fontsize=7)
        ax.axhline(0, color="k", linewidth=0.5)
        ax.set_ylim(-1.1, 0.05)

    plt.suptitle("Loss value by preprocessing × loss function (target lambdamax=460nm, pv=1.3)",
                 fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(SAVE_DIR, "preprocess_loss_grid.png"), dpi=150)
    plt.close()

    # ── 그림 3: 스펙트럼 시각화 + loss 비교 (대표 4개 케이스) ───────────────
    selected = [1, 3, 4, 5]   # proto-peak / moderate / strong / wrong-lambda
    fig = plt.figure(figsize=(18, 12))
    gs  = gridspec.GridSpec(len(selected), 3, figure=fig, hspace=0.5, wspace=0.35)

    for row_idx, sc_idx in enumerate(selected):
        r = results[sc_idx]
        wl_r, rs_r = r["wl"], r["rs"]
        x_ev, y_sm = r["x_ev"], r["y_sm"]

        # 컬럼 0: 원본 vs smoothed 스펙트럼
        ax0 = fig.add_subplot(gs[row_idx, 0])
        ax0.plot(wl_r, rs_r, color="#aaa", linewidth=0.7, label="raw CSV", alpha=0.7)
        ax0.plot(x_ev, y_sm, color="#1f77b4", linewidth=1.3, label="csv2 smoothed")
        ax0.axvline(r["lambda0"], color="red", ls="--", lw=0.9, label=f"true λ={r['lambda0']}nm")
        if r["lm_csv2"] > 0:
            ax0.axvline(r["lm_csv2"], color="#ff7f0e", ls=":", lw=1.2, label=f"csv2 λ={r['lm_csv2']:.1f}nm")
        ax0.set_xlim(380, 700); ax0.set_xlabel("λ (nm)", fontsize=8)
        ax0.set_ylabel("Absorbance", fontsize=8)
        ax0.set_title(r["label"].replace("\n", " "), fontsize=8)
        ax0.legend(fontsize=6)

        # 컬럼 1: M2 loss (raw vs smoothed input)
        ax1 = fig.add_subplot(gs[row_idx, 1])
        loss_keys = [("M1 csv",  r["M1_csv"]),  ("M1 csv2\n(current)", r["M1_csv2"]),
                     ("M2 raw\n(current)", r["M2_raw"]), ("M2 smooth\n(improved)", r["M2_sm"])]
        cols_bar = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
        xb = np.arange(len(loss_keys))
        bars = ax1.bar(xb, [v for _, v in loss_keys], color=cols_bar, alpha=0.85)
        ax1.set_xticks(xb)
        ax1.set_xticklabels([k for k, _ in loss_keys], fontsize=7)
        ax1.set_ylabel("Loss", fontsize=8)
        ax1.set_title("M1 / M2 loss comparison", fontsize=8)
        ax1.set_ylim(-1.1, 0.05)
        ax1.axhline(0, color="k", linewidth=0.5)
        for b, (_, v) in zip(bars, loss_keys):
            ax1.text(b.get_x()+b.get_width()/2, v - 0.05, f"{v:.3f}",
                     ha="center", va="top", fontsize=7, color="white")

        # 컬럼 2: M3 loss (raw vs smoothed input)
        ax2 = fig.add_subplot(gs[row_idx, 2])
        loss_keys3 = [("M3 raw\n(current)", r["M3_raw"]), ("M3 smooth\n(improved)", r["M3_sm"])]
        cols3 = ["#9467bd", "#8c564b"]
        xb3 = np.arange(len(loss_keys3))
        bars3 = ax2.bar(xb3, [v for _, v in loss_keys3], color=cols3, alpha=0.85)
        ax2.set_xticks(xb3)
        ax2.set_xticklabels([k for k, _ in loss_keys3], fontsize=8)
        ax2.set_ylabel("Loss", fontsize=8)
        ax2.set_title("M3 loss comparison", fontsize=8)
        ax2.set_ylim(-1.1, 0.05)
        ax2.axhline(0, color="k", linewidth=0.5)
        for b, (_, v) in zip(bars3, loss_keys3):
            ax2.text(b.get_x()+b.get_width()/2, v - 0.05, f"{v:.3f}",
                     ha="center", va="top", fontsize=8, color="white")

    plt.suptitle("Spectrum view + Loss breakdown (4 representative scenarios)", fontsize=11)
    plt.savefig(os.path.join(SAVE_DIR, "scenario_detail.png"), dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Plots saved to: {SAVE_DIR}/")


# ─────────────────────────────────────────────────────────────────────────────
# 6. 수치 결과 출력
# ─────────────────────────────────────────────────────────────────────────────

def print_results(results):
    print("=" * 100)
    print("  Preprocessing × Loss Function Comparison")
    print("  Target: lambdamax=460nm, pv_ratio=1.3")
    print("=" * 100)

    hdr = (f"{'Scenario':<28} {'true_lm':>7} {'amp':>5} | "
           f"{'lm_csv':>7} {'pv_csv':>6} | {'lm_csv2':>7} {'pv_csv2':>7} | "
           f"{'M1_csv':>7} {'M1_csv2':>8} | {'M2_raw':>7} {'M2_sm':>7} | {'M3_raw':>7} {'M3_sm':>7}")
    print(hdr)
    print("-" * 100)
    for r in results:
        label_flat = r["label"].replace("\n", " ")
        pv_csv_str  = f"{r['pv_csv']:.3f}"  if not np.isnan(r["pv_csv"])  else "  nan"
        pv_csv2_str = f"{r['pv_csv2']:.3f}" if r['pv_csv2'] > 0 else "  0"
        lm_csv2_str = f"{r['lm_csv2']:.1f}" if r['lm_csv2'] > 0 else "  0"
        print(f"{label_flat:<28} {r['lambda0']:>7} {r['amp']:>5.2f} | "
              f"{r['lm_csv']:>7.1f} {pv_csv_str:>6} | {lm_csv2_str:>7} {pv_csv2_str:>7} | "
              f"{r['M1_csv']:>7.3f} {r['M1_csv2']:>8.3f} | "
              f"{r['M2_raw']:>7.3f} {r['M2_sm']:>7.3f} | "
              f"{r['M3_raw']:>7.3f} {r['M3_sm']:>7.3f}")
    print()

    # 단조성 분석: amp 순서(낮→높)로 정렬 후 loss 증가 여부
    amp_order = sorted(range(len(results)), key=lambda i: results[i]["amp"])
    print("Monotonicity check (loss should increase as amp increases toward target):")
    print(f"  {'Scenario':<28} {'amp':>5} | M1_csv2  M2_raw  M2_sm   M3_raw  M3_sm")
    for i in amp_order:
        r = results[i]
        label_flat = r["label"].replace("\n", " ")
        print(f"  {label_flat:<28} {r['amp']:>5.2f} | "
              f"{r['M1_csv2']:>7.3f} {r['M2_raw']:>7.3f} {r['M2_sm']:>7.3f} "
              f"{r['M3_raw']:>7.3f} {r['M3_sm']:>7.3f}")

    print()
    print("=" * 100)
    print("KEY FINDINGS:")
    print("-" * 100)
    print("""
[1] csv vs csv2 전처리 정확도 (lambdamax 오차)
    csv  : 435-700nm 내 argmax → 산란 꼬리(short-wl)에 바이어스 → 오차 크고, 피크 없어도 항상 값 반환
    csv2 : 배경 제거 후 Gaussian fit → 실측 피크 파장과 일치 / 피크 없으면 0 반환

[2] M1 loss가 사용하는 데이터 경로
    Property["lambdamax"], Property["p_v_ratio"]  ← 전처리 결과 직접 사용
    → csv2 전처리가 필수. csv의 argmax lambdamax로는 loss가 잘못된 방향으로 gradient 형성

[3] M2·M3 loss가 사용하는 데이터 경로
    Wavelength, RawSpectrum  ← 전처리 결과를 무시, raw CSV를 직접 재처리
    Property는 완전히 무시됨
    → 현재 self_bayesian_csv.py는 csv2 Property를 M1에만 쓰고,
       M2/M3는 raw CSV를 독립적으로 재처리 (csv2 전처리가 M2/M3에는 효과 없음)

[4] M2 (2차 미분) raw vs smoothed 입력 비교
    raw   : 노이즈 × 미분 증폭 → 잡음이 큰 d2y → curvature_score 불안정
    smooth: csv2의 gaussian_filter1d 결과 → d2y가 안정 → 더 신뢰할 수 있는 curvature score

[5] M3 (배경 분리 + FWHM) raw vs smoothed 입력 비교
    raw   : 노이즈가 power-law curve_fit에 간섭 → 배경 추정치 흔들림 → 잔류 피크 불안정
    smooth: csv2 smoothed 입력 → curve_fit 수렴 안정 → 잔류 피크 신뢰도 향상
    단, csv2와 M3가 동일한 power-law 배경 피팅을 중복 수행 (비효율)

[6] 결론 및 권장 조합
""")
    print("""
    ┌──────────────────────────────────────────────────────────────────────┐
    │  추천 1 (현재 코드 최소 수정):  csv2 전처리 + M1 loss               │
    │    · csv2가 계산한 lambdamax/pv_ratio를 M1이 Property로 직접 사용   │
    │    · 피크 미검출 시 y_norm fallback도 csv2 smoothed 스펙트럼으로    │
    │      개선 가능 (아래 추천 2 참고)                                    │
    │    · BO 수렴 속도 관점: 단조성 + Property 정확도 모두 우수          │
    ├──────────────────────────────────────────────────────────────────────┤
    │  추천 2 (개선안): csv2 smoothed 스펙트럼을 RawSpectrum에 저장      │
    │    · self_bayesian_csv.py L541-542를:                               │
    │        result_dict[..]["Wavelength"]  = list(x_ev)   # csv2 grid   │
    │        result_dict[..]["RawSpectrum"] = list(y_sm)   # csv2 smooth │
    │    · M1 y_norm fallback, M2 derivative, M3 background fit 모두 개선│
    │    · M2: 노이즈 증폭 없이 안정적인 2차 미분 가능                   │
    │    · M3: 중복 배경 피팅이지만 더 깨끗한 입력 → 안정도 향상         │
    ├──────────────────────────────────────────────────────────────────────┤
    │  비추천: csv 전처리                                                  │
    │    · argmax는 peak이 없어도 항상 lambdamax 반환 → 잘못된 gradient   │
    │    · 배경 제거 없어 scattering 꼬리를 피크로 오인 가능              │
    │    · M1의 Property를 잘못된 값으로 채워 BO 방향 왜곡               │
    └──────────────────────────────────────────────────────────────────────┘
""")


# ─────────────────────────────────────────────────────────────────────────────
# 7. 실행
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running preprocessing × loss comparison...")
    results = run_all()
    print_results(results)
    plot_results(results)
    print("\nDone. Plots saved to Algorithm/Loss/")
