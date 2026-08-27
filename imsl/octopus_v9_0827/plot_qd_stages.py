"""
InP QD 합성 Stage별 loss 계산 경로 + S1/S2 y_norm 평가 집중 분석
"""
import numpy as np, sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
sys.path.insert(0, '.')

lam = np.linspace(350, 720, 3000)

def power_bg(n, scale):
    return scale * (350.0 / lam) ** n

def gaussian(amp, center, sigma):
    return amp * np.exp(-0.5 * ((lam - center) / sigma) ** 2)

def make_spectrum(bg_n, bg_s, peaks, noise_amp=0.0, seed=None):
    A = power_bg(bg_n, bg_s)
    for amp, ctr, sig in peaks:
        A += gaussian(amp, ctr, sig)
    if noise_amp > 0:
        rng = np.random.default_rng(seed or 42)
        ns = noise_amp * (1.5 - np.clip((lam-350)/500, 0, 1))
        A += rng.normal(0, 1, len(lam)) * ns
    return np.maximum(A, 0)

def yn_calc(A):
    a420 = np.interp(420, lam, A)
    a460 = np.interp(460, lam, A)
    a550 = np.interp(550, lam, A)
    d = a420 - a550
    yn = float(np.clip((a460 - a550) / d, 0, 1)) if d > 0 else 0.0
    return yn, a420, a460, a550

def loss_yn(yn):
    return float(np.interp(yn, [0.,.35,.45,.55,.65,1.], [-1.5,-1.5,-1.2,-0.6,-0.3,-0.3]))

def loss_peak(lm, pv, target_lm=460, target_pv=1.3, w_lm=0.1, w_pv=0.9,
              wl_min=350, wl_max=720):
    """peak 검출 성공 시 loss 계산"""
    if lm <= target_lm:
        scale = max(target_lm - wl_min, 1.0)
    else:
        scale = max(wl_max - target_lm, 1.0)
    lm_loss = float(np.clip(abs(target_lm - lm) / scale, 0, 1))
    pv_loss  = 0.0 if pv >= target_pv else float(np.clip((target_pv - pv) / target_pv, 0, 1))
    return -(lm_loss * w_lm + pv_loss * w_pv) * 0.3

# ── 6개 Stage 스펙트럼 정의 ──────────────────────────────────────
stages_def = [
    dict(id=0, bg_n=6.0, bg_s=0.38, peaks=[], noise=0.000,
         color='#546e7a', fc='#eceff1',
         title='Stage 0\nBefore mixing',
         has_peak=False, peak_lm=None, peak_pv=None,
         sub0='Solvent+ligand', sub1='Very steep scatter'),

    dict(id=1, bg_n=2.8, bg_s=0.38, peaks=[], noise=0.006,
         color='#4c72b0', fc='#e3f2fd',
         title='Stage 1\nPrecursor injection',
         has_peak=False, peak_lm=None, peak_pv=None,
         sub0='In+P precursors', sub1='Gradual decay, no QD peak'),

    dict(id=2, bg_n=2.5, bg_s=0.34, peaks=[(0.18, 435, 52)], noise=0.004,
         color='#2e7d32', fc='#e8f5e9',
         title='Stage 2\nEarly nucleation',
         has_peak=False, peak_lm=None, peak_pv=None,
         sub0='~1.5nm InP nuclei', sub1='Broad shoulder ~435nm\n(NOT detected as peak)'),

    dict(id=3, bg_n=2.0, bg_s=0.28, peaks=[(0.35, 510, 55)], noise=0.003,
         color='#e65100', fc='#fff3e0',
         title='Stage 3\nEarly growth',
         has_peak=True, peak_lm=510, peak_pv=0.9,
         sub0='QD ~2-3nm', sub1='Broad peak ~510nm -> peak detected'),

    dict(id=4, bg_n=1.8, bg_s=0.26, peaks=[(0.30, 482, 35)], noise=0.002,
         color='#7b1fa2', fc='#f3e5f5',
         title='Stage 4\nLate growth',
         has_peak=True, peak_lm=482, peak_pv=1.1,
         sub0='Ostwald ripening', sub1='Peak ~482nm -> peak detected'),

    dict(id=5, bg_n=1.5, bg_s=0.22, peaks=[(0.28, 460, 20)], noise=0.001,
         color='#c62828', fc='#ffebee',
         title='Stage 5\nTarget QD',
         has_peak=True, peak_lm=460, peak_pv=1.8,
         sub0='Target achieved', sub1='Sharp peak 460nm -> peak detected'),
]

