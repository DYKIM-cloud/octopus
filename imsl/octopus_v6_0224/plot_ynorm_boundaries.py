import numpy as np, sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.optimize import brentq
sys.path.insert(0, '.')

from Analysis.AnalysisUV_poly import smooth_Boxcar

def load_multisample_csv(path):
    import pandas as pd
    df = pd.read_csv(path, header=None)
    wl = df.iloc[4:, 0].astype(float).tolist()
    return {f'Sample_{c}': {'Wavelength': wl,
                             'RawSpectrum': df.iloc[4:, c].astype(float).tolist()}
            for c in range(1, df.shape[1])}

data_dict = load_multisample_csv('2508optimize/spectra_with_params_0407.csv')

# ── y_norm 경계값에 해당하는 power-law 지수 n 역산 ──
ref = 420.0
def yn_from_n(n):
    a420 = (ref/420)**n; a460 = (ref/460)**n; a550 = (ref/550)**n
    return (a460 - a550) / (a420 - a550)

boundaries = [0.35, 0.45, 0.55, 0.65]
boundary_n = {}
for yn_target in boundaries:
    try:
        n_sol = brentq(lambda n: yn_from_n(n) - yn_target, 0.01, 50)
    except Exception:
        n_sol = float('inf')
    boundary_n[yn_target] = n_sol

print('y_norm boundary -> n:')
for yn, n in boundary_n.items():
    print(f'  y_norm={yn:.2f}  ->  n={n:.3f}')

# ── 실제 샘플 Boxcar smoothed 데이터 ──
sample_data = {}
for sid in ['1', '8']:
    uv = data_dict[f'Sample_{sid}']
    wl_raw = np.array(uv['Wavelength']); rs_raw = np.array(uv['RawSpectrum'])
    order  = np.argsort(wl_raw)
    x_full = np.linspace(350., 950., 20000)
    y_interp = np.interp(x_full, wl_raw[order], rs_raw[order])
    sm = smooth_Boxcar(rawSpectrum=np.array([x_full, y_interp]), box_size=250)
    xsm = sm[0]; ysm = sm[1]

    ab_420 = float(ysm[np.argmin(np.abs(xsm - 420.))])
    ab_460 = float(ysm[np.argmin(np.abs(xsm - 460.))])
    ab_550 = float(ysm[np.argmin(np.abs(xsm - 550.))])
    yn     = (ab_460 - ab_550) / (ab_420 - ab_550) if (ab_420 - ab_550) > 0 else 0.

    # 420nm 기준 정규화
    ysm_norm = ysm / ab_420 if ab_420 > 0 else ysm
    sample_data[sid] = dict(xsm=xsm, ysm_norm=ysm_norm, yn=yn, ab_420=ab_420)

# ── Loss 구간 배경 색상 정의 ──
zone_colors = [
    (None,  0.35, '#ffcccc', 'loss=-1.5\n(worst)'),
    (0.35,  0.45, '#ffd9b3', '-1.5~-1.2'),
    (0.45,  0.55, '#fff0b3', '-1.2~-0.6'),
    (0.55,  0.65, '#d4f0d4', '-0.6~-0.3'),
    (0.65,  None, '#c8e6c9', 'loss=-0.3\n(ceiling)'),
]

lam   = np.linspace(350, 700, 2000)
XLIM  = (350, 700)

# ─────────────────────────────────────────────────────────────────
# 그림 구성
# Row 0: 경계별 스펙트럼 오버레이 (전체 한 패널)
# Row 1: 경계별 스펙트럼 개별 패널 5개
# Row 2: y_norm vs n 곡선 + Sample 위치
# ─────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 13))
gs  = gridspec.GridSpec(3, 5, figure=fig, hspace=0.55, wspace=0.35,
                         height_ratios=[1.4, 1.2, 1.1])

# ── (A) 전체 오버레이 패널 (col span 2) ──
ax_ov = fig.add_subplot(gs[0, :2])

