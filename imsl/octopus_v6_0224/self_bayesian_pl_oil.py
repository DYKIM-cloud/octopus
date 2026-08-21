import json
import pickle
import pandas as pd
from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization
from Algorithm.Loss.UV_loss import LossFunctionSelf, LossFunction
from Analysis.AnalysisUV import calculateUV_Data_clean_pl
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
    print("model : {}, model results : {}, model result_size : {}".format(model, model.res, len(model.res)))
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
    wavelength = df.iloc[4:, 0].astype(float).values

    # 각 샘플 column에 대해 반복 (B열부터 시작, index=1)
    for col in range(1, df.shape[1]):
        col_name = f"Sample_{col}"

        # 파라미터 저장: param_dict[col_name] = {...}
        param_info = {
            str(df.iloc[0, 0]): df.iloc[0, col],
            str(df.iloc[1, 0]): df.iloc[1, col],
            str(df.iloc[2, 0]): df.iloc[2, col],
            str(df.iloc[3, 0]): df.iloc[3, col]
        }
        param_dict[col_name] = param_info

        # RawSpectrum 저장: data_dict[col_name] = {'Wavelength': [...], 'RawSpectrum': [...]}
        spectrum = df.iloc[4:, col].astype(float).values
        data_dict[col_name] = {
            'Wavelength': wavelength,
            'RawSpectrum': spectrum
        }

    return param_dict, data_dict

def createNewModel(configpath, savepath, params, loss_obj):

    
    #loss=loss_obj.asymmetric_custom_score()
    #loss=loss_obj.asymmetric_custom_score_pl()
    loss=loss_obj.lambdamaxFWHMIntensityLoss()

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

    loss=loss_obj.asymmetric_custom_score_pl()
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
    i = 0
    while i < 19:

        ## INPUT(실험값)
        params =[{'AddSolution=InP_Injectionrate': 150.0, 'AddSolution=Zn_Injectionrate': 180.0, 'AddSolution=Se_Injectionrate': 1100.0, 'Heat=Temperature':235.0}]
        ## OUTPUT(실험값)
        path = f"DB/flow/s{i}.json"
        data_df=load_json_result_pl(path)
        ## path
        job_script_path="InPZnSe_oil.json"
        load_model_path="flowtest.pkl"  # 반드시 다른이름으로 할 것
        save_model_path = "flowtest.pkl"  # 반드시 다른이름으로 할 것 - 덮어쓰고나면 복구를 못해요.

        #######################################################
        #######################################################
        
        lambda_max, FWHM, intensity=calculateUV_Data_clean_pl(uv_df=data_df)
        print(i, lambda_max, FWHM, intensity)
        i+=1

    '''
    #result_dict={"PL_GetPl":{"Data":{"Property":{'lambdamax': lambda_max, 'FWHM':FWHM, 'intensity':intensity}}}}
    result_dict= extract_result_dict_from_json(path)
    target_condition_dict={
                "PL_GetPl":
                {
                    "Property":{
                        "lambdamax":550,
                        "intensity":62000000,
                        "FWHM":22
                    },
                    "Ratio":{
                        "lambdamax":0.5,
                        "intensity":0.25,
                        "FWHM":0.25
                    }
                }
            }
    

    norm_params = _getNormalizedCondition_PL(params,job_script_path)
    loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=target_condition_dict)
    
    #########################################################
    #########################################################
    
    # 새로 모델 만들기
    createNewModel(configpath=job_script_path,savepath=save_model_path,params=norm_params, loss_obj=loss_obj)
    
    ## 다음 점 추천하기
    #bo_obj = openModel(load_model_path)
    #print(bo_obj.res)
    #print(bo_obj.suggestNextStep())
    
    ## 결과 덮어쓰기
    #overwriteSinglePreviousModel(modelpath=load_model_path, savepath=save_model_path, params=params, loss_obj=loss_obj)
    '''
    