
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [py example simple] UV analysis function for raw spectrum
# @author   Nayeon Kim (kny@kist.re.kr), Hyuk Jun Yoo (yoohj9475@kist.re.kr)
# TEST 2022-02-21, 2022-08-10 

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from numpy.polynomial import Chebyshev
import time
from pathlib import Path
from scipy.signal import find_peaks, peak_prominences, peak_widths, savgol_filter
from scipy.ndimage import gaussian_filter1d
from scipy.fft import rfft, irfft, rfftfreq
from collections import OrderedDict
from scipy.interpolate import UnivariateSpline
# with open("/home/sdl-pc/catkin_ws/src/doosan-robot/ref_UV.json", "r") as json_file:
#     reference_dict = json.load(json_file)
# with open("/home/sdl-pc/catkin_ws/src/doosan-robot/Abs_UV.json", "r") as json_file:
#     uv_dict = json.load(json_file)

def _units_to_points(x, length_x, min_pts=3):
    """실수 단위 길이(length_x)를 포인트 수로 변환 (Δx의 중앙값 사용)."""
    dx = np.diff(x)
    med_dx = np.median(dx) if len(dx) else 1.0
    n = max(min_pts, int(round(length_x / max(med_dx, 1e-12))))
    return n

def trim_by_rolling_std_units(x, y, window_x=5.0, sigma_th=0.01, stable_span_x=10.0):
    """
    이동 표준편차 기준으로 안정화 컷오프.
    - window_x: 이동표준편차를 계산할 윈도우의 x-길이 (예: 5.0 nm)
    - sigma_th: 이동표준편차 임계값
    - stable_span_x: 임계 이하가 연속적으로 유지되어야 하는 x-길이
    반환: (x_trim, y_trim, cut_idx)
    """
    x = np.asarray(x); y = np.asarray(y)
    w = _units_to_points(x, window_x, min_pts=5)
    L = _units_to_points(x, stable_span_x, min_pts=1)

    pad = w//2
    ypad = np.pad(y, (pad, pad), mode='edge')
    sigma = np.array([np.std(ypad[i:i+w]) for i in range(len(y))])

    ok = sigma <= sigma_th
    cnt, cut = 0, 0
    for i, v in enumerate(ok):
        cnt = cnt + 1 if v else 0
        if cnt >= L:
            cut = i - L + 1
            break
    return x[cut:], y[cut:]

def trim_by_slope_stability_units(x, y, window_x=7.5, slope_std_th=0.002, stable_span_x=10.0):
    """
    1차 미분(기울기)의 이동 표준편차 기준.
    - window_x: 기울기 안정성 평가 윈도우의 x-길이
    - slope_std_th: 기울기 이동표준편차 임계값
    - stable_span_x: 임계 이하가 연속적으로 유지되어야 하는 x-길이
    """
    x = np.asarray(x); y = np.asarray(y)
    w = _units_to_points(x, window_x, min_pts=5)
    L = _units_to_points(x, stable_span_x, min_pts=1)

    dy = np.gradient(y, x)
    pad = w//2
    dypad = np.pad(dy, (pad, pad), mode='edge')
    sstd = np.array([np.std(dypad[i:i+w]) for i in range(len(y))])

    ok = sstd <= slope_std_th
    cnt, cut = 0, 0
    for i, v in enumerate(ok):
        cnt = cnt + 1 if v else 0
        if cnt >= L:
            cut = i - L + 1
            break
    return x[cut:], y[cut:]

def trim_by_local_snr_units(x, y, window_x=8.0, snr_th=0.05, stable_span_x=10.0):
    """
    로컬 SNR(= 이동표준편차/이동평균) 기준.
    - window_x: 평균/표준편차 평가 윈도우의 x-길이
    - snr_th: 노이즈비 임계값
    - stable_span_x: 임계 이하가 연속적으로 유지되어야 하는 x-길이
    """
    x = np.asarray(x); y = np.asarray(y)
    w = _units_to_points(x, window_x, min_pts=5)
    L = _units_to_points(x, stable_span_x, min_pts=1)

    pad = w//2
    ypad = np.pad(y, (pad, pad), mode='edge')
    mu  = np.array([np.mean(ypad[i:i+w]) for i in range(len(y))])
    sig = np.array([np.std (ypad[i:i+w]) for i in range(len(y))])
    noise_ratio = np.divide(sig, np.maximum(mu, 1e-12))

    ok = noise_ratio <= snr_th
    cnt, cut = 0, 0
    for i, v in enumerate(ok):
        cnt = cnt + 1 if v else 0
        if cnt >= L:
            cut = i - L + 1
            break
    return x[cut:], y[cut:]

def getCleanSpecturm(uv_dict, reference_dict):
    '''
    get clean spectrum using ref 
    :param uv_dict (dict): get uv information (in dict) belong to USB2000+
    :prarm reference_dict(dict): get uv information (in dict) belong to USB2000+

    :retrun: uv_dict (dict): clean data using reference peak
    '''
    # uv_dict['RawSpectrum'] = [np.log10(np.asarray(reference_dict['RawSpectrum'][i])/np.asarray(uv_dict['RawSpectrum'][i])) for i in range(len(uv_dict['RawSpectrum']))]
    with open('Analysis/background.json','r') as file:
            background_dict = json.load(file)

    ref_spectrum = np.array([reference_dict['Wavelength'],reference_dict['RawSpectrum']], dtype = float)
    ref_smoothed = smooth_Boxcar(rawSpectrum=ref_spectrum, box_size=5)
    reference_dict['RawSpectrum'] = ref_smoothed.tolist()
    uv_spectrum = np.array([uv_dict['Wavelength'],uv_dict['RawSpectrum']], dtype = float)
    uv_smoothed = smooth_Boxcar(rawSpectrum=uv_spectrum, box_size=5)
    uv_dict['RawSpectrum'] = uv_smoothed.tolist()
    bgd_spectrum = np.array([background_dict['Wavelength'],background_dict['RawSpectrum']], dtype = float)
    bgd_smoothed = smooth_Boxcar(rawSpectrum=bgd_spectrum, box_size=5)
    background_dict['RawSpectrum'] = bgd_smoothed.tolist()
    absorbances = []
    for ref, measured, bgd  in zip (reference_dict['RawSpectrum'], uv_dict['RawSpectrum'], background_dict['RawSpectrum']):
        try:
            if ref == 0 or (measured-bgd) == 0:
                absorbances.append(0)
                continue
            absorbances.append(np.log10(abs(ref/(measured-bgd))))
        except:
            break
    uv_dict['RawSpectrum'] = absorbances
    return uv_dict

def getSpectrumArray(uv_dict):
    '''
    extract rawspectrum data from jsonfile

    :param uv_dict (dict): get uv information (in dict) belong to USB2000+

    :return: rawspectrum (numpy.array): [[Wavelength],[Intensity]]
    '''   
    dataWavelength = uv_dict['Wavelength']
    dataIntensity = uv_dict['RawSpectrum']
    dataWavelength_array = np.array(dataWavelength)
    dataIntensity_array = np.array(dataIntensity)
    concatWavelengthIntensity = np.concatenate((dataWavelength_array, dataIntensity_array),axis = 0)
    rawspectrum = concatWavelengthIntensity.reshape((2,int(len(concatWavelengthIntensity)/2)))

    return rawspectrum

def getLocalSpectrumArray(file_path = ''):
    '''
    extract rawspectrum data from jsonfile

    :param file_path (str): location of UV data file

    :instance uv_dict (dict): get uv information (in dict) belong to USB2000+

    :return: rawspectrum (numpy.array): [[Wavelength],[Intensity]]
    '''   
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    # Recipe_Json의 format이 바뀌면 바꿔야할 부분 
    # uv_dict=data[0]["result"][0] 
    # dataWavelength = uv_dict['GetUVdata']['Wavelength']
    # dataIntensity = uv_dict['GetUVdata']['RawSpectrum']
    dataWavelength = data['Wavelength']
    dataIntensity = data['RawSpectrum']
    
    dataWavelength_array = np.array(dataWavelength)
    dataIntensity_array = np.array(dataIntensity)
    concatWavelengthIntensity = np.concatenate((dataWavelength_array, dataIntensity_array),axis = 0)
    rawspectrum = concatWavelengthIntensity.reshape((2,int(len(concatWavelengthIntensity)/2)))

    return rawspectrum

def getSliceSpectrum2(rawSpectrum, min_wl=350, max_wl=800):
    """
    Step 1: Find max Y in [min_wl, min_wl+150]
    Step 2: Slice spectrum from [X_max, X_max+150]
    """
    wavelengths = np.array(rawSpectrum[0])
    intensities = np.array(rawSpectrum[1])

    # Step 1: 찾기
    mask1 = (wavelengths >= min_wl) & (wavelengths <= min_wl + 150)
    if not np.any(mask1):
        raise ValueError("No data points in first search window.")

    sub_wl = wavelengths[mask1]
    sub_int = intensities[mask1]
    max_idx = np.argmax(sub_int) 
    x_max = sub_wl[max_idx]

    # Step 2: Slice [x_max, x_max + 150]
    mask2 = (wavelengths >= x_max) & (wavelengths <= x_max+150)
    slice_wl = wavelengths[mask2]
    slice_int = intensities[mask2]

    if len(slice_wl) == 0:
        raise ValueError("No data points found in final slice.")

    return np.array([slice_wl, slice_int])

def getSliceSpectrum3(rawSpectrum=[],min_wl=350, max_wl=800):
    """
    extract specific range of spectrum

    :param min (int): set minimum point of target Wavelengh range
    :param max (int): set maximum point of target Wavelengh range
    :param rawSpectrum (numpy.array): [[Wavelength],[Intensity]]
    
    :return: sliceSpectrum (numpy.array): sliced spectrum -> range(min, max)
    """
    condition_mask = [
        min_wl <= wl <= min_wl+150 for wl in rawSpectrum[0]
    ]
    
    filtered_wavelengths = [wl for wl, cond in zip(rawSpectrum[0], condition_mask) if cond]
    filtered_intensities = [val for val, cond in zip(rawSpectrum[1], condition_mask) if cond]

    local_max_idx = np.argmax(filtered_intensities)
    #print(local_max_idx)
    max_wavelength = filtered_wavelengths[local_max_idx]
    min2 = max(min_wl, max_wavelength)
    sliceWavelength=[]
    sliceIntensity=[]
    for i in range(len(rawSpectrum[0])):
        if rawSpectrum[0][i] > min2 and rawSpectrum[0][i] < (min2+150):
            sliceWavelength.append(rawSpectrum[0][i])
            sliceIntensity.append(rawSpectrum[1][i])
    concatWavelengthIntensity = np.concatenate((sliceWavelength, sliceIntensity), axis = 0)
    sliceSpectrum = concatWavelengthIntensity.reshape((2, int(len(concatWavelengthIntensity)/2)))

    return sliceSpectrum
