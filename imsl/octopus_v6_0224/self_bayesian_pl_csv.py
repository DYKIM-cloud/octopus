import json
import pickle
import pandas as pd
from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization
from Algorithm.Loss.UV_loss import LossFunctionSelf, LossFunction
from Analysis.AnalysisUV_poly import *
def openConfigFile(config_filename):
    """
    :params config_filename (str): config filename

    :return config_data (dict) config_data
    """
    config_json_path = "{}".format(config_filename)
    with open(config_json_path, "r") as f:
        config_data = json.load(f)
    return config_data

def openModel(pickle_name):
    """
    :params pickle_name (str): model's pickle filename

    :return model (object) model which uploaded new one
    """
    with open("{}".format(pickle_name), 'rb') as f: 
        model = pickle.load(f)
        
    return model

def writeModel(pickle_name, model):
    """
    :params pickle_name (str): model's pickle filename

    :return None
    """
    with open("{}".format(pickle_name), 'wb') as f:
        pickle.dump(model, f)
        
def createModel(algorithm_dict):
    """
    :params algorithm_dict (str): config_dict["algorithm"] in config file

    :return model (object) model 
    """
    model = ASLdiscreteBayesianOptimization(algorithm_dict)

    return model 

def registerData2Model(result_list, params_list, model):
    """
    :params result_list (list): results which want to register inside model depending on params_list
    :params params_list (list): params which want to register inside model depending on result_list
    :params model (object): our model (bo_object-->->res)

    :return model (object) which added new results and params
    """
    
    
    for idx, param in enumerate(params_list):
        model.register(params=params_list[idx], target=result_list[idx])
    return model

def calculateModelResultSize(model):
    """
    :params model (object): model

    :return model (object) model 
    """
    print("model results : {}, model result_size : {}".format(model.res, len(model.res)))
    return model


def _getNormalizedCondition(real_next_points):
    """
    convert real condition to normalized condition
    X' = (value - V_min)/(V_max - V_min) 

    :param real_next_points (list) : 
        [
            {'In': 3300.0, 'P': 500.0, 'heat': 1300.0, 'heat2': 3500.0}
            {'In': 3500.0, 'P': 500.0, 'heat': 1300.0, 'heat2': 3500.0}

        ]
    :return : normalized_next_points (list)
    """
    normalized_next_points = []
    for _, next_point in enumerate(real_next_points):
        new_value={}
        for chemical, rangeList in real_next_points():
            new_value[chemical]=(int(next_point[chemical])-rangeList[0])/(rangeList[1]-rangeList[0]) # X' = (value - V_min)/(V_max - V_min) 
        normalized_next_points.append(new_value)
    
    return normalized_next_points

def _getNormalizedCondition_PL(real_next_points, job_path):
    """
    Normalize each chemical's value using min-max normalization from real_next_points
    X' = (value - V_min)/(V_max - V_min)

    :param real_next_points (list of dicts): e.g.,
        [
            {'In': 3300.0, 'P': 500.0, 'heat': 1300.0, 'heat2': 3500.0},
            {'In': 3500.0, 'P': 500.0, 'heat': 1300.0, 'heat2': 3700.0}
        ]
    :return: normalized_next_points (list of dicts)
    """
    job_data = openConfigFile(job_path)
    prange_dict = job_data['algorithm']['prange']
    keys = prange_dict.keys()
    min_max_dict = {}

    for key in keys:
        vmin = prange_dict[key][0]
        vmax = prange_dict[key][1]
        min_max_dict[key] = (vmin, vmax)

   
    normalized_next_points = []
    for point in real_next_points:
        norm_point = {}
        for chem in keys:
            vmin, vmax = min_max_dict[chem]
            norm_point[chem] = (point[chem] - vmin) / (vmax - vmin)
        normalized_next_points.append(norm_point)

    return normalized_next_points

