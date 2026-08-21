#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [RecipeGenerator] RecipeGenerator file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-21
# TEST 2022-04-11

from queue import Queue
import os, sys
import json
import copy
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from collections import OrderedDict
from Log.Logging_Class import TaskLogger
from Task.TCP import TCP_Class

class Template:
    def __init__(self,):
        """
        Data format
        """
        self.all_data_template={
            "metadata":{},
            "recipe":{},
            "result":{}
        }
        
        """
        Recipe (High part)
        """
        self.recipe_template= {
            "Synthesis":[], 
            "Preprocess":[], 
            "Characterization":[],
            "Evaluation":[],
        }
        
        """
        Recipe (Middle part)
        """
        self.BatchSynthesis_template={
            "Process":"BatchSynthesis",
            "Data":
            []  
        }
        self.FlowSynthesis_template={
            "Process":"FlowSynthesis",
            "Data":
            []
        }
        
        self.Washing_template={
            "Process":"Washing",
            "Data":
            []
        }
        self.Ink_template={
            "Process":"Ink",
            "Data":
            []
        }
        
        self.RDE_template={
            "Process":"RDE",
            "Data":
            []
        }
        self.Electrode_template={
            "Process":"Electrode",
            "Data":
            []
        }
        self.UV_template={
            "Process":"UV",
            "Data":[]
        }
        
        """
        Recipe (bottom part)
        """
        # Robot
        self.MoveContainer_template={
            "Action":"MoveContainer",
            "Data":{
                    "From":"",
                    "To":"",
                    "Container":"",
                    "Setting":{}
                }
        }

        # Batch
        self.PrepareSolution_template={
            "Action":"PrepareSolution",
            "Data":{
                # "To":"",
                "Solution":"",
                "Volume":{
                    "Value":0,"Dimension":"μL"
                    },
                "Concentration":{
                    "Value":0,"Dimension":"mM"
                    },
                "Setting":{}
            }
        }
        self.AddSolution_template={
            "Action":"AddSolution",
            "Data":{
                # "To":"",
                "Solution":"",
                "Volume":{
                    "Value":0,"Dimension":"μL"
                    },
                "Concentration":{
                    "Value":0,"Dimension":"mM"
                    },
                "Injectionrate":{
                    "Value":0,"Dimension":"μL/s"
                    },
                "Setting":{}
            } 
        }
        self.Stir_template={
            "Action": "Stir",
            "Data": {
                # "To": "",
                "StirRate": {
                    "Value": 0,
                    "Dimension": "rpm"
                },
                "Setting":{}
            }
        }
        self.Heat_template={
            "Action": "Heat",
            "Data": {
                # "To": "",
                "Temperature": {
                    "Value": 0,
                    "Dimension": "ºC"
                },
                "Setting":{}
            }
        }
        self.Wait_template={
            "Action": "Wait",
            "Data": {
                # "To": "",
                "Time": {
                    "Value": 0,
                    "Dimension": "sec"
                },
                "Setting":{}
            }
        }
        self.React_template={
            "Action": "React",
            "Data": {
                # "To": "",
                "Time": {
                    "Value": 0,
                    "Dimension": "sec"
                },
                "Setting":{}
            }
        }
        
        # Preprocess (add later)
        self.Sonication_template={
            "Action": "Sonication",
            "Data": {
                # "To": "",
                "Power":{
                    "Value": 0,
                    "Dimension": "kHz"
                },
                "Time": {
                    "Value": 0,
                    "Dimension": "sec"
                },
                "Setting":{}
            }
        }
        self.Centrifugation_template={
            "Action": "Centrifugation",
            "Data": {
                # "To": "",
                "Power":{
                    "Value": 0,
                    "Dimension": "rpm"
                },
                "Time": {
                    "Value": 0,
                    "Dimension": "sec"
                },
                "Setting":{}
            }
        }
        
        # Characterization
        self.GetAbs_template={
            "Action":"GetAbs",
            "Data":{
                "Setting":{}
                },
        }