def getSliceSpectrum(rawSpectrum=[],min_wl=350, max_wl=800):
    """
    extract specific range of spectrum

    :param min (int): set minimum point of target Wavelengh range
    :param max (int): set maximum point of target Wavelengh range
    :param rawSpectrum (numpy.array): [[Wavelength],[Intensity]]
    
    :return: sliceSpectrum (numpy.array): sliced spectrum -> range(min, max)
    """
    sliceWavelength=[]
    sliceIntensity=[]
    for i in range(len(rawSpectrum[0])):
        if rawSpectrum[0][i] > min_wl and rawSpectrum[0][i] < max_wl:
            sliceWavelength.append(rawSpectrum[0][i])
            sliceIntensity.append(rawSpectrum[1][i])
    concatWavelengthIntensity = np.concatenate((sliceWavelength, sliceIntensity), axis = 0)
    sliceSpectrum = concatWavelengthIntensity.reshape((2, int(len(concatWavelengthIntensity)/2)))

    return sliceSpectrum

def normalizeSpectrum(input_rawSpectrum):
    '''
    normalize spectrum

    :param input_rawSpectrum (numpy.array): [[Wavelength],[Intensity]]

    :return: input_rawSpectrum (list): normalized input_rawSpectrum

    '''
    wavelength=input_rawSpectrum[0]
    absorbance_spectrum=input_rawSpectrum[1]
    input_rawSpectrum[1] = (absorbance_spectrum - np.min(absorbance_spectrum)) / (np.max(absorbance_spectrum) - np.min(absorbance_spectrum))
    return input_rawSpectrum

def smooth_Boxcar(rawSpectrum, box_size):
    '''
        Remove noise from raw spectrum using boxcar algorithm

        :param rawSpectrum (numpy.array): [[Wavelength],[Intensity]]
        
        :retrun: smoothingSpectrum (numpy.array): rawSpectrum after smoothing -> [[Wavelength],[Intensity]]
    '''
    box = np.ones(box_size)/box_size
    spectrum_smooth = np.convolve(rawSpectrum[1], box, mode='same')
    spectrum_smooth = spectrum_smooth.reshape((1,len(rawSpectrum[1])))
    smoothingSpectrum = np.concatenate((rawSpectrum.T,spectrum_smooth.T), axis=1)
    smoothingSpectrum = np.delete(smoothingSpectrum.T, (1),axis=0)
    return smoothingSpectrum

def filter_by_prominence(indices, data, min_prom, is_peak=True, min_distance=5):
    filtered_indices = []
    for idx in indices:
        left_idx = max(0, idx - min_distance * 2)
        right_idx = min(len(data), idx + min_distance * 2)
        if is_peak:
            local_min = min(np.min(data[left_idx:idx]), np.min(data[idx:right_idx]))
            prominence = data[idx] - local_min
        else:
            local_max = max(np.max(data[left_idx:idx]), np.max(data[idx:right_idx]))
            prominence = local_max - data[idx]
        if prominence >= min_prom:
            filtered_indices.append(idx)
    return filtered_indices


def fourier_series_fit(x, y, cutoff=0.05):
    """
    Apply low-pass filtered Fourier series reconstruction.

    Parameters:
        x (np.array): Wavelength or time axis (1D)
        y (np.array): Signal values (1D)
        cutoff (float): Frequency threshold for low-pass filtering (unit: 1/distance in x)

    Returns:
        y_fit (np.array): Reconstructed signal
    """
    N = len(x)
    dx = x[1] - x[0]  # spacing
    freqs = rfftfreq(N, d=dx)  # frequency axis
    y_fft = rfft(y)  # forward FFT

    # Low-pass filtering
    y_fft[freqs > cutoff] = 0
    y_fit = irfft(y_fft, n=N)  # inverse FFT
    return x, y_fit

def smooth_polyfit(wavelengths, absorbances, degree=12):
    # Fit polynomial
    x_scaled = []
    wavelengths = np.array(wavelengths)
    wl_min, wl_max = wavelengths.min(), wavelengths.max()
    x_scaled = 2 * (wavelengths - wl_min) / (wl_max - wl_min) - 1
    coeffs = np.polyfit(x_scaled, absorbances, degree)
    poly_scaled = np.poly1d(coeffs)

    # 되돌릴 때도 x_scaled로 평가
    y_fit = poly_scaled(x_scaled)
    return wavelengths, y_fit


def find_peak_after_valley_by_gradient(wavelengths, y_fit, prominence=0.01):
    # 1차 미분 (gradient) 계산
    grad = np.gradient(y_fit, wavelengths)
    base = y_fit[wavelengths == 600]
    # valley: gradient가 -→+로 바뀌는 지점
    valleys, _ = find_peaks(-grad, prominence=prominence)

    # peak: gradient가 +→-로 바뀌는 지점
    peaks, _ = find_peaks(grad * -1, prominence=prominence)

    if len(valleys) == 0 or len(peaks) == 0:
        return 0, 0

    # 가장 먼저 등장하는 valley
    first_valley_idx = valleys[np.argmin(wavelengths[valleys])]
    valley_x = wavelengths[first_valley_idx]

    # 그 이후의 peak만 필터링
    valid_peaks = [p for p in peaks if wavelengths[p] > valley_x]
    if len(valid_peaks) == 0:
        return 0, 0

    # 가장 prominent한 peak 선택
    peak_values = y_fit[valid_peaks]
    best_peak_idx = np.argmax(peak_values)
    peak_x = wavelengths[valid_peaks[best_peak_idx]]

    print(f"First valley at: {valley_x:.2f} nm, Best peak after valley at: {peak_x:.2f} nm")
    peak_valley_ratio = (peak_x - base)/ (valley_x-base) if (valley_x-base) != 0 else 0

    return peak_valley_ratio, peak_x

def find_peak_after_valley_poly(wavelengths, y_fit, prominence=0.01):
    # Find valleys and peaks
    valleys, _ = find_peaks(-y_fit, prominence=prominence)
    peaks, _ = find_peaks(y_fit, prominence=prominence)

    if len(valleys) == 0 or len(peaks) == 0:
        return 0, 0

    # Step 1: 첫 valley 찾기
    first_valley_idx = valleys[np.argmin(wavelengths[valleys])]
    first_valley_x = wavelengths[first_valley_idx]

    # Step 2: 그 이후에 등장하는 peak만 필터링
    valid_peaks = [p for p in peaks if wavelengths[p] > first_valley_x]

    if len(valid_peaks) == 0:
        return 0, 0

    # Step 3: 그 중 가장 prominent한 peak 선택
    peak_values = y_fit[valid_peaks]
    best_peak_idx = np.argmax(peak_values)
    peak_wavelength = wavelengths[valid_peaks[best_peak_idx]]
    valley_wavelength = first_valley_x

    print(peak_wavelength, valley_wavelength)

    peak_valley_ratio = peak_wavelength / valley_wavelength if valley_wavelength != 0 else 0
    return peak_valley_ratio, peak_wavelength

def find_peak_valley_poly(wavelengths, y_fit, prominence=0.01):
    peaks, _ = find_peaks(y_fit, prominence=prominence)
    valleys, _ = find_peaks(-y_fit, prominence=prominence)

    # If peaks or valleys not found, return zeros
    if len(peaks) == 0 or len(valleys) == 0:
        return 0, 0

    # Use most prominent peak and valley
    peak_values = y_fit[peaks]
    valley_values = y_fit[valleys]
    max_peak_idx = np.argmax(peak_values)
    max_valley_idx = np.argmax(valley_values)

    peak_wavelength = wavelengths[peaks[max_peak_idx]]
    valley_wavelength = wavelengths[valleys[max_valley_idx]]
    print(peak_wavelength,valley_wavelength)
    peak_valley_ratio = peak_wavelength / valley_wavelength if valley_wavelength != 0 else 0
    return peak_valley_ratio, peak_wavelength

def polyfit_peak_valley(wavelengths, absorbances, degree=8, prominence=0.01):
    # Fit polynomial
    x_scaled = []
    wavelengths = np.array(wavelengths)
    wl_min, wl_max = wavelengths.min(), wavelengths.max()
    x_scaled = 2 * (wavelengths - wl_min) / (wl_max - wl_min) - 1
    coeffs = np.polyfit(x_scaled, absorbances, degree)
    poly_scaled = np.poly1d(coeffs)

    # 되돌릴 때도 x_scaled로 평가
    y_fit = poly_scaled(x_scaled)
    
    #coeffs = np.polyfit(wavelengths, absorbances, degree)
    #poly = np.poly1d(coeffs)
    #y_fit = poly(wavelengths)



    # Find peaks and valleys using the fitted curve
    peaks, _ = find_peaks(y_fit, prominence=prominence)
    valleys, _ = find_peaks(-y_fit, prominence=prominence)

    # If peaks or valleys not found, return zeros
    if len(peaks) == 0 or len(valleys) == 0:
        return 0, 0

    # Use most prominent peak and valley
    peak_values = y_fit[peaks]
    valley_values = y_fit[valleys]
    max_peak_idx = np.argmax(peak_values)
    max_valley_idx = np.argmax(valley_values)

    peak_wavelength = wavelengths[peaks[max_peak_idx]]
    valley_wavelength = wavelengths[valleys[max_valley_idx]]
    print(peak_wavelength,valley_wavelength)
    plt.plot(wavelengths, absorbances, label='Original')
    plt.plot(wavelengths, poly_scaled(x_scaled), label='Polyfit Curve (8th)', color='orange')
    plt.legend()
    plt.show()
    peak_valley_ratio = peak_wavelength / valley_wavelength if valley_wavelength != 0 else 0
    return peak_valley_ratio, peak_wavelength

def smooth_spline(wavelength, intensity, smoothing_factor=0.0010):
    wavelength = np.array(wavelength)
    intensity = np.array(intensity)

    spline = UnivariateSpline(wavelength, intensity, s=smoothing_factor)
    trend = spline(wavelength)

    return wavelength, trend


