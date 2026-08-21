"""
self_bayesian_csv.py 방식으로 CSV 읽은 뒤
새 loss 함수 적용 → 결과 표 출력 + PNG 저장
"""
import numpy as np
import pandas as pd
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, '.')

from Analysis.AnalysisUV_poly import (calculateUV_Data_clean_csv,
                                      smooth_Boxcar, getSliceSpectrum,
                                      selective_noise_correction,
                                      smooth_polyfit)

# ── CSV 로드 ──────────────────────────────────────────────────────
def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    wavelength = df.iloc[4:, 0].astype(float).tolist()
    data_dict, param_dict = {}, {}
    for col in range(1, df.shape[1]):
        name = f'Sample_{col}'
        keys   = df.iloc[0:4, 0].values.astype(str)
        values = df.iloc[0:4, col].values
        param_dict[name] = dict(zip(keys, values))
        data_dict[name]  = {'Wavelength': wavelength,
                             'RawSpectrum': df.iloc[4:, col].astype(float).tolist()}
    return param_dict, data_dict

# ── 기존 peak branch loss ────────────────────────────────────────
def loss_peak_branch(lm, pv, target_lm=460, target_pv=1.3,
                     w_lm=0.1, w_pv=0.9, wl_min=350, wl_max=850):
    scale = max(target_lm - wl_min, 1.) if lm <= target_lm else max(wl_max - target_lm, 1.)
    lm_loss = float(np.clip(abs(target_lm - lm) / scale, 0, 1))
    pv_loss = 0. if pv >= target_pv else float(np.clip((target_pv - pv) / target_pv, 0, 1))
    return -(lm_loss * w_lm + pv_loss * w_pv) * 0.3

# ── 기존 y_norm branch loss ──────────────────────────────────────
def loss_ynorm_branch(xsm, ysm, target_lm=460):
    a420 = float(ysm[np.argmin(np.abs(xsm - 420.))])
    a460 = float(ysm[np.argmin(np.abs(xsm - float(target_lm)))])
    a550 = float(ysm[np.argmin(np.abs(xsm - 550.))])
    d = a420 - a550
    yn = float(np.clip((a460 - a550) / d, 0, 1)) if d > 0 else 0.
    return yn, float(np.interp(yn, [0.,.35,.45,.55,.65,1.], [-1.5,-1.5,-1.2,-0.6,-0.3,-0.3]))

# ── 새 no-peak branch loss ───────────────────────────────────────
def loss_new_branch(xsm, ysm,
                    target_lm=460., bg_lo=570., bg_hi=680.,
                    search_lo=400., search_hi=540.,
                    pos_bw=30., n_max_ref=8., amp_ref=0.050,
                    w_flat=0.40, w_amp_pos=0.60):
    """
    3-component no-peak loss → [-1.5, -0.3]
    flat_score  : power-law n 작을수록 높음 (배경 완만)
    amp_score   : 잔류 피크 진폭 (5nm 스무딩 후)
    pos_score   : 잔류 피크 위치가 target_lm에 가까울수록 높음
    """
    # 1) power-law 배경 피팅 (570–680nm)
    mask_bg = (xsm >= bg_lo) & (xsm <= bg_hi)
    xb = xsm[mask_bg]; yb = np.maximum(ysm[mask_bg], 1e-9)
    ref_wl = float(xb[0]) if len(xb) > 0 else 570.
    try:
        def pl(lx, a, n): return a * (ref_wl / lx) ** n
        p, _ = curve_fit(pl, xb, yb, p0=[float(yb[0]), 3.],
                         bounds=([0., 0.1], [10., 12.]), maxfev=3000)
        bg_full = np.maximum(pl(xsm, *p), 0.)
        n_fit   = float(p[1])
    except Exception:
        bg_full = np.interp(xsm, [xsm[0], xsm[-1]], [ysm[0], ysm[-1]])
        n_fit   = n_max_ref

    # 2) 잔류 (5nm 스무딩으로 노이즈 억제)
    dx_nm    = float(xsm[1] - xsm[0]) if len(xsm) > 1 else 1.
    sigma_pt = max(int(round(5. / dx_nm)), 1)
    ysm_s    = gaussian_filter1d(ysm, sigma=sigma_pt)
    resid    = np.maximum(ysm_s - bg_full, 0.)

    # 3) flat_score
    flat_score = float(np.clip(1. - n_fit / n_max_ref, 0., 1.))

    # 4) 탐색 구간 내 잔류 피크
    mask_s  = (xsm >= search_lo) & (xsm <= search_hi)
    resid_s = resid[mask_s]; xs_s = xsm[mask_s]

    if len(resid_s) > 0 and resid_s.max() > 1e-6:
        pk_idx    = int(np.argmax(resid_s))
        lm_resid  = float(xs_s[pk_idx])
        amp_resid = float(resid_s[pk_idx])
        pos_score = float(np.exp(-0.5 * ((lm_resid - target_lm) / pos_bw) ** 2))
        amp_score = float(np.clip(amp_resid / amp_ref, 0., 1.))
    else:
        lm_resid  = target_lm
        amp_resid = 0.
        pos_score = 0.
        amp_score = 0.

    # 5) combined → loss
    combined  = w_flat * flat_score + w_amp_pos * amp_score * pos_score
    loss_val  = -1.5 + 1.2 * float(np.clip(combined, 0., 1.))
    return (float(np.clip(loss_val, -1.5, -0.3)),
            flat_score, amp_score, pos_score, n_fit, lm_resid)

