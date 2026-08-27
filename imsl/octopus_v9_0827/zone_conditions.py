import sys, numpy as np, pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

PATH = '2508optimize/spectra_with_params_0407.csv'
df = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()
TARGET_LM = 460.0
PTS = 20000 / 600.0
KEYS = df.iloc[0:4, 0].tolist()

def preprocess(wl_raw, rs_raw):
    order = np.argsort(wl_raw)
    x = np.linspace(350, 950, 20000)
    ys = gaussian_filter1d(np.interp(x, wl_raw[order], rs_raw[order]), sigma=3.0*PTS)
    def fbg(lo, hi, nm=6):
        m = (x>=lo)&(x<=hi); xb, yb = x[m], np.maximum(ys[m], 1e-9); ref = float(xb[0])
        def pl(l, a, n): return a*(ref/l)**n
        try:
            p, _ = curve_fit(pl, xb, yb, p0=[yb[0], 2], bounds=([0,.3],[20,nm]), maxfev=3000)
            return np.maximum(pl(x, *p), 0), float(yb.mean())
        except: return None, 0.0
    bg, bm = fbg(560, 700)
    if bg is None or bm < 0.002: bg, bm = fbg(520, 640)
    if bg is None or bm < 0.002: bg, _ = fbg(420, 510, 4)
    if bg is None: bg = np.interp(x, [x[0], x[-1]], [ys[0], ys[-1]])
    rd = np.maximum(ys - bg, 0)
    pm = (x>=420)&(x<=510)
    pi, pr = find_peaks(rd[pm], prominence=0.007)
    lm, pv = 0.0, 0.0
    if len(pi) > 0:
        wpk = x[pm]; bi = pi[int(np.argmax(pr['prominences']))]; lr = float(wpk[bi])
        wn = (x>=lr-40)&(x<=lr+40)
        def g(l,a,c,s): return a*np.exp(-0.5*((l-c)/s)**2)
        try:
            po, _ = curve_fit(g, x[wn], rd[wn], p0=[rd[wn].max(), lr, 15],
                              bounds=([0,lr-25,5],[2,lr+25,60]), maxfev=2000)
            _, cf, sf = po; lm = float(np.clip(cf, 420, 510))
            yp = g(x[wn], *po)
            r2 = 1 - np.sum((rd[wn]-yp)**2) / max(np.sum((rd[wn]-rd[wn].mean())**2), 1e-12)
            neg, _ = find_peaks(-ys[pm], prominence=0.001)
            hv = any(x[pm][v] < lm for v in neg)
            prom = float(pr['prominences'][int(np.argmax(pr['prominences']))])
            if not (r2>0.85 and prom>0.010 and sf>=8 and (hv or sf<20)):
                lm = 0.0
            else:
                il = int(np.argmin(np.abs(x-lm))); pa = float(ys[il])
                vr = (x>=lm-60)&(x<=lm-10)
                va = float(ys[vr].min()) if vr.sum()>0 else float(ys[pm][0])
                bm2 = (x>=540)&(x<=560); ba = float(ys[bm2].mean())
                d = va - ba
                if d > 0:
                    pv = (pa - ba) / d
                    if pv <= 0: lm, pv = 0.0, 0.0
        except: lm = 0.0
    i4 = int(np.argmin(np.abs(x-420))); it = int(np.argmin(np.abs(x-TARGET_LM))); i5 = int(np.argmin(np.abs(x-550)))
    a4, at, a5 = ys[i4], ys[it], ys[i5]; dn = a4 - a5
    yn = float(np.clip((at-a5)/dn, 0, 1)) if dn>0 and a4>0 else 0.0
    return lm, pv, yn

Y = [0.35, 0.45, 0.55, 0.65]
zones = {z: [] for z in 'ABCDEF'}

for col in range(1, df.shape[1]):
    ks = df.iloc[0:4, 0].values; vs = df.iloc[0:4, col].values
    if pd.isnull(ks).any() or pd.isnull(vs).any(): continue
    if col > 152: break
    cond = dict(zip(KEYS, vs.astype(float)))
    rs = np.array(df.iloc[4:, col].astype(float).tolist())
    wl = np.array(wavelength)
    lm, pv, yn = preprocess(wl, rs)
    row = {'sample': col, 'lm': lm, 'pv': pv, 'yn': yn, **cond}
    if lm > 0 and pv > 0:  zones['A'].append(row)
    elif yn <= Y[0]:        zones['B'].append(row)
    elif yn <= Y[1]:        zones['C'].append(row)
    elif yn <= Y[2]:        zones['D'].append(row)
    elif yn <= Y[3]:        zones['E'].append(row)
    else:                   zones['F'].append(row)

K = KEYS
SHORT = ['preHeat_T', 'Heat_T', 'In_rate', 'P_rate']
ZONE_DESC = {
    'A': 'Peak detected  [-0.3~0]',
    'B': 'Steep scatter  [-1.5]',
    'C': 'Rayleigh       [-1.5~-1.2]',
    'D': 'Gradual decay  [-1.2~-0.6]',
    'E': 'QD-like        [-0.6~-0.3]',
    'F': 'Ceiling        [-0.3]',
}

all_rows = []
for z in 'ABCDEF':
    rows = zones[z]
    print()
    print("=" * 72)
    print("Zone %s  %s  (%d samples)" % (z, ZONE_DESC[z], len(rows)))
    print("=" * 72)
    hdr = " Sam | %s | %s | %s | %s | y_norm | lm    | pv" % tuple(SHORT)
    print(hdr)
    print("-" * 72)
    for r in rows:
        line = " %3d | %9.0f | %6.0f | %7.0f | %6.0f | %.4f | %5.1f | %.3f" % (
            r['sample'], r[K[0]], r[K[1]], r[K[2]], r[K[3]], r['yn'], r['lm'], r['pv']
        )
        print(line)
        all_rows.append({'Zone': z, 'Sample': r['sample'],
                         SHORT[0]: r[K[0]], SHORT[1]: r[K[1]],
                         SHORT[2]: r[K[2]], SHORT[3]: r[K[3]],
                         'y_norm': round(r['yn'],4), 'lambdamax': round(r['lm'],1),
                         'pv_ratio': round(r['pv'],3)})

# 통계 요약
print()
print("=" * 72)
print("구간별 합성 조건 통계 (mean +- std)")
print("=" * 72)
summary_df = pd.DataFrame(all_rows)
for z in 'ABCDEF':
    sub = summary_df[summary_df['Zone']==z]
    if sub.empty: continue
    print("Zone %s (%d):" % (z, len(sub)))
    for s in SHORT:
        print("  %s: %.1f +- %.1f  (min=%.0f, max=%.0f)" % (
            s, sub[s].mean(), sub[s].std(), sub[s].min(), sub[s].max()))

# CSV 저장
out = 'fig/zone_conditions.csv'
summary_df.to_csv(out, index=False)
print("\nSaved:", out)
