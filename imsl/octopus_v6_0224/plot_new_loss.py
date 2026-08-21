"""
no-peak branch 개선 loss 제안 시각화

현재 y_norm 문제:
  - S1(no QD):   y_norm=0.506 → loss=-0.866  (전구체만인데 너무 관대)
  - S2(435nm 어깨): y_norm=0.805 → loss=-0.300 ceiling (과대평가)

제안 새 loss (3 component):
  1. flat_score  : power-law fit 지수 n → 배경이 완만할수록 높음
  2. amp_score   : 배경 제거 후 잔류 피크 진폭 (0~1)
  3. pos_score   : 잔류 피크 위치가 460nm에 가까울수록 높음 (Gaussian weight)

  combined = 0.4 * flat_score + 0.6 * amp_score * pos_score
  loss_new  = -1.5 + 1.2 * clip(combined, 0, 1)   →  [-1.5, -0.3]
"""
import numpy as np, sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.optimize import curve_fit
sys.path.insert(0, '.')

lam = np.linspace(350, 720, 3000)

def power_bg(n, scale):
    return scale * (350.0 / lam) ** n

def gaussian(amp, center, sigma):
    return amp * np.exp(-0.5 * ((lam - center) / sigma) ** 2)

def make_spectrum(bg_n, bg_s, peaks, noise_amp=0.0, seed=0):
    A = power_bg(bg_n, bg_s)
    for amp, c, s in peaks:
        A += gaussian(amp, c, s)
    if noise_amp > 0:
        rng = np.random.default_rng(seed)
        ns = noise_amp * (1.5 - np.clip((lam-350)/500, 0, 1))
        A += rng.normal(0, 1, len(lam)) * ns
    return np.maximum(A, 0)

# ── 현재 y_norm (3점 비율) ──────────────────────────────────────
def loss_ynorm_current(A, x=lam):
    a420 = np.interp(420, x, A)
    a460 = np.interp(460, x, A)
    a550 = np.interp(550, x, A)
    d = a420 - a550
    yn = float(np.clip((a460 - a550) / d, 0, 1)) if d > 0 else 0.0
    return yn, float(np.interp(yn, [0.,.35,.45,.55,.65,1.], [-1.5,-1.5,-1.2,-0.6,-0.3,-0.3]))

# ── 새 loss 함수 ─────────────────────────────────────────────────
def loss_new(A, x=lam,
             target_lm=460.0,
             bg_lo=570.0, bg_hi=680.0,
             search_lo=400.0, search_hi=540.0,
             pos_bw=30.0,          # 위치 가중치 Gaussian 반폭 (nm)
             n_max_ref=8.0,        # flat_score 정규화 기준 n
             amp_ref=0.050,        # amp_score 정규화 기준 잔류 진폭 (노이즈 << 0.05)
             w_flat=0.40,          # flat_score 가중치
             w_amp_pos=0.60):      # amp*pos 가중치
    """
    반환: (loss, flat_score, amp_score, pos_score, n_fit, lm_resid, resid_arr, bg_arr)
    """
    # 1) power-law 배경 피팅 (570-680nm)
    mask_bg = (x >= bg_lo) & (x <= bg_hi)
    xb = x[mask_bg]; yb = np.maximum(A[mask_bg], 1e-9)
    ref_wl = float(xb[0])
    try:
        def pl(lx, a, n): return a * (ref_wl / lx) ** n
        p, _ = curve_fit(pl, xb, yb, p0=[float(yb[0]), 3.0],
                         bounds=([0.0, 0.1], [10.0, 12.0]), maxfev=3000)
        bg = np.maximum(pl(x, *p), 0.0)
        n_fit = float(p[1])
    except Exception:
        bg = np.interp(x, [x[0], x[-1]], [A[0], A[-1]])
        n_fit = n_max_ref

    # 2) 잔류 스펙트럼 — 노이즈 억제를 위해 Gaussian 스무딩 적용
    from scipy.ndimage import gaussian_filter1d
    dx_nm = float(x[1] - x[0])            # 포인트 당 nm (≈ 0.123 nm)
    sigma_pts = int(round(5.0 / dx_nm))   # 5nm 스무딩
    A_smooth = gaussian_filter1d(A, sigma=sigma_pts)
    resid = np.maximum(A_smooth - bg, 0.0)

    # 3) flat_score: n이 작을수록 (배경 완만) 높음
    flat_score = float(np.clip(1.0 - n_fit / n_max_ref, 0.0, 1.0))

    # 4) 탐색 구간 내 잔류 피크
    mask_s = (x >= search_lo) & (x <= search_hi)
    resid_s = resid[mask_s]; x_s = x[mask_s]

    if resid_s.max() > 1e-6:
        peak_idx  = int(np.argmax(resid_s))
        lm_resid  = float(x_s[peak_idx])
        amp_resid = float(resid_s[peak_idx])

        # pos_score: 잔류 피크가 460nm에 가까울수록 1
        pos_score = float(np.exp(-0.5 * ((lm_resid - target_lm) / pos_bw) ** 2))
        # amp_score: 잔류 피크 진폭 (amp_ref 기준 정규화)
        amp_score = float(np.clip(amp_resid / amp_ref, 0.0, 1.0))
    else:
        lm_resid  = float(target_lm)
        amp_resid = 0.0
        pos_score = 0.0
        amp_score = 0.0

    # 5) combined score → loss
    combined = w_flat * flat_score + w_amp_pos * amp_score * pos_score
    loss_val = -1.5 + 1.2 * float(np.clip(combined, 0.0, 1.0))

    return (float(np.clip(loss_val, -1.5, -0.3)),
            flat_score, amp_score, pos_score, n_fit, lm_resid, resid, bg)

