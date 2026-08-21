"""
이론(낮은 flow rate → 긴 체류시간 → 좋은 zone) 기준으로
1) 각 zone에서 이론과 맞지 않는 샘플
2) 조건 유사 / 다른 zone 쌍의 이론 일치 여부
를 평가하고 플롯 생성.

Zone 순위 (좋은 쪽 높음): B=1 < C=2 < D=3 < E=4 < F=5
이론 예측: total_flow ↓  &  Heat_T ↑  →  zone rank ↑
"""
import sys, os, pickle, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D

# ── 전체 records 로드 ─────────────────────────────────────────────────────
with open('fig/all_records.pkl','rb') as f:
    records = pickle.load(f)

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
KEYS = df.iloc[0:4, 0].tolist()

ZCOL   = {'B':'#d62728','C':'#ff7f0e','D':'#9467bd','E':'#1f77b4','F':'#17becf'}
ZRANK  = {'B':1,'C':2,'D':3,'E':4,'F':5}
ZDESC  = {'B':'B [-1.5]','C':'C [-1.5~-1.2]','D':'D [-1.2~-0.6]',
          'E':'E [-0.6~-0.3]','F':'F [-0.3]'}

# B~F 만 사용
recs = [r for r in records if r['zone'] in 'BCDEF']
for r in recs:
    r['total_flow'] = r[KEYS[2]] + r[KEYS[3]]          # In + P
    r['heat_t']     = r[KEYS[1]]
    r['zrank']      = ZRANK[r['zone']]
    # 체류시간 (초) = 8 mL / (total_flow µL/min) * 1000 * 60
    r['res_time']   = 8e6 / r['total_flow'] if r['total_flow'] > 0 else np.nan

# ── zone별 total_flow / Heat_T 통계 ──────────────────────────────────────
print("=== Zone별 total_flow (In+P) 및 Heat_T 통계 ===")
print("Zone | N  | flow mean±std   | Heat_T mean±std | res_time(s) mean")
print("-"*70)
for z in 'BCDEF':
    sub = [r for r in recs if r['zone']==z]
    fl  = np.array([r['total_flow'] for r in sub])
    ht  = np.array([r['heat_t']     for r in sub])
    rt  = np.array([r['res_time']   for r in sub])
    print("  %s  | %2d | %6.0f ± %5.0f | %6.1f ± %4.1f   | %6.1f" % (
        z, len(sub), fl.mean(), fl.std(), ht.mean(), ht.std(), rt.mean()))

# ── 이론 불일치 샘플 탐색 ────────────────────────────────────────────────
# 전략: zone별 total_flow 중앙값 계산 → 이웃 zone과 비교해 '방향이 반대'인 샘플
zone_med_flow = {}
zone_med_heat = {}
for z in 'BCDEF':
    sub = [r for r in recs if r['zone']==z]
    zone_med_flow[z] = np.median([r['total_flow'] for r in sub])
    zone_med_heat[z] = np.median([r['heat_t']     for r in sub])

# 이론 불일치 판단:
#   - zone이 좋은데(rank↑) total_flow 가 높음(체류 짧음)  → 이론 반례
#   - zone이 나쁜데(rank↓) total_flow 가 낮음(체류 길음)  → 이론 반례
# Heat_T도 같이 고려: Heat_T 낮은데 좋은 zone → 반례
# 점수화: expected_rank = (low_flow_score + high_heat_score) / 2
#   low_flow_score = 1 - (total_flow - flow_min) / (flow_max - flow_min)
#   high_heat_score= (heat_t - heat_min) / (heat_max - heat_min)

all_flows = np.array([r['total_flow'] for r in recs])
all_heats = np.array([r['heat_t']     for r in recs])
fmin,fmax = all_flows.min(), all_flows.max()
hmin,hmax = all_heats.min(), all_heats.max()

for r in recs:
    flow_score = 1 - (r['total_flow'] - fmin) / (fmax - fmin)  # 낮을수록 1
    heat_score = (r['heat_t'] - hmin) / (hmax - hmin)           # 높을수록 1
    r['theory_score'] = (flow_score + heat_score) / 2           # 0~1, 높을수록 좋은 zone 예측
    # 예상 zone rank (1~5 매핑)
    r['expected_rank'] = 1 + r['theory_score'] * 4
    r['rank_gap'] = r['zrank'] - r['expected_rank']  # +: 이론보다 좋은 zone, -: 이론보다 나쁜 zone

# 반례: |rank_gap| > 1.5 인 샘플
mismatch = sorted([r for r in recs if abs(r['rank_gap']) > 1.5],
                  key=lambda r: r['rank_gap'])

