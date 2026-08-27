import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()
KEYS = df.iloc[0:4, 0].tolist()
TARGET_LM = 460.0
PTS = 20000 / 600.0
TARGETS = [24, 90]

def preprocess(wl_raw, rs_raw):
    order = np.argsort(wl_raw)
    x = np.linspace(350, 950, 20000)
    y_interp = np.interp(x, wl_raw[order], rs_raw[order])
    y_smooth = gaussian_filter1d(y_interp, sigma=3.0 * PTS)

    def fbg(lo, hi, nm=6):
        m = (x >= lo) & (x <= hi)
        xb, yb = x[m], np.maximum(y_smooth[m], 1e-9)
        ref = float(xb[0])
        def pl(l, a, n): return a * (ref / l) ** n
        try:
            p, _ = curve_fit(pl, xb, yb, p0=[yb[0], 2], bounds=([0,.3],[20,nm]), maxfev=3000)
            return np.maximum(pl(x, *p), 0), float(yb.mean())
        except:
            return None, 0.0

    bg, bm = fbg(560, 700)
    if bg is None or bm < 0.002: bg, bm = fbg(520, 640)
    if bg is None or bm < 0.002: bg, _  = fbg(420, 510, 4)
    if bg is None:
        bg = np.interp(x, [x[0], x[-1]], [y_smooth[0], y_smooth[-1]])

    resid = np.maximum(y_smooth - bg, 0)
    pm = (x >= 420) & (x <= 510)
    pi, pr = find_peaks(resid[pm], prominence=0.007)

    lm, pv = 0.0, 0.0
    gauss_fit = None
    peak_info = {}

    if len(pi) > 0:
        wpk = x[pm]
        bi  = pi[int(np.argmax(pr['prominences']))]
        lr  = float(wpk[bi])
        wn  = (x >= lr - 40) & (x <= lr + 40)

        def g(l, a, c, s): return a * np.exp(-0.5 * ((l - c) / s) ** 2)
        try:
            po, _ = curve_fit(g, x[wn], resid[wn],
                              p0=[resid[wn].max(), lr, 15],
                              bounds=([0, lr-25, 5], [2, lr+25, 60]), maxfev=2000)
            amp_f, cf, sf = po
            lm_cand = float(np.clip(cf, 420, 510))
            yp  = g(x[wn], *po)
            ss_res = float(np.sum((resid[wn] - yp)**2))
            ss_tot = float(np.sum((resid[wn] - resid[wn].mean())**2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            neg, _ = find_peaks(-y_smooth[pm], prominence=0.001)
            hv = any(x[pm][v] < lm_cand for v in neg)
            prom = float(pr['prominences'][int(np.argmax(pr['prominences']))])

            peak_info = dict(r2=r2, prom=prom, sigma=sf, has_valley=hv,
                             rough_lm=lr, amp=amp_f)

            quality = (r2 > 0.85 and prom > 0.010 and sf >= 8 and (hv or sf < 20))
            peak_info['quality'] = quality

            if quality:
                lm = lm_cand
                il = int(np.argmin(np.abs(x - lm)))
                pa = float(y_smooth[il])
                vr = (x >= lm - 60) & (x <= lm - 10)
                va = float(y_smooth[vr].min()) if vr.sum() > 0 else float(y_smooth[pm][0])
                bm2 = (x >= 540) & (x <= 560)
                ba  = float(y_smooth[bm2].mean())
                d = va - ba
                if d > 0:
                    pv = (pa - ba) / d
                    if pv <= 0: lm, pv = 0.0, 0.0
                peak_info.update(peak_ab=pa, valley_ab=va, base_ab=ba)
                gauss_fit = (po, x[wn], g(x[wn], *po))
        except:
            pass

    # y_norm
    i4 = int(np.argmin(np.abs(x - 420)))
    it = int(np.argmin(np.abs(x - TARGET_LM)))
    i5 = int(np.argmin(np.abs(x - 550)))
    a4, at, a5 = y_smooth[i4], y_smooth[it], y_smooth[i5]
    dn = a4 - a5
    yn = float(np.clip((at - a5) / dn, 0, 1)) if dn > 0 and a4 > 0 else 0.0

    return x, y_interp, y_smooth, bg, resid, lm, pv, yn, gauss_fit, peak_info

# ── 데이터 수집 ─────────────────────────────────────────────────────────────
samples = {}
for col in range(1, df.shape[1]):
    if col not in TARGETS: continue
    ks = df.iloc[0:4, 0].values; vs = df.iloc[0:4, col].values
    if pd.isnull(ks).any() or pd.isnull(vs).any(): continue
    cond = dict(zip(KEYS, vs.astype(float)))
    rs = np.array(df.iloc[4:, col].astype(float).tolist())
    wl = np.array(wavelength)
    result = preprocess(wl, rs)
    samples[col] = dict(wl=wl, rs=rs, cond=cond, result=result)

# ── 플롯 ────────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 14))
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.32,
                        top=0.93, bottom=0.07, left=0.07, right=0.97)

ZONE_INFO = {24: ('E', '#1f77b4', '[-0.6~-0.3]'), 90: ('F', '#17becf', '[-0.3]')}

for idx, snum in enumerate(TARGETS):
    d = samples[snum]
    x, y_raw, ys, bg, rd, lm, pv, yn, gfit, pinfo = d['result']
    cond = d['cond']
    zone, col, loss_range = ZONE_INFO[snum]

    xm = (x >= 350) & (x <= 750)   # 표시 구간

    # ── 상단: 전체 스펙트럼 (raw + smooth + bg + residual) ─────────────────
    ax1 = fig.add_subplot(gs[0, idx])

    ax1.plot(x[xm], y_raw[xm],  color='lightgray', lw=1.0, alpha=0.9, label='Raw (interp)')
    ax1.plot(x[xm], ys[xm],     color=col,          lw=2.0, label='Gaussian smooth (σ=3nm)')
    ax1.plot(x[xm], bg[xm],     color='saddlebrown', lw=1.4, ls='--', alpha=0.8, label='Power-law background')
    ax1.fill_between(x[xm], 0, rd[xm], color='green', alpha=0.25, label='Residual (smooth − bg)')

    # 420 / target / 550 마커
    for wl_pt, mk, mc, lab in [
        (420,        'o', 'navy',   'A(420)'),
        (TARGET_LM,  's', 'red',    f'A({int(TARGET_LM)})'),
        (550,        '^', 'olive',  'A(550)'),
    ]:
        ii = int(np.argmin(np.abs(x - wl_pt)))
        ax1.plot(x[ii], ys[ii], marker=mk, ms=8, color=mc, zorder=7, label=lab)

    # 피크 검출 성공 시 마커
    if lm > 0:
        il = int(np.argmin(np.abs(x - lm)))
        ax1.plot(x[il], ys[il], '*', ms=16, color='gold',
                 markeredgecolor='green', markeredgewidth=1.2, zorder=8, label=f'λmax={lm:.1f}nm')
        ax1.axvline(lm, color='green', lw=1.0, ls=':', alpha=0.8)

    # Peak search zone 표시
    ax1.axvspan(420, 510, color='yellow', alpha=0.10, label='Peak search (420–510nm)')

    # y_norm 화살표
    i4  = int(np.argmin(np.abs(x - 420)))
    it  = int(np.argmin(np.abs(x - TARGET_LM)))
    i5  = int(np.argmin(np.abs(x - 550)))
    a4, at, a5 = float(ys[i4]), float(ys[it]), float(ys[i5])
    xv = TARGET_LM + 15
    ax1.annotate('', xy=(xv, a5), xytext=(xv, a4),
                 arrowprops=dict(arrowstyle='<->', color='purple', lw=1.5))
    ax1.annotate('', xy=(xv+10, a5), xytext=(xv+10, at),
                 arrowprops=dict(arrowstyle='<->', color='crimson', lw=2.0))
    ax1.text(xv+14, (a4+a5)/2 - 0.01, '분모\nA420−A550', fontsize=7.5, color='purple', va='center')
    ax1.text(xv+14, (at+a5)/2,          '분자\nA460−A550', fontsize=7.5, color='crimson', va='center')

    ymax = float(ys[xm].max()) * 1.18
    ax1.set_xlim(350, 750); ax1.set_ylim(0, max(ymax, 0.05))
    ax1.set_xlabel('Wavelength (nm)', fontsize=11)
    ax1.set_ylabel('Absorbance', fontsize=11)

    cond_str = ('preHeat_T=%.0f°C  Heat_T=%.0f°C\nIn_rate=%.0f  P_rate=%.0f' %
                (cond[KEYS[0]], cond[KEYS[1]], cond[KEYS[2]], cond[KEYS[3]]))
    ax1.set_title('Sample_%d   Zone %s %s\n%s' % (snum, zone, loss_range, cond_str),
                  fontsize=11, fontweight='bold', color=col)
    ax1.legend(fontsize=8, loc='upper right', ncol=2)

    # y_norm / loss 정보 박스
    loss_map = dict(E=-0.6 + 0.3*(yn-0.55)/0.10, F=-0.3)
    if zone == 'E':
        t = (yn - 0.55) / (0.65 - 0.55)
        loss_val = -0.6 + (-0.3 - (-0.6)) * t
    else:
        loss_val = -0.3

    info_txt = ('y_norm = %.4f\n'
                'λmax   = %.1f nm\n'
                'pv     = %.3f\n'
                'loss   = %.4f') % (yn, lm, pv, loss_val)
    ax1.text(0.02, 0.98, info_txt, transform=ax1.transAxes, fontsize=9,
             va='top', family='monospace',
             bbox=dict(boxstyle='round,pad=0.4', fc='white', alpha=0.92))

    # ── 하단: 420~550nm 확대 + 잔류 피크 상세 ─────────────────────────────
    ax2 = fig.add_subplot(gs[1, idx])

    xz = (x >= 400) & (x <= 560)
    ax2.plot(x[xz], ys[xz],  color=col,          lw=2.0, label='Gaussian smooth')
    ax2.plot(x[xz], bg[xz],  color='saddlebrown', lw=1.4, ls='--', alpha=0.8, label='Background')
    ax2.fill_between(x[xz], 0, rd[xz], color='green', alpha=0.30, label='Residual')
    ax2.axvspan(420, 510, color='yellow', alpha=0.12, label='Peak search zone')

    # Gaussian fit 곡선
    if gfit is not None:
        po_fit, x_fit, y_fit = gfit
        xfm = (x_fit >= 400) & (x_fit <= 560)
        ax2.plot(x_fit[xfm], y_fit[xfm], color='red', lw=2.0, ls='-.',
                 label='Gaussian fit (R²=%.3f)' % pinfo.get('r2', 0))
        ax2.axvline(po_fit[1], color='red', lw=1.0, ls=':', alpha=0.7)
        ax2.text(po_fit[1]+2, y_fit.max()*0.5,
                 'ctr=%.1f\nσ=%.1f' % (po_fit[1], po_fit[2]),
                 fontsize=8, color='red')

    # valley / base 표시 (pv_ratio)
    if lm > 0 and 'peak_ab' in pinfo:
        il = int(np.argmin(np.abs(x - lm)))
        ax2.plot(x[il], pinfo['peak_ab'], 'g^', ms=10, zorder=7, label='Peak')
        # valley 위치 탐색
        vr = (x >= lm - 60) & (x <= lm - 10)
        vi = int(np.argmin(ys[vr]))
        xv_pt = x[vr][vi]
        ax2.plot(xv_pt, pinfo['valley_ab'], 'rv', ms=10, zorder=7, label='Valley')
        bm2 = (x >= 540) & (x <= 560)
        ax2.axhline(pinfo['base_ab'], color='gray', lw=1.0, ls='--', alpha=0.8, label='Base (540~560nm)')

    ax2.set_xlim(400, 560)
    ymax2 = float(ys[xz].max()) * 1.20
    ax2.set_ylim(0, max(ymax2, 0.03))
    ax2.set_xlabel('Wavelength (nm)', fontsize=11)
    ax2.set_ylabel('Absorbance', fontsize=11)
    ax2.set_title('420–560nm 확대  |  잔류 피크 상세', fontsize=11, fontweight='bold')
    ax2.legend(fontsize=8, loc='upper right')

    # 품질 판정 정보
    if pinfo:
        qlines = [
            'R²        = %.3f  (>0.85 ?)  %s' % (pinfo.get('r2',0),   'OK' if pinfo.get('r2',0)>0.85   else 'FAIL'),
            'Prom      = %.4f (>0.010?)  %s' % (pinfo.get('prom',0), 'OK' if pinfo.get('prom',0)>0.010 else 'FAIL'),
            'sigma     = %.1f nm (>=8?) %s' % (pinfo.get('sigma',0), 'OK' if pinfo.get('sigma',0)>=8   else 'FAIL'),
            'has_valley= %s' % str(pinfo.get('has_valley', 'N/A')),
            '=> Quality: %s' % ('PASS' if pinfo.get('quality') else 'FAIL'),
        ]
        qtxt = '\n'.join(qlines)
    else:
        qtxt = 'No peak candidate found\n(prominence < 0.007)'
    ax2.text(0.02, 0.98, qtxt, transform=ax2.transAxes, fontsize=8,
             va='top', family='monospace',
             bbox=dict(boxstyle='round,pad=0.4', fc='#f8f8f8', alpha=0.95))

fig.suptitle('Sample 24 (Zone E) vs Sample 90 (Zone F)  —  _preprocess_spectrum 가공 결과',
             fontsize=13, fontweight='bold')

out = 'fig/sample_24_90_detail.png'
os.makedirs('fig', exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight')
print('Saved:', out)