# ── Stage 스펙트럼 정의 (no-peak 3개) ────────────────────────────
stage_defs = [
    dict(id=0, bg_n=6.0, bg_s=0.38, peaks=[], noise=0.000,
         color='#546e7a', label='Stage 0  Before mixing\n(very steep scatter, n~6)'),
    dict(id=1, bg_n=2.8, bg_s=0.38, peaks=[], noise=0.006,
         color='#4c72b0', label='Stage 1  Precursor injection\n(gradual decay, no QD, n~2.8)'),
    dict(id=2, bg_n=2.5, bg_s=0.34, peaks=[(0.18, 435, 52)], noise=0.004,
         color='#2e7d32', label='Stage 2  Early nucleation\n(broad shoulder ~435nm, n~2.5)'),
]

stages = []
for d in stage_defs:
    A = make_spectrum(d['bg_n'], d['bg_s'], d['peaks'], d['noise'], seed=d['id'])
    yn, l_cur = loss_ynorm_current(A)
    l_new, fl, am, ps, nf, lmr, resid, bg = loss_new(A)
    stages.append({**d, 'A': A, 'resid': resid, 'bg': bg,
                   'yn': yn, 'loss_cur': l_cur,
                   'loss_new': l_new, 'flat': fl, 'amp': am, 'pos': ps,
                   'n_fit': nf, 'lm_resid': lmr})
    print(f"S{d['id']}:  y_norm={yn:.4f}  loss_cur={l_cur:.4f}  "
          f"| flat={fl:.3f}  amp={am:.3f}  pos={ps:.3f}  "
          f"n_fit={nf:.2f}  lm_resid={lmr:.1f}nm  loss_new={l_new:.4f}")

# 참고: 만약 435nm 어깨 대신 460nm 어깨가 있다면?
A_ideal = make_spectrum(2.5, 0.34, [(0.10, 460, 25)], 0.004, seed=99)
_, _, _, _, _, _, resid_i, bg_i = loss_new(A_ideal)
yn_i, l_ci = loss_ynorm_current(A_ideal)
l_ni, fl_i, am_i, ps_i, nf_i, lmr_i, _, _ = loss_new(A_ideal)
print(f"Ideal(460nm):  y_norm={yn_i:.4f}  loss_cur={l_ci:.4f}  "
      f"| flat={fl_i:.3f}  amp={am_i:.3f}  pos={ps_i:.3f}  loss_new={l_ni:.4f}")

# ────────────────────────────────────────────────────────────────────────────
# 그림 구성  (3행 4열)
# Row 0: 스펙트럼 + 배경 + 잔류   (col 0-2: 3개 stage, col 3: 비교용)
# Row 1: 잔류 스펙트럼 + pos weight (col 0-2) + 점수 bar (col 3)
# Row 2: loss 비교 bar (전체 col span)
# ────────────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 13))
gs  = gridspec.GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.32,
                         height_ratios=[1.1, 1.0, 0.75])

XLIM = (350, 720); YLIM = (-0.01, 0.72)

