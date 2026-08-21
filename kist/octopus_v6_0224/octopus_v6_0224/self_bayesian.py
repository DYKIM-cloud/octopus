import json
import pickle
import pandas as pd
from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization
from Algorithm.Loss.UV_loss import LossFunction
from Analysis.AnalysisUV import calculateManualUV_Data
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

def _getNormalizedCondition(self, real_next_points):
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
        for chemical, rangeList in self.prange.items():
            new_value[chemical]=(int(next_point[chemical])-rangeList[0])/(rangeList[1]-rangeList[0]) # X' = (value - V_min)/(V_max - V_min) 
        normalized_next_points.append(new_value)
    
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


def createNewModel(configpath, savepath, params, loss_obj):

    
    optimal_value = loss_obj.lambdamaxpvLoss()

    results=optimal_value


    config_data = openConfigFile(configpath)


    pickle_name=savepath   

    model = createModel(algorithm_dict=config_data["algorithm"])

    model = registerData2Model(result_list=results, params_list=params, model=model)

    calculateModelResultSize(model)

    writeModel(pickle_name=pickle_name, model=model)

    openmodel = openModel(pickle_name)

    calculateModelResultSize(model=openmodel)



def overwriteSinglePreviousModel(modelpath, savepath, params, loss_obj):


    optimal_value, property_tuple = loss_obj.lambdamaxpvLoss()
    results=[optimal_value]

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
    ## INPUT(실험값)
    params =[{'AddSolution=InP_Injectionrate': 700.0, 'AddSolution=A_Injectionrate': 800.0, 'preHeat=Temperature': 50.0, 'Heat=Temperature':200.0}]
    ## OUTPUT(실험값)
    data_dict=load_result(path = "TalkFile_G_InP.txt")
    ## path
    job_script_path="Autonomous_241119.json"
    load_model_path="./model.pkl"  # 반드시 다른이름으로 할 것
    save_model_path = "./model.pkl"  # 반드시 다른이름으로 할 것 - 덮어쓰고나면 복구를 못해요.
    
    #######################################################
    #######################################################
    uv_result,uv_dict=calculateManualUV_Data(uv_dict=data_dict)
    result_dict={"UV_GetUVdata":{"Data":{"Property":{'lambdamax': uv_result["lambdamax"], 'p_v_ratio':uv_result["p_v_ratio"]},"Wavelength":uv_dict["Wavelength"],"RawSpectrum":uv_dict["RawSpectrum"]}}}
    target_condition_dict={
                "GetUVdata":
                {
                    "Property":{
                        "lambdamax":490,
                        "p_v_ratio":2.0
                    },
                    "Ratio":{
                        "lambdamax":0.1,
                        "p_v_ratio":0.9
                    }
                }
            }
    
    loss_obj = LossFunction(result_dict=result_dict, target_condition_dict=target_condition_dict)
    #########################################################
    #########################################################
    
    ## 새로 모델 만들기
    # createNewModel(configpath=job_script_path,savepath=save_model_path,params=params, loss_obj=loss_obj)
    
    ## 다음 점 추천하기
    # bo_obj = openModel(load_model_path)
    # print(bo_obj.suggestNextStep())
    
    ## 결과 덮어쓰기
    # overwriteSinglePreviousModel(modelpath=load_model_path, savepath=save_model_path, params=params, loss_obj=loss_obj)