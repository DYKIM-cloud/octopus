"""
합성 조건이 비슷하지만 다른 zone에 속한 쌍의 스펙트럼 비교 플롯.
zone 차이가 크고 조건 차이가 작은 쌍을 수작업으로 6개 선정.
"""
import sys, os, numpy as np, pandas as pd, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── 데이터 로드 ────────────────────────────────────────────────────────────
PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
KEYS = df.iloc[0:4, 0].tolist()
SHORT = ['preHeat_T', 'Heat_T', 'In_rate', 'P_rate']

with open('fig/similar_cross_zone.pkl', 'rb') as f:
    interesting = pickle.load(f)

# 수동으로 6쌍 선정 (zone 차이·조건 차이 기준으로 의미 있는 것 우선)
# Rank 8:  22(B) vs 143(F)  — 같은 Heat_T=200, 조건 비슷, B↔F 극단
# Rank 10: 105(C) vs 113(F) — Heat_T 246/248, C↔F
# Rank 5:  123(D) vs 152(F) — 조건 거의 같고 Heat_T=200, D↔F
# Rank 4:   92(D) vs  98(C) — Heat_T 241/242, D↔C 미묘
# Rank 7:   90(F) vs  92(D) — Heat_T 245/241, F↔D
# Rank 18:  67(B) vs  84(D) — Heat_T 236/233, P_rate 같음, B↔D 극단

# 쌍 인덱스를 pickle interesting 리스트에서 sample 번호로 찾기
def find_pair(s1, s2, interesting):
    for dist, ri, rj in interesting:
        if set([ri['sample'], rj['sample']]) == set([s1, s2]):
            if ri['sample'] == s1:
                return dist, ri, rj
            else:
                return dist, rj, ri
    return None

# zone 색상
ZCOL = {'B':'#d62728','C':'#ff7f0e','D':'#9467bd','E':'#1f77b4','F':'#17becf','A':'#2ca02c'}
ZDESC = {'B':'급경사 [-1.5]','C':'Rayleigh [-1.5~-1.2]','D':'완만한감소 [-1.2~-0.6]',
         'E':'QD유사 [-0.6~-0.3]','F':'천장 [-0.3]'}

# interesting 에서 sample 딕셔너리로 변환
all_recs = {}
for dist, ri, rj in interesting:
    all_recs[ri['sample']] = ri
    all_recs[rj['sample']] = rj

# 추가 샘플(67, 84, 22, 143 등)도 interesting에서 찾기
PAIR_LIST = [
    (22,  143),  # B vs F — Heat_T 200/200, 극단 차이
    (105, 113),  # C vs F — Heat_T 246/248, 조건 유사
    (123, 152),  # D vs F — Heat_T 200/200, In/P_rate 유사
    ( 92,  98),  # D vs C — Heat_T 241/242, 미묘한 차이
    ( 90,  92),  # F vs D — Heat_T 245/241, 극적 차이
    ( 67,  84),  # B vs D — Heat_T 236/233, P_rate 동일
]

# ── 플롯 ───────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(20, 24))
gs  = gridspec.GridSpec(6, 3, figure=fig, hspace=0.52, wspace=0.28,
                        top=0.95, bottom=0.04, left=0.06, right=0.97)

