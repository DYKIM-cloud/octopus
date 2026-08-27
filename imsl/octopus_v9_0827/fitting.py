import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from numpy.polynomial.polynomial import Polynomial
from scipy.optimize import curve_fit
# --------------------------
# (1) Load data
# --------------------------
# wavelength, absorbance 형태의 CSV 파일을 읽는 경우:
df = pd.read_csv("InP_90.csv", header=None)
wl = df[0].values          # wavelength
abs_raw = df[1].values     # absorbance

# 여기서는 예시를 위해 아래처럼 배열로 있다고 가정
# wl : wavelength array (nm)
# abs_raw : absorbance array

# wl = np.arange(300, 700.5, 0.5)
# abs_raw = ...  # 실제 데이터로 교체

# --------------------------
# (2) Extract 300–350 nm region to fit baseline
# --------------------------
mask = (wl >= 300) & (wl <= 350)
wl_fit = wl[mask]
abs_fit = abs_raw[mask]

# --------------------------
# (3) Fit trendline (choose degree: 1 = linear, 2 = polynomial)
# --------------------------
degree = 2   # 필요 시 1 또는 3으로 변경 가능
coefs = Polynomial.fit(wl_fit, abs_fit, degree).convert().coef

# baseline 함수 생성
baseline = Polynomial(coefs)(wl)

# --------------------------
# (4) Subtract baseline from original data
# --------------------------
abs_corrected = abs_raw - baseline

# --------------------------
# (5) Plot results
# --------------------------
plt.figure(figsize=(9,5))

plt.plot(wl, abs_raw, label="Original Data", color="black")
plt.plot(wl, baseline, label=f"Baseline (poly deg {degree})", color="red")
plt.plot(wl, abs_corrected, label="Corrected (Original - Baseline)", color="blue")

plt.xlabel("Wavelength (nm)")
plt.ylabel("Absorbance (a.u.)")
plt.legend()
plt.grid(True)
plt.show()
