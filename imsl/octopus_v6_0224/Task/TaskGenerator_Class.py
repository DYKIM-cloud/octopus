#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [TaskGenerator] TaskGenerator file
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
from Task.TCP import TCP_Class
from TimeCheker import Timer


class Template:
    def __init__(self,):
        """
        Data format
        """
        self.all_data_template={
            "metadata":{},
            "algorithm":{},
            "process":{},
            "result":{}
        }
        
        """
        Process (High part: Process)
        """
        self.process_template= {
            "Synthesis":[], 
            "Characterization":[],
            "Collection":[]
        }
        
        """
        Process (Middle part: Module)
        """
        self.FlowSynthesis_template={
            "Module":"FlowSynthesis",
            "Data":[]
        }

        self.UV_template={
            "Module":"UV",
            "Data":[]
        }
        
        self.PL_template={
            "Module":"PL",
            "Data":[]
        }
        
        self.Collector_template={
            "Module":"Collector",
            "Data":[]
        }
        """
        Process (bottom part: Task)
        """
        # flow 
        self.FlowSynthesis_AddSolution_template={
            "Task":"FlowSynthesis_AddSolution",
            "Data":{
                "Solution":"",
                "Injectionrate":{
                    "Value":0,"Dimension":"μL/s"
                    },
                "Device":{}
            } 
        }

        self.FlowSynthesis_preHeat_template={
            "Task": "FlowSynthesis_preHeat",
            "Data": {
                "Temperature": {
                    "Value": 0,
                    "Dimension": "ºC"
                },
                "Device":{}
            }
        }

        self.FlowSynthesis_Heat_template={
            "Task": "FlowSynthesis_Heat",
            "Data": {
                "Temperature": {
                    "Value": 0,
                    "Dimension": "ºC"
                },
                "Device":{}
            }
        }

        self.FlowSynthesis_React_template={
            "Task": "FlowSynthesis_React",
            "Data": {
                "Time": {
                    "Value": 0,
                    "Dimension": "sec"
                },
                "Device":{}
            }
        }
        
        # UV-VIS
        # Only Default Value
        self.UV_GetAbs_template={
            "Task":"UV_GetAbs",
            "Data":{
                "Device":{},
                "Hyperparameter":{
                    "WavelengthMin":{
                        "Description":"WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                        "Value": 300,
                        "Dimension": "nm"
                    },
                    "WavelengthMax":{
                        "Description":"WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                        "Value": 700,
                        "Dimension": "nm"
                    },
                    "BoxCarSize":{
                        "Description":"BoxCarSize=10 (int): smooth strength",
                        "Value": 30,
                        "Dimension": "None"
                    },
                    "Prominence":{
                        "Description":"Prominence=0.01 (float): minimum peak Intensity for detection",
                        "Value": 0.010,
                        "Dimension":"None"
                    },
                    "PeakWidth":{
                        "Description":"PeakWidth=20 (int): minumum peak width for detection",
                        "Value": 15,
                        "Dimension": "nm"
                    }
                }
            },
        }
        self.PL_GetPl_template={
            "Task":"PL_GetPl",
            "Data":{
                "Device":{},
                "Hyperparameter":{
                    "WavelengthMin":{
                        "Description":"WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                        "Value": 430,
                        "Dimension": "nm"
                    },
                    "WavelengthMax":{
                        "Description":"WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                        "Value": 700,
                        "Dimension": "nm"
                    },
                    "BoxCarSize":{
                        "Description":"BoxCarSize=10 (int): smooth strength",
                        "Value": 10,
                        "Dimension": "None"
                    },
                    "Prominence":{
                        "Description":"Prominence=0.01 (float): minimum peak Intensity for detection",
                        "Value": 0.01,
                        "Dimension":"None"
                    },
                    "PeakWidth":{
                        "Description":"PeakWidth=20 (int): minumum peak width for detection",
                        "Value": 15,
                        "Dimension": "nm"
                    }
                }
            },
        }
        self.Collector_Collect_template={
            "Task" : "Collector_Collect",
            "Data" : {
                "Volume":{
                    "Value":0,
                    "Dimension":"μL/s"
                },
                "Time":{
                    "Value":0,
                    "Dimension":"s"
                }
            }
        }