print("\n=== 이론 불일치 샘플 (|rank_gap| > 1.5) ===")
print("Sample | Zone | total_flow | Heat_T | res(s) | theory_score | expected_rank | actual_rank | gap  | 판정")
print("-"*100)
for r in mismatch:
    verdict = "이론보다 좋은 zone (의외의 성공)" if r['rank_gap'] > 0 else "이론보다 나쁜 zone (의외의 실패)"
    print("  %3d  |  %s   |  %6.0f    |  %5.1f | %6.1f |   %.3f      |    %.2f       |    %d    | %+.2f | %s" % (
        r['sample'], r['zone'], r['total_flow'], r['heat_t'],
        r['res_time'], r['theory_score'], r['expected_rank'], r['zrank'],
        r['rank_gap'], verdict))

# ── 유사 조건 / 다른 zone 쌍 이론 재평가 ────────────────────────────────
PAIR_LIST = [
    (28, 59,   "완전 동일 조건 In/P=1.00"),
    (132, 152, "In/P 1.51 vs 1.57"),
    (100, 126, "In/P 1.01 vs 1.02"),
    (45,  79,  "In/P 1.20 vs 1.26  (Zone E 희귀)"),
    (113, 116, "In/P 3.50 vs 3.46  고비율"),
    (34,  93,  "In/P 1.00 vs 1.00  이상값 의심"),
]
all_recs_d = {r['sample']:r for r in records}
print("\n=== 유사 조건 쌍 이론 일치 여부 ===")
print("Pair         | flow_i  flow_j | heat_i heat_j | res_i  res_j | zone_i zone_j | theory_winner | actual_better | match?")
print("-"*110)
pair_eval = []
for s1, s2, note in PAIR_LIST:
    r1, r2 = all_recs_d[s1], all_recs_d[s2]
    fl1 = r1[KEYS[2]]+r1[KEYS[3]]; fl2 = r2[KEYS[2]]+r2[KEYS[3]]
    ht1, ht2 = r1[KEYS[1]], r2[KEYS[1]]
    rt1 = 8e6/fl1; rt2 = 8e6/fl2
    zr1 = ZRANK.get(r1['zone'],0); zr2 = ZRANK.get(r2['zone'],0)
    # 이론 승자: flow 낮고 Heat_T 높은 쪽
    flow_favor = s1 if fl1 < fl2 else (s2 if fl2 < fl1 else 'tie')
    heat_favor = s1 if ht1 > ht2 else (s2 if ht2 > ht1 else 'tie')
    if flow_favor == heat_favor:   theory_winner = flow_favor
    elif flow_favor == 'tie':      theory_winner = heat_favor
    elif heat_favor == 'tie':      theory_winner = flow_favor
    else:                          theory_winner = 'conflict'
    actual_better = s1 if zr1 > zr2 else (s2 if zr2 > zr1 else 'tie')
    match = (str(theory_winner) == str(actual_better)) or (theory_winner == 'conflict')
    pair_eval.append(dict(s1=s1,s2=s2,note=note,
                          fl1=fl1,fl2=fl2,ht1=ht1,ht2=ht2,
                          rt1=rt1,rt2=rt2,
                          z1=r1['zone'],z2=r2['zone'],
                          theory_winner=theory_winner,actual_better=actual_better,
                          match=match,
                          yn1=r1['yn'],yn2=r2['yn']))
    print("S%3d vs S%3d | %6.0f %6.0f | %5.1f  %5.1f | %5.0f  %5.0f |   %s      %s   |     S%3d     |     S%3d      |  %s" % (
        s1,s2, fl1,fl2, ht1,ht2, rt1,rt2,
        r1['zone'],r2['zone'],
        theory_winner if theory_winner not in ['tie','conflict'] else 0,
        actual_better if actual_better not in ['tie','conflict'] else 0,
        'YES' if match else 'NO'))

# ════════════════════════════════════════════════════════════════════════════
# 플롯
# ════════════════════════════════════════════════════════════════════════════
fig = plt.figure(figsize=(20, 22))
gs  = gridspec.GridSpec(3, 3, figure=fig, hspace=0.48, wspace=0.32,
                        top=0.94, bottom=0.05, left=0.07, right=0.97)

# ── (1) total_flow vs y_norm scatter, zone별 색 ──────────────────────────
ax1 = fig.add_subplot(gs[0, 0])
for z in 'BCDEF':
    sub = [r for r in recs if r['zone']==z]
    ax1.scatter([r['total_flow'] for r in sub],
                [r['yn'] for r in sub],
                color=ZCOL[z], s=40, alpha=0.75, label=ZDESC[z], zorder=4)
# 이론 불일치 샘플 강조
for r in mismatch:
    ax1.scatter(r['total_flow'], r['yn'],
                s=180, facecolors='none', edgecolors='black', linewidths=2, zorder=5)
    ax1.annotate('S%d'%r['sample'], (r['total_flow'], r['yn']),
                 fontsize=7, ha='left', va='bottom', color='black')
