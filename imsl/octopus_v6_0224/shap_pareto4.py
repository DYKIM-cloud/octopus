# -*- coding: utf-8 -*-
"""
analyze_bo_pickle_shap_logratio_rt_preheat_heat_sorted.py
- 입력: BO pickle (예: '1022core.pickle')
- 출력: ./shap_data/ 내 CSV/PNG (SHAP)
주의: 파일명을 'shap.py'로 저장하지 마세요. (라이브러리 shap 과 충돌)
"""

import os
import pickle
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel

# ========= 사용자 설정 =========
PICKLE_PATH = "1023core.pickle"   # BO 피클 경로
OUTDIR      = "shap_data/shap4"

# 반응로 체적 [µL] (4 mL)
REACTOR_VOLUME_UL = 4000.0
# In/P 외 용매 유량 등 추가가 있으면 여기에 (µL/min). 없으면 0.
EXTRA_FLOW_UL_MIN = 0.0

# pickle 내부 params 키 이름(정확히 일치해야 함)
KEY_PREHEAT = "preHeat=Temperature"
KEY_HEAT    = "Heat=Temperature"
KEY_P       = "AddSolution=InP_Injectionrate"   # P flow
KEY_IN      = "AddSolution=A_Injectionrate"     # In flow

# (선택) 비정규화 범위: pickle이 0~1 정규화인 경우 자동 복원에 사용
AUTO_DENORM = True
PRANGE = {
    KEY_IN:  (100.0, 1250.0),  # In flow [µL/min]
    KEY_P:   (100.0, 1250.0),  # P flow  [µL/min]
    KEY_PREHEAT: (40.0, 60.0), # [°C]
    KEY_HEAT:    (200.0, 250.0) # [°C]
}

# ========= 유틸 =========
def maybe_denorm(val, key):
    """값이 0~1 사이에 대부분 있고 PRANGE가 있으면 (min,max)로 복원."""
    if not AUTO_DENORM or key not in PRANGE:
        return val
    lo, hi = PRANGE[key]
    v = np.asarray(val, dtype=float)
    # 0~1 범위로 '보이는지' 간단 체크
    if np.nanmin(v) >= -1e-6 and np.nanmax(v) <= 1.0 + 1e-6:
        return lo + v * (hi - lo)
    return v

# ========= 1) pickle 로드 & (X,y) 구성 =========
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
    if not all(k in p for k in [KEY_PREHEAT, KEY_HEAT, KEY_P, KEY_IN]):
        continue

    # 원 값 또는 0~1 정규화 → 필요 시 비정규화
    preheat = float(maybe_denorm(p[KEY_PREHEAT], KEY_PREHEAT))
    heat    = float(maybe_denorm(p[KEY_HEAT],    KEY_HEAT))
    p_flow  = float(maybe_denorm(p[KEY_P],       KEY_P))
    in_flow = float(maybe_denorm(p[KEY_IN],      KEY_IN))

    # 방어: 분모 0 방지 (실제 공정상 0이 아니더라도 수치 안전망)
    if p_flow <= 0 or in_flow <= 0:
        # 건너뛰거나, 아주 작은 값으로 대체
        # 여기서는 샘플을 제외
        continue

    # 파생 피처 1) log(In/P)
    log_ratio = np.log(in_flow / p_flow)

    # 파생 피처 2) Reaction Time (s) = (V / (In + P + extra)) * 60
    total_q = in_flow + p_flow + EXTRA_FLOW_UL_MIN
    rt_sec  = (REACTOR_VOLUME_UL / total_q) * 60.0

    rows.append({
        "log(In:P ratio)":     log_ratio,
        "Reaction Time (s)":   rt_sec,
        "preHeat=Temperature": preheat,
        "Heat=Temperature":    heat,
        "target":              float(r["target"])
    })

if not rows:
    raise RuntimeError("필요한 파라미터 키가 있는 res 항목을 찾지 못했거나, 유효 샘플이 0개입니다.")

df = pd.DataFrame(rows)
if len(df) < 5:
    raise RuntimeError("유효 샘플이 너무 적습니다(<5). res/전처리를 점검하세요.")