colors_bnd = ['#c62828', '#e65100', '#f9a825', '#2e7d32']
labels_bnd = [
    f'y_norm=0.35  n={boundary_n[0.35]:.1f}  (steep, loss=-1.5)',
    f'y_norm=0.45  n={boundary_n[0.45]:.1f}  (Rayleigh)',
    f'y_norm=0.55  n={boundary_n[0.55]:.2f}  (gradual)',
    f'y_norm=0.65  n={boundary_n[0.65]:.2f}  (QD-like ceil)',
]

for yn_b, col, lbl in zip(boundaries, colors_bnd, labels_bnd):
    n = boundary_n[yn_b]
    if np.isinf(n):
        A = np.ones_like(lam)
    else:
        A = (ref / lam) ** n
    A_norm = A / np.interp(420, lam, A)
    ax_ov.plot(lam, A_norm, color=col, lw=2.0, label=lbl)

# 실제 샘플
for sid, ls, col_s in [('1','--','#4c72b0'), ('8','-.','#9c27b0')]:
    d = sample_data[sid]
    m = (d['xsm'] >= 350) & (d['xsm'] <= 700)
    ax_ov.plot(d['xsm'][m], d['ysm_norm'][m], color=col_s, lw=1.5,
               ls=ls, label=f'Sample {sid}  y_norm={d["yn"]:.4f}', alpha=0.85)

# 3개 기준점 수직선
for wl, col_l, lbl_l in [(420,'#1a8c2e','420'), (460,'#c44e52','460'), (550,'#8172b3','550')]:
    ax_ov.axvline(wl, color=col_l, lw=0.9, ls=':', alpha=0.7)
    ax_ov.text(wl+3, 0.02, f'{lbl_l}nm', fontsize=7, color=col_l)

ax_ov.set_xlim(XLIM); ax_ov.set_ylim(0, 1.25)
ax_ov.set_xlabel('Wavelength (nm)', fontsize=8)
ax_ov.set_ylabel('Normalized Absorbance\n(A / A_420)', fontsize=8)
ax_ov.set_title('(A) Overlay: y_norm boundary spectra + Actual samples\n'
                'All normalized to A=1 at 420nm', fontsize=9, fontweight='bold')
ax_ov.legend(fontsize=7.5, loc='upper right')
ax_ov.tick_params(labelsize=7)

# ── (B) y_norm vs n 곡선 (col span 1.5 -> col 2~3) ──
ax_yn = fig.add_subplot(gs[0, 2:4])

n_range  = np.linspace(0.05, 12, 1000)
yn_curve = np.array([yn_from_n(n) for n in n_range])

# 구간 배경
for lo, hi, fc, lbl in zone_colors:
    lo_ = lo if lo is not None else 0.0
    hi_ = hi if hi is not None else 1.0
    ax_yn.axhspan(lo_, hi_, alpha=0.35, color=fc)
    ax_yn.text(11.5, (lo_ + hi_)/2, lbl, ha='right', va='center', fontsize=7, color='#555')

ax_yn.plot(n_range, yn_curve, color='#333', lw=2.2, zorder=3)

# 경계점 마커
for yn_b, col in zip(boundaries, colors_bnd):
    n_b = boundary_n[yn_b]
    ax_yn.scatter([n_b], [yn_b], color=col, s=70, zorder=5)
    ax_yn.annotate(f'y_norm={yn_b}\nn={n_b:.2f}',
                   xy=(n_b, yn_b), xytext=(n_b+0.5, yn_b+0.025),
                   fontsize=7, color=col,
                   arrowprops=dict(arrowstyle='->', color=col, lw=0.8))