ax1.set_xlabel('Total flow rate (In+P, µL/min)', fontsize=10)
ax1.set_ylabel('y_norm', fontsize=10)
ax1.set_title('Total flow rate vs y_norm\n(○ = 이론 불일치 샘플)', fontsize=10, fontweight='bold')
ax1.legend(fontsize=7, loc='upper right')

# ── (2) Heat_T vs y_norm scatter ─────────────────────────────────────────
ax2 = fig.add_subplot(gs[0, 1])
for z in 'BCDEF':
    sub = [r for r in recs if r['zone']==z]
    ax2.scatter([r['heat_t'] for r in sub],
                [r['yn'] for r in sub],
                color=ZCOL[z], s=40, alpha=0.75, label=ZDESC[z], zorder=4)
for r in mismatch:
    ax2.scatter(r['heat_t'], r['yn'],
                s=180, facecolors='none', edgecolors='black', linewidths=2, zorder=5)
    ax2.annotate('S%d'%r['sample'], (r['heat_t'], r['yn']),
                 fontsize=7, ha='left', va='bottom', color='black')
ax2.set_xlabel('Heat_T (°C)', fontsize=10)
ax2.set_ylabel('y_norm', fontsize=10)
ax2.set_title('Heat_T vs y_norm\n(○ = 이론 불일치 샘플)', fontsize=10, fontweight='bold')
ax2.legend(fontsize=7, loc='upper left')

# ── (3) 체류시간 vs y_norm ───────────────────────────────────────────────
ax3 = fig.add_subplot(gs[0, 2])
for z in 'BCDEF':
    sub = [r for r in recs if r['zone']==z]
    ax3.scatter([r['res_time'] for r in sub],
                [r['yn'] for r in sub],
                color=ZCOL[z], s=40, alpha=0.75, label=ZDESC[z], zorder=4)
for r in mismatch:
    ax3.scatter(r['res_time'], r['yn'],
                s=180, facecolors='none', edgecolors='black', linewidths=2, zorder=5)
    ax3.annotate('S%d'%r['sample'], (r['res_time'], r['yn']),
                 fontsize=7, ha='left', va='bottom', color='black')
ax3.set_xlabel('Residence time (sec)', fontsize=10)
ax3.set_ylabel('y_norm', fontsize=10)
ax3.set_title('Residence time vs y_norm\n(○ = 이론 불일치 샘플)', fontsize=10, fontweight='bold')
ax3.legend(fontsize=7, loc='upper left')

# ── (4) zone별 total_flow 박스플롯 ──────────────────────────────────────
ax4 = fig.add_subplot(gs[1, 0])
box_data = [[r['total_flow'] for r in recs if r['zone']==z] for z in 'BCDEF']
bp = ax4.boxplot(box_data, patch_artist=True, widths=0.5)
for patch, z in zip(bp['boxes'], 'BCDEF'):
    patch.set_facecolor(ZCOL[z]); patch.set_alpha(0.7)
# 이론 불일치 샘플 점으로 표시
for r in mismatch:
    xi = list('BCDEF').index(r['zone']) + 1
    ax4.plot(xi, r['total_flow'], 'ko', ms=8, zorder=5)
    ax4.annotate('S%d'%r['sample'], (xi, r['total_flow']),
                 fontsize=7, ha='left', va='bottom')
ax4.set_xticklabels([ZDESC[z] for z in 'BCDEF'], fontsize=7.5, rotation=15)
ax4.set_ylabel('Total flow rate (µL/min)', fontsize=10)
ax4.set_title('Zone별 Total flow rate 분포\n(이론: B→F로 갈수록 flow↓)', fontsize=10, fontweight='bold')
ax4.invert_yaxis()   # 위쪽이 낮은 flow (좋은 것)
ax4.text(0.5, 0.97, '← y축 역전: 위쪽 = 낮은 flow = 이론상 좋은 조건',
         transform=ax4.transAxes, fontsize=7.5, ha='center', va='top',
         color='gray', style='italic')

# ── (5) zone별 Heat_T 박스플롯 ─────────────────────────────────────────
ax5 = fig.add_subplot(gs[1, 1])
box_data2 = [[r['heat_t'] for r in recs if r['zone']==z] for z in 'BCDEF']
bp2 = ax5.boxplot(box_data2, patch_artist=True, widths=0.5)
for patch, z in zip(bp2['boxes'], 'BCDEF'):
    patch.set_facecolor(ZCOL[z]); patch.set_alpha(0.7)
for r in mismatch:
    xi = list('BCDEF').index(r['zone']) + 1
    ax5.plot(xi, r['heat_t'], 'ko', ms=8, zorder=5)
    ax5.annotate('S%d'%r['sample'], (xi, r['heat_t']),
                 fontsize=7, ha='left', va='bottom')