X_df = df[["log(In:P ratio)", "Reaction Time (s)", "preHeat=Temperature", "Heat=Temperature"]].copy()
y    = df["target"].to_numpy(dtype=float)

# ========= 2) 새 4D GPR 학습 =========
# 원 _gp는 원피처(Preheat, Heat, P, In) 기준이므로, 파생 4D(log ratio, RT, Preheat, Heat)로 새로 학습
kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=[1.0, 1.0, 1.0, 1.0], nu=2.5) + WhiteKernel(noise_level=1e-2)
gpr = GaussianProcessRegressor(kernel=kernel, normalize_y=True, n_restarts_optimizer=10, random_state=42)
gpr.fit(X_df.values, y)

# ========= 3) KernelExplainer로 SHAP 계산 =========
def gpr_mean(Xin):
    Xin = np.asarray(Xin, dtype=float)
    if Xin.ndim == 1:
        Xin = Xin.reshape(1, -1)
    return gpr.predict(Xin, return_std=False).ravel()

# background: 50~100 권장
bg = shap.sample(X_df, min(len(X_df), 80), random_state=0)
explainer = shap.KernelExplainer(gpr_mean, bg)

# nsamples: 특징 수 × 400 (여기선 4 × 400 = 1600)
sv = explainer.shap_values(X_df, nsamples=1600)  # shape: (n_samples, 4)

# ========= 4) 정렬 & 저장/시각화 =========
# 라벨 가독화 매핑
rename = {
    "preHeat=Temperature": "Preheat Temperature",
    "Heat=Temperature":    "Heat Temperature",
    "Reaction Time (s)":   "Reaction Time (s)",
    "log(In:P ratio)":     "log(In:P ratio)",
}
cols = list(X_df.columns)
# ----- compute global importance -----
# 1) 중요도 기반 정렬 (mean(|SHAP|) 내림차순)
mean_abs = np.abs(sv).mean(axis=0)                 # sv: (n_samples, n_features)
order_idx = np.argsort(mean_abs)[::-1]

sorted_cols   = [X_df.columns[i] for i in order_idx]
sorted_labels = [rename.get(c, c) for c in sorted_cols]
sv_sorted     = sv[:, order_idx]
X_sorted_np   = X_df[sorted_cols].to_numpy()       # ★ DataFrame -> numpy 로 변환

# 2) CSV 저장 (정렬 반영)
imp_df = pd.DataFrame({"feature": sorted_labels, "mean_abs_SHAP": mean_abs[order_idx]})
imp_df.to_csv(os.path.join(OUTDIR, "shap_global_importance.csv"), index=False)
pd.DataFrame(sv_sorted, columns=sorted_labels).to_csv(
    os.path.join(OUTDIR, "shap_values_per_sample.csv"), index=False
)

# 3) Beeswarm (정렬 고정: numpy + sort=False + max_display)
plt.figure()
shap.summary_plot(
    sv_sorted,                 # (n, d) SHAP
    X_sorted_np,               # ★ numpy array (DataFrame 금지)
    feature_names=sorted_labels,
    sort=False,                # ★ SHAP이 다시 정렬하지 못하게
    max_display=len(sorted_labels),  # ★ 표시 개수 = 전체
    show=False
)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_summary_beeswarm.png"),
            dpi=200, bbox_inches="tight")
plt.close()

# 4) 중요도 bar (세로 막대: x=feature, y=importance)
plt.figure(figsize=(max(6, 1.2*len(sorted_labels)), 4))
plt.bar(sorted_labels, mean_abs[order_idx])
plt.ylabel("mean(|SHAP|)")
plt.xticks(rotation=20, ha="right")
plt.title("Global Feature Importance (sorted)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_importance_bar.png"), dpi=200)
plt.close()


print("Saved in ./shap_data/:")
print(" - shap_global_importance.csv")
print(" - shap_values_per_sample.csv")
print(" - shap_summary_beeswarm.png")
print(" - shap_importance_bar.png")
