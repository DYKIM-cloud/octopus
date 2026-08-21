"""
합성 조건이 비슷하지만 서로 다른 zone에 속한 샘플 쌍/그룹을 찾는다.
정규화 유클리드 거리로 nearest-neighbor 탐색 후
zone이 다른 쌍을 거리 기준으로 정렬하여 출력.
"""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from scipy.optimize import curve_fit

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
wavelength = df.iloc[4:, 0].astype(float).tolist()
KEYS = df.iloc[0:4, 0].tolist()
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
    if lm>0 and pv>0: zone='A'
    elif yn<=Y[0]: zone='B'
    elif yn<=Y[1]: zone='C'
    elif yn<=Y[2]: zone='D'
    elif yn<=Y[3]: zone='E'
    else: zone='F'
    records.append(dict(sample=col,zone=zone,yn=yn,lm=lm,pv=pv,
                        wl=wl,rs=rs,x=x,ys=ys,bg=bg,rd=rd,
                        **cond))

# B~F만 대상
recs_bf = [r for r in records if r['zone'] in 'BCDEF']

# 합성 조건 행렬 (정규화)
cond_mat = np.array([[r[k] for k in KEYS] for r in recs_bf], dtype=float)
cmin, cmax = cond_mat.min(0), cond_mat.max(0)
crange = np.where(cmax-cmin > 0, cmax-cmin, 1.0)
cond_norm = (cond_mat - cmin) / crange

# 모든 쌍에 대해 거리 계산, zone 다른 쌍만 추출
pairs = []
n = len(recs_bf)
for i in range(n):
    for j in range(i+1, n):
        if recs_bf[i]['zone'] == recs_bf[j]['zone']:
            continue
        dist = float(np.linalg.norm(cond_norm[i] - cond_norm[j]))
        pairs.append((dist, i, j))

pairs.sort()

# 상위 30쌍 출력
print("합성 조건이 유사하지만 다른 zone에 속한 샘플 쌍 (B~F, 거리 기준 상위 30)")
print("="*90)
print(" Rank | Dist  | Sam_i Zone | Sam_j Zone |  preH_i  preH_j |  HeatT_i HeatT_j | InR_i  InR_j | PR_i   PR_j | yn_i   yn_j")
print("-"*90)
seen = set()
rank = 0
for dist, i, j in pairs:
    ri, rj = recs_bf[i], recs_bf[j]
    key = (min(ri['sample'],rj['sample']), max(ri['sample'],rj['sample']))
    if key in seen: continue
    seen.add(key)
    rank += 1
    if rank > 30: break
    print("%4d | %.3f | %3d  (%s)  | %3d  (%s)  |  %4.0f  %4.0f   |  %5.0f  %5.0f   | %4.0f  %4.0f | %4.0f  %4.0f | %.3f  %.3f" % (
        rank, dist,
        ri['sample'], ri['zone'], rj['sample'], rj['zone'],
        ri[KEYS[0]], rj[KEYS[0]],
        ri[KEYS[1]], rj[KEYS[1]],
        ri[KEYS[2]], rj[KEYS[2]],
        ri[KEYS[3]], rj[KEYS[3]],
        ri['yn'], rj['yn']))

# 가장 흥미로운 쌍 저장 (상위 10, 비인접 구간 우선)
interesting = []
seen2 = set()
for dist, i, j in pairs:
    ri, rj = recs_bf[i], recs_bf[j]
    key = (min(ri['sample'],rj['sample']), max(ri['sample'],rj['sample']))
    if key in seen2: continue
    # zone 차이가 2 이상인 것 우선
    zdiff = abs(ord(ri['zone'])-ord(rj['zone']))
    if zdiff >= 2:
        seen2.add(key)
        interesting.append((dist, ri, rj))
    if len(interesting) >= 8: break

# 부족하면 zdiff=1도 추가
for dist, i, j in pairs:
    ri, rj = recs_bf[i], recs_bf[j]
    key = (min(ri['sample'],rj['sample']), max(ri['sample'],rj['sample']))
    if key in seen2: continue
    seen2.add(key)
    interesting.append((dist, ri, rj))
    if len(interesting) >= 10: break

# pickle로 저장해서 플롯 스크립트에서 재사용
import pickle
with open('fig/similar_cross_zone.pkl','wb') as f:
    pickle.dump(interesting, f)
print("\nPickle saved: fig/similar_cross_zone.pkl")
print("Total interesting pairs:", len(interesting))