ax5.set_xticklabels([ZDESC[z] for z in 'BCDEF'], fontsize=7.5, rotation=15)
ax5.set_ylabel('Heat_T (°C)', fontsize=10)
ax5.set_title('Zone별 Heat_T 분포\n(이론: B→F로 갈수록 Heat_T↑)', fontsize=10, fontweight='bold')

# ── (6) 유사 조건 쌍 이론 일치 요약 ─────────────────────────────────────
ax6 = fig.add_subplot(gs[1, 2])
ax6.axis('off')
col_labels = ['쌍', '이론 승자', '실제 좋은 zone', '일치?', 'flow 차\n(µL/min)', 'Heat_T 차\n(°C)']
table_data = []
for pe in pair_eval:
    tw = 'S%d(↓flow)' % pe['theory_winner'] if pe['theory_winner'] not in ['tie','conflict'] else pe['theory_winner']
    ab = 'S%d' % pe['actual_better'] if pe['actual_better'] not in ['tie','conflict'] else pe['actual_better']
    dfl = pe['fl2'] - pe['fl1']
    dht = pe['ht2'] - pe['ht1']
    table_data.append([
        'S%d vs S%d' % (pe['s1'], pe['s2']),
        tw, ab,
        'YES' if pe['match'] else 'NO',
        '%+.0f' % dfl,
        '%+.1f' % dht
    ])
tbl = ax6.table(cellText=table_data, colLabels=col_labels,
                loc='center', cellLoc='center')
tbl.auto_set_font_size(False); tbl.set_fontsize(8.5)
tbl.scale(1, 1.7)
for (row, col), cell in tbl.get_celld().items():
    if row == 0:
        cell.set_facecolor('#333333'); cell.set_text_props(color='white', fontweight='bold')
    elif col == 3:
        txt = cell.get_text().get_text()
        cell.set_facecolor('#c8f7c5' if txt=='YES' else ('#f7c5c5' if txt=='NO' else '#fffdd0'))
ax6.set_title('유사 조건 쌍 — 이론 일치 여부', fontsize=10, fontweight='bold', pad=12)

# ── (7~12) 이론 불일치 샘플 스펙트럼 (상위 6개) ─────────────────────────
mismatch_show = sorted(mismatch, key=lambda r: abs(r['rank_gap']), reverse=True)[:6]
spec_axes = [fig.add_subplot(gs[2, i]) for i in range(3)]
# 2행으로 나눠서 3개씩
gs2 = gridspec.GridSpecFromSubplotSpec(2, 3, subplot_spec=gs[2, :], hspace=0.55, wspace=0.28)
spec_axes = [fig.add_subplot(gs2[i//3, i%3]) for i in range(6)]

for ax, r in zip(spec_axes, mismatch_show):
    x   = r['x']
    xm  = (x >= 350) & (x <= 700)
    col = ZCOL[r['zone']]
    ax.plot(x[xm], r['ys'][xm], color=col, lw=1.8)
    ax.fill_between(x[xm], 0, r['rd'][xm], color='green', alpha=0.20)
    ax.plot(x[xm], r['bg'][xm], color='gray', lw=1.0, ls='--', alpha=0.7)
    ax.axvspan(420, 510, color='yellow', alpha=0.12)
    ax.set_xlim(350, 700); ax.set_ylim(bottom=0)
    ax.set_xlabel('Wavelength (nm)', fontsize=8)
    ax.set_ylabel('Absorbance', fontsize=8)
    ax.tick_params(labelsize=7.5)

    direction = "이론보다 좋음 ↑" if r['rank_gap'] > 0 else "이론보다 나쁨 ↓"
    fl = r['total_flow']; rt = r['res_time']
    info = ('Zone %s  yn=%.3f\n'
            'flow=%g  res=%.0fs\n'
            'Heat_T=%g°C\n'
            'expected rank=%.1f  actual=%d\n'
            '%s') % (r['zone'], r['yn'], fl, rt, r['heat_t'],
                     r['expected_rank'], r['zrank'], direction)
    ax.text(0.97, 0.97, info, transform=ax.transAxes, fontsize=7,
            ha='right', va='top', family='monospace',
            bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.92))
    ax.set_title('S%d (%s)  gap=%+.2f' % (r['sample'], direction[:6], r['rank_gap']),
                 fontsize=8.5, fontweight='bold', color=col)

fig.suptitle(
    '이론(낮은 flow rate → 긴 체류시간 → 좋은 zone) 기준 평가\n'
    '상단: flow·Heat_T vs y_norm  |  중단: zone별 분포 + 쌍 평가  |  하단: 이론 불일치 샘플 스펙트럼',
    fontsize=12, fontweight='bold')

out = 'fig/theory_eval.png'
os.makedirs('fig', exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight')
print('\nSaved:', out)