# ── Boxcar smoothed 스펙트럼 가져오기 ───────────────────────────
def get_boxcar_smooth(wl_list, rs_list):
    wl_raw = np.array(wl_list); rs_raw = np.array(rs_list)
    order  = np.argsort(wl_raw)
    x_full = np.linspace(350., 950., 20000)
    y_int  = np.interp(x_full, wl_raw[order], rs_raw[order])
    raw    = np.array([x_full, y_int])
    sm     = smooth_Boxcar(rawSpectrum=raw, box_size=250)
    return sm[0], sm[1]

# ── 메인 계산 ────────────────────────────────────────────────────
path = '2508optimize/spectra_with_params_0407.csv'
param_dict, data_dict = load_multisample_csv(path)
n_samples = len(data_dict)

rows = []
for j in range(n_samples):
    i    = j + 1
    key  = f'Sample_{i}'
    uv   = data_dict[key]
    wl   = uv['Wavelength']
    ab   = uv['RawSpectrum']

    data_df = pd.DataFrame(ab, index=wl, columns=[key])

    # 기존 방식으로 peak 검출
    pv_ratio, lambdamax = calculateUV_Data_clean_csv(uv_df=data_df)

    # Boxcar smoothed 스펙트럼 (y_norm / new loss용)
    xsm, ysm = get_boxcar_smooth(wl, ab)

    # 기존 y_norm loss
    yn, loss_cur = loss_ynorm_branch(xsm, ysm)

    if lambdamax > 0 and pv_ratio > 0:
        # peak 검출 → peak branch
        loss_old  = loss_peak_branch(lambdamax, pv_ratio)
        loss_new  = loss_old      # peak branch는 동일
        branch    = 'peak'
        flat, amp, pos = None, None, None
        n_fit_val, lm_res = None, None
    else:
        # no-peak → 새 loss
        loss_old = loss_cur
        loss_new, flat, amp, pos, n_fit_val, lm_res = loss_new_branch(xsm, ysm)
        branch   = 'no-peak'

    rows.append({
        'Sample': i,
        'branch': branch,
        'lm_csv': round(lambdamax, 1),
        'pv_csv': round(pv_ratio, 4),
        'y_norm': round(yn, 4),
        'loss_old': round(loss_old, 4),
        'loss_new': round(loss_new, 4),
        'diff': round(loss_new - loss_old, 4),
        'flat':  round(flat, 3)    if flat  is not None else None,
        'amp':   round(amp, 3)     if amp   is not None else None,
        'pos':   round(pos, 3)     if pos   is not None else None,
        'n_fit': round(n_fit_val, 2) if n_fit_val is not None else None,
        'lm_resid': round(lm_res, 1) if lm_res is not None else None,
    })

df_result = pd.DataFrame(rows)

# ── 콘솔 요약 ────────────────────────────────────────────────────
print(f"Total samples: {n_samples}")
print(f"Peak detected : {(df_result['branch']=='peak').sum()}")
print(f"No-peak       : {(df_result['branch']=='no-peak').sum()}")
print()