class RecipeGenerator(Template,TCP_Class):
    """
    RecipeGenerator class get action sequence, allocate each action's value in json file (recipe)

    class Template --> has template of recipe
    class TCP_Class --> to request hardware information (pump) to use flexible system when we change our solution location or type, kinds

    # Variables
    ------------
    :param TaskLogger_obj (TaskLogger_obj): set logging object
    :param metadata_dict (dict): 
        ex) "metadata" : 
        "metadata" : 
            {
                "subject":"Take scneario",
                "group":"KIST_CSRC",
                "userName":"USER_HJ",
                "researcherId":"yoohj9475@kist.re.kr",
                "researcherPwd":"1234",
                "element":"Ag",
                "experimentType":"automatic",
                "logLevel":"INFO",
                "modeType":"real",
                "todayIterNum":1
            },
    """
    def __init__(self, TaskLogger_obj:object):
        """
        sequence_list=[["MoveContainer","AddSolution","Stir","Heat","Wait","AddSolution","Wait","MoveContainer"],....]
        soliution_list=[{'AgNO3': 2400.0, 'NaBH4': 2400.0, 'H2O2': 1200.0, 'H2O': 2400.0, "PVP55":2000.0, "Citrate":2000.0}, ...]
        """
        Template.__init__(self,)
        TCP_Class.__init__(self,)
        self.TaskLogger_obj=TaskLogger_obj
        self.platform_name="RecipeGenerator"
        # self.subject=metadata_dict["subject"]
        # self.userName=metadata_dict["userName"]

        # self.__TOTAL_RECIPE_FOLDER = "./USER/{}/DB/{}/RecipeJSON".format(self.userName,self.subject)
        # if os.path.isdir(self.__TOTAL_RECIPE_FOLDER) == False:
        #     os.makedirs(self.__TOTAL_RECIPE_FOLDER)

        self.task_hardware_info_dict = self.__requestHardwareInfo()

    def __requestHardwareInfo(self):
        """
        request to all of platform to get detailed information about each devices.
        We use this function to map recipe based on config file. 
        (config file--> only set "AddSolution_Metal", recipe file 
            --> write more detail, ex) "AddSolution":{"Solution":"AgNO3"})
        
            (ex.Batch : pump 0 --> AgNO3, Pump 1 --> DI water... 
                Preprocess : Pipette --> 2-propanol, DI water...)

        total_hardware_info_dict={
            "BatchSynthesis":{
                "Pump":{
                    "AgNO3":
                        {"SolutionType":"Metal",
                        "PumpAddress":0,
                        "PumpUsbAddr":"COM8",
                        "Resolution:1814000
                        "DeviceName":"CavroCentris"
                        },
                    "H2O":
                        {"SolutionType":"Solvent",
                        "PumpAddress":1,
                        "PumpUsbAddr":"COM8",
                        "Resolution:1814000
                        "DeviceName":"CavroCentris"
                        },
                    "NaBH4":
                        {"SolutionType":"Reductant",
                        "PumpAddress":2,
                        "PumpUsbAddr":"COM8",
                        "Resolution:1814000
                        "DeviceName":"CavroCentris"
                        },
                    "H2O2":
                        {"SolutionType":"Oxidant",
                        "PumpAddress":3,
                        "PumpUsbAddr":"COM7",
                        "Resolution:1814000
                        "DeviceName":"CavroCentris"
                        },
                    "Citrate":
                        {"SolutionType":"CA",
                        "PumpAddress":4,
                        "PumpUsbAddr":"COM7",
                        "Resolution:1814000
                        "DeviceName":"CavroCentris"
                        },
                },
                "Pipette", {
                    "PVP55":
                        {"SolutionType":"CA",
                        "PumpAddress":5,
                        "PumpUsbAddr":"COM7",
                        "DeviceName":"20-200μL"}
                },
                "Stirrer:{
                            "stirrerAddress":0,
                            "stirrerUsbAddr":"COM11",
                            "deviceName":"IKA"
                        },
                "LinearActuator":{

                },
                "VialStorage":{
                    
                },
            },
            "UV":{
                "Spectrometer":{
                    "DeviceName":"USB2000+",
                    "DetectionRange":"200-850nm",
                    "Solvent":{
                        "Solution":"H2O",
                        "Value": 2000,
                        "Dimension": "μL"
                    }
                "LightSource":{
                    "DeviceName":"DH-2000-BAL",
                    }
                }
            }
        }
        
        
        :return: total_hardware_info_dict (dict), 
        """
        try:
            total_hardware_info_dict={}
            total_hardware_info_dict["BatchSynthesis"] = self.callServer_BATCH_INFO()
            self.TaskLogger_obj.info(self.platform_name,"receive BATCH_INFO")
            total_hardware_info_dict["UV"]=self.callServer_UV_INFO()
            self.TaskLogger_obj.info(self.platform_name,"receive UV_INFO")
            # total_hardware_info_dict["FLOW"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Washing"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Preprocess"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["RDE"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Electrode"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["UV"] = self.callServer_BATCH_INFO()
        except Exception as e:
            self.TaskLogger_obj.info(self.platform_name,"Each hardware server cannot connect each device --> error message : {}".format(e))
            raise ConnectionError("Each hardware server cannot connect each device --> error message : {}".format(e))

        return total_hardware_info_dict

    def __allocateActionSequence(self, action_type:str, integrated_parameter_dict:dict):
        """

        allocate some value in recipe template

        :param action_type (str or dict): AddSolution or Stir...Electrochemical... etc...
        :param integrated_parameter_dict = dict(parameter_dict, **fixed_params_dict)
        :param graph_json={"Stirrer":"Stirrer_0"} (dict): set graph json (depending on possible hardware in future)
        
        :return: template (dict), 
        """
        if "AddSolution" in action_type:
            empty_template=copy.deepcopy(self.AddSolution_template)
            # AddSolution의 solution type을 delete
            empty_template["Action"]="AddSolution"
            ####################################################
            # AddSolution include pump and pipette
            ####################################################
            # print("####################################################")
            # print(self.task_hardware_info_dict)
            # print("####################################################")
            pump_hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Pump"]
            pipette_hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Pipette"]
            solution_hardware_info = dict(pump_hardware_info, **pipette_hardware_info)
            
            # print("****************************************************")
            # print("solution_hardware_info", solution_hardware_info)
            # print("****************************************************")

            ####################################################
            # self.solution_name_list == pump solution name in BatchSynthesisPlatform
            # self.solution_setting_list == pump setting in BatchSynthesisPlatform
            ####################################################
            solution_name_list_in_platform=list(solution_hardware_info.keys()) # ["AgNO3", "H2O", "PVP55"... ]

            ####################################################
            # solution_name_in_job == wanted solution name in job script
            # solution_index_list == pump solution index in BatchSynthesisPlatform
            # filter_solution_name_list == wanted solution name & match pump setting in BatchSynthesisPlatform
            #   (If this solution can use in platform?)
            ####################################################
            solution_name_in_job=action_type[12:] # AddSolution={solution_name_ValueName} 구분 --> solution_name in jobscript 
            solution_index_list = [i for i, sol_name in enumerate(solution_name_list_in_platform) if sol_name==solution_name_in_job] # solution name is equal
            filter_solution_name_list=[solution_name_list_in_platform[idx] for idx in solution_index_list]
            
            if solution_name_in_job in filter_solution_name_list:
                empty_template["Data"]["Solution"]=solution_name_in_job # solution name들을 넣어줌
                empty_template["Data"]["Volume"]["Value"]=integrated_parameter_dict["AddSolution="+solution_name_in_job+"_Volume"] # Volume 추가
                empty_template["Data"]["Concentration"]["Value"]=integrated_parameter_dict["AddSolution="+solution_name_in_job+"_Concentration"] # Concentration 추가
                empty_template["Data"]["Injectionrate"]["Value"]=integrated_parameter_dict["AddSolution="+solution_name_in_job+"_Injectionrate"] # Injection rate
                empty_template["Data"]["Setting"]=solution_hardware_info[solution_name_in_job]
            else:
                KeyError("[{}] {} vs filter_solution_name_list : {} is different".format(self.platform_name, solution_name_in_job, filter_solution_name_list))
            template=empty_template
            
            return template

        elif "Stir" in action_type:
            empty_template = copy.deepcopy(self.Stir_template)
            empty_template["Data"]["StirRate"]["Value"]=integrated_parameter_dict["Stir=StirRate"] # upload in job script file
            hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Stirrer"][graph_json["To"]] # upload in hardware setting
            empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template

        elif "Heat" in action_type:
            empty_template = copy.deepcopy(self.Heat_template)
            empty_template["Data"]["Temperature"]["Value"]=integrated_parameter_dict["Heat=Temperature"] # upload in job script file
            hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Stirrer"][graph_json["To"]] # upload in hardware setting
            empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template

        elif "Wait" in action_type:
            empty_template = copy.deepcopy(self.Wait_template)
            empty_template["Data"]["Time"]["Value"]=integrated_parameter_dict["Wait=Time"] # upload in job script file
            hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Stirrer"][graph_json["To"]] # upload in hardware setting
            empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template

        elif "React" in action_type:
            empty_template = copy.deepcopy(self.React_template)
            empty_template["Data"]["Time"]["Value"]=integrated_parameter_dict["React=Time"] # upload in job script file
            hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["Stirrer"][graph_json["To"]] # upload in hardware setting
            empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template

        # elif type(action_type)==dict: # Characterization는 어떤 value를 반영할 것인지에따라 달라짐.
        elif "GetAbs" in action_type:
            empty_template=copy.deepcopy(self.GetAbs_template)
            hardware_info=self.task_hardware_info_dict["UV"]
            empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template
            
        elif "RDE" in action_type: # add later
            reactor_location=graph_json["Electrochemical_reactor"]
            template = copy.deepcopy(self.RDE_template)
            return template
        
        elif "MoveContainer" in action_type:
            _, action_content = action_type.split("=")
            empty_template=copy.deepcopy(self.MoveContainer_template) # batch는 항상 vial 먼저 놓기 때문에 storage_empty_to_stirrer 는 처음에 고정
            if action_content == "storage_empty_to_stirrer" or action_content == "stirrer_to_holder":
                move_from, move_to = action_content.split("_to_")
                empty_template["Data"]["From"]=move_from
                empty_template["Data"]["To"]=move_to
                
                empty_template["Data"]["Container"]="Vial"
                
                hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["DS_B"]
                empty_template["Data"]["Setting"]=hardware_info
            
            template=empty_template
            return template

        else:
            raise IndexError("There is no action type in here : {}".format(action_type))

    # def saveRecipeToJSON(self, dict_obj:dict, file_name:str, subject:str, userName:str, mode_type:str):
    #     """
    #     extract action type and action data

    #     :param dict_obj (dict): recipe dict
    #     :param file_name (str): time_str=time.strftime("%Y%m%d_%H%M")
    #     :param mode_type (str): 
        
    #     :return self.__TOTAL_RECIPE_FOLDER+file_name (str): {dir}/{filename}.json
    #     """
    #     subject=metadata_dict["subject"]
    #     userName=metadata_dict["userName"]

    #     TOTAL_RECIPE_FOLDER = "./USER/{}/DB/{}/RecipeJSON".format(userName,subject)
    #     if os.path.isdir(TOTAL_RECIPE_FOLDER) == False:
    #         os.makedirs(TOTAL_RECIPE_FOLDER)

    #     new_path = TOTAL_RECIPE_FOLDER+"/"+mode_type
    #     if os.path.isdir(new_path) == False:
    #         os.makedirs(new_path)
    #     with open(new_path+"/"+file_name, 'w') as outfile:
    #         json.dump(dict_obj, outfile, indent=5)

    #     return new_path

    def generateRecipe(self, recipe_dict:dict, input_next_point:dict):
        """
        allocate synthesis sequence process in json file (recipe) depending on each action_sequence_list
        
        :param recipe_dict (dict) : recipe information in config file
        ex)
        {
            "BatchSynthesis":
            {
                "fixedParams":
                {
                    "H2O2_Concentration" : 0.375,
                    "H2O2_Volume" : 1200,
                    "H2O2_Injectionrate" : 200,
                    "Citrate_Concentration" : 0.02,
                    "Citrate_Volume" : 1200,
                    "Citrate_Injectionrate" : 200,
                    "NaBH4_Concentration" : 0.01,
                    "NaBH4_Volume" : 3000,
                    "NaBH4_Injectionrate" : 200
                },
                "fixedConstants":
                {
                    "baseStirRate":800,
                    "baseTemperature":25,
                    "baseWaitTime":1,
                    "baseReactTime":1
                },
                "fixedSequences":
                [
                    "AddSolution_Solvent","AddSolution_CA","AddSolution_Oxidant", "AddSolution_Reductant","Stir","Heat","Wait", "AddSolution_Metal", "React"
                ],
                "graphJson":
                {
                    "Stirrer":"Stirrer_0"
                }
            },
            "FlowSynthesis":{},
            "Washing":{},
            "Ink":{},
            "Optics":
            {
                "fixedParams":{},
                "fixedConstants":{},
                "fixedSequences":
                [
                    "UV"
                ],
                "graphJson":
                {}
            },
            "Evaluation":{},
            "After":
            {
                "fixedParams":{},
                "fixedConstants":{},
                "fixedSequences":
                [
                    "Store"
                ],
                "graphJson":
                {}
            }
        }
        :param input_next_point (dict) :result of algorithm value dict

        Sub_Params
            :param graph_json={"Stirrer":"Stirrer_1"} (dict) : stirrer location ex) "Stirrer_1", "Stirrer_2"
            --> will be change later after insert graph_json
            :param batch_action_sequence_list (list) : has sequences of synthesiss total process
                --> ex) ["AddSolution_Metal","AddSolution_Salt","AddSolution_Solvent","AddSolution_CA",
                        "AddSolution_pH","Stir","Heat","Wait","AddSolution_Reductant","Wait"]

        :return temp_recipe_template (dict): total recipe_template
        """
        temp_recipe_template= copy.deepcopy(self.recipe_template)
        """
        self.recipe_template= {
            "Synthesis":[], 
            "Preprocess":[], 
            "Characterization":[],
            "Evaluation":[]
        }
        """
        final_platform_name=""
        for platform_name, platform_dict in recipe_dict.items(): # platform_name = "Synthesis", "Preprocess", "Characterization", "Evaluation":
            for process_name, process_dict in platform_dict.items(): # process_name = "BatchSynthesis" or "FlowSynthesis"
                if len(process_dict)!=0:
                    temp_template=copy.deepcopy(getattr(self, process_name+"_template"))
                    integrated_parameter_dict = dict(input_next_point, **process_dict["fixedParams"])
                    integrated_parameter_dict=copy.deepcopy(integrated_parameter_dict)
                    each_action_list=[]
                    ##########################################
                    # if need to additional action in process
                    ##########################################
                    if process_name=="BatchSynthesis":
                        integrated_parameter_dict[process_name+"=Sequence"].insert(0, "MoveContainer=storage_empty_to_stirrer") # batch는 항상 vial 먼저 놓기 때문에 storage_empty_to_stirrer 는 처음에 고정
                        # integrated_parameter_dict[process_name+"=Sequence"].append("MoveContainer=stirrer_to_holder") # batch는 반응이 끝나면 항상 vial을 회수하기 때문에 stirrer_to_holder 는 마지막에 고정
                    elif process_name=="FlowSynthesis":
                        # 추후 촉매 전처리 과정도 도입할 예정
                        pass
                    elif process_name=="Washing":
                        # 추후 촉매 전처리 과정도 도입할 예정
                        pass
                    elif process_name=="Ink":
                        # 추후 촉매 전처리 과정도 도입할 예정
                        pass
                    elif process_name=="UV":
                        pass
                    
                    ##########################################
                    # allocate action depending on sequences
                    ##########################################
                    try:
                        for action_type in integrated_parameter_dict[process_name+"=Sequence"]: # process 안에서도 Sequence에 따라서 action_type 별로 할당
                            temp_each_action_template=self.__allocateActionSequence(action_type, integrated_parameter_dict)
                            each_action_list.append(temp_each_action_template)
                    except KeyError as e:
                        raise KeyError("integrated_parameter_dict has no process_sequences")
                    
                    ##########################################
                    # attach action_list in template
                    ##########################################
                    temp_template["Data"]=each_action_list
                    temp_recipe_template[platform_name].append(temp_template)
                    
                    final_platform_name=platform_name # 모든 platform, 모든 process 끝나면 storage로 저장하는 template 추가
                else: # process is empty
                    del temp_recipe_template[platform_name]
        ###############################################################
        # 모든 platform, 모든 process 끝나면 storage로 저장하는 template 추가
        ###############################################################
        temp_MoveContainer_template=copy.deepcopy(self.MoveContainer_template)
        temp_MoveContainer_template["Data"]["Container"]="Vial"
        temp_MoveContainer_template["Data"]["From"]="holder"
        temp_MoveContainer_template["Data"]["To"]="storage_filled"
        hardware_info=self.task_hardware_info_dict["BatchSynthesis"]["DS_B"]
        temp_MoveContainer_template["Data"]["Setting"]=hardware_info
        temp_recipe_template[final_platform_name][-1]["Data"].append(temp_MoveContainer_template)
            
        self.TaskLogger_obj.info(self.platform_name, "Allocate all of action depending on sequence!")
        
        del integrated_parameter_dict

        return temp_recipe_template