def find_pv_spline(wavelength, intensity, smoothing_factor=0.0010, min_prominence=0.002, min_distance=5, edge_threshold=0.0002):
    wavelength, trend = smooth_spline(wavelength=wavelength, intensity=intensity, smoothing_factor=smoothing_factor)
    grad = trend.derivative()
    second_deriv = trend.derivative(n=2)
    plt.plot(wavelength, grad)
    plt.show()
    sign_changes = []
    for i in range(1, len(grad)):
        if (grad[i - 1] > edge_threshold and grad[i] < -edge_threshold) or \
           (grad[i - 1] < -edge_threshold and grad[i] > edge_threshold):
            sign_changes.append(i)
        elif abs(grad[i]) < edge_threshold and abs(grad[i - 1]) > edge_threshold:
            sign_changes.append(i)

    peaks = [i for i in sign_changes if second_deriv[i] < -edge_threshold]
    valleys = [i for i in sign_changes if second_deriv[i] > edge_threshold]

    filtered_peaks = filter_by_prominence(peaks, trend, min_prominence, is_peak=True, min_distance=min_distance)
    filtered_valleys = filter_by_prominence(valleys, trend, min_prominence, is_peak=False, min_distance=min_distance)

    return filtered_peaks, filtered_valleys


def find_peaks_valleys_spline(
    wavelength,
    intensity,
    smoothing_factor=0.0010,
    min_prominence=0.002,
    min_distance=5,
    edge_threshold=0.0002
):
    wavelength = np.array(wavelength)
    intensity = np.array(intensity)

    spline = UnivariateSpline(wavelength, intensity, s=smoothing_factor)
    trend = spline(wavelength)
    grad = spline.derivative()(wavelength)
    second_deriv = spline.derivative(n=2)(wavelength)
    plt.plot(wavelength,spline(wavelength))
    plt.show()
    sign_changes = []
    for i in range(1, len(grad)):
        if (grad[i - 1] > edge_threshold and grad[i] < -edge_threshold) or \
           (grad[i - 1] < -edge_threshold and grad[i] > edge_threshold):
            sign_changes.append(i)
        elif abs(grad[i]) < edge_threshold and abs(grad[i - 1]) > edge_threshold:
            sign_changes.append(i)

    peaks = [i for i in sign_changes if second_deriv[i] < -edge_threshold]
    valleys = [i for i in sign_changes if second_deriv[i] > edge_threshold]

    filtered_peaks = filter_by_prominence(peaks, trend, min_prominence, is_peak=True, min_distance=min_distance)
    filtered_valleys = filter_by_prominence(valleys, trend, min_prominence, is_peak=False, min_distance=min_distance)

    return filtered_peaks, filtered_valleys
'''
def  analysisPickVelly(rawSpectrum, prominence = 0.01, width_threshold=10):
    Idx_peaks, properties_peaks = find_peaks(rawSpectrum[1], prominence=prominence, width=width_threshold)
    Idx_velly, properties_velly = find_peaks(-rawSpectrum[1], prominence=prominence, width=width_threshold)

    FWHM_peaks = peak_widths(rawSpectrum[1], Idx_peaks)[0]
    filtered_peaks = [peak for peak, width in zip(Idx_peaks, Idx_velly) if width > width_threshold]

    peak_list = []
    velly_list = []
    Intensity_peaks_list = []
    Intensity_velly_list = []
    if len(Idx_peaks)==0:
        pass

    else:    
        peak_list = rawSpectrum[0][Idx_peaks].tolist()
        velly_list = rawSpectrum[0][Idx_velly].tolist()
        Intensity_peaks_list = properties_peaks["prominences"].tolist()
        Intensity_velly_list = properties_velly["prominences"].tolist()

    peak_value = 0
    velly_value = 0
    max_FWHM = 0

    if len(Idx_peaks) == 0:
        peak_velly_ratio = 0
        peak_value = 0
    else:    
        maxPeakIdx = Intensity_peaks_list.index(max(Intensity_peaks_list))
        maxVellyIdx = Intensity_velly_list.index(max(Intensity_velly_list))
        peak_value = peak_list[maxPeakIdx] # Wavelength_peaks[maxIdx] = [value]
        velly_value = velly_list[maxVellyIdx]

        peak_velly_ratio = peak_value/velly_value


    return peak_velly_ratio, peak_value
'''

def analysisPickVelly2(rawSpectrum, prominence = 0.01, width_threshold=10):
    Idx_peaks, properties_peaks = find_peaks(rawSpectrum[1], prominence=prominence, width=width_threshold)
    Idx_velly, properties_velly = find_peaks(-rawSpectrum[1], prominence=prominence, width=width_threshold)

    FWHM_peaks = peak_widths(rawSpectrum[1], Idx_peaks)[0]
    filtered_peaks = [peak for peak, width in zip(Idx_peaks, Idx_velly) if width > width_threshold]

    peak_list = []
    velly_list = []
    Intensity_peaks_list = []
    Intensity_velly_list = []
    if len(Idx_peaks)==0:
        pass

    else:    
        peak_list = rawSpectrum[0][Idx_peaks].tolist()
        velly_list = rawSpectrum[0][Idx_velly].tolist()
        Intensity_peaks_list = properties_peaks["prominences"].tolist()
        Intensity_velly_list = properties_velly["prominences"].tolist()

    peak_value = 0
    velly_value = 0
    peak_wave=0
    velly_wave=0
    max_FWHM = 0
    len_base = len(rawSpectrum[1])-1
    base_value = rawSpectrum[1][len_base]
    wave_list = rawSpectrum[0].tolist()

    if len(Idx_peaks) == 0 or len(Intensity_peaks_list) == 0:
        peak_velly_ratio = 0
        maxPeakIdx = 0
        peak_value = 0
    elif len(Idx_velly) == 0 or len(Intensity_velly_list) == 0:
        peak_velly_ratio = 0
        maxVellyIdx = 0
        velly_value = 0
    else:    
        maxPeakIdx = Intensity_peaks_list.index(max(Intensity_peaks_list))
        maxVellyIdx = Intensity_velly_list.index(max(Intensity_velly_list))
        peak_wave = peak_list[maxPeakIdx] # Wavelength_peaks[maxIdx] = [value]
        velly_wave = velly_list[maxVellyIdx]
        peak_value = rawSpectrum[1][wave_list.index(peak_wave)]
        velly_value = rawSpectrum[1][wave_list.index(velly_wave)]

        peak_velly_ratio = (peak_value-base_value)/(velly_value-base_value)
        if peak_velly_ratio < 0 :
            peak_wave = 0
            peak_velly_ratio = 0
    print(velly_wave)
    return peak_velly_ratio, peak_wave

def analysisPickVelly(
    rawSpectrum, 
    prominence=0.01, 
    width_threshold=10,   # (1) find_peaks 최소 폭, (2) 피크–밸리 최소 간격
):
    """
    rawSpectrum: [wavelength_array, intensity_array]
    prominence:  find_peaks에 전달할 prominence
    width_threshold: 
        - find_peaks에 넘길 최소 폭(width) 조건
        - 피크–밸리 간격의 하한: Δλ ≥ width_threshold
    a:
        - 피크–밸리 간격의 상한 여유: Δλ ≤ width_threshold + a
    반환: (peak_velly_ratio, peak_wave)
        - 조건을 만족하는 쌍이 없으면 (0.0, 0.0) 반환
    """
    wl = np.asarray(rawSpectrum[0])
    y  = np.asarray(rawSpectrum[1])
    if wl.size != y.size or wl.size == 0:
        raise ValueError("rawSpectrum의 길이가 맞지 않거나 비어있습니다.")

    # 1) 피크/밸리 후보 (폭 조건은 width_threshold로 필터)
    Idx_peaks, props_p = find_peaks(y,  prominence=prominence, width=width_threshold)
    Idx_val  = find_peaks(-y, prominence=prominence, width=width_threshold)[0]
    #print(Idx_peaks)
    #print(Idx_val)
    if len(Idx_peaks) == 0 or len(Idx_val) == 0:
        return 0.0, 0.0

    # 2) 좌표/세기 배열
    wl_peaks = wl[Idx_peaks]
    wl_vals  = wl[Idx_val]
    y_peaks  = y[Idx_peaks]
    y_vals   = y[Idx_val]
    base_val = float(y[-1])  # baseline: 마지막 값 (원 코드 유지)

    # 3) 피크–밸리 간격 마스크: width_threshold ≤ Δλ ≤ width_threshold + a
    diff = np.abs(wl_peaks[:, None] - wl_vals[None, :])   # (n_peaks, n_vals)
    sep_mask = (diff >= width_threshold) & (diff <= (width_threshold + 20))

    if not sep_mask.any():
        return 0.0, 0.0

    # 4) PV ratio 행렬 계산 + 간격 조건 반영
    den = y_vals[None, :] - base_val                           # 분모
    pv_matrix = np.where(den == 0.0, 0.0, (y_peaks[:, None] - base_val) / den)
    pv_matrix = np.where(sep_mask, pv_matrix, -np.inf)         # 조건 미충족은 제외

    if np.all(~np.isfinite(pv_matrix)):                        # 모두 제외되면 실패
        return 0.0, 0.0

    i, j = np.unravel_index(np.nanargmax(pv_matrix), pv_matrix.shape)

    # 5) 선택된 결과
    peak_idx   = int(Idx_peaks[i])
    val_idx    = int(Idx_val[j])
    peak_wave  = float(wl[peak_idx])
    val_wave = float(wl[val_idx])  # 필요시 활용
    peak_velly_ratio = float(pv_matrix[i, j])
    #print(val_wave)
    # 음수면 무효 처리(원 코드 규칙 유지)
    if peak_velly_ratio < 0.0:
        return 0.0, 0.0

    return peak_velly_ratio, peak_wave

def analysisMultiPeak(rawSpectrum, prominence = 0.01, width =20):
    '''
        Anaylsis multi-Peak properties

        :param rawSpectrum (numpy.array): [[Wavelength],[Intensity]]
        :param prominence (float): minimum peak Intensity for detection
        :param width (int): minumum peak width for detection(ref. theoretical limits=22nm)

        :return: lambdamax_list (list): wavelength of each peaks
        :return: Intensity_peaks_list (list): intensity of each peaks
        :return: FWHM_peaks_list (list): width of each peaks

    '''
    Idx_peaks, properties = find_peaks(rawSpectrum[1], prominence=prominence, width=width)
    lambdamax_list = []
    Intensity_peaks_list = []
    FWHM_peaks_list = []

    if len(Idx_peaks)==0:
        pass

    else:    
        lambdamax_list = rawSpectrum[0][Idx_peaks].tolist()
        Intensity_peaks_list = properties["prominences"].tolist()
        FWHM_peaks_list = [rawSpectrum[0][int(properties["right_ips"][i])]-rawSpectrum[0][int(properties["left_ips"][i])] for i in range(len(properties['right_ips']))]
        
    return lambdamax_list, Intensity_peaks_list, FWHM_peaks_list

