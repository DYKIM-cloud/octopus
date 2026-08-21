# -*- coding: utf-8 -*-
import os, pickle
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.exceptions import NotFittedError

PICKLE_PATH = "1022core_3.pickle"
OUTDIR = "shap_data"

os.makedirs(OUTDIR, exist_ok=True)

# 1) BO 로드
with open(PICKLE_PATH, "rb") as f:
    bo = pickle.load(f)

# 2) 파라미터 순서(BO가 사용한 정규화 좌표의 순서!) 확정
try:
    param_names = list(bo._space.keys)
except Exception:
    # 최후의 보루: 첫 res의 키를 정렬(권장 X)
    param_names = sorted(list(bo.res[0]["params"].keys()))

# 3) 관측 X, y 추출 (정규화 좌표)
X_obs = np.array([[r["params"][k] for k in param_names] for r in bo.res], dtype=float)
y_obs = np.array([r["target"] for r in bo.res], dtype=float)

print("y stats:", float(y_obs.min()), float(y_obs.max()), float(y_obs.std()))

# 4) GP 가져오기 및 '학습 상태' 확인 → 미학습이면 우리가 fit
gp = getattr(bo, "_gp", None)
assert gp is not None, "bo._gp(GaussianProcessRegressor)를 찾지 못했습니다."

# sklearn GPR은 fit 후에만 X_train_/y_train_ 속성이 생깁니다.
is_fitted = False
try:
    _ = gp.X_train_
    is_fitted = True
except AttributeError:
    is_fitted = False

if not is_fitted:
    # 필요시, y 스케일 안정화를 위해 normalize_y=True로 한 번 더 감싸 학습해도 됩니다.
    # (기존 gp의 하이퍼파라미터/커널을 유지한 채 fit만 수행)
    gp = GaussianProcessRegressor(
        kernel=gp.kernel,            # bo._gp에 설정된 커널 재사용
        alpha=gp.alpha,
        n_restarts_optimizer=gp.n_restarts_optimizer,
        random_state=gp.random_state,
        normalize_y=True             # ← 권장: y가 음수/작은 범위일 때 안정화
    )
    gp.fit(X_obs, y_obs)
    print("GP re-fit done. X_train_.shape:", gp.X_train_.shape)
else:
    # 이미 학습된 경우에도, 예측 분산을 점검
    print("GP already fitted. X_train_.shape:", gp.X_train_.shape)

# 5) 평균 예측이 상수인지 점검 (정상이라면 std > 0)
y_pred = gp.predict(X_obs, return_std=False).ravel()
print("pred range:", float(y_pred.min()), float(y_pred.max()), "std:", float(y_pred.std()))

# 만약 여전히 std == 0이라면:
# - y_obs가 모두 동일하거나,
# - X_obs가 모두 동일/극히 저변동,
# - 파라미터 순서가 어긋났을 수 있습니다. (param_names 재점검)

# 6) KernelExplainer 설정 (background 축소, nsamples 충분히)
X_df = pd.DataFrame(X_obs, columns=param_names)

# background: 50~100 권장 (너무 크면 값이 죽습니다)
BG = min(len(X_df), 80)
bg = shap.sample(X_df, BG, random_state=0)

def gp_mean(X):
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    return gp.predict(X, return_std=False).ravel()

explainer = shap.KernelExplainer(gp_mean, bg)

# 평가 대상: 전부 또는 제한
N_EVAL = min(len(X_df), 800)
X_eval = X_df.iloc[:N_EVAL].copy()

# nsamples: 특징 수 * 300~500 정도 권장 (여기선 400×특징수)
nsamp = 400 * X_eval.shape[1]
sv = explainer.shap_values(X_eval, nsamples=nsamp)

# 7) y축 라벨 변경 후 저장
rename = {
    "preHeat=Temperature": "Preheat Temperature",
    "Heat=Temperature": "Heat Temperature",
    "AddSolution=InP_Injectionrate": "P injection rate",
    "AddSolution=A_Injectionrate": "In injection rate",
}
feat_labels = [rename.get(c, c) for c in X_eval.columns]

# CSV
imp = pd.DataFrame({
    "feature": feat_labels,
    "mean_abs_SHAP": np.abs(sv).mean(axis=0)
}).sort_values("mean_abs_SHAP", ascending=False)
imp.to_csv(os.path.join(OUTDIR, "shap_global_importance_from_BO.csv"), index=False)

pd.DataFrame(sv, columns=feat_labels, index=X_eval.index).to_csv(
    os.path.join(OUTDIR, "shap_values_per_sample_from_BO.csv")
)

# Beeswarm
plt.figure()
shap.summary_plot(sv, X_eval, feature_names=feat_labels, show=False)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "shap_summary_beeswarm_from_BO_renamed.png"),
            dpi=200, bbox_inches="tight")
plt.close()

print("Saved in ./shap/:")
print(" - shap_global_importance_from_BO.csv")
print(" - shap_values_per_sample_from_BO.csv")
print(" - shap_summary_beeswarm_from_BO_renamed.png")
# SHAP 값 sv와 평가 데이터 X_eval이 이미 계산된 상태라고 가정
# imp_df: mean(|SHAP|) 기준으로 정렬된 중요도 DataFrame
imp_df = pd.DataFrame({
    "feature": X_eval.columns,
    "mean_abs_SHAP": np.abs(sv).mean(axis=0)
}).sort_values("mean_abs_SHAP", ascending=False)

# 피처 순서 (중요도 높은 순)
sorted_features = imp_df["feature"].tolist()

# 보기 좋은 이름 매핑
rename = {
    "preHeat=Temperature": "Preheat Temperature",
    "Heat=Temperature": "Heat Temperature",
    "AddSolution=InP_Injectionrate": "P injection rate",
    "AddSolution=A_Injectionrate": "In injection rate",
}
feature_labels_sorted = [rename.get(f, f) for f in sorted_features]

# X_eval 열 순서도 맞춰서 정렬
X_sorted = X_eval[sorted_features]

# beeswarm 플롯 (SHAP 기준 정렬)
plt.figure()
shap.summary_plot(
    sv, 
    X_sorted, 
    feature_names=feature_labels_sorted, 
    show=False, 
    plot_size=(7, 4)  # 가로/세로 비율 조정
)
plt.tight_layout()
plt.savefig("shap_data/shap_summary_beeswarm_from_BO_sorted.png", 
            dpi=200, bbox_inches="tight")
plt.close()
