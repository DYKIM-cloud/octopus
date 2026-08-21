# -*- coding: utf-8 -*-
"""
analyze_bo_csv_incremental_pareto.py

입력: spectra_with_params_loss.csv (헤더 없음)
  - 1~7행: 메타 데이터( A열=키, B..열=샘플 값 ) → 샘플×특성 테이블로 전환
  - 8행~ : 스펙트럼( A열=wavelength, B..열=absorbance ) → 참고용 저장

출력 (./shap/):
  - shap_global_importance.csv
  - shap_values_per_sample.csv              # 모든 샘플 대상
  - shap_importance_bar.png                 # 전역 중요도 막대
  - shap_summary_beeswarm.png               # ★ 요청하신 beeswarm 시각화
  - pareto_front_observed.png               # 전체 샘플
  - pareto_front_step_0030.png, ...        # 증분 프런트(10개씩 증가)
  - spectra_matrix.csv
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import shap
import pickle

# ========= 사용자 설정 =========
CSV_PATH   = "2508optimize\\spectra_with_params_loss2.csv"
OUTDIR     = "shap_data"
TARGET_LAM = 490.0
TARGET_PVR = 2.0
START_N    = 30         # Pareto 계산 시작 샘플 수
STEP_N     = 10         # 증가 단위
ELLIPSE_N_STD = 1.5     # 타원 크기(표준편차 배수)
with open("{}".format("1022core_3.pickle"), 'rb') as f: 
        model = pickle.load(f)
# 정확한 컬럼명
PARAM_COLS = [
    "preHeat=Temperature",
    "Heat=Temperature",
    "AddSolution=InP_Injectionrate",
    "AddSolution=A_Injectionrate",
]
LAM_COL  = "lambdamax"
PVR_COL  = "p_v ratio"   # 공백 포함
LOSS_COL = "loss"        # 0 = 최고, -1.5 = 최저 (값이 클수록 좋음)

os.makedirs(OUTDIR, exist_ok=True)

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

# ========= 3) SHAP (모든 샘플 저장) =========
X = samples_df[PARAM_COLS].apply(pd.to_numeric, errors="coerce")
y = pd.to_numeric(samples_df[LOSS_COL], errors="coerce").values
mask_valid = (~X.isna().any(axis=1)) & (~np.isnan(y))
X = X.loc[mask_valid]
y = y[mask_valid]

if len(X) < 5:
    raise ValueError("유효 샘플이 너무 적습니다(<5).")

# 학습은 간단히 train/test로, SHAP 계산은 전체 X로 수행
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=min(0.25, max(0.1, 0.25)), random_state=42
)
rf = RandomForestRegressor(n_estimators=500, random_state=42)
rf.fit(X_train, y_train)

explainer = shap.TreeExplainer(rf)
X_eval = X.copy()  # ★ 모든 샘플에 대해 SHAP
sv = explainer.shap_values(X_eval)  # (n_all, n_features)

# 저장: 전역 중요도 / 샘플×특징 SHAP
imp = pd.DataFrame({
    "feature": X.columns,
    "mean_abs_SHAP": np.abs(sv).mean(axis=0)
}).sort_values("mean_abs_SHAP", ascending=False)
imp.to_csv(os.path.join(OUTDIR, "shap_global_importance.csv"), index=False)
pd.DataFrame(sv, columns=X.columns, index=X_eval.index).to_csv(
    os.path.join(OUTDIR, "shap_values_per_sample.csv")
)

# 전역 중요도 막대
plt.figure(figsize=(6, max(2, 0.35*len(imp))))
plt.barh(imp["feature"][::-1], imp["mean_abs_SHAP"][::-1])
plt.xlabel("mean(|SHAP|)")
plt.title("Global Feature Importance (RandomForest surrogate on loss)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_importance_bar.png"), dpi=200)
plt.close()

# ★ SHAP beeswarm(요청한 스타일) — 색상바 포함, show=False 후 저장
plt.figure()  # 새로운 figure
shap.summary_plot(sv, X_eval, feature_names=X.columns, show=False)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_summary_beeswarm.png"), dpi=200, bbox_inches="tight")
plt.close()

# ========= 4) Pareto helper =========
def non_dominated_mask(F: np.ndarray) -> np.ndarray:
    """모두 minimize 기준의 값에서 비지배 마스크"""
    n = F.shape[0]
    nd = np.ones(n, dtype=bool)
    for i in range(n):
        if not nd[i]:
            continue
        better_or_equal = (F <= F[i]).all(axis=1)
        strictly_better = (F <  F[i]).any(axis=1)
        dominated = better_or_equal & strictly_better
        dominated[i] = False
        if dominated.any():
            nd[i] = False
    return nd

def fit_cov_ellipse(points: np.ndarray, n_std: float = 1.5, num=200):
    """2D 점들의 공분산 타원 좌표 반환"""
    if points.shape[0] < 2:
        return None
    mu = points.mean(axis=0)
    cov = np.cov(points.T)
    if not np.all(np.isfinite(cov)) or np.linalg.matrix_rank(cov) < 2:
        return None
    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, 1e-12)
    axes = n_std * np.sqrt(vals)
    t = np.linspace(0, 2*np.pi, num)
    circle = np.stack([np.cos(t), np.sin(t)], axis=0)
    ellipse = (vecs @ (axes[:, None] * circle)).T + mu
    return ellipse

def plot_pareto_with_ellipse(lam_vals, pvr_vals, target_lam, target_pvr, out_png, title_suffix=""):
    """편차 minimize 기준 Pareto + 타원 플롯 저장"""
    lam = np.asarray(lam_vals, dtype=float)
    pvr = np.asarray(pvr_vals, dtype=float)
    mask = np.isfinite(lam) & np.isfinite(pvr)
    lam, pvr = lam[mask], pvr[mask]
    if len(lam) == 0:
        return

    dev = np.column_stack([np.abs(lam - target_lam), np.abs(pvr - target_pvr)])
    nd = non_dominated_mask(dev)
    front_pts = np.column_stack([lam[nd], pvr[nd]])

    plt.figure()
    plt.scatter(lam, pvr, alpha=0.35, label="All")
    if front_pts.shape[0] >= 1:
        plt.scatter(front_pts[:,0], front_pts[:,1], s=60, label="Pareto front")
        if front_pts.shape[0] > 1:
            ord_idx = np.argsort(front_pts[:,0])
            plt.plot(front_pts[ord_idx,0], front_pts[ord_idx,1], linewidth=2)
        ell = fit_cov_ellipse(front_pts, n_std=ELLIPSE_N_STD)
        if ell is not None:
            plt.plot(ell[:,0], ell[:,1], linestyle="--", linewidth=1.8, label=f"{ELLIPSE_N_STD}σ ellipse")

    plt.xlabel(f"lambdamax (target {target_lam})")
    plt.ylabel(f"p_v ratio (target {target_pvr})")
    ttl = "Pareto Front (deviation-minimizing)"
    if title_suffix:
        ttl += f" — {title_suffix}"
    plt.title(ttl)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()

# ========= 5) Pareto: 30개 시작 → 10개씩 증가 → 전체 =========
lam_all = pd.to_numeric(samples_df[LAM_COL], errors="coerce").values
pvr_all = pd.to_numeric(samples_df[PVR_COL], errors="coerce").values
N = len(lam_all)

steps = list(range(START_N, N, STEP_N))
if len(steps) == 0 or steps[-1] != N:
    steps.append(N)

for n in steps:
    lam_n = lam_all[:n]
    pvr_n = pvr_all[:n]
    out_png = os.path.join(OUTDIR, f"pareto_front_step_{n:04d}.png")
    plot_pareto_with_ellipse(lam_n, pvr_n, TARGET_LAM, TARGET_PVR, out_png,
                             title_suffix=f"{n} samples")

# 최종(전체) 프런트
plot_pareto_with_ellipse(lam_all, pvr_all, TARGET_LAM, TARGET_PVR,
                         os.path.join(OUTDIR, "pareto_front_observed.png"),
                         title_suffix="All samples")

# ========= 6) 스펙트럼 행렬 저장(옵션) =========
wavelength = pd.to_numeric(spec_rows.iloc[:, 0], errors="coerce").dropna().values
absorb_mat = spec_rows.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
absorb_mat.columns = sample_names[:absorb_mat.shape[1]]
absorb_mat.insert(0, "wavelength", wavelength[:len(absorb_mat)])
absorb_mat.to_csv(os.path.join(OUTDIR, "spectra_matrix.csv"), index=False)

print("Saved in ./shap/:")
print(" - shap_global_importance.csv")
print(" - shap_values_per_sample.csv")
print(" - shap_importance_bar.png")
print(" - shap_summary_beeswarm.png")
print(" - pareto_front_observed.png")
print(" - pareto_front_step_XXXX.png (incremental)")
print(" - spectra_matrix.csv")
