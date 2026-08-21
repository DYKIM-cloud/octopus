"""
calculateUV_Data_clean_csv → lambdamaxpvLoss 구간별 샘플 비교
─────────────────────────────────────────────────────────────────
1) 전체 152개 샘플에 대해
   - calculateUV_Data_clean_csv 로 lambdamax, pv_ratio 추출
   - LossFunction.lambdamaxpvLoss 로 loss 계산
2) loss 범위 [-1.5, 0] 을 구간별로 나눔
3) 각 구간에서 샘플 2개씩 선택 → 파이프라인 곡선 + 결과 시각화
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

try:
    from matplotlib import font_manager
    _fonts = [f.name for f in font_manager.fontManager.ttflist]
    _kor   = next((f for f in ["Malgun Gothic","NanumGothic","AppleGothic"] if f in _fonts), None)
    if _kor:
        matplotlib.rcParams["font.family"] = _kor
except Exception:
    pass
matplotlib.rcParams["axes.unicode_minus"] = False

from Analysis.AnalysisUV_poly import (
    smooth_Boxcar, getSliceSpectrum,
    selective_noise_correction, smooth_polyfit,
    analysisPickVelly,
)
from Algorithm.Loss.UV_loss import LossFunction

# ── 설정 ──────────────────────────────────────────────────────────────────
CSV_PATH   = "2508optimize/spectra_with_params_0407.csv"
N_SAMPLES  = 152
TARGET     = {"GetAbs": {"Property": {"lambdamax": 460, "p_v_ratio": 1.3},
                          "Ratio":    {"lambdamax": 0.1, "p_v_ratio": 0.9}}}

# loss 구간 경계: [-1.5, -1.2, -0.6, -0.3, -0.1, 0.0]
BINS = [-1.5, -1.2, -0.6, -0.3, -0.1, 0.0]
BIN_LABELS = [f"[{BINS[i]:.1f}, {BINS[i+1]:.1f})" for i in range(len(BINS)-1)]
BIN_LABELS[-1] = f"[{BINS[-2]:.1f}, {BINS[-1]:.1f}]"   # 마지막은 닫힘

N_PER_BIN  = 2    # 구간당 선택 샘플 수
OUT_DIR    = "loss_distribution_results"

# ── CSV 로더 ───────────────────────────────────────────────────────────────
def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    data_dict = {}
    wavelength = df.iloc[4:, 0].astype(float).tolist()
    for col in range(1, df.shape[1]):
        name = f"Sample_{col}"
        spectrum = df.iloc[4:, col].astype(float).tolist()
        data_dict[name] = {"Wavelength": wavelength, "RawSpectrum": spectrum}
    return data_dict

# ── Pipeline: calculateUV_Data_clean_csv 내부 재현 (중간 곡선 반환) ────────
def run_csv_pipeline(wl_raw, ab_raw):
    order  = np.argsort(wl_raw)
    x_eval = np.linspace(350, 950, 20000)
    trend  = np.interp(x_eval, wl_raw[order], ab_raw[order])
    raw    = np.array([x_eval, trend])

    smoothed = smooth_Boxcar(raw, box_size=250)
    sliced   = getSliceSpectrum(smoothed, min_wl=360, max_wl=700)
    savgoled = selective_noise_correction(sliced, noise_range=(360,700),
                                          window_length=51, polyorder=3)
    poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
    sliced2  = getSliceSpectrum((poly_wl, poly_ab), min_wl=420, max_wl=550)
    pv, lm   = analysisPickVelly(sliced2, prominence=0.0005, width_threshold=8)

    return {
        "x_eval":  x_eval, "raw": trend,
        "poly_wl": poly_wl, "poly_ab": poly_ab,
        "sliced2": sliced2,
        "pv": pv, "lm": lm,
    }

# ── Loss 계산 ──────────────────────────────────────────────────────────────
def calc_loss(wl_list, ab_list, pv, lm):
    result_dict = {
        "UV_GetAbs": {
            "Data": {
                "Wavelength":  list(wl_list),
                "RawSpectrum": list(ab_list),
                "Property":    {"lambdamax": lm, "p_v_ratio": pv},
            }
        }
    }
    loss_obj = LossFunction(result_dict=result_dict,
                            target_condition_dict=TARGET)
    loss, prop = loss_obj.lambdamaxpvLoss()
    return loss

# ── 전체 샘플 계산 ─────────────────────────────────────────────────────────
def compute_all(data_dict):
    records = []
    for i in range(1, N_SAMPLES + 1):
        key = f"Sample_{i}"
        if key not in data_dict:
            continue
        uv   = data_dict[key]
        wl_r = np.array(uv["Wavelength"], dtype=float)
        ab_r = np.array(uv["RawSpectrum"], dtype=float)
        try:
            pipe = run_csv_pipeline(wl_r, ab_r)
            loss = calc_loss(wl_r, ab_r, pipe["pv"], pipe["lm"])
            records.append({
                "idx": i, "loss": loss,
                "lm": pipe["lm"], "pv": pipe["pv"],
                "pipe": pipe, "wl": wl_r, "ab": ab_r,
            })
        except Exception as e:
            print(f"  [warn] Sample_{i}: {e}")
    return records

# ── 구간 분류 및 샘플 선택 ─────────────────────────────────────────────────
def assign_bins(records):
    """각 구간에서 loss 중앙에 가까운 N_PER_BIN 개 샘플 선택."""
    bins = []
    for b in range(len(BINS) - 1):
        lo, hi = BINS[b], BINS[b+1]
        mid    = (lo + hi) / 2
        if b == len(BINS) - 2:   # 마지막 구간은 닫힘
            members = [r for r in records if lo <= r["loss"] <= hi]
        else:
            members = [r for r in records if lo <= r["loss"] < hi]
        # 중앙값에 가까운 순으로 정렬 후 N_PER_BIN 개 선택
        members.sort(key=lambda r: abs(r["loss"] - mid))
        bins.append({
            "label":   BIN_LABELS[b],
            "lo": lo, "hi": hi,
            "count":   len(members),
            "samples": members[:N_PER_BIN],
        })
    return bins

# ── 개별 샘플 패널 그리기 ──────────────────────────────────────────────────
def draw_panel(ax, rec, title=""):
    pipe = rec["pipe"]
    wl_r = rec["wl"]; ab_r = rec["ab"]

    # 공통 정규화 기준: poly 360-700nm
    m  = (pipe["poly_wl"] >= 360) & (pipe["poly_wl"] <= 700)
    y_mn  = float(pipe["poly_ab"][m].min())
    y_rng = float(pipe["poly_ab"][m].max()) - y_mn
    if y_rng == 0: y_rng = 1.0
    def N(arr): return (arr - y_mn) / y_rng

    # raw 보간 (VIEW 범위)
    order  = np.argsort(wl_r)
    x_view = np.linspace(350, 720, 10000)
    y_view = np.interp(x_view, wl_r[order], ab_r[order])

    ax.plot(x_view, N(y_view),
            color="#cccccc", lw=0.7, alpha=0.7, label="Raw")
    ax.plot(pipe["poly_wl"], N(pipe["poly_ab"]),
            color="#7b2d8b", lw=1.8, label="Polyfit(19)")
    ax.axvspan(420, 550, alpha=0.08, color="purple")

    lm = rec["lm"]; pv = rec["pv"]; loss = rec["loss"]
    if lm > 0:
        idx = np.argmin(np.abs(pipe["poly_wl"] - lm))
        ax.axvline(lm, color="#c44e52", lw=1.0, ls=":")
        ax.scatter([lm], [N(pipe["poly_ab"][idx])],
                   color="#c44e52", s=55, zorder=5, marker="v")

    info = (f"S{rec['idx']}  loss={loss:.3f}\n"
            f"lm={lm:.1f} nm  pv={pv:.3f}")
    ax.text(0.03, 0.97, info, transform=ax.transAxes,
            fontsize=7.5, va="top",
            bbox=dict(boxstyle="round,pad=0.3", fc="lavender", alpha=0.85))

    ax.set_xlim(350, 720)
    ax.set_ylim(-0.10, 1.18)
    ax.set_xlabel("Wavelength (nm)", fontsize=8)
    ax.set_title(title, fontsize=8, pad=3)
    ax.grid(True, lw=0.3, alpha=0.4)
    ax.tick_params(labelsize=7)

# ── 구간별 비교 그래프 ─────────────────────────────────────────────────────
def plot_bins(bins):
    n_bins = len(bins)
    fig = plt.figure(figsize=(5 * N_PER_BIN, 4.5 * n_bins))
    gs  = gridspec.GridSpec(n_bins, N_PER_BIN,
                            hspace=0.55, wspace=0.30)

    for r, binfo in enumerate(bins):
        for c in range(N_PER_BIN):
            ax = fig.add_subplot(gs[r, c])
            if c < len(binfo["samples"]):
                rec   = binfo["samples"][c]
                title = (f"{binfo['label']}  (n={binfo['count']})\n"
                         f"Sample {rec['idx']}")
                draw_panel(ax, rec, title=title)
            else:
                ax.text(0.5, 0.5, "no sample",
                        ha="center", va="center", transform=ax.transAxes,
                        fontsize=9, color="gray")
                ax.set_title(f"{binfo['label']}  (n={binfo['count']})\n—",
                             fontsize=8)
                ax.axis("off")

            if c == 0:
                ax.set_ylabel("Absorbance (norm.)", fontsize=8)

    fig.suptitle(
        "lambdamaxpvLoss 구간별 대표 샘플  (calculateUV_Data_clean_csv)",
        fontsize=12, y=1.005
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "loss_bin_samples.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"그래프 저장: {out}")

# ── loss 분포 히스토그램 ───────────────────────────────────────────────────
def plot_histogram(records, bins):
    losses = [r["loss"] for r in records]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(losses, bins=30, color="#7b2d8b", alpha=0.65, edgecolor="white")

    bin_colors = ["#e63946","#f4a261","#2a9d8f","#457b9d","#1d3557"]
    for i, binfo in enumerate(bins):
        lo, hi = binfo["lo"], binfo["hi"]
        c = bin_colors[i % len(bin_colors)]
        ax.axvspan(lo, hi, alpha=0.15, color=c)
        ax.axvline(lo, color=c, lw=1.0, ls="--")
        ax.text((lo+hi)/2, ax.get_ylim()[1]*0.85,
                f"n={binfo['count']}", ha="center", fontsize=8, color=c)

    ax.axvline(hi, color=bin_colors[(len(bins)-1) % len(bin_colors)], lw=1.0, ls="--")
    ax.set_xlabel("Loss", fontsize=10)
    ax.set_ylabel("Count", fontsize=10)
    ax.set_title("lambdamaxpvLoss 분포 (calculateUV_Data_clean_csv, 152 samples)",
                 fontsize=11)
    ax.grid(True, lw=0.35, alpha=0.4)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "loss_histogram.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"히스토그램 저장: {out}")

# ── 메인 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("CSV 로드 중...")
    data_dict = load_multisample_csv(CSV_PATH)

    print("전체 샘플 loss 계산 중...")
    records = compute_all(data_dict)
    print(f"  완료: {len(records)}개 샘플")

    losses = [r["loss"] for r in records]
    print(f"  loss 범위: [{min(losses):.4f}, {max(losses):.4f}]")
    print(f"  loss 평균: {np.mean(losses):.4f}  std: {np.std(losses):.4f}")

    bins = assign_bins(records)
    print("\n구간별 샘플 수:")
    for b in bins:
        sel_idx = [s["idx"] for s in b["samples"]]
        print(f"  {b['label']}  n={b['count']}  선택={sel_idx}")

    plot_histogram(records, bins)
    plot_bins(bins)
    print("\n완료.")
