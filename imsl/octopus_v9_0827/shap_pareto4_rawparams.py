# -*- coding: utf-8 -*-
"""
shap_pareto4_rawparams.py
- shap_pareto4.py와 동일한 파이프라인이지만, log(In:P ratio)/Reaction Time으로 변환하지 않고
  원본 파라미터(Ratio, TotalFlowrate, Preheat, Heat) 그대로 4D GPR을 학습해 SHAP을 계산.
- 입력: BO pickle (예: '0824.pickle')
- 출력: ./shap_data/shap5_rawparams/ 내 CSV/PNG (SHAP)
"""

import os
import pickle
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
from sklearn.preprocessing import StandardScaler

# ========= 사용자 설정 =========
PICKLE_PATH = "0824.pickle"
OUTDIR      = "shap_data/shap5_rawparams"

# pickle 내부 params 키 이름(정확히 일치해야 함)
KEY_PREHEAT   = "preHeat=Temperature"
KEY_HEAT      = "Heat=Temperature"
KEY_RATIO     = "AddSolution=Ratio"          # In:P ratio
KEY_TOTALFLOW = "AddSolution=TotalFlowrate"  # In+P total flow

# (선택) 비정규화 범위: pickle이 0~1 정규화인 경우 자동 복원에 사용
AUTO_DENORM = True
PRANGE = {
    KEY_RATIO:     (1.2, 2.2),      # In:P ratio [-]
    KEY_TOTALFLOW: (220.0, 720.0), # In+P total flow [µL/min]
    KEY_PREHEAT:   (40.0, 60.0),    # [°C]
    KEY_HEAT:      (225.0, 250.0),  # [°C]
}

# ========= 유틸 =========
def maybe_denorm(val, key):
    """값이 0~1 사이에 대부분 있고 PRANGE가 있으면 (min,max)로 복원."""
    if not AUTO_DENORM or key not in PRANGE:
        return val
    lo, hi = PRANGE[key]
    v = np.asarray(val, dtype=float)
    if np.nanmin(v) >= -1e-6 and np.nanmax(v) <= 1.0 + 1e-6:
        return lo + v * (hi - lo)
    return v

# ========= 1) pickle 로드 & (X,y) 구성 — 원본 파라미터 그대로 =========
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

    preheat    = float(maybe_denorm(p[KEY_PREHEAT],   KEY_PREHEAT))
    heat       = float(maybe_denorm(p[KEY_HEAT],      KEY_HEAT))
    ratio      = float(maybe_denorm(p[KEY_RATIO],     KEY_RATIO))
    totalflow  = float(maybe_denorm(p[KEY_TOTALFLOW], KEY_TOTALFLOW))

    rows.append({
        "In:P Ratio":          ratio,
        "Total Flowrate":      totalflow,
        "preHeat=Temperature": preheat,
        "Heat=Temperature":    heat,
        "target":              float(r["target"])
    })

if not rows:
    raise RuntimeError("필요한 파라미터 키가 있는 res 항목을 찾지 못했거나, 유효 샘플이 0개입니다.")

df = pd.DataFrame(rows)
if len(df) < 5:
    raise RuntimeError("유효 샘플이 너무 적습니다(<5). res/전처리를 점검하세요.")

X_df = df[["In:P Ratio", "Total Flowrate", "preHeat=Temperature", "Heat=Temperature"]].copy()
y    = df["target"].to_numpy(dtype=float)

# ========= 2) 새 4D GPR 학습 (원본 파라미터 기준) =========
# Total Flowrate(수백)와 Heat/Preheat(수십), Ratio(~1~2)의 스케일 차이가 커서
# 표준화 없이 학습하면 Matern length_scale이 degenerate되는 문제가 있었음(shap_pareto4.py 참고) -> 동일하게 표준화 적용
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_df.values)

kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=[1.0, 1.0, 1.0, 1.0], length_scale_bounds=(1e-2, 1e2), nu=2.5) + WhiteKernel(noise_level=1e-2)
gpr = GaussianProcessRegressor(kernel=kernel, normalize_y=True, n_restarts_optimizer=10, random_state=42)
gpr.fit(X_scaled, y)

# ========= 3) KernelExplainer로 SHAP 계산 =========
def gpr_mean(Xin):
    Xin = np.asarray(Xin, dtype=float)
    if Xin.ndim == 1:
        Xin = Xin.reshape(1, -1)
    Xin_scaled = scaler.transform(Xin)
    return gpr.predict(Xin_scaled, return_std=False).ravel()

bg = shap.sample(X_df, min(len(X_df), 80), random_state=0)
explainer = shap.KernelExplainer(gpr_mean, bg)

sv = explainer.shap_values(X_df, nsamples=1600)  # shape: (n_samples, 4)

# ========= 4) 정렬 & 저장/시각화 =========
rename = {
    "preHeat=Temperature": "Preheat Temperature",
    "Heat=Temperature":    "Heat Temperature",
    "In:P Ratio":          "In:P Ratio",
    "Total Flowrate":      "Total Flowrate",
}

mean_abs = np.abs(sv).mean(axis=0)
order_idx = np.argsort(mean_abs)[::-1]

sorted_cols   = [X_df.columns[i] for i in order_idx]
sorted_labels = [rename.get(c, c) for c in sorted_cols]
sv_sorted     = sv[:, order_idx]
X_sorted_np   = X_df[sorted_cols].to_numpy()

imp_df = pd.DataFrame({"feature": sorted_labels, "mean_abs_SHAP": mean_abs[order_idx]})
imp_df.to_csv(os.path.join(OUTDIR, "shap_global_importance.csv"), index=False)
pd.DataFrame(sv_sorted, columns=sorted_labels).to_csv(
    os.path.join(OUTDIR, "shap_values_per_sample.csv"), index=False
)

plt.figure()
shap.summary_plot(
    sv_sorted,
    X_sorted_np,
    feature_names=sorted_labels,
    sort=False,
    max_display=len(sorted_labels),
    show=False
)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_summary_beeswarm.png"),
            dpi=200, bbox_inches="tight")
plt.close()

plt.figure(figsize=(max(6, 1.2*len(sorted_labels)), 4))
plt.bar(sorted_labels, mean_abs[order_idx])
plt.ylabel("mean(|SHAP|)")
plt.xticks(rotation=20, ha="right")
plt.title("Global Feature Importance (raw params, sorted)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_importance_bar.png"), dpi=200)
plt.close()

print("Saved in", OUTDIR, ":")
print(" - shap_global_importance.csv")
print(" - shap_values_per_sample.csv")
print(" - shap_summary_beeswarm.png")
print(" - shap_importance_bar.png")
