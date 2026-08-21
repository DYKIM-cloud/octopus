"""
수정된 CSV 기준 재분석
1) 재현성(결론 3): 동일 조건 쌍의 스펙트럼 동일성 검증
2) 고유량 + 좋은 zone 샘플: raw data 문제 vs loss function 문제 판단
"""
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
ZCOL={'B':'#d62728','C':'#ff7f0e','D':'#9467bd','E':'#1f77b4','F':'#17becf'}
ZRANK={'B':1,'C':2,'D':3,'E':4,'F':5}
wavelength=df.iloc[4:,0].astype(float).tolist()

# ── 전체 샘플 재분석 ─────────────────────────────────────────────────────
records={}
for col in range(1, df.shape[1]):
    ks=df.iloc[0:4,0].values; vs=df.iloc[0:4,col].values
    if pd.isnull(ks).any() or pd.isnull(vs).any(): continue
    sp=df.iloc[4:,col].astype(float).values
    if np.isnan(sp).any(): continue          # S153 NaN 제외
    cond=dict(zip(KEYS,vs.astype(float)))
    wl=np.array(wavelength); rs=np.array(sp)
    x,ys,bg,rd,lm,pv,yn=preprocess(wl,rs)
    if lm>0 and pv>0: zone='A'
    elif yn<=Y[0]: zone='B'
    elif yn<=Y[1]: zone='C'
    elif yn<=Y[2]: zone='D'
    elif yn<=Y[3]: zone='E'
    else: zone='F'
    records[col]=dict(sample=col,zone=zone,yn=yn,lm=lm,pv=pv,
                      wl=wl,rs=rs,x=x,ys=ys,bg=bg,rd=rd,
                      total_flow=cond[KEYS[2]]+cond[KEYS[3]],
                      heat_t=cond[KEYS[1]],**cond)

recs=list(records.values())

# ══════════════════════════════════════════════════════════════════════════
# 분석 1: 재현성 — 동일 스펙트럼 그룹 vs 조건이 같은데 다른 스펙트럼
# ══════════════════════════════════════════════════════════════════════════
n=df.shape[1]-1
same_sp=[]   # 완전히 같은 스펙트럼
same_cond_diff_sp=[]  # 조건 같은데 스펙트럼 다른 쌍

for i in range(1, n+1):
    if i not in records: continue
    for j in range(i+1, n+1):
        if j not in records: continue
        si=df.iloc[4:,i].astype(float).values
        sj=df.iloc[4:,j].astype(float).values
        ci=df.iloc[0:4,i].values.astype(float)
        cj=df.iloc[0:4,j].values.astype(float)
        cond_same=np.allclose(ci,cj,atol=1.0)
        sp_same=np.allclose(si,sj,atol=1e-6)
        if sp_same:
            same_sp.append((i,j))
        elif cond_same and not sp_same:
            sp_diff=float(np.mean(np.abs(si-sj)))
            yn_i=records[i]['yn']; yn_j=records[j]['yn']
            zone_i=records[i]['zone']; zone_j=records[j]['zone']
            same_cond_diff_sp.append((i,j,sp_diff,yn_i,yn_j,zone_i,zone_j,ci))

print("=== 재현성 분석 (수정된 CSV) ===")
print(f"동일 스펙트럼 쌍 수: {len(same_sp)}  (copy된 데이터)")
for p in same_sp[:10]: print("  S%d == S%d" % p)
print()
print(f"조건 동일 + 스펙트럼 다른 쌍 수: {len(same_cond_diff_sp)}")
for item in same_cond_diff_sp:
    i,j,d,yn_i,yn_j,zi,zj,ci=item
    print("  S%d(%s,yn=%.3f) vs S%d(%s,yn=%.3f)  sp_diff=%.4f  cond=%s" % (
        i,zi,yn_i,j,zj,yn_j,d,ci.astype(int)))

# ══════════════════════════════════════════════════════════════════════════
# 분석 2: 고유량 + 좋은 zone 샘플 — raw data vs loss function 문제
# ══════════════════════════════════════════════════════════════════════════
# 이론 불일치 점수 계산
recs_bf=[r for r in recs if r['zone'] in 'BCDEF']
all_flows=np.array([r['total_flow'] for r in recs_bf])
all_heats=np.array([r['heat_t'] for r in recs_bf])
fmin,fmax=all_flows.min(),all_flows.max()
hmin,hmax=all_heats.min(),all_heats.max()
for r in recs_bf:
    fs=1-(r['total_flow']-fmin)/(fmax-fmin)
    hs=(r['heat_t']-hmin)/(hmax-hmin)
    r['theory_score']=(fs+hs)/2
    r['expected_rank']=1+r['theory_score']*4
    r['zrank']=ZRANK[r['zone']]
    r['rank_gap']=r['zrank']-r['expected_rank']
    r['res_time']=8e6/r['total_flow'] if r['total_flow']>0 else np.nan