# 실제 샘플
for sid, col_s in [('1','#4c72b0'), ('8','#9c27b0')]:
    d   = sample_data[sid]
    yn  = d['yn']
    n_e = boundary_n.get(round(yn, 2), None)
    try:
        n_e = brentq(lambda n: yn_from_n(n) - yn, 0.01, 50)
    except Exception:
        n_e = 12.5
    ax_yn.scatter([min(n_e, 12)], [min(yn, 0.95)], color=col_s, s=70, marker='D', zorder=6)
    ax_yn.annotate(f'S{sid}: y_norm={yn:.3f}\n(n={n_e:.1f} equiv)',
                   xy=(min(n_e,12), min(yn,0.95)),
                   xytext=(min(n_e,12)-3, min(yn,0.95)+0.05),
                   fontsize=7, color=col_s, fontweight='bold',
                   arrowprops=dict(arrowstyle='->', color=col_s, lw=0.8))

ax_yn.set_xlim(0, 12); ax_yn.set_ylim(0.25, 1.0)
ax_yn.set_xlabel('Power-law exponent n  (A ∝ (420/λ)^n)', fontsize=8)
ax_yn.set_ylabel('y_norm', fontsize=8)
ax_yn.set_title('(B) y_norm = f(n)\nsteeper spectrum (large n) → lower y_norm', fontsize=9, fontweight='bold')
ax_yn.tick_params(labelsize=7)

# loss scale 서브축 (오른쪽)
ax_yn2 = ax_yn.twinx()
Y_pts = [0.25, 0.35, 0.45, 0.55, 0.65, 1.0]
L_pts = [-1.5,  -1.5, -1.2, -0.6, -0.3, -0.3]
ax_yn2.set_ylim(ax_yn.get_ylim())
loss_ticks = [0.35, 0.45, 0.55, 0.65]
loss_vals  = [np.interp(y, Y_pts, L_pts) for y in loss_ticks]
ax_yn2.set_yticks(loss_ticks)
ax_yn2.set_yticklabels([f'loss={v:.2f}' for v in loss_vals], fontsize=7, color='#555')
ax_yn2.tick_params(right=True, labelright=True)

# ── (C) 범례/설명 패널 ──
ax_leg = fig.add_subplot(gs[0, 4])
ax_leg.axis('off')
desc = [
    ('Spectrum shape', ''),
    ('─────────────', ''),
    (f'y_norm < 0.35', 'Rayleigh보다 가파름'),
    ('', '(과응집/노이즈)'),
    ('', f'loss = -1.5'),
    ('', ''),
    (f'0.35 ~ 0.45', 'Rayleigh (n=4~∞)'),
    ('', '정상 콜로이드 산란'),
    ('', 'loss = -1.5 ~ -1.2'),
    ('', ''),
    (f'0.45 ~ 0.55', '1/λ^4 ~ 1/λ^1'),
    ('', '(Mie / 초기 형성)'),
    ('', 'loss = -1.2 ~ -0.6'),
    ('', ''),
    (f'0.55 ~ 0.65', '거의 flat (n<1)'),
    ('', 'QD 형성 신호 가능'),
    ('', 'loss = -0.6 ~ -0.3'),
    ('', ''),
    (f'>= 0.65', 'Ceiling (QD-like)'),
    ('', 'loss = -0.3 (최고)'),
]
for i, (k, v) in enumerate(desc):
    ax_leg.text(0.02, 0.97 - i*0.047, f'{k}  {v}',
                transform=ax_leg.transAxes, fontsize=7.2,
                color='#222' if k and not k.startswith('─') else '#999',
                fontweight='bold' if ('~' in k or k.startswith('>')) else 'normal',
                family='monospace')
ax_leg.set_title('(C) Zone description', fontsize=9, fontweight='bold')

# ── Row 1: 경계별 개별 패널 ──
zone_labels = ['y_norm < 0.35\nloss = -1.5',
               'y_norm = 0.35~0.45\nloss = -1.5~-1.2',
               'y_norm = 0.45~0.55\nloss = -1.2~-0.6',
               'y_norm = 0.55~0.65\nloss = -0.6~-0.3',
               'y_norm >= 0.65\nloss = -0.3 (ceil)']
zone_fc   = ['#ffcccc','#ffd9b3','#fff0b3','#d4f0d4','#c8e6c9']

