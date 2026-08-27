import numpy as np, sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.optimize import brentq
sys.path.insert(0, '.')

from Analysis.AnalysisUV_poly import smooth_Boxcar, getSliceSpectrum

def load_multisample_csv(path):
    import pandas as pd
    df = pd.read_csv(path, header=None)
    wl = df.iloc[4:, 0].astype(float).tolist()
    return {f'Sample_{c}': {'Wavelength': wl, 'RawSpectrum': df.iloc[4:, c].astype(float).tolist()}
            for c in range(1, df.shape[1])}

data_dict = load_multisample_csv('2508optimize/spectra_with_params_0407.csv')

# ── 이론값 계산 ──
lam = np.linspace(350, 700, 1000)
ref = 420.0
n_vals = [1, 2, 3, 4, 5, 6]
theory = {}
for n in n_vals:
    A = (ref / lam) ** n
    a420 = np.interp(420, lam, A)
    a460 = np.interp(460, lam, A)
    a550 = np.interp(550, lam, A)
    yn = (a460 - a550) / (a420 - a550)
    theory[n] = dict(lam=lam, A=A, yn=yn)

# y_norm curve (vs n)
n_range = np.linspace(0.1, 8, 500)
yn_curve = []
for n in n_range:
    a420 = (ref/420)**n; a460 = (ref/460)**n; a550 = (ref/550)**n
    yn_curve.append((a460 - a550) / (a420 - a550))
yn_curve = np.array(yn_curve)

# ── 실제 샘플 ──
samples_info = {}
for sid in ['1', '8']:
    uv = data_dict[f'Sample_{sid}']
    wl_raw = np.array(uv['Wavelength']); rs_raw = np.array(uv['RawSpectrum'])
    order  = np.argsort(wl_raw)
    x_full = np.linspace(350., 950., 20000)
    y_interp = np.interp(x_full, wl_raw[order], rs_raw[order])
    raw = np.array([x_full, y_interp])
    sm  = smooth_Boxcar(rawSpectrum=raw, box_size=250)
    xsm = sm[0]; ysm = sm[1]

    # single-point y_norm (현재 방식)
    ab_420 = float(ysm[np.argmin(np.abs(xsm - 420.))])
    ab_460 = float(ysm[np.argmin(np.abs(xsm - 460.))])
    ab_550 = float(ysm[np.argmin(np.abs(xsm - 550.))])
    yn_single = (ab_460 - ab_550) / (ab_420 - ab_550) if (ab_420 - ab_550) > 0 else 0.

    # range-average y_norm (개선 방안)
    def avg(lo, hi):
        m = (xsm >= lo) & (xsm <= hi)
        return float(ysm[m].mean()) if m.any() else 0.
    ab_420r = avg(410, 430); ab_460r = avg(450, 470); ab_550r = avg(540, 560)
    yn_range = (ab_460r - ab_550r) / (ab_420r - ab_550r) if (ab_420r - ab_550r) > 0 else 0.

    # 역산 equivalent n
    def eq_n(n):
        a420 = (ref/420)**n; a460 = (ref/460)**n; a550 = (ref/550)**n
        return (a460 - a550) / (a420 - a550) - yn_single
    try:
        n_equiv = brentq(eq_n, 0.01, 50)
    except Exception:
        n_equiv = float('inf')

    samples_info[sid] = dict(
        xsm=xsm, ysm=ysm,
        ab_420=ab_420, ab_460=ab_460, ab_550=ab_550,
        ab_420r=ab_420r, ab_460r=ab_460r, ab_550r=ab_550r,
        yn_single=yn_single, yn_range=yn_range,
        n_equiv=n_equiv,
    )

# ────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 10))
gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.52, wspace=0.38)

# ── (A) 이론 스펙트럼 ──
ax_th = fig.add_subplot(gs[0, 0])
cmap  = plt.cm.plasma
for n in n_vals:
    A_norm = theory[n]['A'] / theory[n]['A'][0]
    ax_th.plot(lam, A_norm, color=cmap(n / 7), lw=1.5, label=f'n={n}  (y_norm={theory[n]["yn"]:.3f})')
ax_th.axvline(420, color='#1a8c2e', lw=1.0, ls='--', alpha=0.7)
ax_th.axvline(460, color='#c44e52', lw=1.0, ls='--', alpha=0.7)
ax_th.axvline(550, color='#8172b3', lw=1.0, ls='--', alpha=0.7)
ax_th.set_xlim(350, 700); ax_th.set_ylim(0)
ax_th.set_xlabel('Wavelength (nm)', fontsize=8)
ax_th.set_ylabel('Normalized Absorbance', fontsize=8)
ax_th.set_title('(A) Pure power-law spectra\nA(lam) = (420/lam)^n  [normalized]', fontsize=9, fontweight='bold')
ax_th.legend(fontsize=7, loc='upper right')
ax_th.tick_params(labelsize=7)
for wl, col, lbl in [(420,'#1a8c2e','420'), (460,'#c44e52','460'), (550,'#8172b3','550')]:
    ax_th.text(wl+3, 0.03, f'{lbl}nm', fontsize=7, color=col)