for row, (s1, s2) in enumerate(PAIR_LIST):
    r1 = all_recs.get(s1)
    r2 = all_recs.get(s2)
    if r1 is None or r2 is None:
        continue

    x    = r1['x']
    xm   = (x >= 350) & (x <= 700)
    xz   = (x >= 400) & (x <= 560)

    c1, c2 = ZCOL[r1['zone']], ZCOL[r2['zone']]

    # ── 왼쪽: 전체 스펙트럼 오버레이 ──────────────────────────────────────
    ax_ov = fig.add_subplot(gs[row, 0])
    ax_ov.plot(x[xm], r1['ys'][xm], color=c1, lw=2.0,
               label='S%d Zone%s yn=%.3f' % (r1['sample'], r1['zone'], r1['yn']))
    ax_ov.plot(x[xm], r2['ys'][xm], color=c2, lw=2.0, ls='--',
               label='S%d Zone%s yn=%.3f' % (r2['sample'], r2['zone'], r2['yn']))
    ax_ov.axvspan(420, 510, color='yellow', alpha=0.12)
    ax_ov.set_xlim(350, 700)
    ax_ov.set_ylim(bottom=0)
    ax_ov.set_xlabel('Wavelength (nm)', fontsize=9)
    ax_ov.set_ylabel('Absorbance', fontsize=9)
    ax_ov.legend(fontsize=8, loc='upper right')
    ax_ov.tick_params(labelsize=8)

    # 합성 조건 차이 표시
    cond_txt = ''
    for k, sh in zip(KEYS, SHORT):
        v1, v2 = r1[k], r2[k]
        diff = v2 - v1
        mark = '  ' if abs(diff) < 5 else ('<< ' if diff < 0 else '>> ')
        cond_txt += '%s: %4.0f vs %4.0f %s\n' % (sh, v1, v2, mark)
    ax_ov.text(0.02, 0.98, cond_txt.rstrip(), transform=ax_ov.transAxes,
               fontsize=7.5, va='top', family='monospace',
               bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9))

    ax_ov.set_title(
        'S%d(Zone%s) vs S%d(Zone%s)' % (r1['sample'],r1['zone'],r2['sample'],r2['zone']),
        fontsize=10, fontweight='bold')

    # ── 가운데: 420~560nm 잔류 확대 ──────────────────────────────────────
    ax_rd = fig.add_subplot(gs[row, 1])
    ax_rd.fill_between(x[xz], 0, r1['rd'][xz], color=c1, alpha=0.35,
                       label='Residual S%d' % r1['sample'])
    ax_rd.fill_between(x[xz], 0, r2['rd'][xz], color=c2, alpha=0.35,
                       label='Residual S%d' % r2['sample'])
    ax_rd.plot(x[xz], r1['rd'][xz], color=c1, lw=1.5)
    ax_rd.plot(x[xz], r2['rd'][xz], color=c2, lw=1.5, ls='--')
    ax_rd.axvspan(420, 510, color='yellow', alpha=0.10)
    ax_rd.axvline(460, color='red', lw=0.8, ls=':', alpha=0.7, label='target 460nm')
    ax_rd.set_xlim(400, 560)
    ax_rd.set_ylim(bottom=0)
    ax_rd.set_xlabel('Wavelength (nm)', fontsize=9)
    ax_rd.set_ylabel('Residual absorbance', fontsize=9)
    ax_rd.legend(fontsize=8)
    ax_rd.tick_params(labelsize=8)
    ax_rd.set_title('배경 제거 후 잔류 신호 (420~560nm)', fontsize=9, fontweight='bold')

    # 잔류 적분값 표시
    dx = x[1] - x[0]
    int1 = float(np.sum(r1['rd'][xz]) * dx)
    int2 = float(np.sum(r2['rd'][xz]) * dx)
    ax_rd.text(0.97, 0.97,
               'Integral S%d: %.4f\nIntegral S%d: %.4f' % (r1['sample'],int1,r2['sample'],int2),
               transform=ax_rd.transAxes, fontsize=8, ha='right', va='top', family='monospace',
               bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9))

    # ── 오른쪽: y_norm 지점 확대 (400~600nm smooth) ──────────────────────
    ax_yn = fig.add_subplot(gs[row, 2])
    xn = (x >= 400) & (x <= 600)
    ax_yn.plot(x[xn], r1['ys'][xn], color=c1, lw=2.0)
    ax_yn.plot(x[xn], r2['ys'][xn], color=c2, lw=2.0, ls='--')

    for ri, ci in [(r1, c1), (r2, c2)]:
        for wl_pt, mk in [(420,'o'),(460,'s'),(550,'^')]:
            ii = int(np.argmin(np.abs(x - wl_pt)))
            ax_yn.plot(x[ii], ri['ys'][ii], marker=mk, ms=7, color=ci, zorder=6)

    # y_norm 계산 값 표시
    def compute_yn(r):
        i4=int(np.argmin(np.abs(x-420))); it=int(np.argmin(np.abs(x-460))); i5=int(np.argmin(np.abs(x-550)))
        a4,at,a5=r['ys'][i4],r['ys'][it],r['ys'][i5]; dn=a4-a5
        return float(np.clip((at-a5)/dn,0,1)) if dn>0 and a4>0 else 0.0, a4, at, a5

    yn1, a4_1, at_1, a5_1 = compute_yn(r1)
    yn2, a4_2, at_2, a5_2 = compute_yn(r2)

    yn_txt = ('S%d: A420=%.3f A460=%.3f A550=%.3f yn=%.3f\n'
              'S%d: A420=%.3f A460=%.3f A550=%.3f yn=%.3f') % (
        r1['sample'], a4_1, at_1, a5_1, yn1,
        r2['sample'], a4_2, at_2, a5_2, yn2)
    ax_yn.text(0.02, 0.98, yn_txt, transform=ax_yn.transAxes,
               fontsize=7.5, va='top', family='monospace',
               bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9))

    ax_yn.axvline(460, color='red', lw=0.8, ls=':', alpha=0.7)
    ax_yn.set_xlim(400, 600)
    ax_yn.set_ylim(bottom=0)
    ax_yn.set_xlabel('Wavelength (nm)', fontsize=9)
    ax_yn.set_ylabel('Absorbance (smooth)', fontsize=9)
    ax_yn.set_title('y_norm 계산 지점  (▲=A550  ■=A460  ●=A420)', fontsize=9, fontweight='bold')
    ax_yn.tick_params(labelsize=8)

fig.suptitle(
    '합성 조건이 유사하지만 다른 Zone에 속한 샘플 쌍 비교 (Zone B~F)\n'
    '좌: Smoothed 스펙트럼 오버레이  |  중: 배경제거 잔류 신호  |  우: y_norm 계산 지점',
    fontsize=12, fontweight='bold')

out = 'fig/cross_zone_comparison.png'
os.makedirs('fig', exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight')
print('Saved:', out)
