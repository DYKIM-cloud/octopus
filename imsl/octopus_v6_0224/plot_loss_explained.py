"""
lambdamaxpvLoss 구간별 상세 설명 플롯
  Page 1: y_norm 개념 + 구간 매핑 다이어그램 + 실제 샘플 스펙트럼 5가지
  Page 2: 피크 검출 성공 분기 — lm_loss / pv_loss / 가중합 3D surface
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

from Analysis.AnalysisUV_poly import calculateUV_Data_clean_csv2
from Algorithm.Loss.UV_loss import LossFunction

# ──────────────────────────────────────────────────────────────────────────────
# 공통 설정
# ──────────────────────────────────────────────────────────────────────────────
PATH = "2508optimize/spectra_with_params_0407.csv"
df   = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()

TARGET_LM = 460.0
TARGET_PV = 1.3
W_LM, W_PV = 0.1, 0.9

Y_STEEP, Y_RAYLEIGH, Y_GRADUAL, Y_QD_LIKE = 0.35, 0.45, 0.55, 0.65
L_WORST, L_RAYLEIGH, L_GRADUAL, L_NO_PEAK_CEIL, PEAK_SCALE = -1.5, -1.2, -0.6, -0.3, 0.3

TARGET_COND = {"GetAbs": {
    "Property": {"lambdamax": TARGET_LM, "p_v_ratio": TARGET_PV},
    "Ratio":    {"lambdamax": W_LM,      "p_v_ratio": W_PV},
}}

PTS_PER_NM = 20000 / 600.0

def preprocess(wl_raw, rs_raw):
    """_preprocess_spectrum 과 동일 파이프라인 (로컬 재현)."""
    order    = np.argsort(wl_raw)
    x_eval   = np.linspace(350, 950, 20000)
    y_interp = np.interp(x_eval, wl_raw[order], rs_raw[order])
    y_smooth = gaussian_filter1d(y_interp, sigma=3.0 * PTS_PER_NM)

    def fit_bg(lo, hi, n_max=6):
        mask = (x_eval >= lo) & (x_eval <= hi)
        xb, yb = x_eval[mask], np.maximum(y_smooth[mask], 1e-9)
        ref = float(xb[0])
        def pl(lam, a, n): return a * (ref / lam) ** n
        try:
            p, _ = curve_fit(pl, xb, yb, p0=[yb[0], 2.0],
                             bounds=([0, .3], [20, n_max]), maxfev=3000)
            return np.maximum(pl(x_eval, *p), 0), float(yb.mean())
        except Exception:
            return None, 0.0

    bg, bm = fit_bg(560, 700)
    if bg is None or bm < 0.002: bg, bm = fit_bg(520, 640)
    if bg is None or bm < 0.002: bg, _  = fit_bg(420, 510, n_max=4)
    if bg is None: bg = np.interp(x_eval, [x_eval[0], x_eval[-1]], [y_smooth[0], y_smooth[-1]])

    resid = np.maximum(y_smooth - bg, 0)
    pk_mask = (x_eval >= 420) & (x_eval <= 510)

    # 피크 탐색
    peaks_i, props = find_peaks(resid[pk_mask], prominence=0.007)
    lambdamax, pv_ratio = 0.0, 0.0
    lm_rough = None
    if len(peaks_i) > 0:
        wl_pk = x_eval[pk_mask]
        best  = peaks_i[int(np.argmax(props["prominences"]))]
        lm_rough = float(wl_pk[best])
        win = (x_eval >= lm_rough - 40) & (x_eval <= lm_rough + 40)
        def _g(lam, amp, ctr, sig): return amp * np.exp(-0.5*((lam-ctr)/sig)**2)
        try:
            po, _ = curve_fit(_g, x_eval[win], resid[win],
                              p0=[resid[win].max(), lm_rough, 15],
                              bounds=([0, lm_rough-25, 5],[2, lm_rough+25, 60]), maxfev=2000)
            amp_fit, ctr_fit, sig_fit = po
            lambdamax = float(np.clip(ctr_fit, 420, 510))
            y_pred = _g(x_eval[win], *po)
            ss_res = float(np.sum((resid[win] - y_pred)**2))
            ss_tot = float(np.sum((resid[win] - resid[win].mean())**2))
            r2     = 1 - ss_res/ss_tot if ss_tot > 0 else 0
            neg, _ = find_peaks(-y_smooth[pk_mask], prominence=0.001)
            has_v  = any(x_eval[pk_mask][v] < lambdamax for v in neg)
            prom   = float(props["prominences"][int(np.argmax(props["prominences"]))])
            if not (r2 > 0.85 and prom > 0.010 and sig_fit >= 8 and (has_v or sig_fit < 20)):
                lambdamax = 0.0
            else:
                idx_lm  = int(np.argmin(np.abs(x_eval - lambdamax)))
                peak_ab = float(y_smooth[idx_lm])
                vr      = (x_eval >= lambdamax-60) & (x_eval <= lambdamax-10)
                val_ab  = float(y_smooth[vr].min()) if vr.sum() > 0 else float(y_smooth[pk_mask][0])
                bm2     = (x_eval >= 540) & (x_eval <= 560)
                base_ab = float(y_smooth[bm2].mean())
                d = val_ab - base_ab
                if d > 0:
                    pv_ratio = (peak_ab - base_ab) / d
                    if pv_ratio <= 0: lambdamax, pv_ratio = 0.0, 0.0
        except Exception:
            lambdamax = 0.0

    # y_norm
    idx_420 = int(np.argmin(np.abs(x_eval - 420)))
    idx_tgt = int(np.argmin(np.abs(x_eval - TARGET_LM)))
    idx_550 = int(np.argmin(np.abs(x_eval - 550)))
    ab420, abtgt, ab550 = y_smooth[idx_420], y_smooth[idx_tgt], y_smooth[idx_550]
    denom = ab420 - ab550
    y_norm = float(np.clip((abtgt - ab550)/denom, 0, 1)) if denom > 0 and ab420 > 0 else 0.0

    return y_smooth, bg, resid, lambdamax, pv_ratio, y_norm, x_eval

# ──────────────────────────────────────────────────────────────────────────────
# 전 샘플 통계 수집
# ──────────────────────────────────────────────────────────────────────────────
records = []
for col in range(1, df.shape[1]):
    keys   = df.iloc[0:4, 0].values
    values = df.iloc[0:4, col].values
    if pd.isnull(keys).any() or pd.isnull(values).any(): continue
    if col > 152: break
    rs_raw = np.array(df.iloc[4:, col].astype(float).tolist())
    wl_raw = np.array(wavelength)
    y_smooth, bg, resid, lm, pv, y_norm, x_eval = preprocess(wl_raw, rs_raw)
    records.append(dict(col=col, wl=wl_raw, rs=rs_raw,
                        y_smooth=y_smooth, bg=bg, resid=resid,
                        lm=lm, pv=pv, y_norm=y_norm, x_eval=x_eval))

# ──────────────────────────────────────────────────────────────────────────────
# 각 구간 대표 샘플 선택
# ──────────────────────────────────────────────────────────────────────────────
def pick(cond, n=1):
    sel = [r for r in records if cond(r)]
    if not sel: return []
    sel.sort(key=lambda r: abs(r['y_norm'] - (
        0.20 if 'steep' in str(cond) else
        0.40 if 'rayl'  in str(cond) else
        0.50 if 'grad'  in str(cond) else 0.60)))
    return sel[:n]

zone_A = [r for r in records if r['lm']>0 and r['pv']>0]                        # 피크 검출
zone_B = [r for r in records if r['lm']==0 and r['y_norm'] <= Y_STEEP]           # 구간 B
zone_C = [r for r in records if r['lm']==0 and Y_STEEP < r['y_norm'] <= Y_RAYLEIGH]
zone_D = [r for r in records if r['lm']==0 and Y_RAYLEIGH < r['y_norm'] <= Y_GRADUAL]
zone_E = [r for r in records if r['lm']==0 and Y_GRADUAL < r['y_norm'] <= Y_QD_LIKE]
zone_F = [r for r in records if r['lm']==0 and r['y_norm'] > Y_QD_LIKE]

def median_sample(zone):
    if not zone: return None
    yn = np.array([r['y_norm'] for r in zone])
    med = float(np.median(yn))
    return zone[int(np.argmin(np.abs(yn - med)))]

sA = zone_A[0] if zone_A else None
sB = median_sample(zone_B)
sC = median_sample(zone_C)
sD = median_sample(zone_D)
sE = median_sample(zone_E)
sF = median_sample(zone_F)

ZONE_SPECS = [
    # (label, color, sample, loss_lo, loss_hi, y_norm_range_str)
    ("A  피크 검출 성공\n[-0.3, 0]",     "#2ca02c", sA, -0.3, 0.0,  "lambdamax & pv_ratio 기반"),
    ("B  급경사 산란\n[-1.5] (flat)",    "#d62728", sB, -1.5, -1.5, f"y_norm ≤ {Y_STEEP}"),
    ("C  Rayleigh 산란\n[-1.5 ~ -1.2]", "#ff7f0e", sC, -1.5, -1.2, f"{Y_STEEP} < y_norm ≤ {Y_RAYLEIGH}"),
    ("D  완만한 감소\n[-1.2 ~ -0.6]",   "#9467bd", sD, -1.2, -0.6, f"{Y_RAYLEIGH} < y_norm ≤ {Y_GRADUAL}"),
    ("E  QD 유사\n[-0.6 ~ -0.3]",       "#1f77b4", sE, -0.6, -0.3, f"{Y_GRADUAL} < y_norm ≤ {Y_QD_LIKE}"),
    ("F  검출 직전 천장\n[-0.3]",        "#17becf", sF, -0.3, -0.3, f"y_norm > {Y_QD_LIKE}"),
]

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1:  전체 구조 개관 + 스펙트럼 예시
# ══════════════════════════════════════════════════════════════════════════════
fig1 = plt.figure(figsize=(20, 22))
gs1  = gridspec.GridSpec(4, 3, figure=fig1, hspace=0.52, wspace=0.32,
                          top=0.95, bottom=0.04, left=0.06, right=0.97)

# ── 패널 (1): y_norm 구간 → Loss 매핑 다이어그램 ─────────────────────────────
ax_map = fig1.add_subplot(gs1[0, :2])

yn_vals = np.linspace(0, 1, 2000)
loss_fn_vals = np.where(
    yn_vals <= Y_STEEP,   L_WORST,
    np.where(yn_vals <= Y_RAYLEIGH, L_WORST  + (L_RAYLEIGH - L_WORST) *(yn_vals-Y_STEEP)   /(Y_RAYLEIGH-Y_STEEP),
    np.where(yn_vals <= Y_GRADUAL,  L_RAYLEIGH+(L_GRADUAL  - L_RAYLEIGH)*(yn_vals-Y_RAYLEIGH)/(Y_GRADUAL-Y_RAYLEIGH),
    np.where(yn_vals <= Y_QD_LIKE,  L_GRADUAL +(L_NO_PEAK_CEIL-L_GRADUAL)*(yn_vals-Y_GRADUAL)/(Y_QD_LIKE-Y_GRADUAL),
             L_NO_PEAK_CEIL))))

ax_map.plot(yn_vals, loss_fn_vals, 'k-', lw=2.5, zorder=5)

zone_colors = ["#d62728","#ff7f0e","#9467bd","#1f77b4","#17becf"]
zone_lims   = [(0, Y_STEEP),(Y_STEEP,Y_RAYLEIGH),(Y_RAYLEIGH,Y_GRADUAL),(Y_GRADUAL,Y_QD_LIKE),(Y_QD_LIKE,1.0)]
zone_labels_short = ["B: 급경사","C: Rayleigh","D: 완만한감소","E: QD유사","F: 천장"]

for (lo, hi), col, lab in zip(zone_lims, zone_colors, zone_labels_short):
    m = (yn_vals >= lo) & (yn_vals <= hi)
    ax_map.fill_between(yn_vals[m], -1.6, loss_fn_vals[m], color=col, alpha=0.18)
    ax_map.axvline(hi, color=col, lw=1, ls='--', alpha=0.6)
    ax_map.text((lo+hi)/2, -1.55, lab, ha='center', fontsize=8.5,
                color=col, fontweight='bold')

ax_map.axhline(-0.3, color='green', lw=1.2, ls=':', alpha=0.7)
ax_map.text(0.68, -0.28, "피크 검출 최소 ceiling (−0.3)", color='green', fontsize=8.5)
ax_map.text(0.02, L_WORST+0.03, "L_WORST = −1.5", color='#d62728', fontsize=8.5)

for yn_bnd, loss_bnd, label in [
    (Y_STEEP,    L_WORST,         f"y={Y_STEEP}"),
    (Y_RAYLEIGH, L_RAYLEIGH,      f"y={Y_RAYLEIGH}"),
    (Y_GRADUAL,  L_GRADUAL,       f"y={Y_GRADUAL}"),
    (Y_QD_LIKE,  L_NO_PEAK_CEIL,  f"y={Y_QD_LIKE}"),
]:
    ax_map.plot(yn_bnd, loss_bnd, 'ko', ms=6, zorder=6)

ax_map.set_xlim(0, 1); ax_map.set_ylim(-1.65, 0.1)
ax_map.set_xlabel("y_norm  =  (A(λ_target) − A(550)) / (A(420) − A(550))", fontsize=11)
ax_map.set_ylabel("Loss value", fontsize=11)
ax_map.set_title("【미검출 분기】  y_norm → Loss 구간 매핑  (피크 미검출 전용)", fontsize=12, fontweight='bold')

# ── 패널 (2): y_norm 물리적 해석 — 이론 scattering 비교 ────────────────────
ax_phy = fig1.add_subplot(gs1[0, 2])

lam  = np.linspace(350, 700, 500)
ref  = 420.0
def yn_theory(n):
    ab = (ref/lam)**n
    a420, atgt, a550 = np.interp(420, lam, ab), np.interp(TARGET_LM, lam, ab), np.interp(550, lam, ab)
    return (atgt - a550)/(a420 - a550)

scatt_n = np.linspace(0.5, 6, 200)
yn_scatt = [yn_theory(n) for n in scatt_n]
ax_phy.plot(scatt_n, yn_scatt, 'k-', lw=2)
ax_phy.axhline(Y_STEEP,    color='#d62728', ls='--', lw=1.2, label=f"Y_STEEP  = {Y_STEEP}")
ax_phy.axhline(Y_RAYLEIGH, color='#ff7f0e', ls='--', lw=1.2, label=f"Y_RAYLEIGH = {Y_RAYLEIGH}")
ax_phy.axhline(Y_GRADUAL,  color='#9467bd', ls='--', lw=1.2, label=f"Y_GRADUAL  = {Y_GRADUAL}")
ax_phy.axhline(Y_QD_LIKE,  color='#1f77b4', ls='--', lw=1.2, label=f"Y_QD_LIKE  = {Y_QD_LIKE}")
ax_phy.axvline(4, color='gray', ls=':', lw=1, alpha=0.7)
ax_phy.text(4.05, 0.55, "Rayleigh\n(n=4)", fontsize=8, color='gray')
ax_phy.axvline(1, color='gray', ls=':', lw=1, alpha=0.7)
ax_phy.text(1.05, 0.62, "Mie\n(n=1)", fontsize=8, color='gray')
ax_phy.set_xlabel("산란 지수 n  [A ∝ (λ_ref/λ)ⁿ]", fontsize=9)
ax_phy.set_ylabel("y_norm", fontsize=9)
ax_phy.set_title("y_norm vs 산란 지수 n\n(이론값 비교)", fontsize=9, fontweight='bold')
ax_phy.legend(fontsize=7.5, loc='upper right')
ax_phy.set_ylim(0.2, 0.8)

# ── 패널 (3~7): 각 구간 대표 스펙트럼 ───────────────────────────────────────
spec_axes = [
    fig1.add_subplot(gs1[1, 0]),  # B
    fig1.add_subplot(gs1[1, 1]),  # C
    fig1.add_subplot(gs1[1, 2]),  # D
    fig1.add_subplot(gs1[2, 0]),  # E
    fig1.add_subplot(gs1[2, 1]),  # F
    fig1.add_subplot(gs1[2, 2]),  # A
]

zone_order = [
    ("B  급경사 산란  (loss = −1.5)",       "#d62728", sB),
    ("C  Rayleigh 수준  (loss −1.5~−1.2)",  "#ff7f0e", sC),
    ("D  완만한 감소  (loss −1.2~−0.6)",    "#9467bd", sD),
    ("E  QD 유사  (loss −0.6~−0.3)",        "#1f77b4", sE),
    ("F  검출 직전 천장  (loss = −0.3)",    "#17becf", sF),
    ("A  피크 검출 성공  (loss −0.3~0)",    "#2ca02c", sA),
]

for ax, (title, col, rec) in zip(spec_axes, zone_order):
    if rec is None:
        ax.text(0.5, 0.5, "해당 샘플 없음", ha='center', va='center', transform=ax.transAxes)
        ax.set_title(title, fontsize=9, color=col, fontweight='bold')
        continue

    x  = rec['x_eval']
    ys = rec['y_smooth']
    bg = rec['bg']
    rd = rec['resid']
    lm = rec['lm']
    pv = rec['pv']
    yn = rec['y_norm']

    xm = (x >= 350) & (x <= 700)
    ax.plot(x[xm], ys[xm], color=col,     lw=1.8, label="Smoothed", zorder=4)
    ax.plot(x[xm], bg[xm], color='gray',  lw=1.0, ls='--', label="Background", alpha=0.7)

    # y_norm 표시 포인트
    for wl_pt, mk, lc in [(420, 'o', 'navy'), (TARGET_LM, 's', 'red'), (550, '^', 'olive')]:
        idx = int(np.argmin(np.abs(x - wl_pt)))
        ax.plot(x[idx], ys[idx], marker=mk, ms=6, color=lc, zorder=6)

    # y_norm 화살표
    idx_420 = int(np.argmin(np.abs(x - 420)))
    idx_tgt = int(np.argmin(np.abs(x - TARGET_LM)))
    idx_550 = int(np.argmin(np.abs(x - 550)))
    a420, atgt, a550 = float(ys[idx_420]), float(ys[idx_tgt]), float(ys[idx_550])

    ax.annotate('', xy=(TARGET_LM, a550), xytext=(TARGET_LM, a420),
                arrowprops=dict(arrowstyle='<->', color='purple', lw=1.2))
    ax.annotate('', xy=(TARGET_LM, a550), xytext=(TARGET_LM, atgt),
                arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))

    # 피크 성공 시 peak/valley/base 표시
    if lm > 0:
        idx_lm = int(np.argmin(np.abs(x - lm)))
        ax.axvline(lm, color='green', lw=1.2, ls=':', alpha=0.8)
        ax.plot(x[idx_lm], ys[idx_lm], '*', ms=12, color='green', zorder=7, label=f"λmax={lm:.1f}nm")

    # 계산된 loss
    result_dict = {"UV_GetAbs": {"Data": {
        "Wavelength": rec['wl'].tolist(), "RawSpectrum": rec['rs'].tolist(),
        "Property":   {"lambdamax": lm, "p_v_ratio": pv},
    }}}
    loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=TARGET_COND)
    loss_val, _ = loss_obj.lambdamaxpvLoss()

    ax.set_xlim(350, 700)
    ymax = float(ys[xm].max()) * 1.15
    ax.set_ylim(0, max(ymax, 0.05))
    ax.set_xlabel("Wavelength (nm)", fontsize=8)
    ax.set_ylabel("Absorbance", fontsize=8)
    ax.set_title(f"{title}\nSample {rec['col']}  |  y_norm={yn:.3f}  |  loss={loss_val:.3f}",
                 fontsize=8.5, color=col, fontweight='bold')

    # 범례 텍스트
    txt = f"A(420)={a420:.3f}\nA({int(TARGET_LM)})={atgt:.3f}\nA(550)={a550:.3f}"
    ax.text(0.97, 0.97, txt, transform=ax.transAxes, fontsize=7.5,
            ha='right', va='top', family='monospace',
            bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))
    ax.tick_params(labelsize=7.5)

# ── 패널 (8): 피크 검출 성공 분기 설명 — 2D heat map ─────────────────────────
ax_pk = fig1.add_subplot(gs1[3, :])

lm_grid = np.linspace(350, 700, 300)
pv_grid = np.linspace(0, 3.0, 200)
LM, PV  = np.meshgrid(lm_grid, pv_grid)
wl_min, wl_max = 350.0, 700.0

def peak_loss(lm, pv):
    scale_left  = max(TARGET_LM - wl_min, 1.0)
    scale_right = max(wl_max - TARGET_LM, 1.0)
    scale = np.where(lm <= TARGET_LM, scale_left, scale_right)
    lm_l = np.clip(np.abs(TARGET_LM - lm) / scale, 0, 1)
    pv_l = np.clip((TARGET_PV - pv) / TARGET_PV, 0, 1)
    pv_l = np.where(pv >= TARGET_PV, 0.0, pv_l)
    return -(lm_l * W_LM + pv_l * W_PV) * PEAK_SCALE

Z = peak_loss(LM, PV)

im = ax_pk.contourf(LM, PV, Z, levels=np.linspace(-0.3, 0, 31), cmap='RdYlGn_r')
cbar = plt.colorbar(im, ax=ax_pk, shrink=0.8)
cbar.set_label("Loss value", fontsize=10)
CS = ax_pk.contour(LM, PV, Z, levels=[-0.27,-0.24,-0.21,-0.18,-0.15,-0.12,-0.09,-0.06,-0.03],
                   colors='white', linewidths=0.7, alpha=0.7)
ax_pk.clabel(CS, inline=True, fontsize=7, fmt="%.2f")

ax_pk.axvline(TARGET_LM, color='white', lw=1.5, ls='--', label=f"target λmax={int(TARGET_LM)}nm")
ax_pk.axhline(TARGET_PV, color='cyan',  lw=1.5, ls='--', label=f"target p_v={TARGET_PV}")
ax_pk.plot(TARGET_LM, TARGET_PV, 'w*', ms=18, zorder=10, label="Optimal (loss=0)")

# 실제 검출된 샘플 표시
for rec in zone_A:
    ax_pk.plot(rec['lm'], rec['pv'], 'o', ms=8, color='#2ca02c',
               markeredgecolor='white', markeredgewidth=0.8, zorder=8)

ax_pk.set_xlabel("Detected λmax (nm)", fontsize=11)
ax_pk.set_ylabel("Detected p_v_ratio", fontsize=11)
ax_pk.set_title(
    "【검출 성공 분기】  loss = −(lm_loss × w_λ + pv_loss × w_pv) × 0.3\n"
    f"  w_λ={W_LM}  w_pv={W_PV}  →  λmax 편차 10%, p_v_ratio 부족 90% 반영  |  범위 [−0.3, 0]",
    fontsize=11, fontweight='bold')
ax_pk.legend(fontsize=9, loc='upper right')
ax_pk.set_xlim(350, 700)
ax_pk.set_ylim(0, 3.0)

# 비대칭 설명 주석
ax_pk.annotate("pv≥target → pv_loss=0\n(p_v_ratio 과잉은 패널티 없음)",
               xy=(TARGET_LM+20, TARGET_PV+0.3), fontsize=8.5, color='cyan',
               bbox=dict(boxstyle='round', fc='black', alpha=0.6))
ax_pk.annotate("λmax=target → lm_loss=0\n(완벽 일치 → loss=0)",
               xy=(TARGET_LM+5, 0.15), fontsize=8.5, color='white',
               bbox=dict(boxstyle='round', fc='black', alpha=0.6))

fig1.suptitle(
    "lambdamaxpvLoss  구간별 상세 설명\n"
    "target: λmax=460nm, p_v_ratio=1.3  |  w_λ=0.1, w_pv=0.9  |  전처리: _preprocess_spectrum (csv2-style)",
    fontsize=13, fontweight='bold', y=0.98)

out1 = "fig/loss_explained_p1.png"
os.makedirs("fig", exist_ok=True)
plt.savefig(out1, dpi=150, bbox_inches='tight')
print(f"Saved: {out1}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2:  _preprocess_spectrum 4단계 파이프라인 시각화 (대표 3 샘플)
# ══════════════════════════════════════════════════════════════════════════════
fig2, axes2 = plt.subplots(3, 4, figsize=(20, 14))
fig2.subplots_adjust(hspace=0.48, wspace=0.30, top=0.92, bottom=0.06, left=0.05, right=0.97)

sample_trio = [
    ("B: 급경사 산란", "#d62728", sB),
    ("D: 완만한 감소", "#9467bd", sD),
    ("A: 피크 검출",   "#2ca02c", sA),
]

STEP_TITLES = [
    "Step 1: Raw spectrum\n(균일 그리드 보간 20000pts)",
    "Step 2: Gaussian smooth\n(σ=3nm, 파란=raw, 빨강=smooth)",
    "Step 3: 배경 제거\n(회색=배경, 녹색=잔류 residual)",
    "Step 4: 피크 탐색 + y_norm\n(loss 계산 입력)",
]

for row, (label, col, rec) in enumerate(sample_trio):
    if rec is None:
        for c in range(4):
            axes2[row, c].text(0.5, 0.5, "샘플 없음", ha='center', va='center',
                               transform=axes2[row, c].transAxes)
        continue

    x    = rec['x_eval']
    ys   = rec['y_smooth']
    bg   = rec['bg']
    rd   = rec['resid']
    lm   = rec['lm']
    pv   = rec['pv']
    yn   = rec['y_norm']
    wl_r = rec['wl']; rs_r = rec['rs']
    xm   = (x >= 350) & (x <= 700)

    # --- col 0: raw interp ---
    ax = axes2[row, 0]
    ax.plot(x[xm], np.interp(x[xm], np.sort(wl_r), rs_r[np.argsort(wl_r)]),
            color='gray', lw=1.0, alpha=0.7)
    ax.set_ylabel(f"{label}\nAbsorbance", fontsize=8.5, color=col, fontweight='bold')
    if row == 0: ax.set_title(STEP_TITLES[0], fontsize=9, fontweight='bold')

    # --- col 1: smooth ---
    ax = axes2[row, 1]
    y_raw_interp = np.interp(x[xm], np.sort(wl_r), rs_r[np.argsort(wl_r)])
    ax.plot(x[xm], y_raw_interp,   color='steelblue', lw=0.8, alpha=0.5, label='Raw interp')
    ax.plot(x[xm], ys[xm],         color='red',       lw=1.5, label='Gaussian smooth')
    if row == 0:
        ax.legend(fontsize=7, loc='upper right')
        ax.set_title(STEP_TITLES[1], fontsize=9, fontweight='bold')

    # --- col 2: residual ---
    ax = axes2[row, 2]
    ax.plot(x[xm], ys[xm], color='steelblue', lw=1.0, alpha=0.5, label='Smoothed')
    ax.plot(x[xm], bg[xm], color='gray',      lw=1.2, ls='--',   label='Background')
    ax.fill_between(x[xm], 0, rd[xm], color='green', alpha=0.3, label='Residual')
    ax.axvspan(420, 510, color='yellow', alpha=0.15, label='Peak search zone')
    if row == 0:
        ax.legend(fontsize=7, loc='upper right')
        ax.set_title(STEP_TITLES[2], fontsize=9, fontweight='bold')

    # --- col 3: peak + y_norm ---
    ax = axes2[row, 3]
    ax.plot(x[xm], ys[xm], color=col, lw=1.8)
    # y_norm 포인트
    for wl_pt, mk, lc, lab in [(420, 'o', 'navy', 'A(420)'),
                                 (TARGET_LM, 's', 'red',  f'A({int(TARGET_LM)})'),
                                 (550, '^', 'olive', 'A(550)')]:
        idx = int(np.argmin(np.abs(x - wl_pt)))
        ax.plot(x[idx], ys[idx], marker=mk, ms=7, color=lc, label=lab, zorder=6)

    idx_420 = int(np.argmin(np.abs(x-420)))
    idx_tgt = int(np.argmin(np.abs(x-TARGET_LM)))
    idx_550 = int(np.argmin(np.abs(x-550)))
    a420, atgt, a550 = float(ys[idx_420]), float(ys[idx_tgt]), float(ys[idx_550])
    # 수직 화살표
    xv = TARGET_LM + 8
    ax.annotate('', xy=(xv, a550), xytext=(xv, a420),
                arrowprops=dict(arrowstyle='<->', color='purple', lw=1.2))
    ax.annotate('', xy=(xv+5, a550), xytext=(xv+5, atgt),
                arrowprops=dict(arrowstyle='<->', color='crimson', lw=1.5))
    ax.text(xv+8, (a420+a550)/2, "분모\n(A420−A550)", fontsize=6.5, color='purple', va='center')
    ax.text(xv+8, (atgt+a550)/2, "분자\n(Atgt−A550)", fontsize=6.5, color='crimson', va='center')

    if lm > 0:
        idx_lm = int(np.argmin(np.abs(x-lm)))
        ax.plot(x[idx_lm], ys[idx_lm], '*', ms=14, color='gold',
                markeredgecolor='green', zorder=7)
        ax.axvline(lm, color='green', lw=1, ls=':')

    result_dict = {"UV_GetAbs": {"Data": {
        "Wavelength": rec['wl'].tolist(), "RawSpectrum": rec['rs'].tolist(),
        "Property":   {"lambdamax": lm, "p_v_ratio": pv},
    }}}
    lobj = LossFunction(result_dict=result_dict, target_condition_dict=TARGET_COND)
    lv, _ = lobj.lambdamaxpvLoss()

    info = (f"y_norm = {yn:.3f}\n"
            f"λmax   = {lm:.1f} nm\n"
            f"pv     = {pv:.3f}\n"
            f"loss   = {lv:.3f}")
    ax.text(0.97, 0.97, info, transform=ax.transAxes, fontsize=8,
            ha='right', va='top', family='monospace',
            bbox=dict(boxstyle='round,pad=0.4', fc='white', alpha=0.9))
    if row == 0:
        ax.legend(fontsize=7, loc='upper left')
        ax.set_title(STEP_TITLES[3], fontsize=9, fontweight='bold')

    for c in range(4):
        axes2[row, c].set_xlim(350, 700)
        axes2[row, c].set_xlabel("Wavelength (nm)", fontsize=8)
        axes2[row, c].tick_params(labelsize=7.5)

fig2.suptitle("_preprocess_spectrum 4단계 파이프라인  —  3가지 대표 스펙트럼",
              fontsize=13, fontweight='bold')

out2 = "fig/loss_explained_p2.png"
plt.savefig(out2, dpi=150, bbox_inches='tight')
print(f"Saved: {out2}")

# 구간별 샘플 수 출력
print("\n=== 구간별 샘플 분포 ===")
for lab, zone in [("A 피크 검출", zone_A), ("B 급경사", zone_B),
                  ("C Rayleigh", zone_C), ("D 완만한감소", zone_D),
                  ("E QD유사",   zone_E), ("F 천장",     zone_F)]:
    print(f"  {lab}: {len(zone):3d}개  "
          + (f"y_norm={np.mean([r['y_norm'] for r in zone]):.3f}±{np.std([r['y_norm'] for r in zone]):.3f}" if zone else ""))
