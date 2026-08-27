# -*- coding: utf-8 -*-
"""
gp_acquisition_next.py
- 재학습한 별도 GPR이 아니라, BO pickle 안에 저장된 "실제 내부 모델"(bo._gp)과
  실제 acquisition 설정(UCB, kappa)을 그대로 사용해서
  "지금 이 시점에 BO가 다음 샘플을 어떻게 선택하는지"를 재현/시각화한다.

절차:
1) pickle 로드 후 bo.suggestNextStep() 을 실제로 호출 -> 내부적으로 self._gp.fit(...) 수행 + UCB 최대화로 다음 후보 반환
   (등록/저장은 하지 않으므로 pickle 파일 자체는 변경되지 않음)
2) 관측된 argmax(현재까지 best)와, 새로 제안된 다음 후보 지점에서
   GP mean / std / UCB = mean + kappa*std 값을 비교
3) 6개 파라미터 쌍에 대해 UCB landscape를 그려서 "왜 그 지점이 선택되었는지" 시각화
   (별 = 관측 argmax, 다이아몬드 = 다음 제안 후보)
4) 지금까지의 실험 이력(iteration별 실제 파라미터 값 변화)을 그려서
   초기 샘플링 구간과 AI(UCB) 추천 구간에서 탐색 패턴이 어떻게 다른지 보여줌

출력: ./shap_data/gp_acquisition_0825/ 에 PNG 2장
"""

import os
import pickle
import itertools
import warnings

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ========= 사용자 설정 =========
PICKLE_PATH = "0825.pickle"
OUTDIR      = "shap_data/gp_acquisition_0825"
GRID_N      = 60

LABELS = {
    "AddSolution=Ratio":         "In:P Ratio",
    "AddSolution=TotalFlowrate": "Total Flowrate (µL/min)",
    "preHeat=Temperature":       "Preheat Temperature (°C)",
    "Heat=Temperature":          "Heat Temperature (°C)",
}

os.makedirs(OUTDIR, exist_ok=True)

# ========= 1) pickle 로드 & 실제 다음 후보 계산 =========
with open(PICKLE_PATH, "rb") as f:
    bo = pickle.load(f)

n_before = len(bo.res)
real_next, norm_next = bo.suggestNextStep()  # 내부에서 self._gp.fit() 수행 (파일 저장은 안 함)
print("[suggestNextStep] real:", real_next[0])
print("[suggestNextStep] norm:", norm_next[0])

keys = bo.space.keys          # bo._gp가 학습된 축 순서 (알파벳 정렬)
prange = bo.prange            # {key: [lo, hi, step]}
gp = bo._gp
kappa = bo.acqHyperparameter["kappa"]

def to_norm(key, real_val):
    lo, hi, _ = prange[key]
    return (real_val - lo) / (hi - lo)

def to_real(key, norm_val):
    lo, hi, _ = prange[key]
    return lo + norm_val * (hi - lo)

def ucb_predict(X_norm):
    mean, std = gp.predict(np.atleast_2d(X_norm), return_std=True)
    return mean, std, mean + kappa * std

# 관측 argmax
y = bo._space.target
best_idx = int(np.argmax(y))
best_norm = bo._space.params[best_idx].copy()
best_target = y[best_idx]

cand_norm = np.array([norm_next[0][k] for k in keys])

m_best, s_best, u_best = ucb_predict(best_norm)
m_cand, s_cand, u_cand = ucb_predict(cand_norm)

print(f"[Observed argmax]  target(raw)={best_target:.4f}  GP mean={m_best[0]:.4f}  std={s_best[0]:.4f}  UCB={u_best[0]:.4f}")
print(f"[Suggested next]                                   GP mean={m_cand[0]:.4f}  std={s_cand[0]:.4f}  UCB={u_cand[0]:.4f}")

with open(os.path.join(OUTDIR, "acquisition_summary.txt"), "w", encoding="utf-8") as f:
    f.write(f"kappa (UCB exploration weight) = {kappa}\n\n")
    f.write("[Observed argmax]\n")
    f.write(f"  real params: { {k: to_real(k, best_norm[i]) for i, k in enumerate(keys)} }\n")
    f.write(f"  raw observed target = {best_target:.4f}\n")
    f.write(f"  GP mean = {m_best[0]:.4f}, GP std = {s_best[0]:.4f}, UCB = {u_best[0]:.4f}\n\n")
    f.write("[Suggested next point]\n")
    f.write(f"  real params: {real_next[0]}\n")
    f.write(f"  GP mean = {m_cand[0]:.4f}, GP std = {s_cand[0]:.4f}, UCB = {u_cand[0]:.4f}\n")

# ========= 2) UCB landscape (실제 내부 GP, 파라미터 쌍별) =========
pairs = list(itertools.combinations(range(len(keys)), 2))

def make_grid_real(fi, fj, fixed_norm):
    lo_i, hi_i, _ = prange[keys[fi]]
    lo_j, hi_j, _ = prange[keys[fj]]
    xi_real = np.linspace(lo_i, hi_i, GRID_N)
    xj_real = np.linspace(lo_j, hi_j, GRID_N)
    XI, XJ = np.meshgrid(xi_real, xj_real)

    grid_norm = np.tile(fixed_norm, (GRID_N * GRID_N, 1))
    grid_norm[:, fi] = (XI.ravel() - lo_i) / (hi_i - lo_i)
    grid_norm[:, fj] = (XJ.ravel() - lo_j) / (hi_j - lo_j)
    return XI, XJ, grid_norm

