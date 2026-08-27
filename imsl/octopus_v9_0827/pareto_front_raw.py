# -*- coding: utf-8 -*-
"""
pareto_front_raw.py
- 입력 1: 2508optimize/small_params_zero.csv (0824.pickle과 동일한 59개 샘플, 원본 UV 스펙트럼)
- 입력 2: 0824.pickle (BO가 실제로 사용한 목표값 lossTarget 읽기용)
- 가공: Analysis.AnalysisUV_poly.calculateUV_Data_clean_csv 로 각 샘플의 (p_v_ratio, lambdamax) 추출
- 목표: lambdamax, p_v_ratio 각각의 "목표값 대비 편차" 최소화 (2목표 Pareto)
- 출력: ./shap_data/shap5/pareto_front_raw.png, pareto_front_raw.csv
"""

import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from Analysis.AnalysisUV_poly import calculateUV_Data_clean_csv

# ========= 사용자 설정 =========
CSV_PATH    = "2508optimize/small_params_zero.csv"
PICKLE_PATH = "0824.pickle"
OUTDIR      = "shap_data/shap5"
N_SAMPLES   = 59

os.makedirs(OUTDIR, exist_ok=True)

# ========= 1) CSV 로드 (self_bayesian_csv.py의 load_multisample_csv와 동일 파싱) =========
def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)
    param_dict = {}
    data_dict = {}
    wavelength = df.iloc[4:, 0].astype(float).tolist()
    for col in range(1, df.shape[1]):
        col_name = f"Sample_{col}"
        keys = df.iloc[0:4, 0].values
        values = df.iloc[0:4, col].values
        param_dict[col_name] = dict(zip(keys.astype(str), values))
        spectrum = df.iloc[4:, col].astype(float).tolist()
        data_dict[col_name] = {"Wavelength": wavelength, "RawSpectrum": spectrum}
    return param_dict, data_dict

param_dict, data_dict = load_multisample_csv(CSV_PATH)

# ========= 2) BO가 실제로 사용한 목표값(lossTarget) 읽기 =========
with open(PICKLE_PATH, "rb") as f:
    bo = pickle.load(f)
target_prop = bo.lossTarget["GetAbs"]["Property"]
TARGET_LAM = float(target_prop["lambdamax"])
TARGET_PVR = float(target_prop["p_v_ratio"])
print(f"target lambdamax={TARGET_LAM}, target p_v_ratio={TARGET_PVR}")

# ========= 3) 샘플별 (lambdamax, p_v_ratio) 계산 =========
rows = []
for i in range(1, N_SAMPLES + 1):
    sample = f"Sample_{i}"
    uv = data_dict[sample]
    data_df = pd.DataFrame(uv["RawSpectrum"], index=uv["Wavelength"], columns=[sample])

    pv_ratio, lambdamax = calculateUV_Data_clean_csv(uv_df=data_df)
    rows.append({"sample": sample, "lambdamax": lambdamax, "p_v_ratio": pv_ratio})

df = pd.DataFrame(rows)

# 검출 실패(0.0) 샘플 제외
valid = (df["lambdamax"] > 0) & (df["p_v_ratio"] > 0)
n_dropped = (~valid).sum()
if n_dropped:
    print(f"피크 미검출로 제외된 샘플: {n_dropped}개")
df = df[valid].reset_index(drop=True)

if len(df) == 0:
    raise RuntimeError("유효 샘플이 0개입니다. calculateUV_Data_clean_csv 검출 파라미터를 확인하세요.")

# ========= 4) 비지배(Pareto) 판정: 목표값 대비 편차 최소화 =========
def non_dominated_mask(F: np.ndarray) -> np.ndarray:
    """F의 모든 열은 '작을수록 좋음(minimize)' 기준. 비지배(Pareto) 마스크 반환."""
    n = F.shape[0]
    nd = np.ones(n, dtype=bool)
    for i in range(n):
        better_or_equal = (F <= F[i]).all(axis=1)
        strictly_better  = (F <  F[i]).any(axis=1)
        dominated = better_or_equal & strictly_better
        dominated[i] = False
        if dominated.any():
            nd[i] = False
    return nd

dev = np.column_stack([
    np.abs(df["lambdamax"].to_numpy()  - TARGET_LAM),
    np.abs(df["p_v_ratio"].to_numpy()  - TARGET_PVR),
])
is_front = non_dominated_mask(dev)
df["is_pareto"] = is_front

df.sort_values("lambdamax").to_csv(
    os.path.join(OUTDIR, "pareto_front_raw.csv"), index=False
)

# ========= 5) 시각화 =========
front = df[df["is_pareto"]].sort_values("lambdamax")
rest  = df[~df["is_pareto"]]

plt.figure(figsize=(7, 5.5))
plt.scatter(rest["lambdamax"], rest["p_v_ratio"], alpha=0.4, color="gray", label="Dominated")
plt.scatter(front["lambdamax"], front["p_v_ratio"], s=70, color="crimson", zorder=3, label="Pareto front")
plt.plot(front["lambdamax"], front["p_v_ratio"], color="crimson", linewidth=1.5, zorder=2)
plt.scatter([TARGET_LAM], [TARGET_PVR], marker="*", s=200, color="gold",
            edgecolor="black", zorder=4, label=f"Target ({TARGET_LAM}, {TARGET_PVR})")

plt.xlabel("lambdamax (nm)")
plt.ylabel("p_v_ratio")
plt.title("Pareto Front: deviation from target lambdamax / p_v_ratio")
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "pareto_front_raw.png"), dpi=200)
plt.close()

print(f"전체 {len(df)}개 중 Pareto front: {is_front.sum()}개")
print("Saved:")
print(f" - {os.path.join(OUTDIR, 'pareto_front_raw.png')}")
print(f" - {os.path.join(OUTDIR, 'pareto_front_raw.csv')}")
