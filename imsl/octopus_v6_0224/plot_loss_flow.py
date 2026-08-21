import pandas as pd, numpy as np, sys, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
sys.path.insert(0, '.')

from Analysis.AnalysisUV_poly import (smooth_Boxcar, getSliceSpectrum,
    selective_noise_correction, smooth_polyfit, analysisPickVelly)

def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    wl = df.iloc[4:, 0].astype(float).tolist()
    return {f'Sample_{c}': {'Wavelength': wl, 'RawSpectrum': df.iloc[4:, c].astype(float).tolist()}
            for c in range(1, df.shape[1])}

data_dict = load_multisample_csv('2508optimize/spectra_with_params_0407.csv')

results = {}
for sid in ['1', '8']:
    uv = data_dict[f'Sample_{sid}']
    wl_raw = np.array(uv['Wavelength'])
    rs_raw = np.array(uv['RawSpectrum'])
    order  = np.argsort(wl_raw)
    x_full = np.linspace(350., 950., 20000)
    y_interp = np.interp(x_full, wl_raw[order], rs_raw[order])
    raw = np.array([x_full, y_interp])

    sm  = smooth_Boxcar(rawSpectrum=raw, box_size=250)
    sl  = getSliceSpectrum(rawSpectrum=sm, min_wl=360, max_wl=700)
    sg  = selective_noise_correction(sl, noise_range=(360, 700), window_length=51, polyorder=3)
    pwl, pab = smooth_polyfit(sg[0], sg[1], degree=19)
    sl2 = getSliceSpectrum(rawSpectrum=(pwl, pab), min_wl=420, max_wl=550)
    pv_ratio, lambdamax = analysisPickVelly(rawSpectrum=sl2, prominence=0.0005, width_threshold=8)

    xsm = sm[0]; ysm = sm[1]
    ab_420 = float(ysm[np.argmin(np.abs(xsm - 420.))])
    ab_460 = float(ysm[np.argmin(np.abs(xsm - 460.))])
    ab_550 = float(ysm[np.argmin(np.abs(xsm - 550.))])
    denom  = ab_420 - ab_550
    y_norm = float(np.clip((ab_460 - ab_550) / denom, 0., 1.)) if denom > 0 else 0.

    Y = [0.35, 0.45, 0.55, 0.65]
    L = [-1.5,  -1.2, -0.6, -0.3]
    if   y_norm <= Y[0]: loss = L[0]
    elif y_norm <= Y[1]: t=(y_norm-Y[0])/(Y[1]-Y[0]); loss=L[0]+(L[1]-L[0])*t
    elif y_norm <= Y[2]: t=(y_norm-Y[1])/(Y[2]-Y[1]); loss=L[1]+(L[2]-L[1])*t
    elif y_norm <= Y[3]: t=(y_norm-Y[2])/(Y[3]-Y[2]); loss=L[2]+(L[3]-L[2])*t
    else:                loss = L[3]

    results[sid] = dict(
        x=x_full, y_raw=y_interp, sm=sm, sl=sl, sg=sg,
        pwl=pwl, pab=pab, sl2=sl2,
        lambdamax=lambdamax, pv_ratio=pv_ratio,
        ab_420=ab_420, ab_460=ab_460, ab_550=ab_550,
        denom=denom, y_norm=y_norm, loss=loss,
        xsm=xsm, ysm=ysm
    )
    print(f'S{sid}: lm={lambdamax:.2f} pv={pv_ratio:.4f} | ab420={ab_420:.5f} ab460={ab_460:.5f} ab550={ab_550:.5f}')
    print(f'       denom={denom:.5f} y_norm={y_norm:.4f} loss={loss:.4f}')

fig = plt.figure(figsize=(18, 9))
gs  = gridspec.GridSpec(2, 4, figure=fig, hspace=0.55, wspace=0.38)

COLORS = dict(raw='#aaaaaa', box='#4c72b0', sg='#2196f3',
              poly='#1a8c2e', peak='#c44e52')
XLIM = (350, 700)

