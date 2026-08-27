# -*- coding: utf-8 -*-
"""
gp_landscape_logratio_rt.py
- gp_landscape_rawparams.py와 동일한 landscape 시각화이지만, BO가 직접 최적화하는
  Ratio(In:P)/TotalFlowrate를 shap_pareto4.py와 같은 방식으로 파생 피처로 변환해서 사용:
    log(In:P ratio) = log(Ratio)
    Reaction Time (s) = (reactor volume / (TotalFlowrate + extra)) * 60
- 나머지 두 피처(Preheat, Heat)는 원본 그대로 사용 -> 최종 4D: log ratio, RT, Preheat, Heat
- 입력: BO pickle (예: '0824.pickle')
- 출력: ./shap_data/gp_landscape_logratio_rt/ 내 PNG
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
OUTDIR      = "shap_data/gp_landscape_logratio_rt_0825"
GRID_N      = 60  # 2D 등고선 해상도 (GRID_N x GRID_N)

# 반응로 체적 [µL] (shap_pareto4.py와 동일: 4 mL)
REACTOR_VOLUME_UL = 4000.0
EXTRA_FLOW_UL_MIN = 0.0

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

FEATURES = ["log(In:P ratio)", "Reaction Time (s)", "preHeat=Temperature", "Heat=Temperature"]
LABELS = {
    "log(In:P ratio)":     "log(In:P ratio)",
    "Reaction Time (s)":   "Reaction Time (s)",
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

# ========= 1) pickle 로드 & (X,y) 구성 — log ratio / RT로 변환 =========
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

    preheat   = float(maybe_denorm(p[KEY_PREHEAT],   KEY_PREHEAT))
    heat      = float(maybe_denorm(p[KEY_HEAT],      KEY_HEAT))
    ratio     = float(maybe_denorm(p[KEY_RATIO],     KEY_RATIO))
    totalflow = float(maybe_denorm(p[KEY_TOTALFLOW], KEY_TOTALFLOW))

    if ratio <= 0 or totalflow <= 0:
        continue

    log_ratio = np.log(ratio)
    total_q = totalflow + EXTRA_FLOW_UL_MIN
    rt_sec = (REACTOR_VOLUME_UL / total_q) * 60.0

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

X_df = df[FEATURES].copy()
y    = df["target"].to_numpy(dtype=float)

# 파생 피처(log ratio, RT)는 물리적 prange가 따로 없으므로 관측 데이터 범위(+5% 여유)를 사용
def padded_range(series, pad_frac=0.05):
    lo, hi = float(series.min()), float(series.max())
    pad = (hi - lo) * pad_frac if hi > lo else 1.0
    return (lo - pad, hi + pad)

FEATURE_RANGE = {
    "log(In:P ratio)":     padded_range(X_df["log(In:P ratio)"]),
    "Reaction Time (s)":   padded_range(X_df["Reaction Time (s)"]),
    "preHeat=Temperature": PRANGE[KEY_PREHEAT],
    "Heat=Temperature":    PRANGE[KEY_HEAT],
}

# ========= 2) 4D GPR 학습 (shap_pareto4.py와 동일한 구성) =========
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

        sc = ax.scatter(X_df[FEATURES[fi]], X_df[FEATURES[fj]], c=y, cmap="viridis",
                         edgecolors="white", linewidths=0.6, s=28, zorder=3)

        ax.scatter(best_point[FEATURES[fi]], best_point[FEATURES[fj]], marker="*",
                   s=300, c="red", edgecolors="black", linewidths=1.0, zorder=4,
                   label="Observed argmax")

        fixed_dims = [k for k in range(len(FEATURES)) if k not in (fi, fj)]
        fixed_desc = ", ".join(f"{FEATURES[k]}={best_point[FEATURES[k]]:.2f}" for k in fixed_dims)
        ax.set_xlabel(LABELS[FEATURES[fi]])
        ax.set_ylabel(LABELS[FEATURES[fj]])
        ax.set_title(f"fixed: {fixed_desc}", fontsize=9)

    axes[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
    title = "GP surrogate mean landscape" if kind == "mean" else "GP surrogate uncertainty (std) landscape"
    fig.suptitle(f"{title} — log(In:P), Reaction Time features\n(pairwise 2D slices, other params fixed at observed argmax)", fontsize=13)
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
fig.suptitle("GP surrogate 1D marginal profile — log(In:P), Reaction Time features (others fixed at observed argmax)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.92])
outpath = os.path.join(OUTDIR, "gp_1d_profile.png")
fig.savefig(outpath, dpi=180)
plt.close(fig)
print("Saved", outpath)

print("Done. Outputs in", OUTDIR)