def analysisSinglePeak(rawSpectrum, prominence = 0.01, width = 20):
    '''
    Anaylsis single-Peak properties

    :param rawSpectrum (numpy.array): [[Wavelength],[Intensity]]
    :param prominence (float): minimum peak Intensity for detection
    :param width (int): minumum peak width for detection

    :return: max_Wavelength (float): wavelength of each peaks
    :return: max_Intensity (float): intensity of each peaks
    :return: max_FWHM (float): width of each peaks

    '''    
    Wavelength_peaks, Intensity_peaks, FWHM_peaks = analysisMultiPeak(rawSpectrum,  prominence=prominence, width=width)
    max_Wavelength = 0
    max_Intensity = 0
    max_FWHM = 0
    if len(Wavelength_peaks) == 0:
        pass
    else:    
        maxIdx = Intensity_peaks.index(max(Intensity_peaks))

        max_Wavelength = Wavelength_peaks[maxIdx] # Wavelength_peaks[maxIdx] = [value]
        max_Intensity = rawSpectrum[1][maxIdx]
        max_FWHM = FWHM_peaks[maxIdx]

    return max_Wavelength, max_Intensity, max_FWHM

def getPlot(Wavelength_peaks, smooth_result, prominence=0.01, width=20, filename="test.png"):
    dir_name=time.strftime("%Y%m%d")
    TOTAL_PLOT_FOLDER = "{}/{}/{}/{}".format("DB","plot",dir_name, "individualPlot")
    if os.path.isdir(TOTAL_PLOT_FOLDER) == False:
        os.makedirs(TOTAL_PLOT_FOLDER)

    Idx_peaks, properties = find_peaks(smooth_result[1], prominence=prominence, width=width)

    if len(Wavelength_peaks)==0:
        plt.plot(smooth_result[0],smooth_result[1])
        plt.title(filename)
    else: 
        Idx_peaks = []
        properties["left_ips"]=properties["left_ips"].astype(int)
        properties["right_ips"]=properties["right_ips"].astype(int)
        
        for i in Wavelength_peaks:
            Idx_peaks.extend(np.where(smooth_result[0]==i)[0])
        plt.plot(smooth_result[0],smooth_result[1])
        plt.plot(Wavelength_peaks, smooth_result[1][Idx_peaks], "x")
        plt.title(filename)
        
        plt.vlines(x=smooth_result[0][Idx_peaks], ymin=smooth_result[1][Idx_peaks] - properties["prominences"],
            ymax = smooth_result[1][Idx_peaks], color = "C1")
        
        for i in range(len(Wavelength_peaks)):
            plt.hlines(y=properties["width_heights"][i], xmin=smooth_result[0][properties["left_ips"][i]],
            xmax=smooth_result[0][properties["right_ips"][i]], color = "C1")

    plot_filename="{}/{}".format(TOTAL_PLOT_FOLDER, filename)
    plt.savefig(plot_filename)
    plt.close()

def comparePlot(UV_result, MasterLoggerName, experiment_num, filename):
    """
    :params: UV_result (numpy.array)
    => [
        "Wavelength": [...],
        "RawSpectrum": [...],
    ]
    :param masterLoggerName (str): implement in dirname of plot --> self.MasterLoggerName
    :param experiment_num=0 (int): similar with cycle_num
    :param filename (str): implement in filename of plot
    """
    dir_name=time.strftime("%Y%m%d")
    TOTAL_PLOT_FOLDER = "{}/{}/{}/{}".format("DB","plot",dir_name, "comparePlot")
    if os.path.isdir(TOTAL_PLOT_FOLDER) == False:
        os.makedirs(TOTAL_PLOT_FOLDER)
    literature_data={
        "Find lambda_max=513nm & FWHM=96nm":"Analysis/Dataset(513nm).csv",
        "Find lambda_max=573nm & FWHM=134nm":"Analysis/Dataset(573nm).csv",
        "Find lambda_max=667nm & FWHM=191nm":"Analysis/Dataset(667nm).csv",
    }
    literauture_df=None
    target_subject=""
    for keys in literature_data.keys():
        if keys in MasterLoggerName:
            literauture_df=pd.read_csv(literature_data[keys])
            target_subject=keys
            break
    literauture_df
    literature_x=literauture_df["Wavelength"].to_numpy()
    literature_y=literauture_df["Intensity"].to_numpy()

    f, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.plot(literature_x,literature_y, linewidth=2.0, color="#800000", label="literature")
    ax.plot(UV_result[0],UV_result[1], linewidth=2.0, color="#000080",label="our result")
    # ax.fill_between(x_extra, y_extra, color='#FA8072', alpha=.25)
    ax.set(xlim=(300.0, 800.0))
    plt.title(target_subject)
    filename="{}/{}_{}(literature vs our result).png".format(TOTAL_PLOT_FOLDER, target_subject, experiment_num)
    plt.legend()
    plt.savefig(filename)
    plt.close()

def calculateUV_Data_clean(uv_df, smooth_sigma=2, wavelength_threshold=435, valley_prominence=0.001):
    smoothed = uv_df.apply(lambda y: gaussian_filter1d(y, sigma=smooth_sigma), axis=0)
    filtered_wavelengths = uv_df.index[(uv_df.index >= wavelength_threshold) & (uv_df.index <= 700)]
    smoothed_filtered = smoothed.loc[filtered_wavelengths]
    base_value = smoothed.loc[uv_df.index[np.abs(uv_df.index - 700).argmin()]]
    
    summary_data = []
    ncols = 1
    nrows = smoothed_filtered.shape[1]
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(8, 4 * nrows), sharex=True)
    if nrows == 1:
        axes = [axes]  # ensure iterable if only one plot

    for i, col in enumerate(smoothed_filtered.columns):
        ax = axes[i]
        y = smoothed_filtered[col]

        lambda_max_val = float(y.idxmax())
        peak_intensity = float(y.loc[lambda_max_val])

        inverted_y = -y.values
        peaks, properties = find_peaks(inverted_y, prominence=valley_prominence)

        if len(peaks) > 0:
            valley_index = peaks[0]
            valley_wavelength = float(y.index[valley_index])
            valley_intensity = float(y.iloc[valley_index])
        else:
            valley_wavelength = float('nan')
            valley_intensity = float('nan')

        try:
            ratio = (peak_intensity - base_value)/(valley_intensity - base_value) if (valley_intensity - base_value) != 0 else float('inf')
        except:
            ratio = float('nan')
    
    return ratio, lambda_max_val

def calculateUV_Data_clean_pl(
    uv_df: pd.DataFrame
) -> float:
    """
    Calculate PL spectrum summary (lambda max, intensity max, FWHM)
    using scipy.signal.find_peaks and peak_widths without wavelength threshold.

    Parameters:
        uv_df (pd.DataFrame): DataFrame with wavelength as index and each column as a sample.

    Returns:
        pd.DataFrame: Summary with lambda max, intensity max, and FWHM for each sample.
    """
    summary = []

    for sample in uv_df.columns:
        x = uv_df.index.values
        y = uv_df[sample].values

        # Peak detection
        peaks, _ = find_peaks(y)
        if len(peaks) == 0:
            summary.append({
                "Sample": sample,
                "Lambda Max (nm)": np.nan,
                "Intensity Max": np.nan,
                "FWHM": np.nan
            })
            continue

        # Choose the highest peak
        max_peak_idx = peaks[np.argmax(y[peaks])]
        lambda_max = x[max_peak_idx]
        intensity_max = y[max_peak_idx]

        # Compute FWHM using peak_widths
        results_half = peak_widths(y, [max_peak_idx], rel_height=0.5)
        fwhm_width = results_half[0][0]
        fwhm_left = results_half[2][0]
        fwhm_right = results_half[3][0]

        # Convert from index to wavelength span
        if 0 <= fwhm_left < len(x) and 0 <= fwhm_right < len(x):
            fwhm = x[int(fwhm_right)] - x[int(fwhm_left)]
        else:
            fwhm = np.nan


    return lambda_max, fwhm, intensity_max


def save_sliced2_to_excel_single_sheet(
    sliced2,
    sample_name: str,
    excel_path: Path
):
    """
    Save sliced UV spectrum into a single Excel sheet,
    appending each sample as new columns.

    Parameters:
        sliced2 (tuple): (wavelength_array, absorbance_array)
        sample_name (str): e.g. 'Sample_2'
        excel_path (Path): Excel file path
    """
    wl, ab = sliced2

    new_df = pd.DataFrame({
        f"{sample_name}_Wavelength": wl,
        f"{sample_name}_Absorbance": ab
    })

    if excel_path.exists():
        # 기존 데이터 로드
        existing_df = pd.read_excel(excel_path)

        # row 수가 다를 수 있으므로 index 기준 concat
        combined_df = pd.concat([existing_df, new_df], axis=1)
    else:
        combined_df = new_df

    combined_df.to_excel(excel_path, index=False)

def save_to_fig(uv_df= pd.DataFrame, i = float):
    for sample in uv_df.columns:
        x = uv_df.index.values
        y = uv_df[sample].values

        # Peak detection
        spectrum = np.array([x,y], dtype = float)
        order = np.argsort(spectrum[0])
        spectrum = np.array([spectrum[0][order], spectrum[1][order]], dtype = float)
        x_eval = np.linspace(350, 950, 20000)
        trend = np.interp(x_eval, spectrum[0], spectrum[1])
        raw = np.array([x_eval, trend], dtype=float)
        
        smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=199)
        sliced = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)
        savgoled = selective_noise_correction(sliced, noise_range=(360, 700), window_length=11, polyorder=3)
        poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
        sliced2 = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)
        sliced3 = getSliceSpectrum(rawSpectrum=(sliced2[1],sliced2[0]), min_wl=0, max_wl=1)
        plt.figure()
        plt.plot(sliced3[1],sliced3[0])
        plt.savefig(os.path.join("fig", f'fig{i}.png'))
        plt.close()
    
def sliced_return(uv_df= pd.DataFrame, i = float):
    for sample in uv_df.columns:
        x = uv_df.index.values
        y = uv_df[sample].values

        # Peak detection
        spectrum = np.array([x,y], dtype = float)
        order = np.argsort(spectrum[0])
        spectrum = np.array([spectrum[0][order], spectrum[1][order]], dtype = float)
        x_eval = np.linspace(350, 950, 20000)
        trend = np.interp(x_eval, spectrum[0], spectrum[1])
        raw = np.array([x_eval, trend], dtype=float)
        
        smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=199)
        sliced = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)
        savgoled = selective_noise_correction(sliced, noise_range=(360, 700), window_length=11, polyorder=3)
        poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
        sliced2 = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)
        sliced3 = getSliceSpectrum(rawSpectrum=(sliced2[1],sliced2[0]), min_wl=0, max_wl=1)
    return sliced3