for row, sid in enumerate(['1', '8']):
    r = results[sid]
    label = f'Sample {sid}'

    # col 0: Raw + Boxcar
    ax0 = fig.add_subplot(gs[row, 0])
    m = (r['x'] >= 350) & (r['x'] <= 700)
    ax0.plot(r['x'][m],  r['y_raw'][m], color=COLORS['raw'], lw=0.8, alpha=0.7, label='Raw')
    ax0.plot(r['xsm'][m], r['ysm'][m],  color=COLORS['box'], lw=1.6, label='Boxcar (box=250)')
    ax0.axvline(420, color='grey', lw=0.7, ls=':')
    ax0.axvline(550, color='grey', lw=0.7, ls=':')
    ax0.set_xlim(XLIM); ax0.set_ylim(bottom=0)
    ax0.set_xlabel('Wavelength (nm)', fontsize=8)
    ax0.set_ylabel('Absorbance', fontsize=8)
    ax0.set_title(f'[{label}]  Step 1-2\nBoxcar smooth  (box=250, ~7.5nm)', fontsize=8.5, fontweight='bold')
    ax0.legend(fontsize=7, loc='upper right')
    ax0.tick_params(labelsize=7)

    # col 1: SavGol + Polyfit
    ax1 = fig.add_subplot(gs[row, 1])
    mp  = (r['pwl'] >= 360) & (r['pwl'] <= 700)
    ax1.plot(r['sg'][0], r['sg'][1], color=COLORS['sg'], lw=1.0, alpha=0.6, label='SavGol (w=51)')
    ax1.plot(r['pwl'][mp], r['pab'][mp], color=COLORS['poly'], lw=1.8, ls='--', label='Poly fit (deg=19)')
    ax1.axvspan(420, 550, alpha=0.10, color='green')
    ax1.axvline(420, color='green', lw=0.8, ls=':')
    ax1.axvline(550, color='green', lw=0.8, ls=':')
    ax1.set_xlim(XLIM); ax1.set_ylim(bottom=0)
    ax1.set_xlabel('Wavelength (nm)', fontsize=8)
    ax1.set_ylabel('Absorbance', fontsize=8)
    ax1.set_title(f'[{label}]  Step 3-5\nSavGol + Polyfit + Slice 420-550nm', fontsize=8.5, fontweight='bold')
    ax1.legend(fontsize=7, loc='upper right')
    ax1.tick_params(labelsize=7)
    ax1.text(485, ax1.get_ylim()[1] * 0.08, 'peak search\n420-550nm',
             fontsize=7, color='green', ha='center')

    sl2_y = r['sl2'][1]
    is_mono = bool(np.all(np.diff(sl2_y) <= 0))
    mono_txt = 'Monotone decreasing\n-> No peak  (lm=0, pv=0)' if is_mono else 'Peak detected!'
    ax1.text(485, ax1.get_ylim()[1] * 0.45, mono_txt, fontsize=7.5, color='#c00',
             ha='center', bbox=dict(boxstyle='round,pad=0.3', fc='#ffeeee', alpha=0.9))

    # col 2: y_norm 계산
    ax2 = fig.add_subplot(gs[row, 2])
    xsm = r['xsm']; ysm = r['ysm']
    m2  = (xsm >= 350) & (xsm <= 700)
    ax2.plot(xsm[m2], ysm[m2], color=COLORS['box'], lw=1.6, label='Boxcar smooth')
    ax2.set_xlim(XLIM); ax2.set_ylim(bottom=0)

    pt_cfg = [
        (420, r['ab_420'], '#1a8c2e', 'ab_420'),
        (460, r['ab_460'], '#c44e52', 'ab_460'),
        (550, r['ab_550'], '#8172b3', 'ab_550'),
    ]
    ymax = ysm[m2].max()
    for wl_pt, ab_pt, col, key in pt_cfg:
        ax2.axvline(wl_pt, color=col, lw=1.0, ls='--', alpha=0.7)
        ax2.scatter([wl_pt], [ab_pt], color=col, s=50, zorder=5)
        offset_x = 18 if wl_pt < 500 else -70
        ax2.annotate(f'{key}={ab_pt:.4f}',
                     xy=(wl_pt, ab_pt),
                     xytext=(wl_pt + offset_x, ab_pt + ymax * 0.12),
                     fontsize=6.5, color=col,
                     arrowprops=dict(arrowstyle='->', color=col, lw=0.8))

    yn = r['y_norm']
    formula = (
        f'y_norm = (ab_460 - ab_550) / (ab_420 - ab_550)\n'
        f'       = ({r["ab_460"]:.4f} - {r["ab_550"]:.4f})'
        f' / ({r["ab_420"]:.4f} - {r["ab_550"]:.4f})\n'
        f'       = {r["ab_460"]-r["ab_550"]:.4f} / {r["denom"]:.4f}  =  {yn:.4f}'
    )
    ax2.text(0.5, 0.97, formula, transform=ax2.transAxes,
             va='top', ha='center', fontsize=7, family='monospace',
             bbox=dict(boxstyle='round,pad=0.4', fc='#f0f4ff', alpha=0.95))
    ax2.set_xlabel('Wavelength (nm)', fontsize=8)
    ax2.set_ylabel('Absorbance', fontsize=8)
    ax2.set_title(f'[{label}]  Step 6\ny_norm calculation  (no peak -> fallback)',
                  fontsize=8.5, fontweight='bold')
    ax2.legend(fontsize=7, loc='upper right')
    ax2.tick_params(labelsize=7)

    # col 3: y_norm -> loss 구간 매핑
    ax3 = fig.add_subplot(gs[row, 3])
    Y_pts = [0.0,  0.35, 0.45, 0.55, 0.65, 1.0]
    L_pts = [-1.5, -1.5, -1.2, -0.6, -0.3, -0.3]
    ax3.plot(Y_pts, L_pts, color='#333', lw=2.0, zorder=2)

    zone_cfg = [
        (0.0,  0.35, '#ffcccc', 'Rayleigh-steep\nloss=-1.5'),
        (0.35, 0.45, '#ffd9b3', '-1.5 ~ -1.2'),
        (0.45, 0.55, '#fff0b3', '-1.2 ~ -0.6'),
        (0.55, 0.65, '#d4f0d4', '-0.6 ~ -0.3'),
        (0.65, 1.00, '#c8e6c9', 'ceiling\nloss=-0.3'),
    ]
    for x0, x1, fc, lbl in zone_cfg:
        y0 = np.interp(x0, Y_pts, L_pts)
        y1 = np.interp(x1, Y_pts, L_pts)
        ax3.fill_betweenx([min(y0, y1) - 0.02, max(y0, y1) + 0.02],
                          x0, x1, alpha=0.35, color=fc, zorder=1)
        mx = (x0 + x1) / 2
        my = np.interp(mx, Y_pts, L_pts)
        ax3.text(mx, my + 0.05, lbl, ha='center', va='bottom', fontsize=6, color='#555')

    yn  = r['y_norm']
    lss = r['loss']
    ax3.scatter([yn], [lss], color='#c44e52', s=80, zorder=6)
    offset_yn = yn - 0.28
    ax3.annotate(f'{label}\ny_norm={yn:.4f}\nloss={lss:.4f}',
                 xy=(yn, lss), xytext=(offset_yn, lss + 0.28),
                 fontsize=7.5, color='#c44e52', fontweight='bold',
                 arrowprops=dict(arrowstyle='->', color='#c44e52', lw=1.0))
    ax3.axhline(-0.3, color='#2e7d32', lw=0.8, ls=':', alpha=0.6)
    ax3.axhline(-1.5, color='#c62828', lw=0.8, ls=':', alpha=0.6)
    ax3.set_xlim(0, 1); ax3.set_ylim(-1.65, 0.05)
    ax3.set_xlabel('y_norm', fontsize=8)
    ax3.set_ylabel('loss', fontsize=8)
    ax3.set_title(f'[{label}]  Step 7\ny_norm -> loss  (piecewise linear)',
                  fontsize=8.5, fontweight='bold')
    ax3.tick_params(labelsize=7)
    ax3.text(1.02, -0.3,  '-0.3', va='center', fontsize=6.5, color='#2e7d32',
             transform=ax3.get_yaxis_transform())
    ax3.text(1.02, -1.5,  '-1.5', va='center', fontsize=6.5, color='#c62828',
             transform=ax3.get_yaxis_transform())

flow_txt = ('CSV Pipeline Loss Flow:  '
            'Raw  ->  Boxcar smooth  ->  SavGol + Polyfit  ->  '
            'analysisPickVelly  ->  [No peak]  ->  y_norm calc  ->  piecewise loss')
fig.text(0.5, 0.995, flow_txt, ha='center', va='top', fontsize=9, color='#333',
         bbox=dict(boxstyle='round,pad=0.3', fc='#e8eaf6', alpha=0.9))

plt.savefig('csv_loss_flow.png', dpi=150, bbox_inches='tight')
print('saved: csv_loss_flow.png')