# 고유량 + 좋은 zone: rank_gap > 1.5 (이론보다 좋은)
anomaly_good = sorted([r for r in recs_bf if r['rank_gap']>1.5],
                      key=lambda r: r['rank_gap'], reverse=True)
print("\n=== 고유량(긴 체류x) + 좋은 zone 이상 샘플 (rank_gap>1.5) ===")
print("Sample | Zone | total_flow | res(s) | Heat_T | yn   | rank_gap")
for r in anomaly_good:
    print("  %3d  |  %s  |  %6.0f  |  %5.0f | %5.1f  | %.3f | %+.2f" % (
        r['sample'],r['zone'],r['total_flow'],r['res_time'],r['heat_t'],r['yn'],r['rank_gap']))

# 각 이상 샘플에 대해 진단
print("\n=== 이상 샘플 진단 ===")
print("판단 기준:")
print("  [Raw 문제] 스펙트럼에 노이즈 스파이크, 음수값, 불연속이 있으면")
print("  [Loss 문제] 스펙트럼은 정상이지만 y_norm이 구조적으로 과대평가되면")
print()

diag_results=[]
for r in anomaly_good:
    rs=r['rs']; wl=r['wl']
    ys=r['ys']; bg=r['bg']
    # 진단 지표
    has_neg = bool(np.any(np.array(rs)<-0.01))
    noise_std = float(np.std(np.diff(rs)))  # 원시 스펙트럼 노이즈 수준
    # 420-510nm 구간 smooth 대비 raw 편차
    wl_arr=np.array(wl)
    pm=(wl_arr>=420)&(wl_arr<=510)
    if pm.sum()>2:
        raw_in_zone=np.array(rs)[pm]
        x_zone=r['x']
        sm_at_raw=np.interp(wl_arr[pm],x_zone,ys)
        peak_zone_dev=float(np.mean(np.abs(raw_in_zone-sm_at_raw)))
        # 피크 존 내 raw 최대값
        raw_peak_max=float(np.max(raw_in_zone))
    else:
        peak_zone_dev=0.0; raw_peak_max=0.0
    # y_norm 계산 재확인
    x=r['x']
    i4=int(np.argmin(np.abs(x-420))); it=int(np.argmin(np.abs(x-TARGET_LM))); i5=int(np.argmin(np.abs(x-550)))
    a4,at,a5=float(ys[i4]),float(ys[it]),float(ys[i5])
    # 배경에서 y_norm 재계산 (배경만으로 y_norm이 얼마?)
    bg4=float(bg[i4]); bgt=float(bg[it]); bg5=float(bg[i5])
    dn_bg=bg4-bg5
    yn_bg=float(np.clip((bgt-bg5)/dn_bg,0,1)) if dn_bg>0 else 0.0
    # 실제 y_norm과 배경만의 y_norm 차이 → 잔류 신호 기여분
    yn_resid_contrib=r['yn']-yn_bg
    # 판단
    if has_neg or noise_std>0.05:
        diagnosis='[Raw 문제] 음수/고노이즈'
    elif peak_zone_dev>0.05:
        diagnosis='[Raw 문제] 피크존 스파이크'
    elif yn_resid_contrib<0.03:
        diagnosis='[Loss 문제] 배경만으로 y_norm 과대'
    elif r['total_flow']>2000 and r['res_time']<4000:
        diagnosis='[Loss 문제] 극고유량인데 y_norm↑ — 배경피팅 오류 의심'
    else:
        diagnosis='[불명확] 추가 검토 필요'
    diag_results.append(dict(**r, has_neg=has_neg, noise_std=noise_std,
                             peak_zone_dev=peak_zone_dev, raw_peak_max=raw_peak_max,
                             yn_bg=yn_bg, yn_resid_contrib=yn_resid_contrib,
                             diagnosis=diagnosis))
    print("S%d (Zone%s, yn=%.3f, flow=%g, res=%.0fs):" % (
        r['sample'],r['zone'],r['yn'],r['total_flow'],r['res_time']))
    print("  neg_val=%s  noise_std=%.4f  pk_zone_dev=%.4f  raw_pk_max=%.3f" % (
        has_neg,noise_std,peak_zone_dev,raw_peak_max))
    print("  yn_bg=%.3f  yn_resid_contrib=%.3f  → %s" % (yn_bg,yn_resid_contrib,diagnosis))
    print()