def calculateUV_Data_clean_csv(
    uv_df: pd.DataFrame
) -> float:
    """
    Calculate PL spectrum summary (lambda max, intensity max, FWHM)
    using scipy.signal.find_peaks and peak_widths without wavelength threshold.

    Parameters:
        uv_df (pd.DataFrame): DataFrame with wavelength as index and each column as a sample.

    Returns:
        pd.DataFrame: Summary with lambda max, intensity max, and FWHM for each sample.
    """
    summary = []
    excel_path = Path("DB26") / "sliced2_uv_spectra.xlsx"
    txt_path = Path('DB26')/ "s2_2.txt"
    for sample in uv_df.columns:
        x = uv_df.index.values
        y = uv_df[sample].values

        # Peak detection
        spectrum = np.array([x,y], dtype = float)
        order = np.argsort(spectrum[0])
        spectrum = np.array([spectrum[0][order], spectrum[1][order]], dtype = float)
        x_eval = np.linspace(350, 950, 20000)
        trend = np.interp(x_eval, spectrum[0], spectrum[1])
        raw = np.array([x_eval, trend], dtype=float)
        
        smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=199)
        
        #plt.plot(smoothed[0],smoothed[1])
        #plt.show()
        sliced = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)
        #plt.plot(sliced[0],sliced[1])
        #plt.show()
        savgoled = selective_noise_correction(sliced, noise_range=(360, 700), window_length=11, polyorder=3)
        #plt.plot(savgoled[0],savgoled[1])
        #lt.show()
        
        #cut_x, cut_y = trim_by_rolling_std_units(sliced2[0], sliced2[1], window_x=5.0, sigma_th=0.01, stable_span_x=10.0)
        #cut_x, cut_y = trim_by_slope_stability_units(sliced[0], sliced[1], window_x=9, slope_std_th=0.011, stable_span_x=4.0)
        #cut_x, cut_y = trim_by_local_snr_units(sliced2[0], sliced2[1], window_x=5, snr_th=0.05, stable_span_x=10.0)
        #sliced = (cut_x,cut_y)
        #poly_wl, poly_ab = smooth_polyfit(sliced[0], sliced[1], degree=19)
        poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)
        #poly_wl, poly_ab = smooth_polyfit(smoothed[0], smoothed[1], degree=12)
        #poly_wl, poly_ab = select_degree_cheb(sliced, deg_min=1, deg_max=30, kfold=5)
        #plt.plot(poly_wl,poly_ab)
        #plt.show()
        #smoothed2 = smooth_Boxcar(rawSpectrum=np.array([savgoled[0],savgoled[1]], dtype=float), box_size=159)
        #sliced2 = getSliceSpectrum(rawSpectrum=smoothed2, min_wl=420, max_wl=550)
        sliced2 = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)
        #sliced2 = getSliceSpectrum(rawSpectrum=smoothed2, min_wl=420, max_wl=550)

        #save_sliced2_to_excel_single_sheet(sliced2=sliced2,sample_name=sample,excel_path=excel_path)
        
        #plt.plot(sliced2[0],sliced2[1])
        #plt.show()
        sliced3 = getSliceSpectrum(rawSpectrum=(sliced2[1],sliced2[0]), min_wl=0, max_wl=1)
        #plt.plot(sliced3[1],sliced3[0])
        #plt.show()
        '''
        with txt_path.open("w", encoding="utf-8") as f:
            for j in range(len(sliced2[0])):
                f.write(f'{sliced2[0][j]}, {sliced2[1][j]}\n')
        '''
        peak_velly_ratio, peak_value = analysisPickVelly(rawSpectrum=(sliced3[1],sliced3[0]), prominence=0.0005, width_threshold=8)
        wave, inten, fwhm = analysisSinglePeak(rawSpectrum=(sliced3[1],sliced3[0]), prominence = 0.01, width = 20)
        #print(wave, inten, fwhm)
        


    return peak_velly_ratio, peak_value

def  calculateUV_Data(uv_dict, reference_dict, WavelengthMin=300, WavelengthMax=849, BoxCarSize=10, Prominence=0.01, PeakWidth=20):
    '''
    Anaylsis multi-Peak properties

    :param uv_dict (dict) : 
    {
        "Name": "C:/Data/20211129_113238_Ag_1.json", 
        "Wavelength": [...],
        "RawSpectrum": [...],
    }
    :param WavelengthMin=300 (int): slice wavlength section depending on WavelengthMin and WavelengthMax
    :param WavelengthMax=800 (int): slice wavlength section depending on wavelength_min and WavelengthMax
    :param BoxCarSize=10 (int): smooth strength
    :param Prominence=0.01 (float): minimum peak Intensity for detection
    :param width=20 (int): minumum peak width for detection
    :param experiment_num=0 (int): similar with cycle_num
    :param masterLoggerName (str): implement in filename of plot

    :return: UV_result, uv_dict (dict) : 
    uv_dict-->{
        "Name": "C:/Data/20YYMMDD_hhmmss_Abs_NP.json",
        "Wavelength": [...],
        "RawSpectrum": [...],
        "Property": {
            "lambdamax":[...],
            "Intensity":[...],
            "FWHM":[...],
        } // add new key:value
    }
    '''
    clean_dict=getCleanSpecturm(uv_dict,reference_dict)
    rawSpectrum = getSpectrumArray(uv_dict=clean_dict)
    #sliceSpectrum = getSliceSpectrum(rawSpectrum, min=WavelengthMin, max=WavelengthMax)
    # smooth_result = smooth_Boxcar(sliceSpectrum,box_size=BoxCarSize)
    smooth_result = smooth_Boxcar(rawSpectrum,box_size=BoxCarSize)
    sliceSpectrum = getSliceSpectrum(smooth_result, min=WavelengthMin, max=WavelengthMax)
    peak_velly_ratio, peak_value = analysisPickVelly(rawSpectrum=sliceSpectrum, prominence=Prominence, width_threshold=PeakWidth)

    UV_result = OrderedDict()
    # UV_result["lambdamax_multi"] = lambdamax_list
    # UV_result["intensity_multi"] = Intensity_peaks_list
    # UV_result["FWHM_multi"] = FWHM_peaks_list
    UV_result["lambdamax"] = peak_value
    UV_result["p_v_ratio"] = peak_velly_ratio

    uv_dict["Property"]=UV_result
    
    # normalize_spectrum = normalizeSpectrum(smooth_result)
    # plot_filename="{}_{}.png".format(masterLoggerName, experiment_num)
    # getPlot(lambdamax_list, smooth_result=smooth_result, filename=plot_filename)
    # comparePlot(normalize_spectrum, masterLoggerName, experiment_num, plot_filename)

    return UV_result, uv_dict


def  calculatePL_Data(uv_dict, WavelengthMin=300, WavelengthMax=849, BoxCarSize=10, Prominence=0.01, PeakWidth=20):
    '''
    Anaylsis multi-Peak properties

    :param uv_dict (dict) : 
    {
        "Name": "C:/Data/20211129_113238_Ag_1.json", 
        "Wavelength": [...],
        "RawSpectrum": [...],
    }
    :param WavelengthMin=300 (int): slice wavlength section depending on WavelengthMin and WavelengthMax
    :param WavelengthMax=800 (int): slice wavlength section depending on wavelength_min and WavelengthMax
    :param BoxCarSize=10 (int): smooth strength
    :param Prominence=0.01 (float): minimum peak Intensity for detection
    :param width=20 (int): minumum peak width for detection
    :param experiment_num=0 (int): similar with cycle_num
    :param masterLoggerName (str): implement in filename of plot

    :return: UV_result, uv_dict (dict) : 
    uv_dict-->{
        "Name": "C:/Data/20YYMMDD_hhmmss_Abs_NP.json",
        "Wavelength": [...],
        "RawSpectrum": [...],
        "Property": {
            "lambdamax":[...],
            "Intensity":[...],
            "FWHM":[...],
        } // add new key:value
    }
    '''
    
    rawSpectrum = getSpectrumArray(uv_dict=uv_dict)
    smooth_result = smooth_Boxcar(rawSpectrum,box_size=BoxCarSize)
    sliceSpectrum = getSliceSpectrum(smooth_result, min_wl=WavelengthMin, max_wl=WavelengthMax)
    uv_dict["Wavelength"]=sliceSpectrum[0].tolist()
    uv_dict["RawSpectrum"]=sliceSpectrum[1].tolist()
    #peak_velly_ratio, peak_value = analysisPickVelly(rawSpectrum=sliceSpectrum, prominence=Prominence, width_threshold=PeakWidth)
    peak_velly_ratio, peak_value = polyfit_peak_valley(uv_dict["Wavelength"], uv_dict["RawSpectrum"], degree=8, prominence=Prominence)
    UV_result = OrderedDict()
    # UV_result["lambdamax_multi"] = lambdamax_list
    # UV_result["intensity_multi"] = Intensity_peaks_list
    # UV_result["FWHM_multi"] = FWHM_peaks_list
    UV_result["lambdamax"] = peak_value
    UV_result["p_v_ratio"] = peak_velly_ratio

    uv_dict["Property"]=UV_result
    
    # normalize_spectrum = normalizeSpectrum(smooth_result)
    # plot_filename="{}_{}.png".format(masterLoggerName, experiment_num)
    # getPlot(lambdamax_list, smooth_result=smooth_result, filename=plot_filename)
    # comparePlot(normalize_spectrum, masterLoggerName, experiment_num, plot_filename)

    return UV_result, uv_dict