# ── (B) y_norm vs n 이론 곡선 ──
ax_yn = fig.add_subplot(gs[0, 1])
ax_yn.plot(n_range, yn_curve, color='#333', lw=2.0, label='y_norm(n)')
# 구간 배경
zone_cfg = [
    (0.0, 0.35, '#ffcccc'), (0.35, 0.45, '#ffd9b3'),
    (0.45, 0.55, '#fff0b3'), (0.55, 0.65, '#d4f0d4'), (0.65, 1.0, '#c8e6c9'),
]
for lo, hi, fc in zone_cfg:
    ax_yn.axhspan(lo, hi, alpha=0.4, color=fc)
ax_yn.axhline(0.65, color='#2e7d32', lw=1.0, ls=':', label='QD-like ceiling (0.65)')
ax_yn.axhline(0.45, color='#c62828', lw=1.0, ls=':', label='Rayleigh n=4 (0.45)')

for sid, col in [('1', '#4c72b0'), ('8', '#e65100')]:
    yn_s = samples_info[sid]['yn_single']
    n_eq = samples_info[sid]['n_equiv']
    ax_yn.scatter([n_eq if n_eq < 9 else 8.5], [yn_s], color=col, s=70, zorder=6)
    ax_yn.annotate(
        f'S{sid}: y_norm={yn_s:.3f}\n(equiv n={n_eq:.1f})',
        xy=(min(n_eq, 8.5), yn_s),
        xytext=(min(n_eq, 8.5) + 0.5, yn_s - (0.05 if sid == '1' else 0.12)),
        fontsize=7, color=col, fontweight='bold',
        arrowprops=dict(arrowstyle='->', color=col, lw=0.8)
    )
ax_yn.set_xlim(0, 9); ax_yn.set_ylim(0.3, 0.9)
ax_yn.set_xlabel('Power-law exponent n', fontsize=8)
ax_yn.set_ylabel('y_norm', fontsize=8)
ax_yn.set_title('(B) y_norm vs scattering exponent n\n(higher n = steeper = lower y_norm)', fontsize=9, fontweight='bold')
ax_yn.legend(fontsize=7, loc='upper right')
ax_yn.tick_params(labelsize=7)
ax_yn.text(7.5, 0.72, 'Flat\nspectrum', fontsize=7, color='#555', ha='center')
ax_yn.text(1.0, 0.37, 'Steep\nspectrum', fontsize=7, color='#555', ha='center')

# ── (C) 과대평가 시나리오 설명 ──
ax_sc = fig.add_subplot(gs[0, 2])
lam_sc = np.linspace(350, 700, 500)
# 시나리오 1: flat spectrum (scattering n=1)
n1 = 1.0
A_flat = (420/lam_sc)**n1; A_flat /= A_flat[0]
# 시나리오 2: flat + 작은 QD shoulder
A_qd = A_flat + 0.15 * np.exp(-0.5*((lam_sc-460)/25)**2)
A_qd /= A_qd[0]
# 시나리오 3: flat + noise spike at 460nm only
rng = np.random.default_rng(42)
A_noise = A_flat.copy()
idx460 = np.argmin(np.abs(lam_sc - 460))
A_noise[idx460-2:idx460+3] += 0.04

def yn_calc(A, lam):
    a420 = np.interp(420, lam, A); a460 = np.interp(460, lam, A); a550 = np.interp(550, lam, A)
    return (a460-a550)/(a420-a550) if (a420-a550)>0 else 0.

yn_flat  = yn_calc(A_flat,  lam_sc)
yn_qd    = yn_calc(A_qd,    lam_sc)
yn_noise = yn_calc(A_noise, lam_sc)

ax_sc.plot(lam_sc, A_flat,  color='#4c72b0', lw=1.5, ls='-',  label=f'Pure scatter (n=1)  y_norm={yn_flat:.3f}')
ax_sc.plot(lam_sc, A_qd,    color='#1a8c2e', lw=1.5, ls='--', label=f'+ small QD shoulder  y_norm={yn_qd:.3f}')
ax_sc.plot(lam_sc, A_noise, color='#c44e52', lw=1.5, ls=':',  label=f'+ noise spike@460nm  y_norm={yn_noise:.3f}')
ax_sc.axvline(460, color='grey', lw=0.8, ls='--', alpha=0.6)
ax_sc.set_xlim(350, 700); ax_sc.set_ylim(0)
ax_sc.set_xlabel('Wavelength (nm)', fontsize=8)
ax_sc.set_ylabel('Normalized Absorbance', fontsize=8)
ax_sc.set_title('(C) Overestimation scenarios\n(flat spectrum or noise spike can inflate y_norm)', fontsize=9, fontweight='bold')
ax_sc.legend(fontsize=7, loc='upper right')
ax_sc.tick_params(labelsize=7)
ax_sc.text(462, 0.07, 'single\npoint', fontsize=7, color='grey', ha='left')