def load_result(path):
    data_dict = {"Wavelength": [], "RawSpectrum": []}

    with open(path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # 첫 줄(헤더) 제거
    lines = lines[2:]

    for line in lines:
        if line.strip(): 
            wavelength, intensity = map(float, line.split(","))
            data_dict["Wavelength"].append(wavelength)
            data_dict["RawSpectrum"].append(intensity)
            
    return data_dict

def load_csv_result(path):
    data = pd.read_csv(path, delimiter=',', skiprows=2)
    wavelengths = data.iloc[:, 0].values
    absorbance = data.iloc[:, 1].values.reshape(-1, 1)
    data_df = pd.DataFrame(absorbance, index=wavelengths, columns=['Sample_1'])
    return data_df

def load_json_result(path):
    """
    Load UV absorbance data from a JSON file.
    Extracts 'Wavelength' and 'RawSpectrum' under 'result' → 'UV_GetAbs' → 'Data'
    Returns: DataFrame with wavelength as index and one column 'Sample_1'
    """
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Navigate into the nested structure
    uv_data = data["result"]["UV_GetAbs"]["Data"]
    wavelengths = uv_data["Wavelength"]
    absorbance = uv_data["RawSpectrum"]

    # Convert to DataFrame
    df = pd.DataFrame(absorbance, index=wavelengths, columns=["Sample_1"])
    return df

def load_json_result_pl(path):
    """
    Load UV absorbance data from a JSON file.
    Extracts 'Wavelength' and 'RawSpectrum' under 'result' → 'UV_GetAbs' → 'Data'
    Returns: DataFrame with wavelength as index and one column 'Sample_1'
    """
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Navigate into the nested structure
    uv_data = data["result"]["PL_GetPl"]["Data"]
    wavelengths = uv_data["Wavelength"]
    absorbance = uv_data["RawSpectrum"]

    # Convert to DataFrame
    df = pd.DataFrame(absorbance, index=wavelengths, columns=["Sample_1"])
    return df

def extract_synthesis_params_from_json(json_path):
    """
    Extracts preHeat temperature, Heat temperature, and injection rates of InP and A
    from a given JSON file, returning a params dict for BO.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    process_list = data["process"]["Synthesis"][0]["Data"]
    param_dict = {}

    for entry in process_list:
        task = entry.get("Task")
        data_block = entry.get("Data", {})

        if task == "FlowSynthesis_preHeat":
            preheat_temp = data_block["Temperature"]["Value"]
            param_dict["preHeat=Temperature"] = preheat_temp

        elif task == "FlowSynthesis_Heat":
            heat_temp = data_block["Temperature"]["Value"]
            param_dict["Heat=Temperature"] = heat_temp

        elif task == "FlowSynthesis_AddSolution":
            solution = data_block["Solution"]
            if solution == 'InP':
                rate = data_block["Injectionrate"]["Value"]
                param_dict[f"AddSolution={solution}_Injectionrate"] = rate
            if solution == 'A':
                rate = data_block["Injectionrate"]["Value"]
                param_dict[f"AddSolution={solution}_Injectionrate"] = rate
        '''
        if task == "FlowSynthesis_preHeat":
            preheat_temp = data_block["Temperature"]["Value"]
            param_dict["preHeat=Temperature"] = (preheat_temp - 40) / 20

        elif task == "FlowSynthesis_Heat":
            heat_temp = data_block["Temperature"]["Value"]
            param_dict["Heat=Temperature"] = (heat_temp - 220) /31

        elif task == "FlowSynthesis_AddSolution":
            solution = data_block["Solution"]
            if solution == 'InP':
                rate = data_block["Injectionrate"]["Value"]
                param_dict[f"AddSolution={solution}_Injectionrate"] = (rate - 100) / 1151
            if solution == 'A':
                rate = data_block["Injectionrate"]["Value"]
                param_dict[f"AddSolution={solution}_Injectionrate"] = (rate - 100) / 1151
        '''

    return [param_dict]

def extract_uv_properties_from_json(json_path):
    """
    Extracts lambdamax and p_v_ratio from the given JSON file's UV absorbance result.
    Returns: peak_valley_ratio, lambda_max
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    property_data = data["result"]["UV_GetAbs"]["Data"]["Property"]

    lambda_max = property_data["lambdamax"]
    peak_valley_ratio = property_data["p_v_ratio"]

    return peak_valley_ratio, lambda_max

def extract_pl_properties_from_json(json_path):
    """
    Extracts lambdamax and p_v_ratio from the given JSON file's UV absorbance result.
    Returns: peak_valley_ratio, lambda_max
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    property_data = data["result"]["PL_GetPl"]["Data"]["Property"]

    lambda_max = property_data["lambdamax"]
    pl_intensity = property_data["intensity"]
    pl_fwhm = property_data["FWHM"]
    return pl_intensity, lambda_max, pl_fwhm

def extract_result_dict_from_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    result_dict = data["result"]

    return result_dict

def load_multisample_csv(path):
    df = pd.read_csv(path, header=None)

    param_dict = {}
    data_dict = {}

    # 첫 번째 열은 공통 wavelength
    wavelength = df.iloc[4:, 0].astype(float).tolist()

    # 각 샘플 column에 대해 반복 (B열부터 시작, index=1)
    for col in range(1, df.shape[1]):
        col_name = f"Sample_{col}"

        keys = df.iloc[0:4, 0].values
        values = df.iloc[0:4, col].values

        # NaN key나 value가 하나라도 있으면 skip
        if pd.isnull(keys).any() or pd.isnull(values).any():
            continue  # 무시하고 다음 column으로

        param_info = dict(zip(keys.astype(str), values))
        param_dict[col_name] = param_info

        # RawSpectrum 저장: data_dict[col_name] = {'Wavelength': [...], 'RawSpectrum': [...]}
        spectrum = df.iloc[4:, col].astype(float).tolist()
        data_dict[col_name] = {
            'Wavelength': wavelength,
            'RawSpectrum': spectrum
        }

    return param_dict, data_dict

def createNewModel(configpath, savepath, params, loss_obj):

    
    #loss=loss_obj.asymmetric_custom_score()
    #loss=loss_obj.asymmetric_custom_score_pl()
    loss, dict=loss_obj.lambdamaxpvLoss()
    print(f"loss={loss}")
    results=[loss]


    config_data = openConfigFile(configpath)

    pickle_name=savepath

    model = createModel(algorithm_dict=config_data["algorithm"])
    
    model = registerData2Model(result_list=results, params_list=params, model=model)

    calculateModelResultSize(model)

    writeModel(pickle_name=pickle_name, model=model)

    openmodel = openModel(pickle_name)

    calculateModelResultSize(model=openmodel)



def overwriteSinglePreviousModel(modelpath, savepath, params, loss_obj):

    #loss=loss_obj.asymmetric_custom_score_pl()
    loss, dict=loss_obj.lambdamaxpvLoss()

    results=[loss]

    # 에러가 나기 전까지 존재하던 pickle 이름을 불러오기
    pickle_name=modelpath
    openmodel = openModel(pickle_name)

    model = registerData2Model(result_list=results, params_list=params, model=openmodel)    
    calculateModelResultSize(model=model)
    
    new_pickle_name=savepath

    writeModel(pickle_name=new_pickle_name, model=model)
    after_BO = openModel(new_pickle_name)
    
    print("=============after================")
    
    calculateModelResultSize(after_BO)
    
    
if __name__ == "__main__":



    import numpy as np
    from pathlib import Path
    import csv
    import matplotlib.pyplot as plt
    '''
    base = Path("2508optimize")
    out_csv = base / "spectra_with_params.csv"
    wavelength_ref = None   # 1행(E열~)에 쓸 참조 파장축
    intensity_rows = []     # 각 파일의 spec[1] 행들
    param_rows = []  
    for i in range(66):
        if i == 3:
            continue

        json_path = base / f"s{i}.json"

        try:
            with json_path.open("r", encoding="utf-8") as f:
                abSpectrum = json.load(f)

            absSpectrum = abSpectrum['result']['UV_GetAbs']['Data']
            spec = np.array([absSpectrum['Wavelength'], absSpectrum['RawSpectrum']], dtype=float)

            # np.interp는 x가 오름차순이어야 하므로 혹시 모를 순서 뒤섞임 방지
            order = np.argsort(spec[0])
            spec2 = np.array([spec[0][order], spec[1][order]], dtype=float)

            x_eval = np.linspace(350, 1150, 25000)
            trend = np.interp(x_eval, spec2[0], spec2[1])
            raw = np.array([x_eval, trend], dtype=float)

            smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=500)
            
            
            sliced = getSliceSpectrum2(rawSpectrum=smoothed, min_wl=380, max_wl=720)
            poly_wl, poly_ab = smooth_polyfit(sliced[0], sliced[1], degree=12)
            sliced2 = getSliceSpectrum2(rawSpectrum=(poly_wl, poly_ab), min_wl=400, max_wl=680)

            peak_velly_ratio, peak_value = analysisPickVelly(rawSpectrum=sliced2, prominence=0.01, width_threshold=20)
            param_dict= extract_synthesis_params_from_json(json_path)
            # 필요 시 사용
            #print(f"s{i} peak = {peak_value}, pv = {peak_velly_ratio}")
            wl = spec2[0]
            y  = spec2[1]

            if wavelength_ref is None:
                wavelength_ref = wl


            intensity_rows.append(y)
            param_rows.append(param_dict[0])


        except Exception as e:
            print(f"[skip] {json_path.name}: {e}")
            continue
    if wavelength_ref is None or not intensity_rows:
        print("수집된 데이터가 없어 CSV를 생성하지 않았습니다.")
    else:
        # param_dict 키 4개를 첫 성공 샘플 기준으로 고정
        param_keys = list(param_rows[0].keys())[:4]

        # 1) 먼저 '기존 레이아웃' 형태의 2D 리스트(rows)를 만든 뒤
        rows = []
        # 1행: A~D 공란, E열부터 파장축
        rows.append(["", "", "", ""] + list(wavelength_ref))

        # 2행~: 각 파일별 [파라미터 4개] + [스펙트럼 intensity]
        for params, y in zip(param_rows, intensity_rows):
            row_params = [params.get(k, "") for k in param_keys]
            rows.append(row_params + list(y))

        # 2) 전치(행<->열)해서 저장
        transposed = list(map(list, zip(*rows)))  # = 행/열 반전

        with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(transposed)
        print(f"CSV 저장 완료: {out_csv}")
    '''
    
    ## INPUT(실험값)
    #params =[{'AddSolution=InP_Injectionrate': 150.0, 'AddSolution=Zn_Injectionrate': 180.0, 'AddSolution=Se_Injectionrate': 1100.0, 'Heat=Temperature':235.0}]
    ## OUTPUT(실험값)
    path = "2508optimize\\spectra_with_params_pl.csv"
    #path = "2508optimize\\spectra_with_params_smoothed.csv"
    param_dict, data_dict=load_multisample_csv(path)
    ## path
    job_script_path="InP_core.json"
    load_model_path = "1023core.pickle"  # 반드시 다른이름으로 할 것
    save_model_path = "1023core.pickle"  # 반드시 다른이름으로 할 것 - 덮어쓰고나면 복구를 못해요.

    #for i in range(len(param_dict),len(param_dict)+1):
    #for j in range(1,len(param_dict)+1):
    for j in range(0,1):
        i = j+1

        #######################################################
        #######################################################
        uv_data = data_dict[f'Sample_{i}']
        wavelengths = uv_data["Wavelength"]
        absorbance = uv_data["RawSpectrum"]
        # Convert to DataFrame
        data_df = pd.DataFrame(absorbance, index=wavelengths, columns=[f'Sample_{i}'])
        peak_velly_ratio, peak_value=calculateUV_Data_clean_csv(uv_df=data_df)
        property_dict = {'lambdamax': peak_value, 'p_v_ratio':peak_velly_ratio}
        #print(i, property_dict)
        #print(property_dict["lambdamax"],property_dict["p_v_ratio"])
        #result_dict={"PL_GetPl":{"Data":{"Property":{'lambdamax': lambda_max, 'FWHM':FWHM, 'intensity':intensity}}}}
        result_dict= {"UV_GetAbs": {
               "Device": {
                    "Spectrometer": {
                         "DeviceName": "USB2000+",
                         "DetectionRange": "200-850nm",
                         "Solvent": {
                              "Solution": "H2O",
                              "Value": 1,
                              "Dimension": "\u03bcL"
                         }
                    },
                    "LightSource": {
                         "DeviceName": "DH-2000-BAL",
                         "DetectionRange": "210-2500nm",
                         "Lamp": "deuterium(25W) and halogen lamps(20W)"
                    }
               },
               "Hyperparameter": {
                    "WavelengthMin": {
                         "Description": "WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                         "Value": 410,
                         "Dimension": "nm"
                    },
                    "WavelengthMax": {
                         "Description": "WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                         "Value": 700,
                         "Dimension": "nm"
                    },
                    "BoxCarSize": {
                         "Description": "BoxCarSize=10 (int): smooth strength",
                         "Value": 30,
                         "Dimension": "None"
                    },
                    "Prominence": {
                         "Description": "Prominence=0.01 (float): minimum peak Intensity for detection",
                         "Value": 0.1,
                         "Dimension": "None"
                    },
                    "PeakWidth": {
                         "Description": "PeakWidth=20 (int): minumum peak width for detection",
                         "Value": 5,
                         "Dimension": "nm"
                    }
               },
               "Data": {
                    "Wavelength": [
                         
                    ],
                    "RawSpectrum": [
                         
                    ],
                    "Property": {
                         
                    }
               }
          }
        }
        result_dict['UV_GetAbs']['Data']['Wavelength'] = data_dict[f'Sample_{i}']['Wavelength']
        result_dict['UV_GetAbs']['Data']['RawSpectrum'] = data_dict[f'Sample_{i}']['RawSpectrum']
        result_dict['UV_GetAbs']['Data']['Property'] = property_dict
        target_condition_dict={
                    "GetAbs":{
                        "Property":{
                            "lambdamax":470,
                            "p_v_ratio":1.1
                        },
                        "Ratio":{
                            "lambdamax":0.1,
                            "p_v_ratio":0.9
                        }
                    }
                }
        

        norm_params = _getNormalizedCondition_PL([param_dict[f'Sample_{i}']],job_script_path)

        loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=target_condition_dict)
        optimal_value, total_property_dict = loss_obj.lambdamaxpvLoss()
        #print(i, optimal_value)


        #########################################################
        #########################################################
        
        # 새로 모델 만들기
        #createNewModel(configpath=job_script_path,savepath=save_model_path,params=norm_params, loss_obj=loss_obj)
        
        ## 다음 점 추천하기
        #bo_obj = openModel(load_model_path)
        #print(bo_obj)
        #print(bo_obj.suggestNextStep())
        
        ## 결과 덮어쓰기
        #overwriteSinglePreviousModel(modelpath=load_model_path, savepath=save_model_path, params=norm_params, loss_obj=loss_obj)
    
    
    #bo_obj = openModel(load_model_path)
    #print(bo_obj.res)
    #print(bo_obj.suggestNextStep())
    