def find_peaks_valleys_gradient(wavelength, intensity, smooth_sigma=1.0, min_prominence=0.01, 
                               min_distance=5, edge_threshold=0.001, width_threshold=None):
    """
    기울기를 이용하여 peak과 valley를 찾는 함수
    
    Parameters:
    -----------
    wavelength : array-like
        파장 데이터
    intensity : array-like
        강도 데이터
    smooth_sigma : float, default=1.0
        가우시안 스무딩 시그마 값 (노이즈 제거용)
    min_prominence : float, default=0.01
        최소 prominence (peak/valley의 최소 높이 차이)
    min_distance : int, default=5
        peak/valley 간 최소 거리 (인덱스 단위)
    edge_threshold : float, default=0.001
        기울기 변화 임계값
    
    Returns:
    --------
    dict: {
        'peak_wavelengths': list of peak wavelengths,
        'peak_intensities': list of peak intensities,
        'peak_indices': list of peak indices,
        'valley_wavelengths': list of valley wavelengths,
        'valley_intensities': list of valley intensities,
        'valley_indices': list of valley indices
    }
    """
    
    wavelength = np.array(wavelength)
    intensity = np.array(intensity)
    
    # 1. 스무딩 (노이즈 제거)
    if smooth_sigma > 0:
        smoothed_intensity = gaussian_filter1d(intensity, sigma=smooth_sigma)
    else:
        smoothed_intensity = intensity.copy()
    
    # 2. 1차 미분 계산 (기울기)
    gradient = np.gradient(smoothed_intensity, wavelength)
    
    # 3. 2차 미분 계산 (곡률)
    second_derivative = np.gradient(gradient, wavelength)
    
    # 4. 기울기가 0에 가까운 지점 찾기 (극값 후보)
    # 연속된 포인트들에서 기울기 부호가 바뀌는 지점 찾기
    gradient_sign_changes = []
    
    for i in range(1, len(gradient)):
        # 기울기 부호가 바뀌는 지점
        if (gradient[i-1] > edge_threshold and gradient[i] < -edge_threshold) or \
           (gradient[i-1] < -edge_threshold and gradient[i] > edge_threshold):
            gradient_sign_changes.append(i)
        # 기울기가 0에 매우 가까운 지점
        elif abs(gradient[i]) < edge_threshold and abs(gradient[i-1]) > edge_threshold:
            gradient_sign_changes.append(i)
    
    # 5. 극값 분류 (peak vs valley)
    peaks = []
    valleys = []
    
    for idx in gradient_sign_changes:
        if idx < len(second_derivative):
            # 2차 미분이 음수면 peak (위로 볼록)
            if second_derivative[idx] < -edge_threshold:
                peaks.append(idx)
            # 2차 미분이 양수면 valley (아래로 볼록)
            elif second_derivative[idx] > edge_threshold:
                valleys.append(idx)
    

    


    def filter_by_distance(indices, min_dist):
        if len(indices) <= 1:
            return indices
        
        filtered = [indices[0]]
        for i in range(1, len(indices)):
            if indices[i] - filtered[-1] >= min_dist:
                filtered.append(indices[i])
        return filtered
    
    peaks = filter_by_distance(peaks, min_distance)
    valleys = filter_by_distance(valleys, min_distance)
    
    # 7. Prominence 조건 적용
    def filter_by_prominence(indices, data, min_prom, is_peak=True):
        filtered_indices = []
        for idx in indices:
            # 주변 영역에서 prominence 계산
            left_idx = max(0, idx - min_distance*2)
            right_idx = min(len(data), idx + min_distance*2)
            
            if is_peak:
                # Peak의 경우: 주변 최소값과의 차이
                local_min = min(np.min(data[left_idx:idx]), np.min(data[idx:right_idx]))
                prominence = data[idx] - local_min
            else:
                # Valley의 경우: 주변 최대값과의 차이
                local_max = max(np.max(data[left_idx:idx]), np.max(data[idx:right_idx]))
                prominence = local_max - data[idx]
            
            if prominence >= min_prom:
                filtered_indices.append(idx)
        
    
        return filtered_indices
    
    peaks = filter_by_prominence(peaks, smoothed_intensity, min_prominence, is_peak=True)
    valleys = filter_by_prominence(valleys, smoothed_intensity, min_prominence, is_peak=False)
    def filter_by_width(indices, data, min_width):
        if not indices or min_width is None:
            return indices
        widths, *_ = peak_widths(data, indices, rel_height=0.5)
        filtered = [idx for idx, width in zip(indices, widths) if width >= min_width]
        return filtered

    peaks = filter_by_width(peaks, smoothed_intensity, width_threshold)
    valleys = filter_by_width(valleys, smoothed_intensity, width_threshold)
    # 8. 결과 정리
    result = {
        'peak_wavelengths': [wavelength[i] for i in peaks],
        'peak_intensities': [smoothed_intensity[i] for i in peaks],
        'peak_indices': peaks,
        'valley_wavelengths': [wavelength[i] for i in valleys],
        'valley_intensities': [smoothed_intensity[i] for i in valleys],
        'valley_indices': valleys,
        'smoothed_intensity': smoothed_intensity,
        'gradient': gradient,
        'second_derivative': second_derivative
    }
    
    return result

def calculate_pv_ratio_gradient(wavelength, intensity, **kwargs):
    """
    기울기 기반 방법으로 peak-valley ratio 계산
    
    Parameters:
    -----------
    wavelength : array-like
        파장 데이터
    intensity : array-like
        강도 데이터
    **kwargs : 
        find_peaks_valleys_gradient 함수의 추가 매개변수
    
    Returns:
    --------
    tuple: (pv_ratio, peak_wavelength, valley_wavelength)
    """
    
    result = find_peaks_valleys_gradient(wavelength, intensity, **kwargs)
    
    peak_wavelengths = result['peak_wavelengths']
    peak_intensities = result['peak_intensities']
    valley_wavelengths = result['valley_wavelengths']
    valley_intensities = result['valley_intensities']
    
    if len(peak_intensities) == 0 or len(valley_intensities) == 0:
        return 0, 0, 0
    
    # 가장 큰 peak와 가장 깊은 valley 선택
    max_peak_idx = np.argmax(peak_intensities)
    min_valley_idx = np.argmin(valley_intensities)
    
    peak_value = peak_wavelengths[max_peak_idx]
    valley_value = valley_wavelengths[min_valley_idx]
    peak_intensity = peak_intensities[max_peak_idx]
    valley_intensity = valley_intensities[min_valley_idx]
    
    # P-V ratio 계산
    if valley_intensity != 0:
        pv_ratio = peak_intensity / valley_intensity
    else:
        pv_ratio = float('inf')
    
    return pv_ratio, peak_value, valley_value

def plot_gradient_analysis(wavelength, intensity, result=None, **kwargs):
    """
    기울기 분석 결과를 시각화하는 함수
    """
    if result is None:
        result = find_peaks_valleys_gradient(wavelength, intensity, **kwargs)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 원본 데이터와 검출된 peak/valley
    axes[0,0].plot(wavelength, intensity, 'b-', alpha=0.7, label='Original')
    axes[0,0].plot(wavelength, result['smoothed_intensity'], 'g-', linewidth=2, label='Smoothed')
    
    # Peak 표시
    if result['peak_indices']:
        axes[0,0].scatter(result['peak_wavelengths'], result['peak_intensities'], 
                         color='red', s=100, marker='^', label='Peaks', zorder=5)
    
    # Valley 표시
    if result['valley_indices']:
        axes[0,0].scatter(result['valley_wavelengths'], result['valley_intensities'], 
                         color='blue', s=100, marker='v', label='Valleys', zorder=5)
    
    axes[0,0].set_xlabel('Wavelength (nm)')
    axes[0,0].set_ylabel('Intensity')
    axes[0,0].set_title('Peak and Valley Detection')
    axes[0,0].legend()
    axes[0,0].grid(True, alpha=0.3)
    
    # 1차 미분 (기울기)
    axes[0,1].plot(wavelength, result['gradient'], 'purple', linewidth=2)
    axes[0,1].axhline(y=0, color='black', linestyle='--', alpha=0.5)
    axes[0,1].set_xlabel('Wavelength (nm)')
    axes[0,1].set_ylabel('Gradient')
    axes[0,1].set_title('First Derivative (Gradient)')
    axes[0,1].grid(True, alpha=0.3)
    
    # 2차 미분 (곡률)
    axes[1,0].plot(wavelength, result['second_derivative'], 'orange', linewidth=2)
    axes[1,0].axhline(y=0, color='black', linestyle='--', alpha=0.5)
    axes[1,0].set_xlabel('Wavelength (nm)')
    axes[1,0].set_ylabel('Second Derivative')
    axes[1,0].set_title('Second Derivative (Curvature)')
    axes[1,0].grid(True, alpha=0.3)
    
    # 검출 결과 요약
    axes[1,1].axis('off')
    summary_text = f"""Detection Results:
    
Peaks found: {len(result['peak_wavelengths'])}
Peak wavelengths: {[f'{w:.1f}' for w in result['peak_wavelengths']]}

Valleys found: {len(result['valley_wavelengths'])}
Valley wavelengths: {[f'{w:.1f}' for w in result['valley_wavelengths']]}

PV Ratio: {calculate_pv_ratio_gradient(wavelength, intensity)[0]:.3f}
"""
    axes[1,1].text(0.1, 0.9, summary_text, transform=axes[1,1].transAxes, 
                   fontsize=10, verticalalignment='top', fontfamily='monospace')
    
    plt.tight_layout()
    plt.show()
    
    return fig

# 기존 코드와 통합하기 위한 함수
def analysisPickVellyGradient(rawSpectrum, smooth_sigma=1.0, min_prominence=0.01, 
                             min_distance=5, edge_threshold=0.001, width_threshold = 20):
    """
    기존 analysisPickVelly 함수를 기울기 기반으로 대체하는 함수
    
    Parameters:
    -----------
    rawSpectrum : numpy.array
        [[Wavelength], [Intensity]] 형태의 스펙트럼 데이터
    
    Returns:
    --------
    tuple: (peak_velly_ratio, peak_value)
    """
    wavelength = rawSpectrum[0]
    intensity = rawSpectrum[1]
    
    pv_ratio, peak_value, valley_value = calculate_pv_ratio_gradient(
        wavelength, intensity, 
        smooth_sigma=smooth_sigma,
        min_prominence=min_prominence,
        min_distance=min_distance,
        edge_threshold=edge_threshold,
        width_threshold=width_threshold
    )
    
    return pv_ratio, peak_value

# 기존 UV 분석 함수와의 통합을 위한 개선된 함수
def calculateUV_Data_improved(uv_dict, reference_dict, WavelengthMin=300, WavelengthMax=849, 
                             BoxCarSize=10, smooth_sigma=2.0, min_prominence=0.01, 
                             min_distance=5, edge_threshold=0.001):
    """
    기울기 기반 peak/valley 검출을 사용한 개선된 UV 데이터 분석 함수
    """
    clean_dict = getCleanSpecturm(uv_dict, reference_dict)
    rawSpectrum = getSpectrumArray(uv_dict=clean_dict)
    smooth_result = smooth_Boxcar(rawSpectrum, box_size=BoxCarSize)
    sliceSpectrum = getSliceSpectrum(smooth_result, min=WavelengthMin, max=WavelengthMax)
    
    # 기울기 기반 분석 사용
    peak_velly_ratio, peak_value = analysisPickVellyGradient(
        rawSpectrum=sliceSpectrum, 
        smooth_sigma=smooth_sigma,
        min_prominence=min_prominence,
        min_distance=min_distance,
        edge_threshold=edge_threshold
    )

    UV_result = OrderedDict()
    UV_result["lambdamax"] = peak_value
    UV_result["p_v_ratio"] = peak_velly_ratio

    uv_dict["Property"] = UV_result
    
    return UV_result, uv_dict