# ══════════════════════════════════════════════════════════════════════════
# 플롯 PAGE 1: 재현성 재분석
# ══════════════════════════════════════════════════════════════════════════
# 진짜 재현성 문제: 조건 같은데 스펙트럼 다른 쌍
fig1, axes1 = plt.subplots(max(len(same_cond_diff_sp),1), 2,
                            figsize=(14, max(len(same_cond_diff_sp)*3.5, 4)))
if len(same_cond_diff_sp)==0:
    axes1 = np.array([[axes1[0], axes1[1]]])
elif len(same_cond_diff_sp)==1:
    axes1 = axes1.reshape(1,2)

fig1.suptitle('재현성 재분석 — 조건 동일 + 스펙트럼 다른 쌍 (수정된 CSV)', fontsize=12, fontweight='bold')

for idx, (i,j,d,yn_i,yn_j,zi,zj,ci) in enumerate(same_cond_diff_sp):
    ri=records[i]; rj=records[j]
    x=ri['x']; xm=(x>=350)&(x<=700)
    ax=axes1[idx,0]
    ax.plot(x[xm],ri['ys'][xm],color=ZCOL[zi],lw=2,label='S%d Zone%s yn=%.3f'%(i,zi,yn_i))
    ax.plot(x[xm],rj['ys'][xm],color=ZCOL[zj],lw=2,ls='--',label='S%d Zone%s yn=%.3f'%(j,zj,yn_j))
    ax.set_title('S%d vs S%d  Δyn=%.3f\ncond=%s'%(i,j,abs(yn_i-yn_j),ci.astype(int)),
                 fontsize=9,fontweight='bold')
    ax.legend(fontsize=8); ax.set_xlim(350,700); ax.set_ylim(bottom=0)
    ax.set_xlabel('Wavelength(nm)',fontsize=8); ax.set_ylabel('Absorbance',fontsize=8)

    ax2=axes1[idx,1]
    raw_i=ri['rs']; raw_j=rj['rs']
    wl_arr=np.array(ri['wl'])
    ax2.plot(wl_arr,raw_i,color=ZCOL[zi],lw=1,alpha=0.8,label='S%d raw'%i)
    ax2.plot(wl_arr,raw_j,color=ZCOL[zj],lw=1,alpha=0.8,ls='--',label='S%d raw'%j)
    ax2.set_title('Raw spectrum 비교  (노이즈/아티팩트 확인)',fontsize=9,fontweight='bold')
    ax2.legend(fontsize=8); ax2.set_xlim(350,700); ax2.set_ylim(bottom=0)
    ax2.set_xlabel('Wavelength(nm)',fontsize=8); ax2.set_ylabel('Raw Absorbance',fontsize=8)
    diff_arr=np.abs(np.array(raw_i)-np.array(raw_j))
    ax2.fill_between(wl_arr,0,diff_arr,color='red',alpha=0.25,label='|diff|')
    ax2.legend(fontsize=8)

if len(same_cond_diff_sp)==0:
    axes1[0,0].text(0.5,0.5,'조건 동일 + 스펙트럼 다른 쌍 없음\n(재현성 문제 해결됨)',
                    ha='center',va='center',transform=axes1[0,0].transAxes,fontsize=12)
    axes1[0,1].axis('off')

plt.tight_layout()
out1='fig/reproducibility_reanalysis.png'
os.makedirs('fig',exist_ok=True)
plt.savefig(out1,dpi=150,bbox_inches='tight')
print('Saved:',out1)

# ══════════════════════════════════════════════════════════════════════════
# 플롯 PAGE 2: 고유량 + 좋은 zone 이상 샘플 진단
# ══════════════════════════════════════════════════════════════════════════
show = diag_results[:8]
ncols=4; nrows=int(np.ceil(len(show)/2))
fig2=plt.figure(figsize=(20, nrows*7))
gs2=gridspec.GridSpec(nrows,ncols,figure=fig2,hspace=0.55,wspace=0.30,
                      top=0.93,bottom=0.04,left=0.06,right=0.97)