# ── (D)(E) 실제 샘플 단일점 vs 범위평균 비교 ──
for col_idx, sid in enumerate(['1', '8']):
    ax = fig.add_subplot(gs[1, col_idx])
    r  = samples_info[sid]
    m  = (r['xsm'] >= 350) & (r['xsm'] <= 700)
    ax.plot(r['xsm'][m], r['ysm'][m], color='#4c72b0', lw=1.5, label='Boxcar smooth')

    # 단일점
    for wl_pt, ab_pt, col_pt in [(420, r['ab_420'], '#1a8c2e'),
                                   (460, r['ab_460'], '#c44e52'),
                                   (550, r['ab_550'], '#8172b3')]:
        ax.scatter([wl_pt], [ab_pt], color=col_pt, s=55, zorder=6, marker='o')
        ax.axvline(wl_pt, color=col_pt, lw=0.8, ls='--', alpha=0.5)

    # 범위 평균 구간 표시
    for lo, hi, ab_r, col_pt in [(410,430,r['ab_420r'],'#1a8c2e'),
                                   (450,470,r['ab_460r'],'#c44e52'),
                                   (540,560,r['ab_550r'],'#8172b3')]:
        ax.axvspan(lo, hi, alpha=0.18, color=col_pt)
        ax.hlines(ab_r, lo, hi, colors=col_pt, lw=2.0, ls='-', zorder=5)

    yn_s = r['yn_single']
    yn_r = r['yn_range']
    diff = yn_r - yn_s
    ax.text(0.5, 0.97,
            f'Single-point y_norm = {yn_s:.4f}\n'
            f'Range-avg   y_norm = {yn_r:.4f}   (diff={diff:+.4f})',
            transform=ax.transAxes, va='top', ha='center', fontsize=7.5,
            family='monospace',
            bbox=dict(boxstyle='round,pad=0.4', fc='#f0f4ff', alpha=0.95))
    ax.set_xlim(350, 700); ax.set_ylim(bottom=0)
    ax.set_xlabel('Wavelength (nm)', fontsize=8)
    ax.set_ylabel('Absorbance', fontsize=8)
    ax.set_title(f'({"D" if sid=="1" else "E"}) Sample {sid}  |  Single-point vs Range-avg\n'
                 f'dot=single point,  shaded band=±10nm average',
                 fontsize=9, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, loc='upper right')

# ── (F) 두 방법 y_norm 비교 막대 ──
ax_bar = fig.add_subplot(gs[1, 2])
sids = ['1', '8']
x = np.arange(2)
w = 0.3
ys_s = [samples_info[s]['yn_single'] for s in sids]
ys_r = [samples_info[s]['yn_range']  for s in sids]
bars1 = ax_bar.bar(x - w/2, ys_s, w, color='#4c72b0', label='Single-point (current)', alpha=0.85)
bars2 = ax_bar.bar(x + w/2, ys_r, w, color='#dd8452', label='Range-avg (±10nm)',     alpha=0.85)
ax_bar.axhline(0.65, color='#2e7d32', lw=1.2, ls='--', label='QD-like ceiling (0.65)')
ax_bar.axhline(0.45, color='#c62828', lw=1.2, ls=':', label='Rayleigh n=4 (0.45)')
for bar in bars1:
    ax_bar.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005,
                f'{bar.get_height():.4f}', ha='center', va='bottom', fontsize=8, color='#4c72b0')
for bar in bars2:
    ax_bar.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005,
                f'{bar.get_height():.4f}', ha='center', va='bottom', fontsize=8, color='#e65100')
ax_bar.set_xticks(x); ax_bar.set_xticklabels(['Sample 1', 'Sample 8'], fontsize=9)
ax_bar.set_ylim(0, 1.05); ax_bar.set_ylabel('y_norm', fontsize=8)
ax_bar.set_title('(F) y_norm comparison\nSingle-point vs Range-average', fontsize=9, fontweight='bold')
ax_bar.legend(fontsize=7, loc='upper left')
ax_bar.tick_params(labelsize=7)
ax_bar.text(0.5, 0.28,
            'Both samples: y_norm >= 0.65\n=> loss=-0.3 (ceiling)\neven without clear QD peak\n=> possible overestimation',
            transform=ax_bar.transAxes, ha='center', va='center', fontsize=8,
            color='#c00', bbox=dict(boxstyle='round,pad=0.4', fc='#ffeeee', alpha=0.92))

fig.suptitle('y_norm Overestimation Analysis  |  (ab_460 - ab_550) / (ab_420 - ab_550)',
             fontsize=12, fontweight='bold', y=1.01)

plt.tight_layout()
plt.savefig('ynorm_overestimation.png', dpi=150, bbox_inches='tight')
print('saved: ynorm_overestimation.png')

# 수치 요약
print()
for sid in ['1', '8']:
    r = samples_info[sid]
    print(f'Sample {sid}: single={r["yn_single"]:.4f}  range={r["yn_range"]:.4f}  '
          f'diff={r["yn_range"]-r["yn_single"]:+.4f}  n_equiv={r["n_equiv"]:.2f}')
