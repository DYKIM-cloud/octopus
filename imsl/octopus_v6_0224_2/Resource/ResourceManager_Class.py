import time
import os, sys
import json, copy
import socket
# import numpy as np
import threading
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from more_itertools import locate
from Hardware.FlowSynthesis.Pump import PumpParameter, DillutePumpParamter
from Hardware.FlowSynthesis.Heater import HeaterParameter
from Hardware.Collect.collector import CollectorParameter
from Hardware.UV.uv import UVParameter
from Hardware.UV.pl import PLParameter
class ResourceManager():
    """
    ResourceManager class check status of devices, and update device information from NodeManager
    # function
    """
    def __init__(self, module_list:list):
        self.module_list=module_list
        self.component_name="ResourceManager"
        ################################
        # module로부터 매번 받도록 하기 #
        # 아마 module에 resource manager를 따로 만들어야할 듯
        # 특정 job에서 module 실행한다고 하면, 아예 처음부터 지정해버리기
        ################################
        self.task_device_location_dict={
            "FlowSynthesis":{
                "Line":["?"]*1,
                # "preHeater":["?"]*1,
                # "Heater":["?"]*1
            },
            "UV":{ 
                "Spectroscopy":["?"]*1
            },
            "PL":{ 
                "Spectroscopy":["?"]*1
            },
            "FlowDillution":{
                "Line":["?"]*1,
            },
            "Collector":{
                "Vial":["?"]*80
            }
        }
        ################################
        # module로부터 매번 받도록 하기 #
        # 아마 module에 resource manager를 따로 만들어야할 듯
        ################################
        self.task_device_status_dict={
            "FlowSynthesis_Line":False,
            # "FlowSynthesis_Heater":False,
            # "FlowSynthesis_preHeater":False,
            "UV_Spectroscopy":False,
            "PL_Spectroscopy":False,
            "FlowDillution_Line":False,
            "Collector_Vial":False

        }
        #########################################
        # module로부터 처음 연결할 때 받도록 하기 #
        #########################################
        # task_device_info_dict 받을 때 같이 
        #########################################
        # protect for collision between each devices
        self.task_device_mask_dict={
            "FlowSynthesis_AddSolution":["FlowSynthesis_Line"],
            "FlowSynthesis_preHeat":["FlowSynthesis_Line"],
            "FlowSynthesis_Heat":["FlowSynthesis_Line"],
            "UV_GetAbs":["UV_Spectroscopy"],
            "PL_GetPl":["PL_Spectroscopy"],
            "FlowDillution_AddSolution":["FlowDillution_Line"],
            "Collector_Collect":["Collector_Vial"]
        }
        self.task_device_info_dict = self.requestHardwareInfo()

    ##################################################
    # callServer를 하나로 만들어서 paramater에서 받기  #
    ##################################################
    def requestHardwareInfo(self):
        """
        request to all of platform to get detailed information about each devices.
        We use this function to map recipe based on config file. 
        (config file--> only set "AddSolution_Metal", recipe file 
            --> write more detail, ex) "AddSolution":{"Solution":"AgNO3"}
        
            (ex.Batch : pump 0 --> AgNO3, Pump 1 --> DI water... 
                Preprocess : Pipette --> 2-propanol, DI water...)
        total_device_info_dict=
        {
            "FlowSynthesis":{
                "Pump":{
                    "AgNO3":
                        {"SolutionType":"Metal",
                        "PumpAddress":1, # 0->1
                        "PumpUsbAddr":"/dev/ttyPUMP2",
                        "Resolution":1814000,
                        "Concentration":0.00125,
                        "SyringeVolume":5000,
                        "DeviceName":"CavroCentris"
                        },
                    "NaBH4":
                        {"SolutionType":"Reductant",
                        "PumpAddress":2,
                        "PumpUsbAddr":"/dev/ttyPUMP2",
                        "Resolution":1814000,
                        "Concentration":0.01,
                        "SyringeVolume":5000,
                        "DeviceName":"CavroCentris"
                        },
                    "H2O2":
                        {"SolutionType":"Oxidant",
                        "PumpAddress":3,
                        "PumpUsbAddr":"/dev/ttyPUMP1",
                        "Resolution":1814000,
                        "Concentration":0.375,
                        "Density":1.45,
                        "MolarMass":34.0147,
                        "SyringeVolume":5000,
                        "DeviceName":"CavroCentris"
                        },
                    "Citrate":
                        {"SolutionType":"CA",
                        "PumpAddress":4,
                        "PumpUsbAddr":"/dev/ttyPUMP1",
                        "Resolution":1814000,
                        "Concentration":0.02,
                        "SyringeVolume":5000,
                        "DeviceName":"CavroCentris"
                        },
                },
                "Pipette": {
                    "PVP55":
                        {"SolutionType":"CA",
                        "PumpAddress":5,
                        "PumpUsbAddr":"COM7",
                        "DeviceName":"20-200μL"}
                },
                "Stirrer":{
                    "Stirrer_0":{
                        "Address":0,
                        "Port":"COM5",
                        "DeviceName":"IKA_RET",
                        "Temperature":25
                    },
                    "Stirrer_1":{
                        "Address":0,
                        "Port":"COM6",
                        "DeviceName":"IKA_RET",
                        "Temperature":25
                    }
                },
            ...
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
        :return: total_device_info_dict (dict), 
        """
        try:
            total_device_info_dict={}
            for module_name in self.module_list:
                temp_device_info_dict={}
                if module_name == "FlowSynthesis":
                    pump_obj = PumpParameter()
                    heater_obj = HeaterParameter()
                    temp_device_info_dict["Pump"] = pump_obj.pump_info
                    temp_device_info_dict["Heater"] = heater_obj.heater_info
                    total_device_info_dict[module_name] = temp_device_info_dict
                elif module_name == "UV":
                    uv_obj = UVParameter()
                    temp_device_info_dict["UV"] = uv_obj.UV_info
                    total_device_info_dict[module_name] = temp_device_info_dict
                elif module_name == "PL":
                    pl_obj = PLParameter()
                    temp_device_info_dict["PL"] = pl_obj.PL_info
                    total_device_info_dict[module_name] = temp_device_info_dict
                elif module_name == "Collector":
                    collector_obj = CollectorParameter()
                    temp_device_info_dict["Collector"] = collector_obj.collector_info
                    total_device_info_dict[module_name] = temp_device_info_dict
                
        except Exception as e:
            raise ConnectionError("Each module node cannot connect each device --> error message : {}".format(e))
        
        return total_device_info_dict
    
    ##################################################
    # module로 옮기기  #
    ##################################################
    def __find_indexes(self, lst:list, value:int):
        """
        extract index in lst, matching with value
        
        Examples
        ----------------
        >>> lst=[0,0,"?","?","?",0,0,0]
        >>> jobID=0
        >>> index_list = self.__find_indexes(lst, jobID)
        >>> print(index_list)
        [0,1,5,6,7] 
        """
        return list(locate(lst, lambda x: x == value))
    
    ##################################################
    # callServer로 받아오는걸로 바꾸고, 해당 함수는 각 모듈로 옮기기  #
    ##################################################
    def allocateLocation(self, module_idx:int, module_type:str, jobID:int, total_recipe_template_list:list):
        """
        :param module_type: "BatchSynthesis", "FlowSynthesis", "UV" ... 
        :param jobID: allocate jobID in location_dict
        :param total_recipe_template_list: reflect recipe information in hardware location
        
        self.task_device_location_dict (dict)

        ex) self.task_device_location_dict={
                "Stirrer":["?","?","?","?","?","?","?","?"], # "?"==empty
                "vialHolder":["?","?","?","?","?","?","?","?"]
            }
        }
        """
        # allocate location information in self.location_dict depending on temperature 
        if module_type == "FlowSynthesis" or module_type == "FlowDillution":

            # search each temperature and stirrate setting in total_recipe_template_list
            temperature_in_recipe_list=[]
            for recipe in total_recipe_template_list:
                task_dict_list=[]
                for process_info in recipe["Synthesis"]:
                    if process_info["Module"]=="FlowSynthesis": # if locate FlowSynthesis in first
                        task_dict_list=process_info["Data"]
                for task_dict in task_dict_list:
                    if task_dict["Task"]=="FlowSynthesis_preHeat": 
                        temperature_in_recipe_list.append(task_dict["Data"]["Temperature"]["Value"])
                    if task_dict["Task"]=="FlowSynthesis_Heat": # we split depending on temperature (differenet temperature --> different stirrer)
                        temperature_in_recipe_list.append(task_dict["Data"]["Temperature"]["Value"])
                    else: # exclude AddSolution, Wait, React, Pipette...
                        pass
            # if 60 in temperature_in_recipe_list: # mix some temperature include 60
            #     empty_stirrer_0_hole_index=[]
            #     # empty_stirrer_1_hole_index=[]
            #     empty_vialHolder_index=[]
            #     while True: # while satisfy "if" condition
            #         empty_stirrer_0_hole_index=self.__find_indexes(self.task_device_location_dict[module_type]["Stirrer"][:8], "?") # "?" == empty, calculate "?" or not
            #         # empty_stirrer_1_hole_index=self.__find_indexes(self.task_device_location_dict[module_type]["Stirrer"][8:], "?") # "?" == empty, calculate "?" or not
            #         empty_vialHolder_index=self.__find_indexes(self.task_device_location_dict[module_type]["vialHolder"],"?") # "?" == empty
            #         # match recipe information with spare location of stirrer
            #         if temperature_in_recipe_list.count(60) <= len(empty_stirrer_0_hole_index) and \
            #             len(temperature_in_recipe_list) <= len(empty_vialHolder_index):
            #             break
            #     popped_stirrer_hole_index_list=[]
            #     popped_vialHolder_index_list=[]
            #     for idx, temperature in enumerate(temperature_in_recipe_list):
            #         if temperature == 60:
            #             popped_stirrer_hole_index=empty_stirrer_0_hole_index.pop(0) # pop first element in list
            #             self.task_device_location_dict[module_type]["Stirrer"][popped_stirrer_hole_index]=jobID
            #             popped_stirrer_hole_index_list.append(popped_stirrer_hole_index)
            #         # elif temperature == 60:
            #         #     popped_stirrer_hole_index=empty_stirrer_1_hole_index.pop(0) # pop first element in list
            #         #     self.task_device_location_dict[module_type]["Stirrer"][popped_stirrer_hole_index]=jobID
            #         #     popped_stirrer_hole_index_list.append(popped_stirrer_hole_index) 
            #         popped_vialHolder_index=empty_vialHolder_index.pop(0) # pop first element in list
            #         self.task_device_location_dict[module_type]["vialHolder"][popped_vialHolder_index]=jobID
            #         popped_vialHolder_index_list.append(popped_vialHolder_index)
            
            # else: # all temperature set 25 (RT)
            empty_line_index=[]
            while True: # while satisfy "if" condition
                empty_line_index = self.__find_indexes(self.task_device_location_dict[module_type]["Line"],"?")
                # if len(temperature_in_recipe_list) <= len(empty_line_index):
                break

            popped_line_index_list=[]
            for idx in range(1):

                popped_line_index=empty_line_index.pop(0) # pop first element in list
                self.task_device_location_dict[module_type]["Line"][popped_line_index]=jobID
                popped_line_index_list.append(popped_line_index)
            
            task_location_dict={
                "Line":popped_line_index_list,
            }

        elif module_type=="UV": # 
            popped_spectroscopy_index_list=[]
            while True: # while satisfy "if" condition
                empty_spectroscopy_index_list=self.__find_indexes(self.task_device_location_dict[module_type]["Spectroscopy"], "?")
                if len(total_recipe_template_list) <= len(empty_spectroscopy_index_list):
                    break
            for idx in range(len(total_recipe_template_list)):
                popped_spectroscopy_index=empty_spectroscopy_index_list.pop(0) # pop first element in list
                self.task_device_location_dict[module_type]["Spectroscopy"][popped_spectroscopy_index]=jobID
                popped_spectroscopy_index_list.append(popped_spectroscopy_index)
            task_location_dict={
                "spectroscopy":popped_spectroscopy_index_list
            }
        elif module_type=="PL": # 
            popped_spectroscopy_index_list=[]
            while True: # while satisfy "if" condition
                empty_spectroscopy_index_list=self.__find_indexes(self.task_device_location_dict[module_type]["Spectroscopy"], "?")
                if len(total_recipe_template_list) <= len(empty_spectroscopy_index_list):
                    break
            for idx in range(len(total_recipe_template_list)):
                popped_spectroscopy_index=empty_spectroscopy_index_list.pop(0) # pop first element in list
                self.task_device_location_dict[module_type]["Spectroscopy"][popped_spectroscopy_index]=jobID
                popped_spectroscopy_index_list.append(popped_spectroscopy_index)
            task_location_dict={
                "spectroscopy":popped_spectroscopy_index_list
            }
            
        elif module_type=="Collector":
            popped_collector_index_list=[]
            while True: # while satisfy "if" condition
                empty_collector_index_list=self.__find_indexes(self.task_device_location_dict[module_type]["Vial"], "?")
                if len(total_recipe_template_list) <= len(empty_collector_index_list):
                    break
            for idx in range(len(total_recipe_template_list)):
                popped_collector_index=empty_collector_index_list.pop(0) # pop first element in list
                self.task_device_location_dict[module_type]["Vial"][popped_collector_index]=jobID
                popped_collector_index_list.append(popped_collector_index)
            task_location_dict={
                "Vial":popped_collector_index_list
            }

            
        return task_location_dict
    
    def notifyNumbersOfTasks(self, total_recipe_template_list:list):
        """
        :param total_recipe_template_list: reflect recipe information in hardware location

        :return iter_num (int) : return minmum iter_num due to ClosedPacking scheduling
        """
        module_seq_list = [] # need this var to implement in location_dict
        iter_num=0
        for key, values in total_recipe_template_list[0].items():
            for value in values:
                if "Module" in value:
                    module_seq_list.append(value["Module"])
        # module_seq_list[0]을 보는 이유 : 뒤에 있는 공정들은 어차피 나중에 할거니깐. 
        # 지금 당장 시작해야하는 공정이 비어있으면 일단 실행.
        remained_resource_dict={}
        remained_resource_len_list=[]
        while True: # while satisfy "if" condition
            for device_name, device_resource_dict in self.task_device_location_dict[module_seq_list[0]].items():
                empty_resource_list=self.__find_indexes(device_resource_dict, "?")
                remained_resource_dict[device_name]=empty_resource_list
                remained_resource_len_list.append(len(empty_resource_list))
            if 0 not in remained_resource_len_list:
                break
        remained_resource_len_list.append(len(total_recipe_template_list))
        iter_num=min(remained_resource_len_list) # return minmum iter_num due to ClosedPacking scheduling
        return iter_num
    
    ##################################################
    # callServer를 하나로 만들어서 paramater에서 받기  #
    ##################################################
    def refreshDeviceLocation(self, module_type:str, device_type:str, jobID:int):
        """
        :param module_type (str): reflect process information of hardware location in module (BatchSynthesis, UV)
        :param jobID (int) : return job id

        :return self.task_device_location_dict[module_type] (dict)
        """
        device_values=self.task_device_location_dict[module_type][device_type]
        location_index_list=self.__find_indexes(device_values, jobID)
        for location_index in location_index_list:
            self.task_device_location_dict[module_type][device_type][location_index]="?"
        return self.task_device_location_dict[module_type]
    
    def refreshModuleLocation(self, module_type:str, jobID:int):
        """
        :param module_type (str): reflect process information of hardware location in module (BatchSynthesis, UV)
        :param jobID (int) : return job id

        :return self.task_device_location_dict[module_type] (dict)
        """
        for device_type, device_values in self.task_device_location_dict[module_type].items():
            location_index_list=self.__find_indexes(device_values, jobID)
            for location_index in location_index_list:
                self.task_device_location_dict[module_type][device_type][location_index]="?"
        return self.task_device_location_dict[module_type]

    ##################################################
    # callServer를 하나로 만들어서 paramater에서 받기  #
    ##################################################
    def refreshTotalLocation(self, jobID:int):
        """
        :param jobID (int) : return job id

        :return self.task_device_location_dict (dict)

        ex) self.task_device_location_dict={
            "BatchSynthesis":{ 
                "Stirrer":["?","?","?","?","?","?","?","?"], # "?"==empty
                "vialHolder":["?","?","?","?","?","?","?","?"]
            },
            "UV":{ 
                "vialHolder":["?","?","?","?","?","?","?","?"]
            }
        }
        """
        for module_type in self.task_device_location_dict.keys():
            self.refreshModuleLocation(module_type, jobID)
        return self.task_device_location_dict
    
    def updateStatus(self, task_name:str, status:bool):
        """
        :param task_name (str) : task name that you want to update 
        :return self.task_device_location_dict (dict)

        ex) 
        self.task_device_status_dict={
            "BatchSynthesis_RoboticArm":False,
            "BatchSynthesis_VialStorage":False,
            "BatchSynthesis_LinearAcutator":True,
            "BatchSynthesis_Pump":False,
            "UV_RoboticArm":False,
            "UV_Pipette":False,
            "UV_Spectroscopy":False
        }
        self.task_device_mask_dict={
            "PrepareContainer":["BatchSynthesis_RoboticArm","BatchSynthesis_VialStorage","BatchSynthesis_LinearAcutator","UV_RoboticArm"],
            "AddSolution":["BatchSynthesis_RoboticArm","BatchSynthesis_LinearAcutator","BatchSynthesis_Pump"],
            "React":["BatchSynthesis_RoboticArm","BatchSynthesis_LinearAcutator","UV_RoboticArm"],
            "GetAbs":["BatchSynthesis_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"],
            "MoveContainer":["BatchSynthesis_RoboticArm","BatchSynthesis_VialStorage","BatchSynthesis_LinearAcutator","UV_RoboticArm"],
        }
        """
        # self.serverLogger_obj.debug(self.component_name,"start to update status")
        time.sleep(1)
        device_criterion_list=self.task_device_mask_dict[task_name]
        
        # thread function
        def update_status_each(input_device_name, input_status):
            self.task_device_status_dict[input_device_name]=input_status # UV_RoboticArm is okay. (not disturb in AddSolution task)
        # define thread
        thread_list=[]
        for device_name in device_criterion_list:
            thread = threading.Thread(target=update_status_each, args=(device_name, status))
            thread_list.append(thread)
        # start thread
        for thread in thread_list: 
            thread.start()
        # main thread wait thread termination
        for thread in thread_list:
            thread.join()
        # self.serverLogger_obj.debug(self.component_name,"finish to update status")

    def checkStatus(self, task_name:str):
        """
        :param task_name (str) : task name that you want to update 
        while True:
            if len(criterion_count_list)==len(device_criterion_list) and all(not item for item in criterion_count_list):
                break
        
        :return: int(delay_time)
        """
        # self.serverLogger_obj.debug(self.component_name,"start to check status")
        start_wait_time=time.time()
        finish_wait_time=start_wait_time
        while True:
            time.sleep(2)
            criterion_count_list=[]
            device_criterion_list=self.task_device_mask_dict[task_name]
            # thread function
            def countCriterion(device_name):
                criterion_count_list.append(self.task_device_status_dict[device_name])
            # define thread
            thread_list=[]
            for device_name in device_criterion_list:
                thread = threading.Thread(target=countCriterion, args=(device_name,))
                thread_list.append(thread)
            # start thread
            for thread in thread_list: 
                thread.start()
            # main thread wait thread termination
            for thread in thread_list:
                thread.join()
            if len(criterion_count_list)==len(device_criterion_list) and all(not item for item in criterion_count_list):
                finish_wait_time=time.time()
                break
        # self.serverLogger_obj.debug(self.component_name,"finish to check status")
        if round(finish_wait_time-start_wait_time, 2) < 5:
            delay_time=0
        else:
            delay_time=round(finish_wait_time-start_wait_time, 2)
        return delay_time
    

if __name__ == "__main__":
    ResourceManager_obj=ResourceManager(["FlowSynthesis", "UV", "PL", "Collector"])
    print(ResourceManager_obj.task_device_info_dict)
    # print(PumpParameter.pump_info)