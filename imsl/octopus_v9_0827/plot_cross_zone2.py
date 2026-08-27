"""
In/P ratio 기준 조건 유사 / 다른 Zone 쌍 비교 플롯
선정 기준: In/P ratio 차이 작고, zone 차이 큰 쌍 우선
"""
import sys, os, numpy as np, pandas as pd, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

with open('fig/all_records.pkl','rb') as f:
    records = pickle.load(f)

PATH = '2508optimize/spectra_with_params_0407.csv'
df   = pd.read_csv(PATH, header=None)
KEYS = df.iloc[0:4,0].tolist()

# 전체 records를 sample 번호로 인덱싱
all_recs = {r['sample']: r for r in records}

# 6쌍 수동 선정 (zone 차이·In/P ratio 유사성 기준)
# Rank 1:  28(C)  vs 59(D)  — 완전 동일 조건, In/P=1.00 vs 1.00
# Rank 3: 132(D)  vs152(F)  — In/P 1.51 vs 1.57, D↔F
# Rank 5: 100(C)  vs126(D)  — In/P 1.01 vs 1.02, C↔D
# Rank 8:  45(E)  vs 79(D)  — In/P 1.20 vs 1.26, E↔D  (Zone E 드문 사례)
# Rank16: 113(F)  vs116(C)  — In/P 3.50 vs 3.46, F↔C 극단
# Rank18:  34(B)  vs 93(C)  — In/P 1.00 vs 1.00, B↔C (34번 이상값)
PAIR_LIST = [
    (28,  59,  "완전 동일 조건 (In/P=1.00)"),
    (132, 152, "In/P 1.51 vs 1.57"),
    (100, 126, "In/P 1.01 vs 1.02"),
    (45,  79,  "In/P 1.20 vs 1.26  (Zone E 희귀)"),
    (113, 116, "In/P 3.50 vs 3.46  (고비율 극단 비교)"),
    (34,  93,  "In/P 1.00 vs 1.00  (34번 이상값 의심)"),
]

ZCOL  = {'B':'#d62728','C':'#ff7f0e','D':'#9467bd','E':'#1f77b4','F':'#17becf','A':'#2ca02c'}
ZDESC = {'B':'Zone B [-1.5]','C':'Zone C [-1.5~-1.2]','D':'Zone D [-1.2~-0.6]',
         'E':'Zone E [-0.6~-0.3]','F':'Zone F [-0.3]'}

fig = plt.figure(figsize=(20, 26))
gs  = gridspec.GridSpec(6, 3, figure=fig, hspace=0.50, wspace=0.28,
                        top=0.95, bottom=0.04, left=0.06, right=0.97)

