# -*- coding: utf-8 -*-
"""
pareto_front.py
- 입력: BO pickle (예: '0824.pickle') — shap_pareto4.py와 동일한 파싱 로직 사용
- 목표 1: target (품질, 클수록 좋음)
- 목표 2: Reaction Time [s] (처리량 비용, 작을수록 좋음)
- 출력: ./shap_data/shap5/pareto_front.png, pareto_front.csv
"""

import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ========= 사용자 설정 (shap_pareto4.py와 동일) =========
PICKLE_PATH = "0824.pickle"
OUTDIR      = "shap_data/shap5"

REACTOR_VOLUME_UL = 4000.0
EXTRA_FLOW_UL_MIN = 0.0

# target 분포가 두 그룹으로 뚜렷이 갈라짐(양호 -0.03~-0.06 vs 실패 -0.34~-1.02).
# 짧은 RT에서 나온 실패 샘플이 극단값으로 Pareto front에 끼어드는 걸 막기 위한 품질 하한선.
MIN_TARGET = -0.1

KEY_PREHEAT   = "preHeat=Temperature"
KEY_HEAT      = "Heat=Temperature"
KEY_RATIO     = "AddSolution=Ratio"          # In:P ratio
KEY_TOTALFLOW = "AddSolution=TotalFlowrate"  # In+P total flow

AUTO_DENORM = True
PRANGE = {
    KEY_RATIO:     (1.2, 2.2),
    KEY_TOTALFLOW: (220.0, 720.0),
    KEY_PREHEAT:   (40.0, 60.0),
    KEY_HEAT:      (225.0, 250.0),
}

def maybe_denorm(val, key):
    if not AUTO_DENORM or key not in PRANGE:
        return val
    lo, hi = PRANGE[key]
    v = np.asarray(val, dtype=float)
    if np.nanmin(v) >= -1e-6 and np.nanmax(v) <= 1.0 + 1e-6:
        return lo + v * (hi - lo)
    return v

# ========= 1) pickle 로드 & (target, Reaction Time) 구성 =========
os.makedirs(OUTDIR, exist_ok=True)

with open(PICKLE_PATH, "rb") as f:
    bo = pickle.load(f)

if not hasattr(bo, "res") or len(bo.res) == 0:
    raise RuntimeError("model.res 가 비어 있습니다. pickle을 확인하세요.")

rows = []
for r in bo.res:
    if "target" not in r or "params" not in r:
        continue
    p = r["params"]
    if not all(k in p for k in [KEY_PREHEAT, KEY_HEAT, KEY_RATIO, KEY_TOTALFLOW]):
        continue

    ratio     = float(maybe_denorm(p[KEY_RATIO],     KEY_RATIO))
    totalflow = float(maybe_denorm(p[KEY_TOTALFLOW], KEY_TOTALFLOW))
    if ratio <= 0 or totalflow <= 0:
        continue

    total_q = totalflow + EXTRA_FLOW_UL_MIN
    rt_sec  = (REACTOR_VOLUME_UL / total_q) * 60.0

    rows.append({
        "Reaction Time (s)": rt_sec,
        "target":            float(r["target"]),
    })

if not rows:
    raise RuntimeError("필요한 파라미터 키가 있는 res 항목을 찾지 못했거나, 유효 샘플이 0개입니다.")

df = pd.DataFrame(rows)

# ========= 2) 비지배(non-dominated) 판정 =========
def non_dominated_mask(F: np.ndarray) -> np.ndarray:
    """F의 모든 열은 '작을수록 좋음(minimize)' 기준. 비지배(Pareto) 마스크 반환."""
    n = F.shape[0]
    nd = np.ones(n, dtype=bool)
    for i in range(n):
        better_or_equal = (F <= F[i]).all(axis=1)
        strictly_better  = (F <  F[i]).any(axis=1)
        dominated = better_or_equal & strictly_better
        dominated[i] = False
        if dominated.any():
            nd[i] = False
    return nd

# 품질 하한선 미달 샘플(주로 짧은 RT의 실패 샘플)은 Pareto 계산에서 제외
df["passed_quality_gate"] = df["target"] > MIN_TARGET
good = df[df["passed_quality_gate"]].copy()
failed = df[~df["passed_quality_gate"]].copy()

# target은 클수록 좋으므로 부호를 뒤집어 '작을수록 좋음' 기준으로 통일
F = np.column_stack([-good["target"].to_numpy(), good["Reaction Time (s)"].to_numpy()])
good["is_pareto"] = non_dominated_mask(F)
failed["is_pareto"] = False

df = pd.concat([good, failed]).sort_values("target", ascending=False)
df.to_csv(os.path.join(OUTDIR, "pareto_front.csv"), index=False)

# ========= 3) 시각화 =========
front = good[good["is_pareto"]].sort_values("Reaction Time (s)")
dominated_good = good[~good["is_pareto"]]

plt.figure(figsize=(7, 5.5))
plt.scatter(failed["Reaction Time (s)"], failed["target"],
            alpha=0.5, color="lightgray", marker="x", label=f"Below quality gate (target ≤ {MIN_TARGET})")
plt.scatter(dominated_good["Reaction Time (s)"], dominated_good["target"],
            alpha=0.5, color="steelblue", label="Dominated (passed gate)")
plt.scatter(front["Reaction Time (s)"], front["target"],
            s=70, color="crimson", zorder=3, label="Pareto front (passed gate)")
plt.plot(front["Reaction Time (s)"], front["target"],
         color="crimson", linewidth=1.5, zorder=2)

plt.xlabel("Reaction Time (s)  — lower is better (process cost)")
plt.ylabel("target  — higher is better (quality)")
plt.title("Pareto Front: Quality vs. Reaction Time (quality-gated)")
plt.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "pareto_front.png"), dpi=200)
plt.close()

print(f"전체 {len(df)}개 중 품질 하한 통과: {len(good)}개, 그 중 Pareto front: {good['is_pareto'].sum()}개")
print("Saved:")
print(f" - {os.path.join(OUTDIR, 'pareto_front.png')}")
print(f" - {os.path.join(OUTDIR, 'pareto_front.csv')}")
