"""
합성 조건 유사 / 다른 Zone 쌍 탐색 — In_rate/P_rate 비율 기준
비교 변수: preHeat_T, Heat_T, In/P_ratio (In_rate / P_rate)
"""
import sys, os, numpy as np, pandas as pd, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()
KEYS = df.iloc[0:4, 0].tolist()   # preHeat_T, Heat_T, In_rate, P_rate
TARGET_LM = 460.0
PTS = 20000 / 600.0

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
records=[]
for col in range(1,df.shape[1]):
    ks=df.iloc[0:4,0].values; vs=df.iloc[0:4,col].values
    if pd.isnull(ks).any() or pd.isnull(vs).any(): continue
    if col>152: break
    cond=dict(zip(KEYS,vs.astype(float)))
    rs=np.array(df.iloc[4:,col].astype(float).tolist())
    wl=np.array(wavelength)
    x,ys,bg,rd,lm,pv,yn=preprocess(wl,rs)
    in_rate  = cond[KEYS[2]]
    p_rate   = cond[KEYS[3]]
    ip_ratio = in_rate / max(p_rate, 1.0)   # In/P 비율
    if lm>0 and pv>0: zone='A'
    elif yn<=Y[0]: zone='B'
    elif yn<=Y[1]: zone='C'
    elif yn<=Y[2]: zone='D'
    elif yn<=Y[3]: zone='E'
    else: zone='F'
    records.append(dict(sample=col, zone=zone, yn=yn, lm=lm, pv=pv,
                        wl=wl, rs=rs, x=x, ys=ys, bg=bg, rd=rd,
                        ip_ratio=ip_ratio, **cond))

# B~F만 대상
recs_bf = [r for r in records if r['zone'] in 'BCDEF']

# 비교 변수: preHeat_T, Heat_T, In/P_ratio
# 정규화 후 유클리드 거리
def get_vec(r):
    return np.array([r[KEYS[0]], r[KEYS[1]], r['ip_ratio']])

vecs = np.array([get_vec(r) for r in recs_bf], dtype=float)
vmin, vmax = vecs.min(0), vecs.max(0)
vrange = np.where(vmax-vmin > 0, vmax-vmin, 1.0)
vecs_n = (vecs - vmin) / vrange

# 모든 이종 zone 쌍
pairs=[]
n=len(recs_bf)
for i in range(n):
    for j in range(i+1,n):
        if recs_bf[i]['zone']==recs_bf[j]['zone']: continue
        dist=float(np.linalg.norm(vecs_n[i]-vecs_n[j]))
        pairs.append((dist,i,j))
pairs.sort()

# ── 상위 30쌍 출력 ─────────────────────────────────────────────────────────
print("합성 조건 유사 / 다른 Zone 쌍  (비교: preHeat_T, Heat_T, In/P_ratio)")
print("="*95)
print(" Rank| Dist | Si(Zi) Sj(Zj) | preH_i preH_j | Heat_i Heat_j | InP_i  InP_j  | In_i  P_i   In_j  P_j  | yn_i   yn_j")
print("-"*95)
seen=set(); rank=0
for dist,i,j in pairs:
    ri,rj=recs_bf[i],recs_bf[j]
    key=(min(ri['sample'],rj['sample']),max(ri['sample'],rj['sample']))
    if key in seen: continue
    seen.add(key); rank+=1
    if rank>30: break
    print("%4d|%.4f|%3d(%s) %3d(%s)|  %4.0f  %4.0f |  %5.0f  %5.0f| %6.2f %6.2f|%4.0f %4.0f  %4.0f %4.0f| %.3f  %.3f" % (
        rank,dist,
        ri['sample'],ri['zone'],rj['sample'],rj['zone'],
        ri[KEYS[0]],rj[KEYS[0]],
        ri[KEYS[1]],rj[KEYS[1]],
        ri['ip_ratio'],rj['ip_ratio'],
        ri[KEYS[2]],ri[KEYS[3]],rj[KEYS[2]],rj[KEYS[3]],
        ri['yn'],rj['yn']))

# ── 흥미로운 쌍 선정 (zone 차이 큰 것 우선) ──────────────────────────────
interesting=[]
seen2=set()
# 1순위: zdiff >= 2
for dist,i,j in pairs:
    ri,rj=recs_bf[i],recs_bf[j]
    key=(min(ri['sample'],rj['sample']),max(ri['sample'],rj['sample']))
    if key in seen2: continue
    if abs(ord(ri['zone'])-ord(rj['zone']))>=2:
        seen2.add(key); interesting.append((dist,ri,rj))
    if len(interesting)>=8: break
# 2순위: zdiff == 1
for dist,i,j in pairs:
    ri,rj=recs_bf[i],recs_bf[j]
    key=(min(ri['sample'],rj['sample']),max(ri['sample'],rj['sample']))
    if key in seen2: continue
    seen2.add(key); interesting.append((dist,ri,rj))
    if len(interesting)>=10: break

os.makedirs('fig',exist_ok=True)
with open('fig/similar_cross_zone2.pkl','wb') as f:
    pickle.dump(interesting,f)
with open('fig/all_records.pkl','wb') as f:
    pickle.dump(records,f)
print("\nPickle saved: fig/similar_cross_zone2.pkl  (%d pairs)" % len(interesting))
print("Pickle saved: fig/all_records.pkl  (%d records)" % len(records))

# In/P ratio 분포 출력
print("\n=== In/P ratio 분포 per zone ===")
for z in 'BCDEF':
    sub=[r for r in recs_bf if r['zone']==z]
    if not sub: continue
    ratios=np.array([r['ip_ratio'] for r in sub])
    print("Zone %s (%2d): ratio mean=%.2f std=%.2f  min=%.2f max=%.2f" % (
        z,len(sub),ratios.mean(),ratios.std(),ratios.min(),ratios.max()))
