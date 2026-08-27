import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
KEYS = df.iloc[0:4, 0].tolist()
TARGET_LM, PTS = 460.0, 20000/600.0

def preprocess(wl_raw, rs_raw):
    order = np.argsort(wl_raw)
    x = np.linspace(350, 950, 20000)
    ys = gaussian_filter1d(np.interp(x, wl_raw[order], rs_raw[order]), sigma=3.0*PTS)
    def fbg(lo,hi,nm=6):
        m=(x>=lo)&(x<=hi); xb,yb=x[m],np.maximum(ys[m],1e-9); ref=float(xb[0])
        def pl(l,a,n): return a*(ref/l)**n
        try:
            p,_=curve_fit(pl,xb,yb,p0=[yb[0],2],bounds=([0,.3],[20,nm]),maxfev=3000)
            return np.maximum(pl(x,*p),0),float(yb.mean())
        except: return None,0.0
    bg,bm=fbg(560,700)
    if bg is None or bm<0.002: bg,bm=fbg(520,640)
    if bg is None or bm<0.002: bg,_=fbg(420,510,4)
    if bg is None: bg=np.interp(x,[x[0],x[-1]],[ys[0],ys[-1]])
    rd=np.maximum(ys-bg,0)
    pm=(x>=420)&(x<=510); pi,pr=find_peaks(rd[pm],prominence=0.007)
    lm,pv=0.0,0.0
    if len(pi)>0:
        wpk=x[pm]; bi=pi[int(np.argmax(pr['prominences']))]; lr=float(wpk[bi])
        wn=(x>=lr-40)&(x<=lr+40)
        def g(l,a,c,s): return a*np.exp(-0.5*((l-c)/s)**2)
        try:
            po,_=curve_fit(g,x[wn],rd[wn],p0=[rd[wn].max(),lr,15],
                           bounds=([0,lr-25,5],[2,lr+25,60]),maxfev=2000)
            _,cf,sf=po; lm=float(np.clip(cf,420,510))
            yp=g(x[wn],*po)
            r2=1-np.sum((rd[wn]-yp)**2)/max(np.sum((rd[wn]-rd[wn].mean())**2),1e-12)
            neg,_=find_peaks(-ys[pm],prominence=0.001)
            hv=any(x[pm][v]<lm for v in neg)
            prom=float(pr['prominences'][int(np.argmax(pr['prominences']))])
            if not(r2>0.85 and prom>0.010 and sf>=8 and (hv or sf<20)): lm=0.0
            else:
                il=int(np.argmin(np.abs(x-lm))); pa=float(ys[il])
                vr=(x>=lm-60)&(x<=lm-10)
                va=float(ys[vr].min()) if vr.sum()>0 else float(ys[pm][0])
                bm2=(x>=540)&(x<=560); ba=float(ys[bm2].mean())
                d=va-ba
                if d>0: pv=(pa-ba)/d
                if pv<=0: lm,pv=0.0,0.0
        except: lm=0.0
    i4=int(np.argmin(np.abs(x-420))); it=int(np.argmin(np.abs(x-TARGET_LM))); i5=int(np.argmin(np.abs(x-550)))
    a4,at,a5=ys[i4],ys[it],ys[i5]; dn=a4-a5
    yn=float(np.clip((at-a5)/dn,0,1)) if dn>0 and a4>0 else 0.0
    return x,ys,bg,rd,lm,pv,yn

Y=[0.35,0.45,0.55,0.65]
wavelength=df.iloc[4:,0].astype(float).tolist()

results=[]
for col in range(1, df.shape[1]):
    vs=df.iloc[0:4,col].values
    if pd.isnull(vs).any(): continue
    sp=df.iloc[4:,col].astype(float).values
    if np.isnan(sp).any(): continue
    wl=np.array(wavelength); rs=np.array(sp)
    has_neg = bool(np.any(rs < -0.01))
    noise_std = float(np.std(np.diff(rs)))
    x,ys,bg,rd,lm,pv,yn=preprocess(wl,rs)
    if lm>0 and pv>0: zone='A'
    elif yn<=Y[0]: zone='B'
    elif yn<=Y[1]: zone='C'
    elif yn<=Y[2]: zone='D'
    elif yn<=Y[3]: zone='E'
    else: zone='F'
    cond=dict(zip(KEYS,vs.astype(float)))
    results.append(dict(sample=col,zone=zone,yn=yn,lm=lm,pv=pv,
                        has_neg=has_neg,noise_std=noise_std,
                        total_flow=cond[KEYS[2]]+cond[KEYS[3]],
                        heat_t=cond[KEYS[1]],**cond))

print("=== Good samples (has_neg=False, noise_std<0.15) per Zone ===\n")
THRESH = 0.15
for zone in 'ABCDEF':
    good = [r for r in results
            if r['zone']==zone and not r['has_neg'] and r['noise_std']<THRESH]
    good.sort(key=lambda r: r['noise_std'])
    picks = good[:2]
    print("Zone %s  good=%d" % (zone, len(good)))
    for r in picks:
        print("  S%-3d | yn=%.3f | noise=%.4f | flow=%4g | Heat_T=%g | In=%g P=%g" % (
            r['sample'],r['yn'],r['noise_std'],r['total_flow'],
            r['heat_t'],r[KEYS[2]],r[KEYS[3]]))
    if not picks:
        # 기준 완화 — noise_std < 0.25
        good2=[r for r in results if r['zone']==zone and not r['has_neg'] and r['noise_std']<0.25]
        good2.sort(key=lambda r: r['noise_std'])
        print("  (relaxed noise<0.25):")
        for r in good2[:2]:
            print("  S%-3d | yn=%.3f | noise=%.4f | flow=%4g | Heat_T=%g | In=%g P=%g" % (
                r['sample'],r['yn'],r['noise_std'],r['total_flow'],
                r['heat_t'],r[KEYS[2]],r[KEYS[3]]))
    print()

# 전체 통계
print("=== Stats per zone ===")
for zone in 'ABCDEF':
    all_z=[r for r in results if r['zone']==zone]
    good=[r for r in all_z if not r['has_neg'] and r['noise_std']<0.15]
    print("Zone %s: total=%d  good=%d  (%.0f%%)" % (
        zone,len(all_z),len(good),100*len(good)/max(len(all_z),1)))