def  calculatePL_Data_improved(uv_dict, WavelengthMin=300, WavelengthMax=849, 
                             BoxCarSize=10, smooth_sigma=2.0, min_prominence=0.01, 
                             min_distance=5, edge_threshold=0.001, width_threshold=20):

    
    rawSpectrum = getSpectrumArray(uv_dict=uv_dict)
    smooth_result = smooth_Boxcar(rawSpectrum,box_size=BoxCarSize)
    sliceSpectrum = getSliceSpectrum(smooth_result, min=WavelengthMin, max=WavelengthMax)
    uv_dict["Wavelength"]=sliceSpectrum[0].tolist()
    uv_dict["RawSpectrum"]=sliceSpectrum[1].tolist()
    peak_velly_ratio, peak_value = analysisPickVellyGradient(
        rawSpectrum=sliceSpectrum, 
        smooth_sigma=smooth_sigma,
        min_prominence=min_prominence,
        min_distance=min_distance,
        edge_threshold=edge_threshold,
        width_threshold=width_threshold
    )

    UV_result = OrderedDict()
    # UV_result["lambdamax_multi"] = lambdamax_list
    # UV_result["intensity_multi"] = Intensity_peaks_list
    # UV_result["FWHM_multi"] = FWHM_peaks_list
    UV_result["lambdamax"] = peak_value
    UV_result["p_v_ratio"] = peak_velly_ratio

    uv_dict["Property"]=UV_result
    
    # normalize_spectrum = normalizeSpectrum(smooth_result)
    # plot_filename="{}_{}.png".format(masterLoggerName, experiment_num)
    # getPlot(lambdamax_list, smooth_result=smooth_result, filename=plot_filename)
    # comparePlot(normalize_spectrum, masterLoggerName, experiment_num, plot_filename)

    return UV_result, uv_dict


def select_degree_cheb(spectrum, deg_min=10, deg_max=30, kfold=5):
    x = np.asarray(spectrum[0]).ravel()
    y = np.asarray(spectrum[1]).ravel()
    assert len(x) == len(y) and len(x) > deg_max

    # 도메인(파장 범위) 지정: 수치안정
    domain = [float(np.min(x)), float(np.max(x))]

    # k-fold 분할 (연속 구간 분할; 스펙트럼은 정렬되어 있다고 가정)
    n = len(x)
    idx = np.arange(n)
    folds = np.array_split(idx, kfold)

    def bic_of_deg(deg):
        # CV RMSE
        cv_err = []
        for f in range(kfold):
            val_idx = folds[f]
            tr_idx = np.setdiff1d(idx, val_idx, assume_unique=False)

            ch = Chebyshev.fit(x[tr_idx], y[tr_idx], deg=deg, domain=domain)
            y_hat_val = ch(x[val_idx])
            cv_err.append(np.sqrt(np.mean((y[val_idx] - y_hat_val) ** 2)))
        cv_rmse = float(np.mean(cv_err))

        # 전체 적합 후 BIC
        ch_full = Chebyshev.fit(x, y, deg=deg, domain=domain)
        y_hat_full = ch_full(x)
        sse = float(np.sum((y - y_hat_full) ** 2))
        k_params = deg + 1
        bic = n * np.log(sse / n) + k_params * np.log(n)
        return cv_rmse, bic

    # 각 차수 평가
    records = []
    for deg in range(deg_min, deg_max + 1):
        cv_rmse, bic = bic_of_deg(deg)
        records.append((deg, cv_rmse, bic))

    # BIC 최소 차수 선택
    best = min(records, key=lambda t: t[2])  # (deg, cv_rmse, bic)
    #print(best)
    best_deg = best[0]

    # 최적 차수로 전체 적합 → (x, y_fit) 반환
    ch_best = Chebyshev.fit(x, y, deg=best_deg, domain=domain)
    y_fit = ch_best(x)

    return x, y_fit

def selective_noise_correction(sample_array, noise_range=(430, 460), 
                             window_length=5, polyorder=3):
    """
    특정 wavelength 구간의 noise를 선택적으로 보정하는 함수

    Parameters:
    sample_dict (dict): {'wavelength': array, 'absorbance': array} 형태의 샘플 데이터
    base_dict (dict): {'wavelength': array, 'absorbance': array} 형태의 base 데이터
    noise_range (tuple): noise를 보정할 파장 범위 (기본값: 430-460nm)
    window_length (int): Savitzky-Golay filter의 window 크기
    polyorder (int): Savitzky-Golay filter의 다항식 차수

    Returns:
    dict: noise가 보정된 데이터 {'wavelength': array, 'absorbance': array}
    """
    

    wavelength = sample_array[0]
    sample_data = sample_array[1]
        #print(base_data)
    
    # 노이즈 구간 인덱스 찾기 > 노이즈 레인지 수정하기
    noise_idx = (wavelength >= noise_range[0]) & (wavelength <= noise_range[1])
    sample_data[0]
    # 노이즈 구간만 보정-plan1
    corrected_data = sample_data.copy()

    # correction_factor = np.mean(sample_data[noise_idx]) / np.mean(base_data[noise_idx])
    # corrected_data[noise_idx] = sample_data[noise_idx] - (base_data[noise_idx] * correction_factor)

    # Smoothing 적용-plan1
    corrected_data = savgol_filter(corrected_data, window_length=window_length, polyorder=polyorder)

    # sample_data의 noise_range 부분을 corrected_data로 변경
    sample_data[noise_idx] = corrected_data[noise_idx]
    
    # 결과를 dictionary로 반환
    sample_array[1] = sample_data
    return sample_array