no_pk = df_result[df_result['branch'] == 'no-peak'].copy()
print(f"No-peak loss_old  mean={no_pk['loss_old'].mean():.4f}  "
      f"min={no_pk['loss_old'].min():.4f}  max={no_pk['loss_old'].max():.4f}")
print(f"No-peak loss_new  mean={no_pk['loss_new'].mean():.4f}  "
      f"min={no_pk['loss_new'].min():.4f}  max={no_pk['loss_new'].max():.4f}")
print()
print(df_result.to_string(index=False))

# CSV 저장
df_result.to_csv('loss_comparison_table.csv', index=False, encoding='utf-8-sig')
print('\nsaved: loss_comparison_table.csv')

# ── 시각화 ───────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 7))

# 1) loss_old vs loss_new scatter
ax = axes[0]
pk  = df_result[df_result['branch'] == 'peak']
npk = df_result[df_result['branch'] == 'no-peak']
ax.scatter(pk['loss_old'],  pk['loss_new'],  color='#4c72b0', s=30,
           alpha=0.7, label=f'Peak detected ({len(pk)})', zorder=4)
ax.scatter(npk['loss_old'], npk['loss_new'], color='#c44e52', s=30,
           alpha=0.7, label=f'No-peak ({len(npk)})', zorder=4)
lim = [-1.55, 0.05]
ax.plot(lim, lim, 'k--', lw=1.0, alpha=0.5, label='y=x (no change)')
ax.fill_between(lim, lim, [0.05, 0.05], alpha=0.06, color='green',
                label='new > old (improved)')
ax.fill_between(lim, [-1.55, -1.55], lim, alpha=0.06, color='red',
                label='new < old (penalized more)')
ax.set_xlim(lim); ax.set_ylim(lim)
ax.set_xlabel('loss_old (current y_norm)', fontsize=9)
ax.set_ylabel('loss_new (proposed)', fontsize=9)
ax.set_title('(A) loss_old vs loss_new\n(red=no-peak, blue=peak)', fontsize=10, fontweight='bold')
ax.legend(fontsize=7.5); ax.tick_params(labelsize=8)

# 2) no-peak 샘플: diff 분포 (히스토그램)
ax2 = axes[1]
diff = npk['diff']
ax2.hist(diff[diff >= 0], bins=20, color='#2e7d32', alpha=0.7, label='new > old (less penalty)')
ax2.hist(diff[diff <  0], bins=20, color='#c62828', alpha=0.7, label='new < old (more penalty)')
ax2.axvline(0, color='k', lw=1.2, ls='--')
ax2.axvline(diff.mean(), color='orange', lw=1.5, ls='-',
            label=f'mean diff={diff.mean():.3f}')
ax2.set_xlabel('loss_new - loss_old', fontsize=9)
ax2.set_ylabel('Count', fontsize=9)
ax2.set_title('(B) No-peak samples: loss difference\n(positive = new loss is higher/better)',
              fontsize=10, fontweight='bold')
ax2.legend(fontsize=8); ax2.tick_params(labelsize=8)

# 3) no-peak: 샘플별 loss 비교 (가로 bar)
ax3 = axes[2]
npk_sorted = npk.sort_values('loss_old')
y_pos = np.arange(len(npk_sorted))
ax3.barh(y_pos, npk_sorted['loss_new'], height=0.4, color='#4c72b0',
         alpha=0.8, label='loss_new', align='center')
ax3.barh(y_pos - 0.4, npk_sorted['loss_old'], height=0.4, color='#dd8452',
         alpha=0.8, label='loss_old', align='center')
ax3.axvline(-0.3,  color='#2e7d32', lw=0.8, ls=':', alpha=0.6)
ax3.axvline(-1.5,  color='#c62828', lw=0.8, ls=':', alpha=0.6)
ax3.set_yticks(y_pos - 0.2)
ax3.set_yticklabels([f"S{int(r)}" for r in npk_sorted['Sample']], fontsize=5.5)
ax3.set_xlabel('loss', fontsize=9)
ax3.set_title(f'(C) No-peak samples ({len(npk_sorted)}개) loss 비교\n'
              f'sorted by loss_old', fontsize=10, fontweight='bold')
ax3.legend(fontsize=8); ax3.tick_params(labelsize=7)

plt.tight_layout()
plt.savefig('loss_comparison_result.png', dpi=150, bbox_inches='tight')
print('saved: loss_comparison_result.png')
