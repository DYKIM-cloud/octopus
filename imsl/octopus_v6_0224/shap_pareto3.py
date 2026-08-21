# -*- coding: utf-8 -*-
"""
analyze_bo_csv_shap_logratio_rt.py
(주의) 파일명을 shap.py 로 저장하지 마세요. (라이브러리 shap 과 충돌합니다.)

입력: spectra_with_params_loss.csv (헤더 없음)
  - 1~7행: 메타 데이터( A열=키, B..열=샘플 값 ) → 샘플×특성 테이블로 전환
  - 8행~ : 스펙트럼( A열=wavelength, B..열=absorbance ) → 참고용 저장

출력 (./shap_data/):
  - shap_global_importance.csv
  - shap_values_per_sample.csv
  - shap_importance_bar.png
  - shap_summary_beeswarm.png
  - spectra_matrix.csv
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
import pickle
from sklearn.gaussian_process import GaussianProcessRegressor

# ========= 사용자 설정 =========
CSV_PATH    = "2508optimize\\spectra_with_params_loss.csv"  # CSV 경로
PICKLE_PATH = "1023core.pickle"                              # BO 피클(커널/alpha 재사용)
OUTDIR      = "shap_data/shap3"

# 반응로 체적 [µL] (4 mL)
REACTOR_VOLUME_UL = 4000.0
# In/P 외 다른 유량(용매 등)이 있으면 추가 [µL/min]
EXTRA_FLOW_UL_MIN = 0.0

# CSV 컬럼명
PARAM_COLS = [
    "preHeat=Temperature",
    "Heat=Temperature",
    "AddSolution=InP_Injectionrate",   # P
    "AddSolution=A_Injectionrate",     # In
]
LAM_COL  = "lambdamax"
PVR_COL  = "p_v ratio"                 # 공백 포함
LOSS_COL = "loss"                      # 0 = 최고, -1.5 = 최저 (값이 클수록 좋음)

os.makedirs(OUTDIR, exist_ok=True)

# ========= 0) BO pickle 로드 (GPR 커널/alpha 재사용) =========
with open(PICKLE_PATH, "rb") as f:
    model = pickle.load(f)

gp_base = getattr(model, "_gp", None)
if gp_base is None:
    raise RuntimeError("model._gp (GaussianProcessRegressor)가 없습니다. 피클을 확인하세요.")

# ========= 1) CSV 로드 & 블록 분리 =========
raw = pd.read_csv(CSV_PATH, header=None)
meta_rows = raw.iloc[0:7, :]   # 상단 7행: 메타
spec_rows = raw.iloc[7:, :]    # 8행~ : 스펙트럼

# ========= 2) 메타 → 샘플×특성 테이블 =========
meta_keys = meta_rows.iloc[:, 0].astype(str).str.strip().tolist()
meta_vals = meta_rows.iloc[:, 1:].copy()

# 샘플명 추정
sample_header_candidates = ["sample", "sample_id", "id", "name"]
header_idx = next((i for i, k in enumerate(meta_keys)
                   if any(c in k.lower() for c in sample_header_candidates)), None)
if header_idx is not None:
    sample_names = meta_vals.iloc[header_idx, :].astype(str).str.strip().tolist()
else:
    sample_names = [f"S{i+1}" for i in range(meta_vals.shape[1])]

samples_df = meta_vals.copy()
samples_df.index = meta_keys
samples_df.columns = sample_names
samples_df = samples_df.T.reset_index(drop=True)

# 숫자형 변환
for c in samples_df.columns:
    samples_df[c] = pd.to_numeric(samples_df[c], errors="ignore")

# 필수 컬럼 체크
missing = [c for c in PARAM_COLS + [LAM_COL, PVR_COL, LOSS_COL] if c not in samples_df.columns]
if missing:
    raise ValueError(f"필수 컬럼 누락: {missing}\n현재 열: {list(samples_df.columns)}")

# ========= 3) SHAP (KernelExplainer + GPR, log(In/P) + Reaction Time) =========

# 3-1) 원본 X,y
X_raw = samples_df[PARAM_COLS].apply(pd.to_numeric, errors="coerce")
y     = pd.to_numeric(samples_df[LOSS_COL], errors="coerce").values
valid = (~X_raw.isna().any(axis=1)) & (~np.isnan(y))
X_raw = X_raw.loc[valid].copy()
y     = y[valid]

if len(X_raw) < 5:
    raise ValueError("유효 샘플이 너무 적습니다(<5).")

X_phys = X_raw.astype(float)

# 3-2) In/P → log ratio, Reaction Time
P_COL  = "AddSolution=InP_Injectionrate"   # P
IN_COL = "AddSolution=A_Injectionrate"     # In

p_flow  = X_phys[P_COL].astype(float)
in_flow = X_phys[IN_COL].astype(float)

# log ratio (ln(In/P))
log_ratio = np.log(in_flow / p_flow)
# Reaction time (s)
total_q = in_flow + p_flow + EXTRA_FLOW_UL_MIN
rt_sec  = (REACTOR_VOLUME_UL / total_q) * 60.0

# 최종 피처 테이블
X_feat = pd.DataFrame({
    "log(In:P ratio)":    log_ratio,
    "Reaction Time (s)":  rt_sec,
    "preHeat=Temperature": X_phys["preHeat=Temperature"].astype(float),
    "Heat=Temperature":    X_phys["Heat=Temperature"].astype(float),
}, index=X_phys.index)

# 결측 제거
mask_valid2 = (~X_feat.isna().any(axis=1))
X_feat = X_feat.loc[mask_valid2]
y      = y[mask_valid2]

# ========= 4) Gaussian Process 구성 및 학습 =========
gp = GaussianProcessRegressor(
    kernel=gp_base.kernel,
    alpha=gp_base.alpha,
    n_restarts_optimizer=gp_base.n_restarts_optimizer,
    random_state=gp_base.random_state,
    normalize_y=True
)
gp.fit(X_feat.values, y)

# ========= 5) KernelExplainer 구성 및 SHAP 계산 =========
def gp_mean(Xin):
    Xin = np.asarray(Xin, dtype=float)
    if Xin.ndim == 1:
        Xin = Xin.reshape(1, -1)
    return gp.predict(Xin, return_std=False).ravel()

X_eval = X_feat.copy()
bg = shap.sample(X_eval, min(len(X_eval), 80), random_state=0)
explainer = shap.KernelExplainer(gp_mean, bg)
sv = explainer.shap_values(X_eval, nsamples=400 * X_eval.shape[1])

# ========= 6) 순서 및 y축 라벨 적용 =========
ordered_cols   = ["log(In:P ratio)", "Reaction Time (s)", "preHeat=Temperature", "Heat=Temperature"]
ordered_labels = ["log(In:P ratio)", "Reaction Time (s)", "Preheat Temperature", "Heat Temperature"]

sv_ordered = np.column_stack([sv[:, X_eval.columns.get_loc(c)] for c in ordered_cols])
X_ordered  = X_eval[ordered_cols]

# ========= 7) 저장 및 시각화 =========
imp = pd.DataFrame({
    "feature": ordered_labels,
    "mean_abs_SHAP": np.abs(sv_ordered).mean(axis=0)
})
imp.to_csv(os.path.join(OUTDIR, "shap_global_importance.csv"), index=False)
pd.DataFrame(sv_ordered, columns=ordered_labels, index=X_ordered.index).to_csv(
    os.path.join(OUTDIR, "shap_values_per_sample.csv")
)

# 전역 중요도 막대
plt.figure(figsize=(6, max(2, 0.35*len(imp))))
plt.barh(imp["feature"][::-1], imp["mean_abs_SHAP"][::-1])
plt.xlabel("mean(|SHAP|)")
plt.title("Global Feature Importance (GPR + KernelExplainer on loss)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_importance_bar.png"), dpi=200)
plt.close()

# Beeswarm (요청한 순서)
plt.figure()
shap.summary_plot(sv_ordered, X_ordered, feature_names=ordered_labels, show=False)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_summary_beeswarm.png"),
            dpi=200, bbox_inches="tight")
plt.close()

# ========= 8) 스펙트럼 행렬 저장 =========
wavelength = pd.to_numeric(spec_rows.iloc[:, 0], errors="coerce").dropna().values
absorb_mat = spec_rows.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
absorb_mat.columns = sample_names[:absorb_mat.shape[1]]
absorb_mat.insert(0, "wavelength", wavelength[:len(absorb_mat)])
absorb_mat.to_csv(os.path.join(OUTDIR, "spectra_matrix.csv"), index=False)

print("Saved in ./shap_data/:")
print(" - shap_global_importance.csv")
print(" - shap_values_per_sample.csv")
print(" - shap_importance_bar.png")
print(" - shap_summary_beeswarm.png")
print(" - spectra_matrix.csv")