for row, (s1, s2, note) in enumerate(PAIR_LIST):
    r1 = all_recs.get(s1)
    r2 = all_recs.get(s2)
    if r1 is None or r2 is None:
        continue

    x  = r1['x']
    xm = (x >= 350) & (x <= 700)
    xz = (x >= 400) & (x <= 560)
    c1, c2 = ZCOL[r1['zone']], ZCOL[r2['zone']]

    ip1 = r1['ip_ratio']
    ip2 = r2['ip_ratio']

    # ── 왼쪽: Smoothed 스펙트럼 오버레이 ─────────────────────────────────
    ax_ov = fig.add_subplot(gs[row, 0])
    ax_ov.plot(x[xm], r1['ys'][xm], color=c1, lw=2.2,
               label='S%d %s  yn=%.3f' % (r1['sample'], ZDESC[r1['zone']], r1['yn']))
    ax_ov.plot(x[xm], r2['ys'][xm], color=c2, lw=2.2, ls='--',
               label='S%d %s  yn=%.3f' % (r2['sample'], ZDESC[r2['zone']], r2['yn']))
    ax_ov.axvspan(420, 510, color='yellow', alpha=0.12, label='Peak zone')
    ax_ov.axvline(460, color='red', lw=0.8, ls=':', alpha=0.6)
    ax_ov.set_xlim(350, 700); ax_ov.set_ylim(bottom=0)
    ax_ov.set_xlabel('Wavelength (nm)', fontsize=9)
    ax_ov.set_ylabel('Absorbance', fontsize=9)
    ax_ov.legend(fontsize=7.5, loc='upper right')
    ax_ov.tick_params(labelsize=8)

    # 조건 박스
    def fmt_cond(r):
        return ('preH=%g  Heat=%g\nIn=%g  P=%g\nIn/P=%.2f' % (
            r[KEYS[0]], r[KEYS[1]], r[KEYS[2]], r[KEYS[3]], r['ip_ratio']))
    cbox  = 'S%d: %s\nS%d: %s' % (r1['sample'], fmt_cond(r1), r2['sample'], fmt_cond(r2))
    ax_ov.text(0.02, 0.98, cbox, transform=ax_ov.transAxes,
               fontsize=7, va='top', family='monospace',
               bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.92))
    ax_ov.set_title('[%s]\nS%d(%s) vs S%d(%s)' % (
        note, r1['sample'],r1['zone'], r2['sample'],r2['zone']),
        fontsize=9, fontweight='bold')

    # ── 가운데: 잔류 신호 (배경 제거 후) ─────────────────────────────────
    ax_rd = fig.add_subplot(gs[row, 1])
    ax_rd.fill_between(x[xz], 0, r1['rd'][xz], color=c1, alpha=0.40,
                       label='Resid S%d (In/P=%.2f)' % (r1['sample'], ip1))
    ax_rd.fill_between(x[xz], 0, r2['rd'][xz], color=c2, alpha=0.40,
                       label='Resid S%d (In/P=%.2f)' % (r2['sample'], ip2))
    ax_rd.plot(x[xz], r1['rd'][xz], color=c1, lw=1.5)
    ax_rd.plot(x[xz], r2['rd'][xz], color=c2, lw=1.5, ls='--')
    ax_rd.axvspan(420, 510, color='yellow', alpha=0.10)
    ax_rd.axvline(460, color='red', lw=0.8, ls=':', alpha=0.6, label='460nm')
    ax_rd.set_xlim(400, 560); ax_rd.set_ylim(bottom=0)
    ax_rd.set_xlabel('Wavelength (nm)', fontsize=9)
    ax_rd.set_ylabel('Residual', fontsize=9)
    ax_rd.legend(fontsize=7.5)
    ax_rd.tick_params(labelsize=8)
    ax_rd.set_title('배경 제거 후 잔류 신호', fontsize=9, fontweight='bold')

    dx = float(x[1]-x[0])
    int1 = float(np.sum(r1['rd'][xz])*dx)
    int2 = float(np.sum(r2['rd'][xz])*dx)
    ax_rd.text(0.97, 0.97,
               'Integral S%d: %.4f\nIntegral S%d: %.4f' % (r1['sample'],int1,r2['sample'],int2),
               transform=ax_rd.transAxes, fontsize=8, ha='right', va='top', family='monospace',
               bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9))

    # ── 오른쪽: In/P ratio bar + y_norm bar ──────────────────────────────
    ax_bar = fig.add_subplot(gs[row, 2])

    labels  = ['S%d\n%s' % (r1['sample'],r1['zone']), 'S%d\n%s' % (r2['sample'],r2['zone'])]
    x_pos   = np.array([0, 1])
    width   = 0.35

    ax_bar2 = ax_bar.twinx()

    b1 = ax_bar.bar(x_pos - width/2, [ip1, ip2], width,
                    color=[c1, c2], alpha=0.75, label='In/P ratio')
    b2 = ax_bar2.bar(x_pos + width/2, [r1['yn'], r2['yn']], width,
                     color=[c1, c2], alpha=0.40, hatch='//', label='y_norm')

    # 구간 경계선 (y_norm 축)
    for bnd, lab, lc in [(0.35,'Y_STEEP','#d62728'),(0.45,'Y_RAYLEIGH','#ff7f0e'),
                          (0.55,'Y_GRADUAL','#9467bd'),(0.65,'Y_QD_LIKE','#1f77b4')]:
        ax_bar2.axhline(bnd, color=lc, lw=1.0, ls='--', alpha=0.7)
        ax_bar2.text(1.55, bnd+0.005, lab, fontsize=6.5, color=lc, va='bottom')

    for bar, val in zip(b1, [ip1, ip2]):
        ax_bar.text(bar.get_x()+bar.get_width()/2, val+0.03, '%.2f'%val,
                    ha='center', va='bottom', fontsize=8, fontweight='bold')
    for bar, val in zip(b2, [r1['yn'], r2['yn']]):
        ax_bar2.text(bar.get_x()+bar.get_width()/2, val+0.005, '%.3f'%val,
                     ha='center', va='bottom', fontsize=8)

    ax_bar.set_xticks(x_pos); ax_bar.set_xticklabels(labels, fontsize=9)
    ax_bar.set_ylabel('In/P ratio', fontsize=9)
    ax_bar2.set_ylabel('y_norm', fontsize=9)
    ax_bar2.set_ylim(0, 1.05)
    ax_bar.set_ylim(0, max(ip1,ip2)*1.4+0.2)
    ax_bar.tick_params(labelsize=8); ax_bar2.tick_params(labelsize=8)

    lines1, labs1 = ax_bar.get_legend_handles_labels()
    lines2, labs2 = ax_bar2.get_legend_handles_labels()
    ax_bar.legend(lines1+lines2, labs1+labs2, fontsize=7.5, loc='upper left')
    ax_bar.set_title('In/P ratio  vs  y_norm', fontsize=9, fontweight='bold')

    # yn 차이 표시
    delta_yn = r2['yn'] - r1['yn']
    delta_ip = ip2 - ip1
    ax_bar.text(0.5, 0.02,
                'Δ(In/P) = %+.2f\nΔ(y_norm) = %+.3f' % (delta_ip, delta_yn),
                transform=ax_bar.transAxes, ha='center', va='bottom', fontsize=8.5,
                bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', alpha=0.9))

fig.suptitle(
    '합성 조건 유사 / 다른 Zone 샘플 쌍 비교  ─  In/P ratio 기준\n'
    '좌: Smoothed 스펙트럼  |  중: 잔류 신호  |  우: In/P ratio vs y_norm',
    fontsize=12, fontweight='bold')

out = 'fig/cross_zone_comparison2.png'
os.makedirs('fig', exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches='tight')
print('Saved:', out)