if __name__ == "__main__":
    # rawSpectrum = getLocalSpectrumArray(file_path="./Analysis/test_recipe4.json")
    # # clean_dict=getCleanSpecturm(uv_dict,reference_dict)
    # # rawSpectrum = getSpectrumArray(uv_dict=clean_dict)
    # sliceSpectrum = getSliceSpectrum(rawSpectrum=rawSpectrum, min=300, max=850)
    # # print(sliceSpectrum)
    # smooth_result = smooth_Boxcar(sliceSpectrum,60)
    # # Idx_peaks, properties = find_peaks(sliceSpectrum[1], prominence=0.001, width=20)

    # # Wavelength_peaks, Intensity_peaks, FWHM_peaks  = analysisSinglePeak(rawSpectrum=smooth_result, prominence=0.01, width=20) 
    # Wavelength_peaks, Intensity_peaks, FWHM_peaks = analysisMultiPeak(rawSpectrum=smooth_result, prominence=0.01, width=20) 
    # # FWHM_peaks_list = peak_widths(sliceSpectrum[1], Idx_peaks, rel_height = 0.5)
    # print('lambda: ',Wavelength_peaks, 'Intensity: ', Intensity_peaks, 'maxFWHM: ', FWHM_peaks)

    # rawSpectrum = getLocalSpectrumArray(file_path="./Analysis/test_recipe4.json")
    # referenceSpectrum = getLocalSpectrumArray(file_path="./Analysis/test_recipe4.json")
    # clean_dict=getCleanSpecturm(rawSpectrum, referenceSpectrum)

    # print(clean_dict)
    # rawSpectrum = getLocalSpectrumArray(file_path="Hardware\\UV\\sample.json")
    # referenceSpectrum = getLocalSpectrumArray(file_path="Hardware\\UV\\reference.json")
    import json 
    with open('Analysis\\sample.json','r') as file:
        rawSpectrum1 = json.load(file)

    with open('Analysis\\reference.json','r') as file:
        referenceSpectrum = json.load(file)
    abs_dict= getCleanSpecturm(rawSpectrum1, referenceSpectrum)
    abs_spec=getSpectrumArray(abs_dict)
    plt.plot(abs_spec[0],abs_spec[1])
    plt.show()
    rawSpectrum = getLocalSpectrumArray(file_path="./Analysis/sample.json")
    
    refSpectrum = getLocalSpectrumArray(file_path="./Analysis/reference.json")
    #absSpectrum = getCleanSpecturm(rawSpectrum1, referenceSpectrum)
    #absSpectrum2 = getSpectrumArray(absSpectrum)
    #plt.plot(absSpectrum['Wavelength'],absSpectrum['RawSpectrum'])
    #plt.show()
    '''
    for i in range(0, 33):
        if i !=3:
            with open(f'DB\\s{i}.json','r') as file:
                abSpectrum = json.load(file)
            absSpectrum = abSpectrum['result']['UV_GetAbs']['Data']
            uv_result, calc_result = calculatePL_Data(absSpectrum, WavelengthMin=420, WavelengthMax=700, BoxCarSize=10, Prominence=0.01, PeakWidth=20)
            print(calc_result['Property'])
    '''
    '''
    for i in range(65,66):
        if i !=3:

            with open(f'DB\\s{i}.json','r') as file:
                abSpectrum = json.load(file)
            absSpectrum = abSpectrum['result']['UV_GetAbs']['Data']
            spec2 = [absSpectrum['Wavelength'],absSpectrum['RawSpectrum']]
            spec2= np.array(spec2)
            #wavelength, trend= smooth_polyfit(spec2[0], spec2[1], degree=12)
            #wavelength, trend= fourier_series_fit(spec2[0], spec2[1], cutoff=0.05)
            
            wavelength = spec2[0]
            x_eval = np.linspace(350, 1150, 25000)
            trend = np.interp(x_eval, spec2[0], spec2[1])
            raw = np.array([x_eval, trend])
            smoothed = smooth_Boxcar(rawSpectrum= raw, box_size= 500)
            sliced = getSliceSpectrum2(rawSpectrum=spec2,min_wl=400, max_wl=720)
            #wavelength, trend = smooth_spline(spec2[0],spec2[1], smoothing_factor= 0.01)

            #poly_wl, poly_ab= smooth_polyfit(smoothed[0], smoothed[1], degree=12)
            #ply = [poly_wl,poly_ab]
            #sliced2 = getSliceSpectrum2(rawSpectrum=ply,min_wl=380, max_wl=720)
            sliced2 = getSliceSpectrum2(rawSpectrum=smoothed,min_wl=380, max_wl=720)
            poly_wl, poly_ab= smooth_polyfit(sliced2[0], sliced2[1], degree=12)
            ply = [poly_wl,poly_ab]
            

            #sliced2 = getSliceSpectrum2(rawSpectrum=smoothed,min_wl=400, max_wl=700)
            #peak_valley_ratio, peak_wavelength = polyfit_peak_valley(sliced2[0], sliced2[1], degree=12, prominence=0.01)
            peak_valley_ratio, peak_wavelength = analysisPickVelly(ply, prominence = 0.01, width_threshold=10)
            #peak_valley_ratio, peak_wavelength = find_peak_after_valley_by_gradient(sliced2[0], sliced2[1], prominence=0.05)
            #peak_valley_ratio, peak_wavelength= find_peak_after_valley_poly(sliced2[0], sliced2[1], prominence=0.05)

            print(peak_valley_ratio)
            plt.plot(sliced[0], sliced[1], label='Original')
            plt.plot(ply[0], ply[1], label='Polyfit Curve (12th)', color='orange')
            plt.legend()
            plt.show()
            #plt.plot(sliced2[0], sliced2[1])
            #plt.show()
    '''
    from pathlib import Path
    import sys, os
    sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) 

    from Algorithm.Loss.UV_loss import *

    base = Path("DB")

    for i in range(0,1):           # range(0,66)와 동일
        if i == 3:
            continue

        json_path = base / f"s{i}.json"
        txt_path = base / f"s{i}_sliced.txt"


        try:
            with json_path.open("r", encoding="utf-8") as f:
                abSpectrum = json.load(f)

            absSpectrum = abSpectrum['result']['UV_GetAbs']['Data']
            spec2 = np.array([absSpectrum['Wavelength'], absSpectrum['RawSpectrum']], dtype=float)

            # np.interp는 x가 오름차순이어야 하므로 혹시 모를 순서 뒤섞임 방지


            x_eval = np.linspace(350, 1150, 25000)
            trend = np.interp(x_eval, spec2[0], spec2[1])
            raw = np.array([x_eval, trend], dtype=float)

            smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=199)
            smoothed2 = smooth_Boxcar(rawSpectrum=spec2, box_size=5)
            sliced = getSliceSpectrum2(rawSpectrum=smoothed2, min_wl=400, max_wl=720)

            sliced2 = getSliceSpectrum2(rawSpectrum=smoothed, min_wl=380, max_wl=720)

            #cut_x, cut_y = trim_by_rolling_std_units(sliced2[0], sliced2[1], window_x=5.0, sigma_th=0.01, stable_span_x=10.0)
            cut_x, cut_y = trim_by_slope_stability_units(sliced2[0], sliced2[1], window_x=6, slope_std_th=0.012, stable_span_x=3.0)
            #cut_x, cut_y = trim_by_local_snr_units(sliced2[0], sliced2[1], window_x=5, snr_th=0.05, stable_span_x=10.0)
            sliced2 = (cut_x,cut_y)
            #poly_wl, poly_ab = smooth_polyfit(sliced2[0], sliced2[1], degree=12)
            poly_wl, poly_ab = select_degree_cheb(sliced2, deg_min=1, deg_max=30, kfold=5)
            sliced3 = getSliceSpectrum2(rawSpectrum=(poly_wl, poly_ab), min_wl=400, max_wl=680)
            
            peak_velly_ratio, peak_wave = analysisPickVelly(sliced3, prominence = 0.01, width_threshold=20)
            print(peak_velly_ratio, peak_wave)
            target_condition_dict={
                        "GetAbs":
                        {
                            "Property":{
                                "lambdamax":490,
                                "p_v_ratio":2
                            },
                            "Ratio":{
                                "lambdamax":0.1,
                                "p_v_ratio":0.9
                            }
                        }
                    }
            result_dict ={"UV_GetAbs": {"Data": {"Wavelength": [],"RawSpectrum": [],"Property": {"lambdamax": 0, "p_v_ratio": 0}}}}
            result_dict["UV_GetAbs"]["Data"]["Wavelength"] = sliced[0].tolist()
            result_dict["UV_GetAbs"]["Data"]["RawSpectrum"] = sliced[1].tolist()
            result_dict["UV_GetAbs"]["Data"]["Property"]["lambdamax"] = peak_wave
            result_dict["UV_GetAbs"]["Data"]["Property"]["p_v_ratio"] = peak_velly_ratio
            loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=target_condition_dict)
            optimal_value, total_property_dict = loss_obj.lambdamaxpvLoss()
            #print(optimal_value)
            
            #plt.plot(sliced3[0],sliced3[1])
            #plt.show()
            '''
            with txt_path.open("w", encoding="utf-8") as f:
                for j in range(len(sliced[0])):
                    f.write(f'{sliced[0][j]}, {sliced[1][j]}\n')
            '''
            # 필요 시 사용
            # print(peak_valley_ratio)

            # ---- 그림 그리기 & 저장 (창 띄우지 않음) ----
            '''
            fig, ax = plt.subplots()
            ax.plot(sliced[0], sliced[1], label='Original')
            ax.plot(poly_wl, poly_ab, label='Polyfit Curve (12th)', color='orange')
            ax.set_xlabel("Wavelength (nm)")
            ax.set_ylabel("Absorbance (a.u.)")
            ax.set_title(f"Absorption Spectrum — {json_path.name}")
            # 그림 안에도 파일명 박스 표시(선택)
            ax.text(0.01, 0.99, json_path.name, transform=ax.transAxes,
                    va='top', ha='left', fontsize=9,
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.6))
            ax.legend()
            ax.grid(True, alpha=0.3)

            # 저장 경로: JSON이 있던 동일 폴더, 파일명에 json 이름 반영
            out_path = json_path.with_name(f"{json_path.stem}_diagram.png")
            fig.savefig(out_path, dpi=200, bbox_inches="tight")
            plt.close(fig)  # 메모리 누수 방지
            print(f"Saved: {out_path}")
            '''

        except Exception as e:
            print(f"[skip] {json_path.name}: {e}")
            continue

    #np.savetxt("DB\\sliced3.txt", sliced, fmt="%.3f")
    #plt.plot(sliced[0],sliced[1])
    #plt.show()

    #plt.plot(calc_result['Wavelength'],calc_result['RawSpectrum'])
    #plt.show()
    
    #print(absSpectrum)
    #plt.plot(rawSpectrum[0],rawSpectrum[1])
    #plt.show()
    #plt.plot(refSpectrum[0],refSpectrum[1])
    #plt.show()
    #plt.plot(absrawSpectrum['Wavelength'],absrawSpectrum['RawSpectrum'])
    #plt.show()
    #plt.plot(absSpectrum2[0],absSpectrum2[1])
    #plt.show()
    #plt.plot(uv_dict[0],uv_dict[1])
   # plt.show()
    # clean_dict=getCleanSpecturm(uv_dict,reference_dict)
    # rawSpectrum = getSpectrumArray(uv_dict=clean_dict)

    #smooth_result = smooth_Boxcar(absSpectrum1, 10)
    #sliceSpectrum = getSliceSpectrum(rawSpectrum=absSpectrum2, min=420, max=850)
    #sliceSpectrum = getSliceSpectrum(rawSpectrum=rawSpectrum, min=300, max=850)
    #plt.plot(sliceSpectrum[0],sliceSpectrum[1])
    #plt.show()
    # print(sliceSpectrum)

    #sliceSpectrum = getSliceSpectrum(rawSpectrum=smooth_result, min=420, max=850)
    #smooth_result = smooth_Boxcar(sliceSpectrum,10)

    #plt.plot(sliceSpectrum[0],sliceSpectrum[1])
    #plt.show()

    # Idx_peaks, properties = find_peaks(sliceSpectrum[1], prominence=0.001, width=20)

    #Wavelength_peaks, Intensity_peaks, FWHM_peaks  = analysisSinglePeak(rawSpectrum=sliceSpectrum, prominence=0.01, width=20) 
    #Wavelength_peaks, Intensity_peaks, FWHM_peaks = analysisMultiPeak(rawSpectrum=smooth_result, prominence=0.01, width=20) 
    # FWHM_peaks_list = peak_widths(sliceSpectrum[1], Idx_peaks, rel_height = 0.5)
    
    #print('lambda: ',Wavelength_peaks, 'Intensity: ', Intensity_peaks, 'maxFWHM: ', FWHM_peaks)

    #plt.plot(absSpectrum['Wavelength'],absSpectrum['RawSpectrum'])
    #plt.show()
    #print(rawSpectrum)
    #plt.plot(rawSpectrum['Wavelength'],rawSpectrum['RawSpectrum'])
    #plt.show()
def  calculateUV_Data(uv_dict, reference_dict, WavelengthMin=300, WavelengthMax=849, BoxCarSize=10, Prominence=0.01, PeakWidth=20):

    spec2 = [uv_dict['Wavelength'],uv_dict['RawSpectrum']]
    spec2= np.array(spec2)

    wavelength = spec2[0]
    x_eval = np.linspace(350, 950, 20000)
    trend = np.interp(x_eval, spec2[0], spec2[1])
    raw = np.array([x_eval, trend])
    smoothed = smooth_Boxcar(rawSpectrum= raw, box_size= BoxCarSize)
    sliced = getSliceSpectrum2(rawSpectrum=smoothed,min_wl=WavelengthMin, max_wl=WavelengthMax)
    poly_wl, poly_ab= smooth_polyfit(sliced[0], sliced[1], degree=12)
    ply = [poly_wl,poly_ab]


    peak_valley_ratio, peak_wavelength = analysisPickVelly(ply, prominence = Prominence, width_threshold=PeakWidth)
    UV_result = OrderedDict()
    # UV_result["lambdamax_multi"] = lambdamax_list
    # UV_result["intensity_multi"] = Intensity_peaks_list
    # UV_result["FWHM_multi"] = FWHM_peaks_list
    UV_result["lambdamax"] = peak_wavelength
    UV_result["p_v_ratio"] = peak_valley_ratio

    uv_dict["Property"]=UV_result
    
    # normalize_spectrum = normalizeSpectrum(smooth_result)
    # plot_filename="{}_{}.png".format(masterLoggerName, experiment_num)
    # getPlot(lambdamax_list, smooth_result=smooth_result, filename=plot_filename)
    # comparePlot(normalize_spectrum, masterLoggerName, experiment_num, plot_filename)

    return UV_result, uv_dict

