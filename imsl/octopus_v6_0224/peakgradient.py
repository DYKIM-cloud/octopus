import numpy as np
from scipy.signal import peak_prominences
from collections import OrderedDict
import matplotlib.pyplot as plt
import json
# AnalysisUV.py에 정의된 함수들
from Analysis.AnalysisUV import getSpectrumArray, smooth_Boxcar, getSliceSpectrum  

def calculatePL_Data_slope(
    uv_dict,
    WavelengthMin=300,
    WavelengthMax=849,
    BoxCarSize=10,
    Prominence=0.01
):
    """
    Gradient-based peak/valley detection with prominence filtering.
    :param uv_dict: {"Wavelength": [...], "RawSpectrum": [...]}
    :param WavelengthMin, WavelengthMax: 탐색 파장 범위 (nm)
    :param BoxCarSize: boxcar smoothing window size
    :param Prominence: 최소 prominence (노이즈 제거용)
    :return: (UV_result, uv_dict) where UV_result에는 peak λ, valley λ, p/v ratio 포함
    """
    # 1) 스펙트럼 배열 생성 및 스무딩
    rawSpectrum = getSpectrumArray(uv_dict)
    smooth_spec = smooth_Boxcar(rawSpectrum, box_size=BoxCarSize)
    # 2) 범위 자르기
    slice_spec = getSliceSpectrum(smooth_spec, min=WavelengthMin, max=WavelengthMax)
    x = slice_spec[0]
    y = slice_spec[1]
    plt.plot(slice_spec[0],slice_spec[1])
    plt.show()
    # 3) 기울기 계산
    slopes = np.gradient(y, x)

    # 4) 기울기 부호 변화 지점(교차점) 검색
    peak_idx = [i for i in range(1, len(slopes)) if slopes[i-1] > 0 and slopes[i] < 0]
    valley_idx = [i for i in range(1, len(slopes)) if slopes[i-1] < 0 and slopes[i] > 0]

    # 5) 후보점들의 prominence 계산
    if peak_idx:
        prom_peaks, _, _ = peak_prominences(y, peak_idx)
        # threshold 이상만 필터
        filt_peaks = [idx for idx, p in zip(peak_idx, prom_peaks) if p >= Prominence]
    else:
        filt_peaks = []

    if valley_idx:
        prom_valleys, _, _ = peak_prominences(-y, valley_idx)
        filt_valleys = [idx for idx, p in zip(valley_idx, prom_valleys) if p >= Prominence]
    else:
        filt_valleys = []

    # 6) 최종 peak/valley 선정 (가장 강한 intensity 기준)
    if filt_peaks:
        peak_strengths = [y[i] for i in filt_peaks]
        best_peak = filt_peaks[int(np.argmax(peak_strengths))]
    else:
        best_peak = int(np.argmax(y))  # fallback: 전체 최대

    if filt_valleys:
        valley_strengths = [y[i] for i in filt_valleys]
        best_valley = filt_valleys[int(np.argmax(valley_strengths))]
    else:
        best_valley = int(np.argmin(y))  # fallback: 전체 최소

    # 7) 결과 정리
    lambda_max    = float(x[best_peak])
    intensity_max = float(y[best_peak])
    lambda_valley = float(x[best_valley])
    intensity_valley = float(y[best_valley])
    p_v_ratio = (intensity_max - intensity_valley) / intensity_valley if intensity_valley != 0 else np.inf

    UV_result = OrderedDict([
        ("lambda_max", lambda_max),
        ("valley_lambda", lambda_valley),
        ("p_v_ratio", p_v_ratio)
    ])
    uv_dict["Property"] = UV_result

    return UV_result, uv_dict

with open('DB\\s0.json','r') as file:
    spectrum = json.load(file)
testspectrum = spectrum['result']['UV_GetAbs']['Data']
uv_result, calc_result = calculatePL_Data_slope(testspectrum, WavelengthMin=410, WavelengthMax=700, BoxCarSize=10, Prominence=0.01)
print(calc_result['Property'])
