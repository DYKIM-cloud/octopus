
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
import time
from scipy.signal import find_peaks, peak_prominences, peak_widths
from scipy.ndimage import gaussian_filter1d
from collections import OrderedDict

# with open("/home/sdl-pc/catkin_ws/src/doosan-robot/ref_UV.json", "r") as json_file:
#     reference_dict = json.load(json_file)
# with open("/home/sdl-pc/catkin_ws/src/doosan-robot/Abs_UV.json", "r") as json_file:
#     uv_dict = json.load(json_file)


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

def getSliceSpectrum(rawSpectrum=[],min=350, max=800):
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
        if rawSpectrum[0][i] > min and rawSpectrum[0][i] < max:
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
        max_Intensity = Intensity_peaks[maxIdx]
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
    sliceSpectrum = getSliceSpectrum(smooth_result, min=WavelengthMin, max=WavelengthMax)
    uv_dict["Wavelength"]=sliceSpectrum[0].tolist()
    uv_dict["RawSpectrum"]=sliceSpectrum[1].tolist()
    peak_velly_ratio, peak_value = analysisPickVelly(rawSpectrum=smooth_result, prominence=Prominence, width_threshold=PeakWidth)

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
    from pathlib import Path
    import json
    import sys, os
    sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))) 
    from Algorithm.Loss.UV_loss import *
    with open('DB\\s0.json','r') as file:
        rawSpectrum1 = json.load(file)

    with open('Analysis\\reference.json','r') as file:
        referenceSpectrum = json.load(file)
    
    rawSpectrum = getLocalSpectrumArray(file_path="./Analysis/sample.json")
    
    refSpectrum = getLocalSpectrumArray(file_path="./Analysis/reference.json")
    #absSpectrum = getCleanSpecturm(rawSpectrum1, referenceSpectrum)
    absSpectrum = rawSpectrum1['result']['UV_GetAbs']['Data']
    absSpectrum = getSpectrumArray(absSpectrum)
    smoothed = smooth_Boxcar(absSpectrum,30)
    sliced = getSliceSpectrum(rawSpectrum=smoothed,min=400, max=700)
    peak_velly_ratio, peak_wave = analysisPickVelly(sliced, prominence = 0.01, width_threshold=20)
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
    print(optimal_value)
    '''
    path = Path('DB\\s0_box.txt')
    with path.open("w", encoding="utf-8") as f:
        for j in range(len(smoothed[0])):
            f.write(f"{smoothed[0][j]}, {smoothed[1][j]}\n")
    '''
    #absSpectrum2 = getSpectrumArray(absSpectrum)
    '''
    plt.plot(absSpectrum['Wavelength'],absSpectrum['RawSpectrum'])
    plt.show()
    uv_result, calc_result = calculateUV_Data(rawSpectrum1, referenceSpectrum, WavelengthMin=419, WavelengthMax=700, BoxCarSize=5, Prominence=0.01, PeakWidth=5)
    print(calc_result['Property'])
    plt.plot(calc_result['Wavelength'],calc_result['RawSpectrum'])
    plt.show()
    '''
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