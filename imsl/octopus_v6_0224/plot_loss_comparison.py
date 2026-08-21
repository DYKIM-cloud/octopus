"""
lambdamaxpvLoss Before/After 비교 플롯
  Before: 외부 calculateUV_Data_clean_csv2 결과를 Property에서 읽는 방식
  After : _preprocess_spectrum을 내부에서 호출하는 방식 (현재 코드)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import curve_fit

from Analysis.AnalysisUV_poly import calculateUV_Data_clean_csv2
from Algorithm.Loss.UV_loss import LossFunction

# ─── 데이터 로드 ──────────────────────────────────────────────────────────────
PATH = "2508optimize/spectra_with_params_0407.csv"
df = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()

TARGET_COND = {
    "GetAbs": {
        "Property": {"lambdamax": 460, "p_v_ratio": 1.3},
        "Ratio":    {"lambdamax": 0.1, "p_v_ratio": 0.9},
    }
}

n_samples = 0
for col in range(1, df.shape[1]):
    keys   = df.iloc[0:4, 0].values
    values = df.iloc[0:4, col].values
    if pd.isnull(keys).any() or pd.isnull(values).any():
        continue
    n_samples += 1

MAX_SAMPLES = min(n_samples, 152)

loss_before = []   # csv2 Property를 그대로 읽던 방식 (구 코드 재현)
loss_after  = []   # 현재 코드: _preprocess_spectrum 내부 호출

lm_before  = []
lm_after   = []
pv_before  = []
pv_after   = []

valid_idx  = []

# ── 구 코드 loss 계산 함수 (Before) ──────────────────────────────────────────
def _loss_before(lambdamax, pv_ratio, wl_raw, rs_raw,
                 target_lm=460, target_pv=1.3, w_lm=0.1, w_pv=0.9):
    """수정 전 lambdamaxpvLoss 로직 (외부 Property + boxcar smooth)."""
    Y_STEEP, Y_RAYLEIGH, Y_GRADUAL, Y_QD_LIKE = 0.35, 0.45, 0.55, 0.65
    L_WORST, L_RAYLEIGH, L_GRADUAL, L_NO_PEAK_CEIL = -1.5, -1.2, -0.6, -0.3
    PEAK_SCALE = 0.3

    order     = np.argsort(wl_raw)
    wl_s      = wl_raw[order]; rs_s = rs_raw[order]
    x_eval    = np.linspace(float(wl_s.min()), float(wl_s.max()), 5000)
    rs_interp = np.interp(x_eval, wl_s, rs_s)
    rs_smooth = np.convolve(rs_interp, np.ones(200) / 200, mode='same')

    idx_420 = int(np.argmin(np.abs(x_eval - 420.0)))
    idx_tgt = int(np.argmin(np.abs(x_eval - float(target_lm))))
    idx_550 = int(np.argmin(np.abs(x_eval - 550.0)))
    ab_420  = float(rs_smooth[idx_420])
    ab_tgt  = float(rs_smooth[idx_tgt])
    ab_550  = float(rs_smooth[idx_550])

    denom  = ab_420 - ab_550
    y_norm = float(np.clip((ab_tgt - ab_550) / denom, 0.0, 1.0)) if denom > 0 and ab_420 > 0 else 0.0

    if lambdamax > 0 and pv_ratio > 0:
        if lambdamax <= target_lm:
            scale = float(max(target_lm - float(wl_raw.min()), 1.0))
        else:
            scale = float(max(float(wl_raw.max()) - target_lm, 1.0))
        lm_loss = float(np.clip(abs(target_lm - lambdamax) / scale, 0.0, 1.0))
        pv_loss = float(np.clip((target_pv - pv_ratio) / target_pv, 0.0, 1.0)) if pv_ratio < target_pv else 0.0
        return -(lm_loss * w_lm + pv_loss * w_pv) * PEAK_SCALE
    else:
        if y_norm <= Y_STEEP:      return L_WORST
        elif y_norm <= Y_RAYLEIGH: return L_WORST  + (L_RAYLEIGH - L_WORST)  * (y_norm - Y_STEEP)    / (Y_RAYLEIGH - Y_STEEP)
        elif y_norm <= Y_GRADUAL:  return L_RAYLEIGH+ (L_GRADUAL  - L_RAYLEIGH)*(y_norm - Y_RAYLEIGH)/(Y_GRADUAL - Y_RAYLEIGH)
        elif y_norm <= Y_QD_LIKE:  return L_GRADUAL + (L_NO_PEAK_CEIL - L_GRADUAL)*(y_norm - Y_GRADUAL)/(Y_QD_LIKE - Y_GRADUAL)
        else:                      return L_NO_PEAK_CEIL

# ─── 전 샘플 루프 ─────────────────────────────────────────────────────────────
sample_num = 0
for col in range(1, df.shape[1]):
    if sample_num >= MAX_SAMPLES:
        break
    keys   = df.iloc[0:4, 0].values
    values = df.iloc[0:4, col].values
    if pd.isnull(keys).any() or pd.isnull(values).any():
        continue

    spectrum = df.iloc[4:, col].astype(float).tolist()
    wl_raw   = np.array(wavelength)
    rs_raw   = np.array(spectrum)

    data_df  = pd.DataFrame(spectrum, index=wavelength, columns=[f'Sample_{col}'])
    pv_csv2, lm_csv2 = calculateUV_Data_clean_csv2(
        uv_df=data_df, gauss_sigma_nm=3.0,
        bg_wl_min=560.0, bg_wl_max=700.0,
        peak_wl_min=420.0, peak_wl_max=510.0,
        prominence=0.007, plot=False
    )

    # Before: 외부 csv2 Property 읽기
    lb = _loss_before(lm_csv2, pv_csv2, wl_raw, rs_raw)
    loss_before.append(lb)
    lm_before.append(lm_csv2)
    pv_before.append(pv_csv2)

    # After: 내부 _preprocess_spectrum 호출 (현재 코드)
    result_dict = {"UV_GetAbs": {"Data": {
        "Wavelength":  wl_raw.tolist(),
        "RawSpectrum": rs_raw.tolist(),
        "Property":    {"lambdamax": lm_csv2, "p_v_ratio": pv_csv2},
    }}}
    loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=TARGET_COND)
    la, tpd  = loss_obj.lambdamaxpvLoss()
    loss_after.append(float(la))
    lm_after.append(tpd.get("lambdamax", 0))
    pv_after.append(tpd.get("p_v_ratio",  0))

    valid_idx.append(sample_num + 1)
    sample_num += 1

loss_before = np.array(loss_before)
loss_after  = np.array(loss_after)
lm_before   = np.array(lm_before,  dtype=float)
lm_after    = np.array(lm_after,   dtype=float)
pv_before   = np.array(pv_before,  dtype=float)
pv_after    = np.array(pv_after,   dtype=float)
x           = np.array(valid_idx)

diff = loss_after - loss_before

# peak detected 마스크
peak_b = (lm_before > 0) & (pv_before > 0)
peak_a = (lm_after  > 0) & (pv_after  > 0)
agree  = peak_b & peak_a
only_b = peak_b & ~peak_a
only_a = peak_a & ~peak_b
neither = ~peak_b & ~peak_a

# ─── 플롯 ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 18))
gs  = gridspec.GridSpec(4, 2, figure=fig, hspace=0.42, wspace=0.32)

C_BEF = "#4C72B0"
C_AFT = "#DD8452"
C_DIF = "#55A868"

# ── (1) Loss 전체 추이 ─────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(x, loss_before, color=C_BEF, lw=1.2, alpha=0.7, label="Before (csv2 Property + boxcar)")
ax1.plot(x, loss_after,  color=C_AFT, lw=1.2, alpha=0.7, label="After  (_preprocess_spectrum)")
ax1.axhline(-0.3, ls="--", lw=0.8, color="gray", alpha=0.6, label="No-peak ceiling (−0.3)")
ax1.axhline(-1.5, ls=":",  lw=0.8, color="gray", alpha=0.6, label="Worst (−1.5)")
ax1.set_xlabel("Sample index", fontsize=11)
ax1.set_ylabel("Loss value", fontsize=11)
ax1.set_title("Loss per Sample  —  Before vs After", fontsize=13, fontweight="bold")
ax1.legend(fontsize=9)
ax1.set_ylim(-1.7, 0.1)

# ── (2) 차이 (After − Before) ──────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, :])
ax2.bar(x, diff, color=np.where(diff >= 0, C_AFT, C_BEF), alpha=0.8, width=0.9)
ax2.axhline(0, color="black", lw=0.8)
ax2.set_xlabel("Sample index", fontsize=11)
ax2.set_ylabel("After − Before", fontsize=11)
ax2.set_title("Loss Difference  (positive = After는 더 높은 loss = 덜 패널티)", fontsize=12)
n_imp  = int((diff > 0.01).sum())
n_det  = int((diff < -0.01).sum())
n_same = len(diff) - n_imp - n_det
ax2.text(0.01, 0.97, f"↑ improved: {n_imp}  ↓ degraded: {n_det}  ≈ same: {n_same}",
         transform=ax2.transAxes, va="top", fontsize=10,
         bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))

# ── (3) λmax 비교 (scatter) ───────────────────────────────────────────────
ax3 = fig.add_subplot(gs[2, 0])
both_detected = peak_b & peak_a
ax3.scatter(lm_before[both_detected], lm_after[both_detected],
            s=25, alpha=0.7, color="#2ca02c", label="Both detected")
ax3.scatter(lm_before[only_b], lm_after[only_b],
            s=35, alpha=0.8, color=C_BEF, marker="^", label="Before only")
ax3.scatter(lm_before[only_a], lm_after[only_a],
            s=35, alpha=0.8, color=C_AFT, marker="v", label="After only")
lims = [410, 520]
ax3.plot(lims, lims, "k--", lw=0.8, alpha=0.5)
ax3.set_xlim(*lims); ax3.set_ylim(*lims)
ax3.set_xlabel("λmax  Before (nm)", fontsize=10)
ax3.set_ylabel("λmax  After  (nm)", fontsize=10)
ax3.set_title("λmax Comparison", fontsize=11)
ax3.legend(fontsize=8)

# ── (4) p_v_ratio 비교 (scatter) ──────────────────────────────────────────
ax4 = fig.add_subplot(gs[2, 1])
ax4.scatter(pv_before[both_detected], pv_after[both_detected],
            s=25, alpha=0.7, color="#2ca02c")
ax4.scatter(pv_before[only_b], pv_after[only_b],
            s=35, alpha=0.8, color=C_BEF, marker="^")
ax4.scatter(pv_before[only_a], pv_after[only_a],
            s=35, alpha=0.8, color=C_AFT, marker="v")
lims2 = [0, max(pv_before.max(), pv_after.max()) * 1.05 + 0.1]
ax4.plot(lims2, lims2, "k--", lw=0.8, alpha=0.5)
ax4.set_xlim(*lims2); ax4.set_ylim(*lims2)
ax4.set_xlabel("p_v_ratio  Before", fontsize=10)
ax4.set_ylabel("p_v_ratio  After",  fontsize=10)
ax4.set_title("p_v_ratio Comparison", fontsize=11)

# ── (5) Peak 검출 현황 누적 바 ────────────────────────────────────────────
ax5 = fig.add_subplot(gs[3, 0])
cats = ["Both\ndetected", "Before\nonly", "After\nonly", "Neither"]
cnts = [int(both_detected.sum()), int(only_b.sum()), int(only_a.sum()), int(neither.sum())]
colors = ["#2ca02c", C_BEF, C_AFT, "#aaaaaa"]
bars = ax5.bar(cats, cnts, color=colors, alpha=0.85, edgecolor="white")
for bar, cnt in zip(bars, cnts):
    ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             str(cnt), ha="center", va="bottom", fontsize=10)
ax5.set_ylabel("# Samples", fontsize=10)
ax5.set_title("Peak Detection Agreement", fontsize=11)

# ── (6) Loss 분포 histogram ────────────────────────────────────────────────
ax6 = fig.add_subplot(gs[3, 1])
bins = np.linspace(-1.55, 0.05, 33)
ax6.hist(loss_before, bins=bins, color=C_BEF, alpha=0.6, label="Before", edgecolor="white")
ax6.hist(loss_after,  bins=bins, color=C_AFT, alpha=0.6, label="After",  edgecolor="white")
ax6.axvline(-0.3, ls="--", color="gray", lw=0.9, label="−0.3")
ax6.set_xlabel("Loss value", fontsize=10)
ax6.set_ylabel("Count", fontsize=10)
ax6.set_title("Loss Distribution", fontsize=11)
ax6.legend(fontsize=8)

# 통계 텍스트
stats = (
    f"Before  mean={loss_before.mean():.3f}  std={loss_before.std():.3f}\n"
    f"After   mean={loss_after.mean():.3f}  std={loss_after.std():.3f}\n"
    f"Peak detected (Before): {int(peak_b.sum())}  /  (After): {int(peak_a.sum())}"
)
fig.text(0.01, 0.01, stats, fontsize=10, va="bottom",
         bbox=dict(boxstyle="round,pad=0.4", fc="#f0f0f0", alpha=0.9))

out_path = "fig/loss_before_after.png"
os.makedirs("fig", exist_ok=True)
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Saved: {out_path}")
print(stats)