for idx,dr in enumerate(show):
    row=idx//2; col_base=(idx%2)*2
    x=dr['x']; xm=(x>=350)&(x<=700); xz=(x>=390)&(x<=560)
    c=ZCOL[dr['zone']]
    wl_arr=np.array(dr['wl']); rs_arr=np.array(dr['rs'])

    # 좌: raw + smooth 비교
    ax_l=fig2.add_subplot(gs2[row,col_base])
    ax_l.plot(wl_arr,rs_arr,color='lightgray',lw=0.8,alpha=0.9,label='Raw')
    ax_l.plot(x[xm],dr['ys'][xm],color=c,lw=2.0,label='Smooth')
    ax_l.plot(x[xm],dr['bg'][xm],color='saddlebrown',lw=1.2,ls='--',alpha=0.8,label='Background')
    ax_l.axvspan(420,510,color='yellow',alpha=0.12)
    ax_l.set_xlim(350,700); ax_l.set_ylim(bottom=0)
    ax_l.set_xlabel('Wavelength(nm)',fontsize=9); ax_l.set_ylabel('Absorbance',fontsize=9)
    ax_l.legend(fontsize=7.5,loc='upper right')
    diag_short=dr['diagnosis'][:25]
    ax_l.set_title('S%d (Zone%s)  flow=%g  res=%.0fs\n%s' % (
        dr['sample'],dr['zone'],dr['total_flow'],dr['res_time'],dr['diagnosis']),
        fontsize=8.5,fontweight='bold',color=c)
    info=('yn=%.3f\nyn_bg(배경만)=%.3f\nyn_resid 기여=%.3f\nnoise_std=%.4f\nhas_neg=%s') % (
        dr['yn'],dr['yn_bg'],dr['yn_resid_contrib'],dr['noise_std'],dr['has_neg'])
    ax_l.text(0.02,0.98,info,transform=ax_l.transAxes,fontsize=7.5,va='top',family='monospace',
              bbox=dict(boxstyle='round,pad=0.3',fc='white',alpha=0.92))

    # 우: 420-560nm 확대 + raw 노이즈 확인
    ax_r=fig2.add_subplot(gs2[row,col_base+1])
    pm_wl=(wl_arr>=390)&(wl_arr<=560)
    ax_r.plot(wl_arr[pm_wl],rs_arr[pm_wl],color='lightgray',lw=1.0,alpha=0.9,label='Raw')
    ax_r.plot(x[xz],dr['ys'][xz],color=c,lw=2.0,label='Smooth')
    ax_r.fill_between(x[xz],0,dr['rd'][xz],color='green',alpha=0.25,label='Residual')
    ax_r.plot(x[xz],dr['bg'][xz],color='saddlebrown',lw=1.2,ls='--',alpha=0.7,label='Background')
    ax_r.axvspan(420,510,color='yellow',alpha=0.12,label='Peak zone')
    ax_r.axvline(460,color='red',lw=0.8,ls=':',alpha=0.7,label='460nm')
    ax_r.set_xlim(390,560); ax_r.set_ylim(bottom=0)
    ax_r.set_xlabel('Wavelength(nm)',fontsize=9); ax_r.set_ylabel('Absorbance',fontsize=9)
    ax_r.legend(fontsize=7,loc='upper right')
    ax_r.set_title('420–560nm 확대  |  raw vs smooth',fontsize=9,fontweight='bold')

    # y_norm 기여 분해 표시
    i4=int(np.argmin(np.abs(x-420))); it=int(np.argmin(np.abs(x-TARGET_LM))); i5=int(np.argmin(np.abs(x-550)))
    a4,at,a5=float(dr['ys'][i4]),float(dr['ys'][it]),float(dr['ys'][i5])
    bg4,bgt,bg5=float(dr['bg'][i4]),float(dr['bg'][it]),float(dr['bg'][i5])
    for ax_tmp,wl_pt,mk,mc,lab in [(ax_l,420,'o','navy','A420'),(ax_l,TARGET_LM,'s','red','A460'),(ax_l,550,'^','olive','A550')]:
        ii=int(np.argmin(np.abs(x-wl_pt)))
        ax_tmp.plot(x[ii],dr['ys'][ii],marker=mk,ms=7,color=mc,zorder=6)

fig2.suptitle('고유량 + 좋은 Zone 이상 샘플 진단\n[Raw 문제]: 스펙트럼 자체 결함  /  [Loss 문제]: y_norm 구조적 과대평가',
              fontsize=12,fontweight='bold')
out2='fig/anomaly_diagnosis.png'
plt.savefig(out2,dpi=150,bbox_inches='tight')
print('Saved:',out2)
