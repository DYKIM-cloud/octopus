import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from numpy.polynomial.polynomial import Polynomial
from scipy.optimize import curve_fit
# --------------------------
# (1) Load data
# --------------------------
# wavelength, absorbance 형태의 CSV 파일을 읽는 경우:
df = pd.read_csv("InP_broad.csv", header=None)
wl = df[0].values          # wavelength
abs_raw = df[1].values     # absorbance

def model(wl, a0, a1, a2, amp1, cen1, wid1):
    # Background: exponential tail
    bg = a0 * np.exp(-a1 * wl) + a2
    
    # Peak: Gaussian
    peak1 = amp1 * np.exp(-(wl - cen1)**2 / (2 * wid1**2))
    
    return bg + peak1

# wl, abs_raw 는 CSV에서 읽은 데이터
p0 = [1.0, 0.01, 0.0,     # 배경 초기값(적당히)
      0.2, 470.0, 20.0]   # 피크 초기값: 진폭, 중심, 폭

popt, pcov = curve_fit(model, wl, abs_raw, p0=p0)

abs_fit = model(wl, *popt)
bg_fit  = popt[0] * np.exp(-popt[1]*wl) + popt[2]
peak_fit = abs_fit - bg_fit
plt.plot(wl, abs_raw, label="Original Data", color="black")
plt.plot(wl, bg_fit, label=f"Baseline", color="red")
plt.plot(wl, peak_fit, label="Corrected (Original - Baseline)", color="blue")
plt.show()