if __name__ == "__main__":
    input_next_point={
            "AddSolution=AgNO3_Concentration" : 0.375,
            "AddSolution=AgNO3_Volume" : 1200,
            "AddSolution=AgNO3_Injectionrate" : 200
        }
    metadata_dict={
        "subject":"Take_scneario",
        "group":"KIST_CSRC",
        "logLevel":"INFO",
        "modeType":"real",
        "todayIterNum":1,
        "userName":"HJ",
        "jobID":0,
        "jobFileName":"USER/HJ/job_script/20230516_autonomous_test.json",
        "batchSize":8
    }
    recipe_dict={
        "Synthesis":{
            "BatchSynthesis":
            {
                "fixedParams":
                {
                    "BatchSynthesis=Sequence":["AddSolution_Citrate","AddSolution_H2O2", "AddSolution_NaBH4","Stir","Heat","Wait", "AddSolution_AgNO3", "React"],
                    
                    "AddSolution=H2O2_Concentration" : 0.375,
                    "AddSolution=H2O2_Volume" : 1200,
                    "AddSolution=H2O2_Injectionrate" : 200,
                    "AddSolution=Citrate_Concentration" : 0.02,
                    "AddSolution=Citrate_Volume" : 1200,
                    "AddSolution=Citrate_Injectionrate" : 200,
                    "AddSolution=NaBH4_Concentration" : 0.01,
                    "AddSolution=NaBH4_Volume" : 3000,
                    "AddSolution=NaBH4_Injectionrate" : 200,

                    "Stir=StirRate":800,
                    "Heat=Temperature":25,
                    "Wait=Time":1,
                    "React=Time":1
                },
                "graphJson":
                {
                    "To":"Stirrer_0"
                }
            },
            "FlowSynthesis":{}
        },
        "Preprocess":{
            "Washing":{},
            "Ink":{}
        },
        "Characterization":{
            "UV":
            {
                "fixedParams":
                {
                    "UV=Sequence":["GetAbs"]
                },
                "graphJson":
                {}
            }
        },
        "Evaluation":{
            "RDE":{},
            "Electrode":{}
        }
    }
    TaskLogger_obj=TaskLogger(metadata_dict)
    RecipeGenerator_obj=RecipeGenerator(TaskLogger_obj, metadata_dict)
    import time
    for i in range(2):
        dict_obj = RecipeGenerator_obj.allocateActionSequence(recipe_dict, input_next_point)
        time.sleep(2)
        RecipeGenerator_obj.saveRecipeToJSON(dict_obj=dict_obj, file_name="1234_{}.json".format(i), mode_type="virtual")