stages = []
for d in stages_def:
    A = make_spectrum(d['bg_n'], d['bg_s'], d['peaks'], d['noise'], seed=d['id'])
    yn, a420, a460, a550 = yn_calc(A)
    if d['has_peak']:
        lss = loss_peak(d['peak_lm'], d['peak_pv'])
        branch = 'PEAK branch'
    else:
        lss = loss_yn(yn)
        branch = 'y_norm branch'
    stages.append({**d, 'A': A, 'yn': yn, 'a420': a420, 'a460': a460,
                   'a550': a550, 'loss': lss, 'branch': branch})
    flag = ''
    if d['has_peak']:
        flag = f' | lm={d["peak_lm"]}nm  pv={d["peak_pv"]}'
    print(f"S{d['id']}: {branch:20s}  y_norm={yn:.4f}  loss={lss:.4f}{flag}")

# ──────────────────────────────────────────────────────────────────
# 그림 구성
# Row 0: 전체 오버레이(col 0-3) | loss 경로 다이어그램(col 4-5)
# Row 1: Stage 0-5 개별 패널
# ──────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(22, 12))
gs  = gridspec.GridSpec(2, 6, figure=fig, hspace=0.55, wspace=0.28,
                         height_ratios=[1.35, 1.05])

XLIM = (350, 720)
YLIM = (-0.01, 0.90)
REF  = [(420,'#1a8c2e'), (460,'#c44e52'), (550,'#8172b3')]

# ── (A) 전체 오버레이 (col 0-3) ──────────────────────────────────
ax_ov = fig.add_subplot(gs[0, :4])

for st in stages:
    ls   = '-' if not st['has_peak'] else '--'
    lw   = 2.2 if not st['has_peak'] else 1.8
    desc = ('y_norm branch' if not st['has_peak']
            else f"peak branch  lm={st['peak_lm']}nm")
    ax_ov.plot(lam, st['A'], color=st['color'], lw=lw, ls=ls,
               label=f"S{st['id']}: {st['title'].split(chr(10))[1]}  "
                     f"[{desc}]  loss={st['loss']:.3f}")

for wl, col in REF:
    ax_ov.axvline(wl, color=col, lw=1.0, ls=':', alpha=0.75)
    ax_ov.text(wl+2, YLIM[1]*0.97, f'{wl}nm', fontsize=8, color=col, va='top')

# 분기 레이블
ax_ov.text(530, 0.80, 'solid = no peak  (y_norm branch)',
           fontsize=8, color='#333',
           bbox=dict(boxstyle='round,pad=0.3', fc='#f0f0f0', alpha=0.9))
ax_ov.text(530, 0.73, 'dashed = peak detected  (peak branch)',
           fontsize=8, color='#333',
           bbox=dict(boxstyle='round,pad=0.3', fc='#fff9c4', alpha=0.9))

ax_ov.set_xlim(XLIM); ax_ov.set_ylim(YLIM)
ax_ov.set_xlabel('Wavelength (nm)', fontsize=9)
ax_ov.set_ylabel('Absorbance', fontsize=9)
ax_ov.set_title('(A) InP QD synthesis — UV-vis evolution\n'
                'Solid: no peak detected (y_norm branch)  |  Dashed: peak detected (peak branch)',
                fontsize=10, fontweight='bold')