# ── Row 0: 스펙트럼 + 배경 ──────────────────────────────────────
for ci, st in enumerate(stages):
    ax = fig.add_subplot(gs[0, ci])
    ax.fill_between(lam, 0, st['A'], color=st['color'], alpha=0.12)
    ax.plot(lam, st['A'],  color=st['color'], lw=2.0, label='Total A(λ)')
    ax.plot(lam, st['bg'], color='#999',      lw=1.2, ls='--', label=f'BG fit (n={st["n_fit"]:.1f})')
    ax.fill_between(lam, st['bg'], st['A'],
                     where=st['A']>st['bg'], color='#e67e22', alpha=0.25, label='Residual')
    for wl, col in [(420,'#1a8c2e'),(460,'#c44e52'),(550,'#8172b3')]:
        ax.axvline(wl, color=col, lw=0.9, ls=':', alpha=0.7)
    ax.set_xlim(XLIM); ax.set_ylim(YLIM)
    ax.set_xlabel('Wavelength (nm)', fontsize=8)
    ax.set_ylabel('Absorbance', fontsize=8)
    ax.set_title(f'({"ABC"[ci]}) {st["label"]}', fontsize=8.5, fontweight='bold',
                 color=st['color'])
    ax.legend(fontsize=7, loc='upper right')
    ax.tick_params(labelsize=7)

# col 3: 이상적 비교 (460nm 어깨)
ax3 = fig.add_subplot(gs[0, 3])
ax3.fill_between(lam, 0, A_ideal, color='#c62828', alpha=0.12)
ax3.plot(lam, A_ideal, color='#c62828', lw=2.0, label='Total A(λ)')
ax3.plot(lam, bg_i,    color='#999',    lw=1.2, ls='--', label=f'BG fit (n={nf_i:.1f})')
ax3.fill_between(lam, bg_i, A_ideal,
                  where=A_ideal>bg_i, color='#e67e22', alpha=0.25, label='Residual')
for wl, col in [(420,'#1a8c2e'),(460,'#c44e52'),(550,'#8172b3')]:
    ax3.axvline(wl, color=col, lw=0.9, ls=':', alpha=0.7)
ax3.set_xlim(XLIM); ax3.set_ylim(YLIM)
ax3.set_xlabel('Wavelength (nm)', fontsize=8)
ax3.set_title('(D) Reference: 460nm shoulder\n(same bg as S2, peak at 460nm)', fontsize=8.5,
              fontweight='bold', color='#c62828')
ax3.legend(fontsize=7, loc='upper right')
ax3.tick_params(labelsize=7)

# ── Row 1: 잔류 + pos weight ─────────────────────────────────────
pos_weight = np.exp(-0.5 * ((lam - 460) / 30) ** 2)   # pos_score 가중치 곡선

for ci, st in enumerate(stages):
    ax = fig.add_subplot(gs[1, ci])
    ax.fill_between(lam, 0, st['resid'], color='#e67e22', alpha=0.30, label='Residual')
    ax.plot(lam, st['resid'], color='#e67e22', lw=1.5)
    # pos weight
    ax2r = ax.twinx()
    ax2r.plot(lam, pos_weight, color='#8172b3', lw=1.2, ls='--', alpha=0.7,
              label='pos weight\nexp(-(λ-460)²/30²)')
    ax2r.set_ylim(0, 1.6); ax2r.set_yticks([0, 0.5, 1.0])
    ax2r.tick_params(labelsize=6.5, labelcolor='#8172b3')
    if st['lm_resid'] is not None and st['amp'] > 0.01:
        ax.axvline(st['lm_resid'], color='#e67e22', lw=1.2, ls=':')
        ax.text(st['lm_resid']+3, ax.get_ylim()[1]*0.85 if ci<2 else 0.15,
                f"lm_resid={st['lm_resid']:.0f}nm\n"
                f"pos={st['pos']:.3f}\namp={st['amp']:.3f}",
                fontsize=7, color='#e67e22')
    ax.axvline(460, color='#c44e52', lw=1.0, ls=':', alpha=0.7)
    ax.set_xlim(XLIM); ax.set_ylim(-0.005, 0.25)
    ax.set_xlabel('Wavelength (nm)', fontsize=8)
    ax.set_ylabel('Residual', fontsize=8)
    ax.set_title(f'Residual spectrum  S{st["id"]}\n'
                 f'flat={st["flat"]:.3f}  amp={st["amp"]:.3f}  pos={st["pos"]:.3f}',
                 fontsize=8.5, fontweight='bold', color=st['color'])
    ax.legend(fontsize=7, loc='upper right')
    ax.tick_params(labelsize=7)