fig, axes = plt.subplots(2, 3, figsize=(18, 11))
axes = axes.ravel()
for ax, (fi, fj) in zip(axes, pairs):
    XI, XJ, grid_norm = make_grid_real(fi, fj, cand_norm)
    mean, std, ucb = ucb_predict(grid_norm)
    Z = ucb.reshape(GRID_N, GRID_N)

    cf = ax.contourf(XI, XJ, Z, levels=25, cmap="plasma")
    fig.colorbar(cf, ax=ax, shrink=0.85, label="UCB")

    # 실제 관측 샘플 (real 단위로 변환)
    xs_real = np.array([to_real(keys[fi], v) for v in bo._space.params[:, fi]])
    ys_real = np.array([to_real(keys[fj], v) for v in bo._space.params[:, fj]])
    ax.scatter(xs_real, ys_real, c="white", edgecolors="black", s=22, linewidths=0.5, zorder=3, label="observed")

    best_x = to_real(keys[fi], best_norm[fi]); best_y = to_real(keys[fj], best_norm[fj])
    cand_x = to_real(keys[fi], cand_norm[fi]); cand_y = to_real(keys[fj], cand_norm[fj])
    ax.scatter(best_x, best_y, marker="*", s=280, c="red", edgecolors="black", linewidths=1.0, zorder=4, label="Observed argmax")
    ax.scatter(cand_x, cand_y, marker="D", s=140, c="cyan", edgecolors="black", linewidths=1.0, zorder=5, label="Suggested next")

    fixed_dims = [k for k in range(len(keys)) if k not in (fi, fj)]
    fixed_desc = ", ".join(f"{LABELS[keys[k]]}={to_real(keys[k], cand_norm[k]):.1f}" for k in fixed_dims)
    ax.set_xlabel(LABELS[keys[fi]])
    ax.set_ylabel(LABELS[keys[fj]])
    ax.set_title(f"fixed(at next-candidate): {fixed_desc}", fontsize=8.5)

axes[0].legend(loc="upper right", fontsize=7.5, framealpha=0.9)
fig.suptitle(f"Actual BO acquisition landscape: UCB = mean + {kappa:g}·std\n(internal GP, other params fixed at the newly suggested candidate)", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(os.path.join(OUTDIR, "acquisition_landscape.png"), dpi=180)
plt.close(fig)
print("Saved", os.path.join(OUTDIR, "acquisition_landscape.png"))

# ========= 3) 탐색 이력 (iteration별 실제 파라미터 변화) =========
sampling_num = bo.samplingNum
n = len(bo.res)
iters = np.arange(n)
phase = np.where(iters < sampling_num, "initial sampling", "AI (UCB) suggested")

real_history = {k: np.array([to_real(k, bo._space.params[i, ki]) for i in range(n)]) for ki, k in enumerate(keys)}
targets_hist = bo._space.target
running_best = np.maximum.accumulate(targets_hist)

fig, axes = plt.subplots(1, 5, figsize=(24, 4.5))
colors = np.where(phase == "initial sampling", "tab:gray", "tab:blue")

for ax, k in zip(axes[:4], keys):
    ax.scatter(iters, real_history[k], c=colors, s=20)
    ax.axvline(sampling_num - 0.5, color="black", ls="--", lw=1)
    # 새로 제안된 다음 후보를 iteration n 위치에 표시
    ax.scatter([n], [real_next[0][k]], marker="D", s=90, c="red", edgecolors="black", zorder=5)
    ax.set_xlabel("iteration")
    ax.set_ylabel(LABELS[k])
    ax.set_title(LABELS[k], fontsize=10)

ax = axes[4]
ax.scatter(iters, targets_hist, c=colors, s=20, label="target (each trial)")
ax.plot(iters, running_best, color="tab:red", lw=1.5, label="running best")
ax.axvline(sampling_num - 0.5, color="black", ls="--", lw=1)
ax.set_xlabel("iteration")
ax.set_ylabel("target")
ax.set_title("target history", fontsize=10)
ax.legend(fontsize=8)

import matplotlib.patches as mpatches
handles = [
    mpatches.Patch(color="tab:gray", label="initial sampling (latin)"),
    mpatches.Patch(color="tab:blue", label="AI (UCB) suggested"),
    plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="red", markeredgecolor="black", markersize=9, label="newly suggested next"),
]
fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.06), fontsize=9)

fig.suptitle(f"Search history over {n} trials (dashed line = end of initial random sampling, iter={sampling_num})", fontsize=12, y=1.12)
fig.tight_layout()
fig.savefig(os.path.join(OUTDIR, "search_trajectory.png"), dpi=180, bbox_inches="tight")
plt.close(fig)
print("Saved", os.path.join(OUTDIR, "search_trajectory.png"))

print("Done. Outputs in", OUTDIR)