ax_ov.legend(fontsize=7.5, loc='upper right', framealpha=0.93)
ax_ov.tick_params(labelsize=8)

# ── (B) Loss 계산 경로 + S1/S2 y_norm 집중 (col 4-5) ──────────────
ax_b = fig.add_subplot(gs[0, 4:])

Y_pts = [0.,.35,.45,.55,.65,1.]
L_pts = [-1.5,-1.5,-1.2,-0.6,-0.3,-0.3]

for lo, hi, fc in [(0.,.35,'#ffcccc'),(0.35,.45,'#ffd9b3'),(0.45,.55,'#fff0b3'),
                    (0.55,.65,'#d4f0d4'),(0.65,1.0,'#c8e6c9')]:
    l0=np.interp(lo,Y_pts,L_pts); l1=np.interp(hi,Y_pts,L_pts)
    ax_b.fill_betweenx([min(l0,l1)-0.04, max(l0,l1)+0.04], lo, hi, alpha=0.4, color=fc)

ax_b.plot(Y_pts, L_pts, color='#333', lw=2.2, zorder=3)
for yn_b in [0.35,0.45,0.55,0.65]:
    ax_b.axvline(yn_b, color='#ccc', lw=0.8, ls=':')

# no-peak stages (y_norm 평가 대상)
no_pk_offsets = {0:(-0.12,+0.08), 1:(+0.03,+0.09), 2:(-0.14,-0.11)}
for st in stages:
    yn=st['yn']; lss=st['loss']
    if not st['has_peak']:
        ax_b.scatter([yn],[lss], color=st['color'], s=100, zorder=6,
                     edgecolors='k', linewidth=0.8)
        ox,oy = no_pk_offsets.get(st['id'],(0.03,0.07))
        ax_b.annotate(f"S{st['id']}: y_norm={yn:.3f}\nloss={lss:.3f}",
                      xy=(yn,lss), xytext=(yn+ox, lss+oy),
                      fontsize=8, color=st['color'], fontweight='bold',
                      arrowprops=dict(arrowstyle='->', color=st['color'], lw=1.0))

# peak-detected stages: 오른쪽 범례로 표시
peak_y = -0.05
for st in stages:
    if st['has_peak']:
        ax_b.scatter([0.95],[st['loss']], color=st['color'], s=80, marker='D', zorder=6)
        ax_b.text(0.96, st['loss']+0.01,
                  f"S{st['id']}: peak branch  lm={st['peak_lm']}nm  loss={st['loss']:.3f}",
                  fontsize=7, color=st['color'], va='bottom')

# peak branch 구분선
ax_b.axhline(-0.3, color='#2e7d32', lw=1.0, ls='--', alpha=0.5)
ax_b.text(0.01, -0.28, 'ceiling = -0.300', fontsize=7, color='#2e7d32')
ax_b.text(0.01, -1.55, 'worst  = -1.500', fontsize=7, color='#c62828')

# S1 vs S2 평가 quality 화살표
s1 = next(s for s in stages if s['id']==1)
s2 = next(s for s in stages if s['id']==2)
ax_b.annotate('', xy=(s2['yn'], s2['loss']),
               xytext=(s1['yn'], s1['loss']),
               arrowprops=dict(arrowstyle='->', color='#555', lw=1.5, linestyle='dashed'))
mid_yn = (s1['yn']+s2['yn'])/2; mid_l = (s1['loss']+s2['loss'])/2
ax_b.text(mid_yn+0.02, mid_l-0.12,
          f"S1->S2\ny_norm +{s2['yn']-s1['yn']:.3f}\nloss  +{s2['loss']-s1['loss']:.3f}",
          fontsize=7.5, color='#555',
          bbox=dict(boxstyle='round,pad=0.3', fc='#fffff0', alpha=0.95))