# col 3: 이상적 케이스 잔류
ax_r3 = fig.add_subplot(gs[1, 3])
ax_r3.fill_between(lam, 0, resid_i, color='#e67e22', alpha=0.30, label='Residual')
ax_r3.plot(lam, resid_i, color='#e67e22', lw=1.5)
ax_r3b = ax_r3.twinx()
ax_r3b.plot(lam, pos_weight, color='#8172b3', lw=1.2, ls='--', alpha=0.7)
ax_r3b.set_ylim(0, 1.6); ax_r3b.tick_params(labelsize=6.5, labelcolor='#8172b3')
ax_r3.axvline(460, color='#c44e52', lw=1.0, ls=':')
ax_r3.axvline(lmr_i, color='#e67e22', lw=1.2, ls=':')
ax_r3.text(lmr_i+3, 0.10,
           f"lm_resid={lmr_i:.0f}nm\npos={ps_i:.3f}\namp={am_i:.3f}",
           fontsize=7, color='#e67e22')
ax_r3.set_xlim(XLIM); ax_r3.set_ylim(-0.005, 0.25)
ax_r3.set_xlabel('Wavelength (nm)', fontsize=8)
ax_r3.set_title(f'Residual  Reference (460nm)\n'
                f'flat={fl_i:.3f}  amp={am_i:.3f}  pos={ps_i:.3f}',
                fontsize=8.5, fontweight='bold', color='#c62828')
ax_r3.tick_params(labelsize=7)

# ── Row 2: loss 비교 bar chart ──────────────────────────────────
ax_bar = fig.add_subplot(gs[2, :])

labels    = [f'S0\nBefore mixing', f'S1\nPrecursor\ninjection',
             f'S2\nEarly\nnucleation\n(435nm)', f'Ref\n460nm\nshoulder']
loss_cur  = [st['loss_cur'] for st in stages] + [l_ci]
loss_new_ = [st['loss_new'] for st in stages] + [l_ni]
colors    = [st['color'] for st in stages] + ['#c62828']

x = np.arange(len(labels)); w = 0.32
b1 = ax_bar.bar(x - w/2, loss_cur,  w, label='Current y_norm loss', color='#aaa',  alpha=0.8)
b2 = ax_bar.bar(x + w/2, loss_new_, w, label='Proposed new loss',   color='#2196f3', alpha=0.8)

# 색깔 테두리
for bar, col in zip(b1, colors):
    bar.set_edgecolor(col); bar.set_linewidth(2.0)
for bar, col in zip(b2, colors):
    bar.set_edgecolor(col); bar.set_linewidth(2.0)

for bar, val in zip(list(b1)+list(b2), loss_cur+loss_new_):
    ax_bar.text(bar.get_x()+bar.get_width()/2, val-0.07,
                f'{val:.3f}', ha='center', va='top', fontsize=8.5, fontweight='bold')

ax_bar.axhline(-0.30, color='#2e7d32', lw=1.0, ls='--', alpha=0.6)
ax_bar.axhline(-1.50, color='#c62828', lw=1.0, ls='--', alpha=0.6)
ax_bar.text(3.65, -0.27, '-0.3 ceiling', fontsize=8, color='#2e7d32')
ax_bar.text(3.65, -1.47, '-1.5 worst',   fontsize=8, color='#c62828')

ax_bar.set_xticks(x); ax_bar.set_xticklabels(labels, fontsize=9)
ax_bar.set_ylim(-1.65, 0.05)
ax_bar.set_ylabel('loss', fontsize=9)
ax_bar.set_title('(E) Loss comparison: Current y_norm  vs  Proposed new loss\n'
                 'S2가 ceiling에 도달하던 문제 개선 / Ref(460nm)와 S2(435nm) 차별화',
                 fontsize=10, fontweight='bold')
ax_bar.legend(fontsize=9, loc='lower right')
ax_bar.tick_params(labelsize=8)

fig.suptitle(
    'Proposed No-Peak Loss  =  -1.5 + 1.2 * clip(0.4*flat_score + 0.6*amp_score*pos_score, 0, 1)\n'
    'flat_score: power-law n small (flat bg) → high  |  '
    'amp_score: residual amplitude at peak → high  |  '
    'pos_score: exp(-(lm_resid-460)²/30²) → penalize off-target',
    fontsize=10.5, fontweight='bold', y=1.01)

plt.savefig('new_loss_proposal.png', dpi=150, bbox_inches='tight')
print('saved: new_loss_proposal.png')