class TaskGenerator(Template):
    """
    TaskGenerator class get task sequence, allocate each task's value in json file (recipe)

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
    def __init__(self, TaskLogger_obj:object, ResourceManager_obj:object):
        """
        sequence_list=[["MoveContainer","AddSolution","Stir","Heat","Mix","AddSolution","Mix","MoveContainer"],....]
        soliution_list=[{'AgNO3': 2400.0, 'NaBH4': 2400.0, 'H2O2': 1200.0, 'H2O': 2400.0, "PVP55":2000.0, "Citrate":2000.0}, ...]
        """
        Template.__init__(self,)
        TCP_Class.__init__(self,)
        self.TaskLogger_obj=TaskLogger_obj
        self.component_name="TaskGenerator"

        self.ResourceManager_obj=ResourceManager_obj
        self.task_device_info_dict = self.ResourceManager_obj.task_device_info_dict
    def __find_module_in_process(self, process_module_dict, module_name):
        for process, module_list in process_module_dict.items():
            if module_name in module_list:
                return process
        raise Exception("there is no module name: {} --> {}".format(process_module_dict, module_name))

    def _allocateTaskInfo(self, big_process_module_dict:dict, input_task_name:str, integrated_parameter_dict:dict):
        """
        allocate some value in recipe template

        :param big_process_module_dict (dict): 
        :param input_task_name (str): BatchSynthesis_AddSolution=AgNO3 or BatchSynthesis_Stir...ElectroAnalysis_Electrochemical... etc...
        :param integrated_parameter_dict (dict) --> dict(parameter_dict, **fixed_params_dict)

        :return: template (dict), 
        """
        module_name=""
        task_name=""
        task_content=""
        if "=" in input_task_name:
            module_task_name, task_content = input_task_name.split("=")
        else:
            module_task_name=input_task_name
        module_name, task_name=module_task_name.split("_")
        template_name="{}_template".format(module_task_name)
        if hasattr(self, template_name):
            template = getattr(self, template_name)
            empty_template=copy.deepcopy(template)
        else:
            raise ValueError("{} has no template in class".format(template_name))
        if "FlowSynthesis" == module_name:
            if "AddSolution" == task_name:
                # AddSolution의 solution type을 delete
                ####################################################
                # AddSolution include pump and pipette
                ####################################################
                # print("####################################################")
                # print(self.task_device_info_dict)
                # print("####################################################")
                pump_device_info=self.task_device_info_dict[module_name]["Pump"]
                solution_device_info = dict(pump_device_info)
                # print("****************************************************")
                # print("solution_device_info", solution_device_info)
                # print("****************************************************")

                ####################################################
                # self.solution_name_list == pump solution name in BatchSynthesisPlatform
                # self.solution_Device_list == pump Device in BatchSynthesisPlatform
                ####################################################
                solution_name_list_in_platform=list(solution_device_info.keys()) # ["AgNO3", "H2O", "PVP55"... ]
                ####################################################
                # solution_name_in_job == wanted solution name in job script
                # solution_index_list == pump solution index in BatchSynthesisPlatform
                # filter_solution_name_list == wanted solution name & match pump Device in BatchSynthesisPlatform
                #   (If this solution can use in platform?)
                ####################################################
                solution_name_in_job=task_content # AddSolution={solution_name_ValueName} separate --> solution_name in jobscript 
                solution_index_list = [i for i, sol_name in enumerate(solution_name_list_in_platform) if sol_name==solution_name_in_job] # solution name is equal
                filter_solution_name_list=[solution_name_list_in_platform[idx] for idx in solution_index_list]
                if solution_name_in_job in filter_solution_name_list:
                    empty_template["Data"]["Solution"]=solution_name_in_job # add solution name
                    empty_template["Data"]["Injectionrate"]["Value"]=integrated_parameter_dict[task_name+"="+solution_name_in_job+"_Injectionrate"] # Injection rate
                    empty_template["Data"]["Device"]=solution_device_info[solution_name_in_job]
                else:
                    KeyError("[{}] {} vs filter_solution_name_list : {} is different".format(self.component_name, solution_name_in_job, filter_solution_name_list))
                template=empty_template
                
                return template

            elif "preHeat" == task_name:
                empty_template["Data"]["Temperature"]["Value"]=integrated_parameter_dict["preHeat=Temperature"] # upload in job script file
                device_info=self.task_device_info_dict[module_name]["Heater"]["preHeater"] # upload in hardware Device
                empty_template["Data"]["Device"]=device_info
                
                template=empty_template
                return template

            elif "Heat" == task_name:
                empty_template["Data"]["Temperature"]["Value"]=integrated_parameter_dict["Heat=Temperature"] # upload in job script file
                device_info=self.task_device_info_dict[module_name]["Heater"]["Heater"] # upload in hardware Device
                empty_template["Data"]["Device"]=device_info
                
                template=empty_template
                return template
        
        elif "UV" == module_name:
        # elif type(task_type)==dict: # The characterization varies depending on what value it is intended to reflect.
            if "GetAbs" == task_name:
                uv_hyperparameter_include_parameter_name_list=[]
                parameter_name_list=list(integrated_parameter_dict.keys())
                for parameter_name in parameter_name_list:
                    if "Hyperparameter" in parameter_name and "GetAbs" in parameter_name:
                        uv_hyperparameter_include_parameter_name_list.append(parameter_name)
                        _, hyperparameter_name=parameter_name.split("_")
                        empty_template["Data"]["Hyperparameter"][hyperparameter_name]["Value"]=integrated_parameter_dict[parameter_name] # add Volume
                device_info=self.task_device_info_dict[module_name]
                empty_template["Data"]["Device"]=device_info[module_name]
                template=empty_template
                return template
            
        elif "PL" == module_name:
            if "GetPl" == task_name:
                pl_hyperparameter_include_parameter_name_list=[]
                parameter_name_list=list(integrated_parameter_dict.keys()) 
                for parameter_name in parameter_name_list:
                    if "Hyperparameter" in parameter_name and "GetPl" in parameter_name:
                        pl_hyperparameter_include_parameter_name_list.append(parameter_name)
                        _, hyperparameter_name=parameter_name.split("_")
                        empty_template["Data"]["Hyperparameter"][hyperparameter_name]["Value"]=integrated_parameter_dict[parameter_name] # add Volume
                device_info=self.task_device_info_dict[module_name]
                empty_template["Data"]["Device"]=device_info[module_name]
                template=empty_template
                return template

        elif "Collector" == module_name:
            if "Collect" == task_name:
                empty_template["Data"]["Volume"]["Value"] = integrated_parameter_dict["Collect=Volume"]
                device_info = self.task_device_info_dict[module_name]
                empty_template["Data"]["Device"] = device_info[module_name]
                
                flow_rate_list = []
                pump_device_info=self.task_device_info_dict[module_name]["Collector"]
                solution_device_info = dict(pump_device_info)
                solution_name_list_in_platform=list(solution_device_info.keys())
                
                for inst_task, inst_value in integrated_parameter_dict.items():
                    if "AddSolution" in inst_task:
                        flow_rate_list.append(integrated_parameter_dict[inst_task]) # Injection rate

                timer_obj=Timer(flow_rate_list)
                total_time=timer_obj.volume_timer(volume = integrated_parameter_dict["Collect=Volume"])
                empty_template["Data"]["Time"]["Value"] = total_time

                template=empty_template
                return template

    def _addTaskSequence(self, module_name, module_dict):
        temp_module_dict=copy.deepcopy(module_dict)

        if module_name=="FlowSynthesis":
            # later
            pass

        elif module_name=="UV":
            pass
        
        # module_idx=module_seq_list.index(module_name)
        # current_process=self.__find_module_in_process(big_process_temp_module_dict, module_name)
        # previous_process=self.__find_module_in_process(big_process_temp_module_dict, module_seq_list[module_idx-1])
        # if (module_idx==0) or (current_process=="Synthesis" and previous_process=="Preprocess"):
        #     temp_module_dict["Sequence"].insert(0, "AMR_MoveContainer=Storage2{}".format(module_name))
        # elif module_idx==len(module_seq_list)-1:
        #     temp_module_dict["Sequence"].append("AMR_MoveContainer={}_to_Storage".format(module_name))
        # temp_module_dict["Sequence"].append("AMR_MoveContainer={}_to_{}".format(module_name, module_seq_list[module_idx+1]))
        return temp_module_dict

    def generateRecipe(self, recipe_dict:dict, input_next_point={}):
        """
        allocate synthesis sequence process in json file (recipe) depending on each task_sequence_list
        
        :param recipe_dict (dict) : recipe information in config file
        ex)
        process_dict = {
            "Synthesis":{
                "BatchSynthesis":
                {
                    "Sequence":["AddSolution_Citrate","AddSolution_NaBH4","Stir","Heat","Mix", "AddSolution_AgNO3", "React"],
                    "fixedParams":
                    {

                        "AddSolution=Citrate_Concentration" : 20,
                        "AddSolution=Citrate_Volume" : 1200,
                        "AddSolution=Citrate_Injectionrate" : 200,
                        "AddSolution=NaBH4_Concentration" : 10,
                        "AddSolution=NaBH4_Volume" : 3000,
                        "AddSolution=NaBH4_Injectionrate" : 200,

                        "Stir=StirRate":1000,
                        "Heat=Temperature":25,
                        "Mix=Time":300,
                        "React=Time":1200
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
                        "UV=Sequence":["GetAbs"],
                        "UV=Hyperparameter_WavelengthMin":300, 
                        "UV=Hyperparameter_WavelengthMax":849, 
                        "UV=Hyperparameter_BoxCarSize":10, 
                        "UV=Hyperparameter_Prominence":0.01, 
                        "UV=Hyperparameter_PeakWidth":20
                    }
                }
            },
            "Evaluation":{
                "RDE":{},
                "Electrode":{}
            }
        }
        :param input_next_point (dict) :result of algorithm value dict
        
        :return temp_process_template (dict): total process_template
        """
        temp_process_template= copy.deepcopy(self.process_template)
        """
        self.process_template= {
            "Synthesis":[], 
            "Characterization":[]
        }
        """
        final_big_process_name=""
        final_module_name=""
        module_seq_list=[]
        big_process_module_dict={
            "Synthesis":[], 
            "Characterization":[],
            "Collection":[]
        }
        for big_process_name, big_process_dict in recipe_dict.items():
            for module_name, module_dict in big_process_dict.items():
                if len(module_dict)!=0:
                    module_seq_list.append(module_name)
                    big_process_module_dict[big_process_name].append(module_name)
        for big_process_name, big_process_dict in recipe_dict.items(): # big_process_name = "Synthesis", "Preprocess", "Characterization", "Evaluation":
            count=0
            for module_name, module_dict in big_process_dict.items(): # module_name = "BatchSynthesis" or "FlowSynthesis"
                if len(module_dict)!=0:
                    integrated_parameter_dict = dict(input_next_point, **module_dict["fixedParams"])
                    integrated_parameter_dict=copy.deepcopy(integrated_parameter_dict)
                    ####################################################
                    # if need to additional task in module (not changed)
                    ####################################################
                    module_template=copy.deepcopy(getattr(self, module_name+"_template"))
                    module_task_list=[]
                    added_module_dict={}
                    # added_module_dict=self._addTaskSequence(big_process_module_dict, module_name, module_dict, module_seq_list)
                    added_module_dict=self._addTaskSequence(module_name, module_dict)
                    ########################################
                    # allocate task depending on sequences #
                    ########################################
                    # try:
                    for task_name in added_module_dict["Sequence"]: # Allocate task_name according to the Sequence within the module.
                        temp_each_task_template=self._allocateTaskInfo(big_process_module_dict, task_name, integrated_parameter_dict)
                        # print(temp_each_task_template)
                        module_task_list.append(temp_each_task_template)
                    # except KeyError as e:
                    #     print(e)
                    #     raise KeyError("integrated_parameter_dict has no module_sequences")
                    ##########################################
                    # attach task_list in template
                    ##########################################
                    module_template["Data"]=module_task_list
                    temp_process_template[big_process_name].append(module_template)
                    final_module_name=module_name # "Add a template to save to storage after every process completion."
                    final_big_process_name=big_process_name

                else: # process is empty
                    count+=1
            # if empty_process -> delete
            if count==len(list(big_process_dict.keys())):
                del temp_process_template[big_process_name]
        """
        modified later (notion --> https://www.notion.so/2024-03-28-code-9aabcf883b0e49e9b0ff0057480b36e4)
        """
        return temp_process_template


if __name__ == "__main__":
    from Log.Logging_Class import TaskLogger
    sys.path.append(
    os.path.abspath("/home/sdl-main/catkin_ws/src/Octopus"))
    from Resource.ResourceManager_Class import ResourceManager
    input_next_point={
        "AddSolution=InP_Injectionrate" : 100,
        "AddSolution=A_Injectionrate" : 100,
        "preHeat=Temperature" : 30,
        "Heat=Temperature" : 150
    }
    metadata_dict={
        "subject":"InP_core_test",
        "group":"Hanyang",
        "logLevel":"DEBUG",
        "modeType":"virtual",
        "todayIterNum":1,
        "userName":"NY",
        "jobID":0,
        "jobFileName":"USER/NY/job_script/20240417_automatic_test.json",
        "batchSize":1
    }
    recipe_dict={
        "Synthesis":{
            "FlowSynthesis":{
                "Sequence":["FlowSynthesis_AddSolution=InP","FlowSynthesis_AddSolution=A","FlowSynthesis_preHeat","FlowSynthesis_Heat"],
                "fixedParams":{}
            }
        },
        "Characterization":{
            "UV":
            {
                "Sequence":["UV_GetAbs"],
                "fixedParams":
                {"Hyperparameter":
                    {
                        "WavelengthMin":{
                            "Description":"WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                            "Value": 350,
                            "Dimension": "nm"
                        },
                        "WavelengthMax":{
                            "Description":"WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                            "Value": 849,
                            "Dimension": "nm"
                        },
                        "BoxCarSize":{
                            "Description":"BoxCarSize=10 (int): smooth strength",
                            "Value": 10,
                            "Dimension": "None"
                        },
                        "Prominence":{
                            "Description":"Prominence=0.01 (float): minimum peak Intensity for detection",
                            "Value": 0.01,
                            "Dimension": "None"
                        },
                        "PeakWidth":{
                            "Description":"PeakWidth=20 (int): minumum peak width for detection",
                            "Value": 20,
                            "Dimension": "nm"
                        }
                    }
                }
            },
            "PL":
            {
                "Sequence":["PL_GetPl"],
                "fixedParams": {
                    "Hyperparameter":{
                        "WavelengthMin":{
                            "Description":"WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                            "Value": 300,
                            "Dimension": "nm"
                        },
                        "WavelengthMax":{
                            "Description":"WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max",
                            "Value": 849,
                            "Dimension": "nm"
                        },
                        "BoxCarSize":{
                            "Description":"BoxCarSize=10 (int): smooth strength",
                            "Value": 10,
                            "Dimension": "None"
                        },
                        "Prominence":{
                            "Description":"Prominence=0.01 (float): minimum peak Intensity for detection",
                            "Value": 0.01,
                            "Dimension": "None"
                        },
                        "PeakWidth":{
                            "Description":"PeakWidth=20 (int): minumum peak width for detection",
                            "Value": 20,
                            "Dimension": "nm"
                        }
                    }
                }
            }
        },
        "Collection":{
            "Collector":{
                "Sequence":["Collector_Collect"],
                "fixedParams":{"Collect=Volume": 1000}
            }
        }
    }
    TaskLogger_obj=TaskLogger(metadata_dict,userName="NY")
    sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
    sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
    sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../Resource/")))    
    
    TaskLogger_obj=TaskLogger(metadata_dict,userName="NY")
    ResourceManager_obj=ResourceManager(["FlowSynthesis", "UV", "PL", "Collector"])
    TaskGenerator_obj=TaskGenerator(TaskLogger_obj,ResourceManager_obj)
    
    # import time
    # for i in range(2):
    dict_obj = TaskGenerator_obj.generateRecipe(recipe_dict, input_next_point)
    print(dict_obj)
        # time.sleep(2)        
        # TaskGenerator_obj.saveRecipeToJSON(dict_obj=dict_obj, file_name="20240128_{}.json".format(i), mode_type="virtual")
