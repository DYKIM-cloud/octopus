# -*- coding: utf-8 -*-
"""
gp_landscape_rawparams.py
- shap_pareto4_rawparams.py와 동일한 방식으로 BO pickle에서 원본 파라미터(Ratio,
  TotalFlowrate, Preheat, Heat)와 target을 추출해 4D GPR을 학습.
- SHAP(변수 중요도)이 아니라, GP surrogate 자체의 landscape(예측 평균/불확실성 곡면)를
  argmax 한 점만 보지 않고 전체적으로 시각화하기 위한 스크립트.
- 출력:
    gp_mean_landscape.png : 모든 파라미터 쌍(6쌍)에 대한 GP 예측 평균 2D 등고선
    gp_std_landscape.png  : 동일한 쌍에 대한 GP 예측 표준편차(불확실성) 2D 등고선
    gp_1d_profile.png     : 각 파라미터를 단독으로 스윕한 1D 평균±95% 구간 프로파일
- 2D 슬라이스는 나머지 두 파라미터를 "관측된 최적점(argmax target)" 값으로 고정해서 그림.
"""

import os
import pickle
import itertools

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
from sklearn.preprocessing import StandardScaler

# ========= 사용자 설정 =========
PICKLE_PATH = "0825.pickle"
OUTDIR      = "shap_data/gp_landscape_rawparams_0825"
GRID_N      = 60  # 2D 등고선 해상도 (GRID_N x GRID_N)

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

LABELS = {
    "In:P Ratio":          "In:P Ratio",
    "Total Flowrate":      "Total Flowrate (µL/min)",
    "preHeat=Temperature": "Preheat Temperature (°C)",
    "Heat=Temperature":    "Heat Temperature (°C)",
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

FEATURES = ["In:P Ratio", "Total Flowrate", "preHeat=Temperature", "Heat=Temperature"]
X_df = df[FEATURES].copy()
y    = df["target"].to_numpy(dtype=float)

FEATURE_RANGE = {
    "In:P Ratio":          PRANGE[KEY_RATIO],
    "Total Flowrate":      PRANGE[KEY_TOTALFLOW],
    "preHeat=Temperature": PRANGE[KEY_PREHEAT],
    "Heat=Temperature":    PRANGE[KEY_HEAT],
}

# ========= 2) 4D GPR 학습 (shap_pareto4_rawparams.py와 동일한 구성) =========
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_df.values)

kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(length_scale=[1.0, 1.0, 1.0, 1.0], length_scale_bounds=(1e-2, 1e2), nu=2.5) + WhiteKernel(noise_level=1e-2)
gpr = GaussianProcessRegressor(kernel=kernel, normalize_y=True, n_restarts_optimizer=10, random_state=42)
gpr.fit(X_scaled, y)

def gp_predict(X_real):
    """X_real: (n,4) array in FEATURES order, raw units -> (mean, std)"""
    X_real = np.asarray(X_real, dtype=float)
    X_scaled_ = scaler.transform(X_real)
    mean, std = gpr.predict(X_scaled_, return_std=True)
    return mean, std

# 관측된 argmax(BO가 지금까지 최고라고 본 점)
best_idx = int(np.argmax(y))
best_point = X_df.iloc[best_idx]
best_target = y[best_idx]
print(f"[Observed argmax] target={best_target:.4f} @ {best_point.to_dict()}")

# ========= 3) 2D pairwise landscape (나머지 두 축은 argmax 점으로 고정) =========
pairs = list(itertools.combinations(range(len(FEATURES)), 2))  # 6 pairs

def make_grid(fi, fj):
    xi = np.linspace(*FEATURE_RANGE[FEATURES[fi]], GRID_N)
    xj = np.linspace(*FEATURE_RANGE[FEATURES[fj]], GRID_N)
    XI, XJ = np.meshgrid(xi, xj)
    grid = np.tile(best_point.values.astype(float), (GRID_N * GRID_N, 1))
    grid[:, fi] = XI.ravel()
    grid[:, fj] = XJ.ravel()
    return XI, XJ, grid

def plot_pairwise(kind):
    """kind: 'mean' or 'std'"""
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    axes = axes.ravel()
    cmap = "viridis" if kind == "mean" else "magma"

    for ax, (fi, fj) in zip(axes, pairs):
        XI, XJ, grid = make_grid(fi, fj)
        mean, std = gp_predict(grid)
        Z = (mean if kind == "mean" else std).reshape(GRID_N, GRID_N)

        cf = ax.contourf(XI, XJ, Z, levels=25, cmap=cmap)
        fig.colorbar(cf, ax=ax, shrink=0.85)

        # 실제 관측 샘플 오버레이 (target 값으로 색칠)
        sc = ax.scatter(X_df[FEATURES[fi]], X_df[FEATURES[fj]], c=y, cmap="viridis",
                         edgecolors="white", linewidths=0.6, s=28, zorder=3)

        # 관측된 argmax 지점 표시
        ax.scatter(best_point[FEATURES[fi]], best_point[FEATURES[fj]], marker="*",
                   s=300, c="red", edgecolors="black", linewidths=1.0, zorder=4,
                   label="Observed argmax")

        fixed_dims = [k for k in range(len(FEATURES)) if k not in (fi, fj)]
        fixed_desc = ", ".join(f"{FEATURES[k]}={best_point[FEATURES[k]]:.1f}" for k in fixed_dims)
        ax.set_xlabel(LABELS[FEATURES[fi]])
        ax.set_ylabel(LABELS[FEATURES[fj]])
        ax.set_title(f"fixed: {fixed_desc}", fontsize=9)

    axes[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
    title = "GP surrogate mean landscape" if kind == "mean" else "GP surrogate uncertainty (std) landscape"
    fig.suptitle(f"{title}\n(pairwise 2D slices, other params fixed at observed argmax)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    outpath = os.path.join(OUTDIR, f"gp_{kind}_landscape.png")
    fig.savefig(outpath, dpi=180)
    plt.close(fig)
    print("Saved", outpath)

plot_pairwise("mean")
plot_pairwise("std")

# ========= 4) 1D marginal profile (파라미터 하나씩 스윕, 나머지는 argmax 고정) =========
fig, axes = plt.subplots(1, 4, figsize=(20, 4.5))
for ax, feat in zip(axes, FEATURES):
    fi = FEATURES.index(feat)
    xs = np.linspace(*FEATURE_RANGE[feat], 200)
    grid = np.tile(best_point.values.astype(float), (200, 1))
    grid[:, fi] = xs
    mean, std = gp_predict(grid)

    ax.plot(xs, mean, color="tab:blue", lw=2, label="GP mean")
    ax.fill_between(xs, mean - 1.96 * std, mean + 1.96 * std, color="tab:blue", alpha=0.2, label="95% CI")
    ax.scatter(X_df[feat], y, color="black", s=18, zorder=3, label="observed (raw)")
    ax.axvline(best_point[feat], color="red", ls="--", lw=1, label="argmax")
    ax.set_xlabel(LABELS[feat])
    ax.set_ylabel("target")
    ax.set_title(feat, fontsize=10)

axes[0].legend(fontsize=8)
fig.suptitle("GP surrogate 1D marginal profile (others fixed at observed argmax)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.92])
outpath = os.path.join(OUTDIR, "gp_1d_profile.png")
fig.savefig(outpath, dpi=180)
plt.close(fig)
print("Saved", outpath)

print("Done. Outputs in", OUTDIR)