# 5개 구간을 대표하는 n값 (경계값 + 극단값 포함)
rep_n_sets = [
    [10.0, boundary_n[0.35]],                          # 0.35 이하 구간
    [boundary_n[0.35], boundary_n[0.45]],              # 0.35~0.45
    [boundary_n[0.45], boundary_n[0.55]],              # 0.45~0.55
    [boundary_n[0.55], boundary_n[0.65]],              # 0.55~0.65
    [boundary_n[0.65], 0.2],                           # 0.65 이상 (flat)
]
rep_n_colors = [
    ['#c62828', '#e65100'],
    ['#e65100', '#f9a825'],
    ['#f9a825', '#8bc34a'],
    ['#8bc34a', '#2e7d32'],
    ['#2e7d32', '#1565c0'],
]

for col_idx in range(5):
    ax = fig.add_subplot(gs[1, col_idx])
    ax.set_facecolor(zone_fc[col_idx] + '44')  # 투명 배경

    for n_val, col_v in zip(rep_n_sets[col_idx], rep_n_colors[col_idx]):
        if np.isinf(n_val) or n_val > 30:
            A = np.ones_like(lam)
            lbl = 'n=inf (flat)'
        else:
            A = (ref / lam) ** n_val
            lbl = f'n={n_val:.2f}'
        A_norm = A / np.interp(420, lam, A)
        yn_val = yn_from_n(n_val) if not np.isinf(n_val) and n_val > 0.01 else 1.0
        ax.plot(lam, A_norm, color=col_v, lw=2.0,
                label=f'{lbl}\ny_norm={yn_val:.3f}')

    # 실제 샘플 중 이 구간에 해당하는 것 표시
    for sid, col_s, ls_s in [('1','#4c72b0','--'), ('8','#9c27b0','-.')]:
        d  = sample_data[sid]
        yn = d['yn']
        lo = zone_colors[col_idx][0]; hi = zone_colors[col_idx][1]
        lo_ = lo if lo is not None else -np.inf
        hi_ = hi if hi is not None else np.inf
        if lo_ <= yn < hi_:
            m = (d['xsm'] >= 350) & (d['xsm'] <= 700)
            ax.plot(d['xsm'][m], d['ysm_norm'][m], color=col_s, lw=1.5, ls=ls_s,
                    label=f'Sample {sid}  y={yn:.3f}', alpha=0.9)

    # 3개 기준 수직선
    for wl_r, col_r in [(420,'#1a8c2e'), (460,'#c44e52'), (550,'#8172b3')]:
        ax.axvline(wl_r, color=col_r, lw=0.8, ls=':', alpha=0.6)

    ax.set_xlim(XLIM); ax.set_ylim(0, 1.35)
    ax.set_xlabel('Wavelength (nm)', fontsize=7)
    ax.set_ylabel('A / A_420', fontsize=7)
    ax.set_title(zone_labels[col_idx], fontsize=8, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', fc=zone_fc[col_idx], alpha=0.8))
    ax.legend(fontsize=6.5, loc='upper right')
    ax.tick_params(labelsize=6.5)

    # 구간 레이블
    lo_txt = zone_colors[col_idx][0]; hi_txt = zone_colors[col_idx][1]
    lo_str = f'{lo_txt:.2f}' if lo_txt is not None else '-inf'
    hi_str = f'{hi_txt:.2f}' if hi_txt is not None else 'inf'

# ── Row 2: y_norm -> loss 구간 매핑 + 실제 포인트 (wide panel) ──
ax_map = fig.add_subplot(gs[2, :3])
Y_pts2 = [0.0,  0.35, 0.45, 0.55, 0.65, 1.0]
L_pts2 = [-1.5, -1.5, -1.2, -0.6, -0.3, -0.3]
ax_map.plot(Y_pts2, L_pts2, color='#333', lw=2.5, zorder=3, label='y_norm -> loss')
for lo, hi, fc, lbl in zone_colors:
    lo_ = lo if lo is not None else 0.0
    hi_ = hi if hi is not None else 1.0
    l0  = np.interp(lo_, Y_pts2, L_pts2)
    l1  = np.interp(hi_, Y_pts2, L_pts2)
    ax_map.fill_betweenx([min(l0,l1)-0.03, max(l0,l1)+0.03], lo_, hi_,
                          alpha=0.4, color=fc, zorder=1)
    ax_map.text((lo_+hi_)/2, (min(l0,l1)+max(l0,l1))/2, lbl.replace('\n',' '),
                ha='center', va='center', fontsize=7.5, color='#444')

# 경계 마커
for yn_b, col in zip(boundaries, colors_bnd):
    lv = np.interp(yn_b, Y_pts2, L_pts2)
    ax_map.scatter([yn_b], [lv], color=col, s=80, zorder=6)
    ax_map.text(yn_b, lv - 0.08, f'y={yn_b}', ha='center', fontsize=7.5, color=col, fontweight='bold')

# 실제 샘플
for sid, col_s, ms in [('1','#4c72b0','D'), ('8','#9c27b0','s')]:
    yn = sample_data[sid]['yn']
    lv = np.interp(yn, Y_pts2, L_pts2)
    ax_map.scatter([yn], [lv], color=col_s, s=90, marker=ms, zorder=7)
    ax_map.annotate(f'Sample {sid}\ny_norm={yn:.4f}\nloss={lv:.4f}',
                    xy=(yn, lv), xytext=(yn+0.05, lv+0.15),
                    fontsize=8, color=col_s, fontweight='bold',
                    arrowprops=dict(arrowstyle='->', color=col_s, lw=1.0))

ax_map.set_xlim(0, 1.0); ax_map.set_ylim(-1.65, 0.05)
ax_map.set_xlabel('y_norm  =  (ab_460 - ab_550) / (ab_420 - ab_550)', fontsize=9)
ax_map.set_ylabel('loss', fontsize=9)
ax_map.set_title('(D) y_norm -> loss piecewise linear mapping  (no-peak branch)\n'
                 'diamond=Sample1, square=Sample8', fontsize=9, fontweight='bold')
ax_map.tick_params(labelsize=8)
ax_map.axhline(-0.3, color='#2e7d32', lw=0.8, ls=':', alpha=0.5)
ax_map.axhline(-1.5, color='#c62828', lw=0.8, ls=':', alpha=0.5)

# ── 수식 설명 패널 ──
ax_eq = fig.add_subplot(gs[2, 3:])
ax_eq.axis('off')
eq_lines = [
    ('y_norm formula (no-peak branch):', True),
    ('', False),
    ('y_norm = (ab_460 - ab_550)', False),
    ('         / (ab_420 - ab_550)', False),
    ('', False),
    ('Interpretation:', True),
    ('  0 = ab_460 same as ab_550', False),
    ('      (flat after 460nm)', False),
    ('  1 = ab_460 same as ab_420', False),
    ('      (completely flat)', False),
    ('', False),
    ('Issue:', True),
    ('  Pure scattering (n=1) already', False),
    ('  gives y_norm~0.63, near', False),
    ('  the QD-like ceiling (0.65)', False),
    ('  -> possible overestimation', False),
    ('', False),
    ('Sample 1: y_norm=0.636 (n~0.89)', False),
    ('Sample 8: y_norm=0.762 (very flat)', False),
]
for i, (line, bold) in enumerate(eq_lines):
    ax_eq.text(0.02, 0.97 - i*0.048, line,
               transform=ax_eq.transAxes, fontsize=7.5,
               fontweight='bold' if bold else 'normal',
               family='monospace', color='#1a1a2e')
ax_eq.set_title('(E) Formula & Interpretation', fontsize=9, fontweight='bold')

fig.suptitle('y_norm Zone Boundaries: Spectral Shape at Each Threshold\n'
             'y_norm = (ab_460 - ab_550) / (ab_420 - ab_550)  |  Boxcar-smoothed spectrum',
             fontsize=12, fontweight='bold', y=1.005)

plt.savefig('ynorm_boundaries.png', dpi=150, bbox_inches='tight')
print('saved: ynorm_boundaries.png')
