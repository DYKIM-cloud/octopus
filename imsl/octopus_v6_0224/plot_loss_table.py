import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df = pd.read_csv('loss_comparison_table.csv', encoding='utf-8-sig')

# 컬럼 정리
df['branch_short'] = df['branch'].map({'peak': 'PEAK', 'no-peak': 'no-peak'})
df['lm_resid']     = df['lm_resid'].fillna('-')
df['n_fit']        = df['n_fit'].fillna('-')
df['flat']         = df['flat'].fillna('-')
df['amp']          = df['amp'].fillna('-')
df['pos']          = df['pos'].fillna('-')

# 표시용 컬럼 선택
cols = ['Sample', 'branch_short', 'lm_csv', 'pv_csv',
        'loss_old', 'loss_new', 'diff',
        'n_fit', 'flat', 'amp', 'pos', 'lm_resid']
headers = ['#', 'Branch', 'lm\n(nm)', 'pv\nratio',
           'loss\nOLD', 'loss\nNEW', 'diff\n(new-old)',
           'n_fit', 'flat\nscore', 'amp\nscore', 'pos\nscore', 'lm\nresid']

table_data = df[cols].values.tolist()

# ── 행 당 색상 결정 ──────────────────────────────────────────────
def row_color(row):
    branch = row[1]
    diff   = row[6]
    if branch == 'PEAK':
        return '#dbeafe'          # 파란색 (peak)
    try:
        d = float(diff)
        if d > 0.05:   return '#dcfce7'   # 초록 (개선)
        if d < -0.05:  return '#fee2e2'   # 빨간 (더 엄격)
        return '#f9fafb'                   # 회색 (거의 동일)
    except:
        return '#f9fafb'

# ── 그림 ─────────────────────────────────────────────────────────
n_rows = len(table_data)
row_h  = 0.22          # 행 높이 (인치)
fig_h  = row_h * (n_rows + 2) + 1.5
fig, ax = plt.subplots(figsize=(20, fig_h))
ax.axis('off')

col_widths = [0.042, 0.055, 0.055, 0.055,
              0.065, 0.065, 0.075,
              0.055, 0.065, 0.065, 0.065, 0.065]

tbl = ax.table(
    cellText=table_data,
    colLabels=headers,
    cellLoc='center',
    loc='upper center',
    colWidths=col_widths,
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(7.2)
tbl.scale(1, 1.28)

# 헤더 스타일
for j in range(len(headers)):
    cell = tbl[0, j]
    cell.set_facecolor('#1e3a5f')
    cell.set_text_props(color='white', fontweight='bold', fontsize=7.5)
    cell.set_edgecolor('#4a90d9')

# 데이터 행 스타일
for i, row in enumerate(table_data):
    fc = row_color(row)
    for j in range(len(headers)):
        cell = tbl[i+1, j]
        cell.set_facecolor(fc)
        cell.set_edgecolor('#d1d5db')

        # diff 컬럼 텍스트 색상
        if j == 6:
            try:
                d = float(row[j])
                cell.set_text_props(color='#15803d' if d > 0 else '#b91c1c',
                                    fontweight='bold')
            except:
                pass
        # loss 컬럼 색상
        if j in [4, 5]:
            try:
                v = float(row[j])
                if v >= -0.31:
                    cell.set_text_props(color='#166534', fontweight='bold')
                elif v <= -1.45:
                    cell.set_text_props(color='#991b1b', fontweight='bold')
            except:
                pass
        # branch 컬럼
        if j == 1 and str(row[j]) == 'PEAK':
            cell.set_text_props(color='#1d4ed8', fontweight='bold')

# 타이틀 및 범례
fig.suptitle(
    'Loss Comparison Table — All 152 Samples\n'
    'OLD: current y_norm branch  |  NEW: proposed (flat_score + amp_score * pos_score)\n'
    'Peak branch (S34, S49, S120): loss unchanged',
    fontsize=11, fontweight='bold', y=0.995
)

# 범례 박스
legend_ax = fig.add_axes([0.01, 0.002, 0.98, 0.018])
legend_ax.axis('off')
legend_items = [
    ('#dbeafe', 'PEAK branch (no change)'),
    ('#dcfce7', 'diff > +0.05: new loss higher (less penalty, improved)'),
    ('#f9fafb', '-0.05 ≤ diff ≤ +0.05: nearly same'),
    ('#fee2e2', 'diff < -0.05: new loss lower (more penalty, stricter)'),
]
x_pos = 0.02
for fc, label in legend_items:
    legend_ax.add_patch(plt.Rectangle((x_pos, 0.1), 0.018, 0.8,
                                       transform=legend_ax.transAxes,
                                       facecolor=fc, edgecolor='#aaa', linewidth=0.8,
                                       clip_on=False))
    legend_ax.text(x_pos + 0.022, 0.5, label,
                   transform=legend_ax.transAxes, fontsize=8, va='center')
    x_pos += 0.26

plt.savefig('loss_full_table.png', dpi=130, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print('saved: loss_full_table.png')