ax_b.set_xlim(0, 1.0); ax_b.set_ylim(-1.62, 0.15)
ax_b.set_xlabel('y_norm  =  (ab_460 - ab_550) / (ab_420 - ab_550)', fontsize=8)
ax_b.set_ylabel('loss', fontsize=9)
ax_b.set_title('(B) Loss by branch\ncircle = y_norm branch  |  diamond = peak branch',
               fontsize=10, fontweight='bold')
ax_b.tick_params(labelsize=8)

# ── Row 1: 개별 Stage 패널 ──────────────────────────────────────
YLIM2 = (-0.01, 0.88)
for col_i, st in enumerate(stages):
    ax = fig.add_subplot(gs[1, col_i])

    is_focus = st['id'] in [1, 2]  # 핵심 평가 대상
    if is_focus:
        ax.set_facecolor('#fffff0')
    else:
        ax.set_facecolor(st['fc'] + '50')

    ax.fill_between(lam, 0, st['A'], color=st['color'], alpha=0.15)
    ax.plot(lam, st['A'], color=st['color'], lw=2.0,
            ls='-' if not st['has_peak'] else '--')

    # 3개 기준점
    for wl, col_v in REF:
        ax.axvline(wl, color=col_v, lw=0.9, ls=':', alpha=0.65)
        ab = np.interp(wl, lam, st['A'])
        ax.scatter([wl],[ab], color=col_v, s=35, zorder=7)

    ax.set_xlim(XLIM); ax.set_ylim(YLIM2)
    ax.set_xlabel('Wavelength (nm)', fontsize=7)
    ax.set_ylabel('Absorbance', fontsize=7)
    ax.tick_params(labelsize=6.5)

    ax.set_title(st['title'], fontsize=8.5, fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.22', fc=st['fc'], alpha=0.85))
    ax.text(0.04, 0.97, f'S{st["id"]}', transform=ax.transAxes,
            fontsize=12, fontweight='bold', va='top', color=st['color'])

    if st['has_peak']:
        # peak branch 표시
        ax.text(0.5, 0.78,
                f'PEAK DETECTED\nlm={st["peak_lm"]}nm\nloss={st["loss"]:.3f}',
                transform=ax.transAxes, ha='center', va='center', fontsize=7.5,
                color='#1a5276', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', fc='#d6eaf8', alpha=0.95,
                          edgecolor='#2980b9', linewidth=1.2))
        ax.text(0.5, 0.01, st['sub1'].split('\n')[0],
                transform=ax.transAxes, ha='center', va='bottom',
                fontsize=6, color='#555', style='italic')
    else:
        # y_norm branch 표시
        extra = ''
        if st['id'] == 2:
            extra = '\n[435nm tail -> ab_460 up]'
        ax.text(0.04, 0.72,
                f'y_norm={st["yn"]:.3f}\nloss  ={st["loss"]:.3f}\n(y_norm branch){extra}',
                transform=ax.transAxes, fontsize=7, family='monospace',
                bbox=dict(boxstyle='round,pad=0.28', fc='white', alpha=0.95,
                          edgecolor='#aaa' if not is_focus else '#f39c12',
                          linewidth=0.8 if not is_focus else 1.5))
        ax.text(0.5, 0.01, st['sub1'],
                transform=ax.transAxes, ha='center', va='bottom',
                fontsize=5.8, color='#555', style='italic')

        # 핵심 대상 강조 테두리
        if is_focus:
            for sp in ax.spines.values():
                sp.set_edgecolor('#f39c12'); sp.set_linewidth(2.0)

fig.suptitle(
    'InP QD Synthesis — Loss Calculation Branch by Stage\n'
    'S0, S1, S2: no peak detected -> y_norm branch  |  '
    'S3, S4, S5: peak detected -> peak branch  |  '
    'Key focus: does y_norm correctly rank S1 < S2?',
    fontsize=11, fontweight='bold', y=1.012)

plt.savefig('qd_stages.png', dpi=150, bbox_inches='tight')
print('saved: qd_stages.png')
