# -*- coding: utf-8 -*-
"""
gp_acquisition_kappa_sim.py
- 실제 BO pickle의 acqHyperparameter(kappa)를 여러 값으로 바꿔가며
  bo.suggestNextStep()을 다시 호출해서, kappa가 낮아질 때
  "acq max"(다음 제안 후보)가 관측 argmax 쪽으로 수렴하는지 시뮬레이션.
- pickle 파일 자체는 저장하지 않음(메모리 상에서만 kappa를 바꿔 실험).

출력: ./shap_data/gp_acquisition_0825/kappa_sim_summary.csv
      ./shap_data/gp_acquisition_0825/kappa_sim_landscape.png
"""

import os
import pickle
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

PICKLE_PATH = "0825.pickle"
OUTDIR      = "shap_data/gp_acquisition_0825"
KAPPAS      = [10.0, 5.0, 2.0, 0.5, 0.0]   # 원래(10.0) -> 점점 낮춤(탐험 가중치 감소), 0.0=순수 exploitation(mean만)
GRID_N      = 60

LABELS = {
    "AddSolution=Ratio":         "In:P Ratio",
    "AddSolution=TotalFlowrate": "Total Flowrate (µL/min)",
    "preHeat=Temperature":       "Preheat Temperature (°C)",
    "Heat=Temperature":          "Heat Temperature (°C)",
}

os.makedirs(OUTDIR, exist_ok=True)

def load_bo():
    with open(PICKLE_PATH, "rb") as f:
        return pickle.load(f)

def to_real(prange, key, norm_val):
    lo, hi, _ = prange[key]
    return lo + norm_val * (hi - lo)

def to_norm(prange, key, real_val):
    lo, hi, _ = prange[key]
    return (real_val - lo) / (hi - lo)

rows = []
candidates = {}  # kappa -> (bo, cand_norm, keys, prange)

for kappa in KAPPAS:
    bo = load_bo()  # kappa마다 깨끗한 pickle을 새로 로드 (서로 영향 없게)
    bo.acqHyperparameter = {"kappa": kappa}

    real_next, norm_next = bo.suggestNextStep()
    keys = bo.space.keys
    prange = bo.prange
    gp = bo._gp

    cand_norm = np.array([norm_next[0][k] for k in keys])
    y = bo._space.target
    best_idx = int(np.argmax(y))
    best_norm = bo._space.params[best_idx]

    m_cand, s_cand = gp.predict(cand_norm.reshape(1, -1), return_std=True)
    m_best, s_best = gp.predict(best_norm.reshape(1, -1), return_std=True)
    ucb_cand = m_cand[0] + kappa * s_cand[0]
    ucb_best = m_best[0] + kappa * s_best[0]

    dist_to_argmax = np.sqrt(np.sum((cand_norm - best_norm) ** 2))

    rows.append({
        "kappa": kappa,
        **{LABELS[k]: real_next[0][k] for k in keys},
        "GP_mean_at_candidate": m_cand[0],
        "GP_std_at_candidate": s_cand[0],
        "UCB_at_candidate": ucb_cand,
        "UCB_at_observed_argmax": ucb_best,
        "dist_to_observed_argmax(normalized)": dist_to_argmax,
    })
    candidates[kappa] = (bo, cand_norm, best_norm, keys, prange)
    print(f"[kappa={kappa}] next candidate = {real_next[0]}  (dist to argmax(norm)={dist_to_argmax:.3f})")

summary_df = pd.DataFrame(rows)
summary_df.to_csv(os.path.join(OUTDIR, "kappa_sim_summary.csv"), index=False, encoding="utf-8-sig")
print("\nSaved", os.path.join(OUTDIR, "kappa_sim_summary.csv"))
try:
    print(summary_df.to_string(index=False))
except UnicodeEncodeError:
    print(summary_df.to_string(index=False).encode("ascii", "replace").decode("ascii"))

# ========= Ratio vs Heat Temperature 단면으로, kappa별 UCB landscape 비교 =========
FI_KEY = "AddSolution=Ratio"
FJ_KEY = "Heat=Temperature"

fig, axes = plt.subplots(1, len(KAPPAS), figsize=(6 * len(KAPPAS), 5.2))
for ax, kappa in zip(axes, KAPPAS):
    bo, cand_norm, best_norm, keys, prange = candidates[kappa]
    gp = bo._gp
    fi = keys.index(FI_KEY)
    fj = keys.index(FJ_KEY)

    lo_i, hi_i, _ = prange[FI_KEY]
    lo_j, hi_j, _ = prange[FJ_KEY]
    xi_real = np.linspace(lo_i, hi_i, GRID_N)
    xj_real = np.linspace(lo_j, hi_j, GRID_N)
    XI, XJ = np.meshgrid(xi_real, xj_real)

    grid_norm = np.tile(cand_norm, (GRID_N * GRID_N, 1))
    grid_norm[:, fi] = (XI.ravel() - lo_i) / (hi_i - lo_i)
    grid_norm[:, fj] = (XJ.ravel() - lo_j) / (hi_j - lo_j)

    mean, std = gp.predict(grid_norm, return_std=True)
    Z = (mean + kappa * std).reshape(GRID_N, GRID_N)

    cf = ax.contourf(XI, XJ, Z, levels=25, cmap="plasma")
    fig.colorbar(cf, ax=ax, shrink=0.85, label="UCB")

    xs_real = np.array([to_real(prange, FI_KEY, v) for v in bo._space.params[:, fi]])
    ys_real = np.array([to_real(prange, FJ_KEY, v) for v in bo._space.params[:, fj]])
    ax.scatter(xs_real, ys_real, c="white", edgecolors="black", s=20, linewidths=0.5, zorder=3)

    ax.scatter(to_real(prange, FI_KEY, best_norm[fi]), to_real(prange, FJ_KEY, best_norm[fj]),
               marker="*", s=260, c="red", edgecolors="black", linewidths=1.0, zorder=4, label="Observed argmax")
    ax.scatter(to_real(prange, FI_KEY, cand_norm[fi]), to_real(prange, FJ_KEY, cand_norm[fj]),
               marker="D", s=130, c="cyan", edgecolors="black", linewidths=1.0, zorder=5, label="acq max (next)")

    ax.set_xlabel(LABELS[FI_KEY])
    ax.set_ylabel(LABELS[FJ_KEY])
    ax.set_title(f"kappa = {kappa:g}", fontsize=12)

axes[0].legend(loc="upper right", fontsize=8, framealpha=0.9)
fig.suptitle("Effect of kappa on UCB acquisition landscape (Ratio x Heat Temperature slice)\nas kappa decreases, acq-max (diamond) should move toward the exploitation optimum near observed argmax (star)", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.90])
outpath = os.path.join(OUTDIR, "kappa_sim_landscape.png")
fig.savefig(outpath, dpi=180)
plt.close(fig)
print("Saved", outpath)
