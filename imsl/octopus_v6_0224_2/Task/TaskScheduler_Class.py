#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [Scheduler] Scheduler file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-01
# TEST 2022-04-11

from queue import Queue
import time
import os, sys
import json, copy
import threading
import itertools
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Task.TCP import TCP_Class
from Analysis import AnalysisUV
# from Log.DigitalSecretary import AlertMessage
from TimeCheker import Timer
from Hardware.FlowSynthesis.Pump import AsiaPump, Pump_total
from Hardware.FlowSynthesis.Heater import AsiaHeaterCooler, Heater_total
from Hardware.Collect.collector import AsiaCollector
from Hardware.UV.uv import UV
from Hardware.UV.pl import PL
from Hardware.UV.OceanOptics.oceanoptics import OceanOpticsSpectrometer

Vial_queue = Queue()
the_number_of_Vial = 80

def initVialNum():
    """
    initialize tip number depending on Queue.

    :return: None: 
    """
    for num in range(the_number_of_Vial):
        Vial_queue.put(num)  

def popVialNum():
    """
    pop tip number depending on Queue.

    :return: vial_num (int): get vial number in UV_queue
    """
    empty_true = Vial_queue.empty()
    if empty_true==True:
        initVialNum()
    tip_num=Vial_queue.get()

    return tip_num   

class FlowSynthesisModule():
    """
    [BatchSynthesisModule] BatchSynthesisModule inherited Linear actuator, stirrer, syringe pump class

    # Variable
    :param module_name="BatchSynthesis" (str): set log name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _initializeDevice():
    2. _AllocateTecanAddress(solution_dict):
    3. _AllocateTecanUSBAddress(tecan_addr):
    4. _allocateAddress(stirrer_name):
    5. AddSolution(task_info_list):
    6. Stir(task_info_list):
    7. Heat(task_info_list):
    8. Mix(task_info_list):
    9. React(task_info_list):
    """
    def __init__(self,module_name="FlowSynthesis", ResourceManager_obj={}):

        self.__module_name= "{}".format(module_name)
        self.line_queue = Queue()
        self.the_number_of_line = 1

        # self.tip_1000_queue = Queue()
        # self.tip_100_queue = Queue()
        # self.the_number_of_tip_1000 = 96
        # self.the_number_of_tip_100 = 96
        self.__initLine()

        self.ResourceManager_obj=ResourceManager_obj

    def __initLine(self):
        """
        initialize vial number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_line):
            self.line_queue.put(num)  
    

    def __popLine(self):
        """
        pop vial number depending on Queue.

        :return: vial_num (int): get vial number in vial_bottom_queue
        """
        empty_true = self.line_queue.empty()
        if empty_true==True:
            self.__initLine()
        Line_num=self.line_queue.get()

        return Line_num

  
    def FlowSynthesis_AddSolution(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Add solution depending on task_info_list. This list included 1 cycle batch synthesis process.

        :param task_info_list (list): "Task":"AddSolution","Data":[] <- task_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        :(inside) task_dict : { "To":"Stirrer_1","Data":[] }
        :(inside) task_dict["Data"] : 
            [
                {
                    "Solution":"AgNO3",
                    "Volume":
                    {
                        "Value":1500,
                        "Dimension":"ul"
                    },
                    "Concentration":
                    {
                        "Value":20,
                        "Dimension":"mM"
                    },
                    "Injectionrate":
                    {
                        "Value":1000,
                        "Dimension":"ul/s"
                    }
                },
                ...
            
            ex) total_solution_queue :  [
                {'Solution': 'H2O2', 
                'Volume': {'Value': 1200, 'Dimension': 'μL'}, 
                'Concentration': {'Value': 0.375, 'Dimension': 'mM'}, 
                'Injectionrate': {'Value': 200, 'Dimension': 'μL/s'}, 
                'Setting': {'SolutionType': 'Oxidant', 'PumpAddress': 3, 'PumpUsbAddr': '/dev/ttyUSB0', 'Resolution': 1814000, 
                'Concentration': 0.75, 'Density': 1.45, 'MolarMass': 34.0147, 'SyringeVolume': 5000, 'DeviceName': 'CavroCentris'}}]
            ]
        """
        res_msg=""
        current_func_name=sys._getframe().f_code.co_name
        pipette_idx_list=[]

        for line_task_idx, task_dict in enumerate(task_info_list): # for each line
            # check & update status of device
            taskStartTime=time.strftime("%Y-%m-%d %H:%M:%S")
            delay_time=self.ResourceManager_obj.checkStatus(current_func_name) # wait until not busy
            taskFinishTime=time.strftime("%Y-%m-%d %H:%M:%S")
            delay_time_str="{}~{}".format(taskStartTime, taskFinishTime)
            TaskLogger_obj.addDelayTime(delay_time)
            TaskLogger_obj.appendDelayTime(delay_time_str, delay_time)
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "AddSolution")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), line_task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system
            
            # Real Injection
            # extract experimental information from task_dict
            action_type="single" # 1개의 용액 (not 1개의 pump)
            solution_name=task_dict["Solution"]
            injection_rate=task_dict["Injectionrate"]["Value"]
            injection_rate_dimension=task_dict["Injectionrate"]["Dimension"]
            mode_type=mode_type
            pump_obj=AsiaPump(TaskLogger_obj, 'Asia', solution_name, mode_type=mode_type)
            
            # execute injection
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            inst_msg = "Start Injection Queue --> {},{}{}".format(solution_name, injection_rate, injection_rate_dimension)
            TaskLogger_obj.debug("PUMP", inst_msg)
            TaskLogger_obj.debug("PUMP", "inject solution-->Start!")
            res_msg=pump_obj.addSolution(flowrate=injection_rate)
            TaskLogger_obj.debug("PUMP", "inject solution-->Done!")
            
            # initialize status of device
            self.ResourceManager_obj.updateStatus(current_func_name, False)

        TaskLogger_obj.debug(self.__module_name, "Finish Injection Queue")
            
        return res_msg

    def FlowSynthesis_Heat(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Heat our stirrer depending on task_info_list

        {
            "Task":"Heat",
            "Data":

            // this part is task_info_list //
                [
                    {
                        "Temperature":60,
                    }
                ]
            // this part is task_info_list //
        }

        :param task_info_list (list): queue of stiirer heat work

        return res_msg (str): response message from Windows10 // str == real mode, bool == virtual mode
        """
        res_msg=""
        current_func_name=sys._getframe().f_code.co_name
        for task_idx,task_dict in enumerate(task_info_list):
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "Heat")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system
            # execute task
            TaskLogger_obj.debug(self.__module_name, "Start Heat Queue {} (Stirrer)".format(task_idx))
            # stirrer_addr = self._allocateAddress(location_dict["Stirrer"][task_idx])
            temperature = task_dict["Temperature"]["Value"] # Temperature : Celsius
            Heater_obj=AsiaHeaterCooler(TaskLogger_obj, device_name='Heater', mode_type=mode_type)
            res_msg=Heater_obj.controlHeater(temperature)            
        for task_idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.debug(self.__module_name, "Finish Heat Queue {} (Stirrer)".format(task_idx))

        return res_msg

    def FlowSynthesis_preHeat(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Heat our stirrer depending on task_info_list

        {
            "Task":"Heat",
            "Data":

            // this part is task_info_list //
                [
                    {
                        "Temperature":60,
                    }
                ]
            // this part is task_info_list //
        }

        :param task_info_list (list): queue of stiirer heat work

        return res_msg (str): response message from Windows10 // str == real mode, bool == virtual mode
        """
        res_msg=""
        current_func_name=sys._getframe().f_code.co_name
        for task_idx,task_dict in enumerate(task_info_list):
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "preHeat")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system
            # execute task
            TaskLogger_obj.debug(self.__module_name, "Start preHeat Queue {} (preHeater)".format(task_idx))
            # stirrer_addr = self._allocateAddress(location_dict["preHeater"][task_idx])
            temperature = task_dict["Temperature"]["Value"] # Temperature : Celsius
            preHeater_obj=AsiaHeaterCooler(TaskLogger_obj, device_name='preHeater', mode_type=mode_type)
            res_msg=preHeater_obj.controlHeater(temperature)            
        for task_idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.debug(self.__module_name, "Finish preHeat Queue {} (preHeater)".format(task_idx))
        return res_msg
    

class UVModule(TCP_Class):
    """
    [UVModule] UVModule Class inherited UV-Vis and Pipette class

    # Variable
    :param module_name="UV-Vis" (str): set UV-Vis Characterization module name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _Cuvette2ExtractSolution(cycle_num, vialHolder_loc=0):
    2. GetUVdata(task_info_list):
    """
    def __init__(self,module_name="UV", ResourceManager_obj={}):
        self.__module_name = "{}".format(module_name) 
        self.Spectroscopy_queue = Queue()
        self.the_number_of_Spectroscopy = 1
        self.__initSpectroscopyNum()
        self.ResourceManager_obj=ResourceManager_obj
   

    def __initSpectroscopyNum(self):
        """
        initialize cuvette number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_Spectroscopy):
            self.Spectroscopy_queue.put(num)  

    def __popSpectroscopyNum(self):
        """
        pop the_number_of_Spectroscopy number depending on Queue.

        :return: vial_num (int): get vial number in UV_queue
        """
        empty_true = self.Spectroscopy_queue.empty()
        if empty_true==True:
            self.__initSpectroscopyNum()
        tip_num=self.Spectroscopy_queue.get()

        return tip_num    

    def UV_GetAbs(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        get UV data included _Cuvette2ExtractSolution() func

        :param task_info_list =
        [
            {
                "Setting": {
                    "Spectrometer": {
                        "DeviceName": "USB2000+",
                        "DetectionRange": "200-850nm",
                        "Solvent": {
                                "Solution": "H2O",
                                "Value": 2000,
                                "Dimension": "\u03bcL"
                        }
                    },
                    "LightSource": {
                        "DeviceName": "DH-2000-BAL",
                        "DetectionRange": "210-2500nm",
                        "Lamp": "deuterium(25W) and halogen lamps(20W)"
                    }
                }
            },
            ...
            ...
        ]
        :return: result_list (dict in list) ex) [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        """
        # [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        res_msg=""
        result_list=[]
        current_func_name=sys._getframe().f_code.co_name
        UV_obj = UV(TaskLogger_obj, 'UV', mode_type)
        
        for task_idx, task_dict in enumerate(task_info_list):
            # check & update status of device
            taskStartTime=time.strftime("%Y-%m-%d %H:%M:%S")
            taskFinishTime=time.strftime("%Y-%m-%d %H:%M:%S")
            
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "GetAbs")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system

            # # Get Reference peaks
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            TaskLogger_obj.debug("UV", "UV-VIS Characterization-->Start!")
            # reference_dict=UV_obj.loadRef()
            reference_dict=UV_obj.loadRef()
            
            TaskLogger_obj.debug("UV", "UV-VIS Characterization-->Done!")

            # Get Absorbance peaks
            # self.ResourceManager_obj.updateStatus(current_func_name, True)
            TaskLogger_obj.debug(self.__module_name, "Start UV-VIS Characterization")
            TaskLogger_obj.debug("UV", "UV-VIS Characterization-->Start!")
            absorbance_dict=UV_obj.getAbs()

            current_time = time.strftime("%Y%m%d_%H%M%S")
            filename = f"data_{current_time}.txt"
            file_path = "C:\\Users\\SY\\Desktop\\octopus_old\\octopus_v5\\USER\\NY\\DB\\Measurement\\" + filename
            with open(file_path, "w") as f:
                json_string = json.dumps(absorbance_dict, indent=4)
                f.write(json_string)


            TaskLogger_obj.debug("UV", "UV-VIS Characterization-->Done!")
            self.ResourceManager_obj.updateStatus(current_func_name, False)
            # Caculate peaks
            WavelengthMin=task_dict["Hyperparameter"]["WavelengthMin"]["Value"]
            WavelengthMax=task_dict["Hyperparameter"]["WavelengthMax"]["Value"]
            BoxCarSize=task_dict["Hyperparameter"]["BoxCarSize"]["Value"]
            Prominence=task_dict["Hyperparameter"]["Prominence"]["Value"]
            PeakWidth=task_dict["Hyperparameter"]["PeakWidth"]["Value"]

            UV_result, each_calculate_res_dict=AnalysisUV.calculateUV_Data(absorbance_dict, reference_dict, WavelengthMin, WavelengthMax, BoxCarSize, Prominence, PeakWidth) 
            # UV_result --> OrderedDict([('lambdamax', [391.39295]), ('Intensity', [0.01058083862181636]), ('FWHM', [49.33331611590667])])"""
            TaskLogger_obj.debug(self.__module_name, "{} result : {}".format(task_idx, UV_result))
            # integrated_res_dict={
            #     "Setting":task_dict,
            #     "Data":each_calculate_res_dict
            # }
            
            task_dict["Data"]=each_calculate_res_dict
            result_list.append(task_dict)

            TaskLogger_obj.debug(self.__module_name, "Finish UV-VIS Characterization")

        return result_list

class PLModule(TCP_Class):
    """
    [PLModule] PLModule Class inherited UV-Vis and Pipette class

    # Variable
    :param module_name="UV-Vis" (str): set UV-Vis Characterization module name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _Cuvette2ExtractSolution(cycle_num, vialHolder_loc=0):
    2. GetUVdata(task_info_list):
    """
    def __init__(self,module_name="PL", ResourceManager_obj={}):
        self.__module_name = "{}".format(module_name) 
        self.Spectroscopy_queue = Queue()
        self.the_number_of_Spectroscopy = 1
        self.__initSpectroscopyNum()
        self.ResourceManager_obj=ResourceManager_obj
   

    def __initSpectroscopyNum(self):
        """
        initialize cuvette number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_Spectroscopy):
            self.Spectroscopy_queue.put(num)  

    def __popSpectroscopyNum(self):
        """
        pop the_number_of_Spectroscopy number depending on Queue.

        :return: vial_num (int): get vial number in UV_queue
        """
        empty_true = self.Spectroscopy_queue.empty()
        if empty_true==True:
            self.__initSpectroscopyNum()
        tip_num=self.Spectroscopy_queue.get()

        return tip_num    
    
    def PL_GetPl(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        get PL data included _Cuvette2ExtractSolution() func

        :param task_info_list =
        [
            {
                "Setting": {
                    "Spectrometer": {
                        "DeviceName": "USB2000+",
                        "DetectionRange": "200-850nm",
                        "Solvent": {
                                "Solution": "H2O",
                                "Value": 2000,
                                "Dimension": "\u03bcL"
                        }
                    },
                    "LightSource": {
                        "DeviceName": "DH-2000-BAL",
                        "DetectionRange": "210-2500nm",
                        "Lamp": "deuterium(25W) and halogen lamps(20W)"
                    }
                }
            },
            ...
            ...
        ]
        :return: result_list (dict in list) ex) [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        """
        # [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        res_msg=""
        result_list=[]
        current_func_name=sys._getframe().f_code.co_name
        PL_obj = PL(TaskLogger_obj, 'PL', mode_type)
        
        for task_idx, task_dict in enumerate(task_info_list):
            # check & update status of device
            taskStartTime=time.strftime("%Y-%m-%d %H:%M:%S")
            taskFinishTime=time.strftime("%Y-%m-%d %H:%M:%S")
            
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "GetPl")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system

            # # Get Reference peaks
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            # Get Absorbance peaks
            # self.ResourceManager_obj.updateStatus(current_func_name, True)
            TaskLogger_obj.debug(self.__module_name, "Start UV-VIS Characterization")
            TaskLogger_obj.debug("PL", "UV-VIS Characterization-->Start!")
            absorbance_dict=PL_obj.getPl()
            TaskLogger_obj.debug("PL", "UV-VIS Characterization-->Done!")
            self.ResourceManager_obj.updateStatus(current_func_name, False)
            # Caculate peaks
            WavelengthMin=task_dict["Hyperparameter"]["WavelengthMin"]["Value"]
            WavelengthMax=task_dict["Hyperparameter"]["WavelengthMax"]["Value"]
            BoxCarSize=task_dict["Hyperparameter"]["BoxCarSize"]["Value"]
            Prominence=task_dict["Hyperparameter"]["Prominence"]["Value"]
            PeakWidth=task_dict["Hyperparameter"]["PeakWidth"]["Value"]

            UV_result, each_calculate_res_dict=AnalysisUV.calculatePL_Data(absorbance_dict, WavelengthMin, WavelengthMax, BoxCarSize, Prominence, PeakWidth) 
            # UV_result --> OrderedDict([('lambdamax', [391.39295]), ('Intensity', [0.01058083862181636]), ('FWHM', [49.33331611590667])])"""
            TaskLogger_obj.debug(self.__module_name, "{} result : {}".format(task_idx, UV_result))
            # integrated_res_dict={
            #     "Setting":task_dict,
            #     "Data":each_calculate_res_dict
            # }
            task_dict["Data"]=each_calculate_res_dict
            result_list.append(task_dict)

            TaskLogger_obj.debug(self.__module_name, "Finish UV-VIS Characterization")

        return result_list
    
class CollectorModule(TCP_Class):
    def __init__(self,module_name="Collector", ResourceManager_obj={}, Timer_obj={}):

        self.__module_name= "{}".format(module_name)
        self.vial_queue = Queue()
        self.the_number_of_vial = 80

        # self.tip_1000_queue = Queue()
        # self.tip_100_queue = Queue()
        # self.the_number_of_tip_1000 = 96
        # self.the_number_of_tip_100 = 96
        # self.__initVial()

        self.ResourceManager_obj=ResourceManager_obj

    def __usedVialNum(self, volume):
        Limpette_100 = False
        Limpette_1000 = False
        
        if volume ==100:
            Limpette_100 = True
        elif volume%100!=0:
            Limpette_1000 = True
            Limpette_100 = True
        else:
            Limpette_1000 = True
        
        return Limpette_100, Limpette_1000
    # def __initVial(self):
    #     """
    #     initialize vial number depending on Queue.

    #     :return: None: 
    #     """
    #     for num in range(self.the_number_of_vial):
    #         self.vial_queue.put(num)  
    

    # def __popVial(self):
    #     """
    #     pop vial number depending on Queue.

    #     :return: vial_num (int): get vial number in vial_bottom_queue
    #     """
    #     empty_true = self.vial_queue.empty()
    #     if empty_true==True:
    #         self.__initVial()
    #     Vial_num=self.vial_queue.get()
    #     return Vial_num
    
    # def __alertVial(self):
    #     alert_text = "[{}] vial number({}) is no enough, plese fill vial".format(self.__module_name, self.vial_queue.qsize())
    #     if self.vial_queue.qsize() <=10:
    #         print(alert_text)
    
    def __makecollectorList(self, volume, time):
        num_of_vial = volume//1500
        left_volume = volume%1500
        if num_of_vial == 0:
            left_time = time
        else: 
            each_time = time//num_of_vial
            left_time = time%num_of_vial
        
        volumeList = []
        timeList = []
        
        for _ in range(num_of_vial):
            volumeList.append(1500)
            timeList.append(each_time)
        if left_volume != 0:
            volumeList.append(left_volume)
            timeList.append(left_time)
            
        return volumeList, timeList
        
    def Collector_Collect(self, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        res_msg=""
        result_list=[]
        current_func_name=sys._getframe().f_code.co_name
        Collector_obj = AsiaCollector(TaskLogger_obj, 'Asia', mode_type)
        
        for task_idx, task_dict in enumerate(task_info_list):
            # check & update status of device
            taskStartTime=time.strftime("%Y-%m-%d %H:%M:%S")
            taskFinishTime=time.strftime("%Y-%m-%d %H:%M:%S")
            
            # update status of device every batch
            TaskLogger_obj.current_module_name="{}-->{}".format(self.__module_name, "Collect")
            TaskLogger_obj.status="{}_{}/{}:{}".format(len(task_info_list), task_idx, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system
            # execute task
            TaskLogger_obj.debug(self.__module_name, "Start Collect Queue {} (Collector)".format(task_idx))
            total_volume_list, total_time_list = self.__makecollectorList(volume = task_dict["Volume"]["Value"], time=task_dict["Time"]["Value"])

            for idx in range(len(total_volume_list)):
                vial_idx = popVialNum()
                res_msg = Collector_obj.collect(vial_num=vial_idx, volume=total_volume_list[idx], collecting_time=total_time_list[idx]) ## 여기
        for task_idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.debug(self.__module_name, "Finish preHeat Queue {} (preHeater)".format(task_idx))
        return res_msg


class TaskScheduler(FlowSynthesisModule, UVModule, PLModule, CollectorModule):
    """
    TaskScheduler class read recipe file (json), and allocate & link each task to proper devices
    
    :param schedule_mode (str): "FCFS" or "Backfill" or "ClosedPacking" 
    
    # function
    def _get_data_by_module(self,module_key, module_dict)
    def _task2Device (action_type, task_info_list)
    def _scheduleAllTask(self, total_recipe_template_list:list, jobID:int, TaskLogger_obj:object, mode_type:str)
    def scheduleAlltask (total_recipe_template_list)
    """
    def __init__(self, serverLogger_obj:object, ResourceManager_obj:object, schedule_mode:str):
        self.serverLogger_obj=serverLogger_obj
        self.ResourceManager_obj=ResourceManager_obj

        self.__module_name="TaskScheduler"
        self.schedule_mode=schedule_mode

        FlowSynthesisModule.__init__(self, "BatchSynthesis", ResourceManager_obj=self.ResourceManager_obj)
        UVModule.__init__(self, "UV", ResourceManager_obj=self.ResourceManager_obj)
        PLModule.__init__(self, "PL", ResourceManager_obj=self.ResourceManager_obj)
        CollectorModule.__init__(self, "BatchSynthesis", ResourceManager_obj=self.ResourceManager_obj)
        # MobilePlatform.__init__(self, "Mobile Robot Platform") # change later

        # print("self.task_device_status_dict",id(self.task_device_status_dict))
        # print("self.ResourceManager_obj.task_device_status_dict",id(self.ResourceManager_obj.task_device_status_dict))
    
    def _get_data_by_module(self, module_idx, module_type, total_task_list):
        """
        self._get_data_by_module --> modify
        """
        temp_list=[]
        for task_list in total_task_list:
            if task_list[module_idx]["Module"] == module_type:
                temp_list.append(task_list[module_idx]["Data"])
        return temp_list
            
    def _integrate_to_task(self, module_dict):
        """
        self._get_data_by_module --> modify
        """
        temp_list=[]
        for module_list in module_dict.values():
            temp_list.extend(module_list)
        return temp_list

    def _task2Device(self, task_type:str, task_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type:str):
        """
        allocate task to each device depending on task_info_list
        ***Caution : initialize syringe pump before we start*** 
        
        :param task_type (str): ex) "AddSolution", "Heat"...
        :param task_info_list (dicts in list): 

        :return: list(empty) or list(in characterization cases)
        """
        return_value = getattr(self, task_type)(task_info_list, jobID, location_dict, TaskLogger_obj, mode_type)
        if type(return_value) == str: # if task_type don't return some chemical data (AddSolution, Stir...)
            return return_value
        elif type(return_value) == list: # if task_type return some chemical data (measurement, calcination, UV...),
            return_result_list=[]
            for result_dict in return_value:
                temp_dict = {task_type:result_dict}
                return_result_list.append(temp_dict)
            return return_result_list
        
    def _shutdown(self,TaskLogger_obj,mode_type):
        heat_shutdown_obj = Heater_total(TaskLogger_obj, mode_type=mode_type)
        heat_shutdown_obj.shutdown()
        pump_shutdown_obj = Pump_total(TaskLogger_obj, mode_type=mode_type)
        pump_shutdown_obj.shutdown()
        print("Device system was terminated")
    def _scheduleAllTask(self, total_recipe_template_list:list, jobID:int, TaskLogger_obj:object, mode_type:str):
        total_result_lists_in_list=[]
        
        module_seq_list = [] # need this var to implement in location_dict
        for key, values in total_recipe_template_list[0].items(): 
            # key -> Synthesis, Preprocess, Evaluation, Characterization
            # values -> {"Module":[...]},{"Module":[...]},...
            for value in values:
                if "Module" in value:
                    module_seq_list.append(value["Module"])
        TaskLogger_obj.info(self.__module_name, "check location: {}".format(self.ResourceManager_obj.task_device_location_dict))
        # integrate and make matrix of recipe
        injection_rate_list=[]
        total_task_name_list = []
        for module_idx, module_type in enumerate(module_seq_list):
            total_task_list=[]
            for each_recipe in total_recipe_template_list:
                each_task_list=self._integrate_to_task(each_recipe)
                total_task_list.append(each_task_list)
            
            # module_type : Batch, Flow, Washing, Ink, UV, RDE, Electrode // if not --> pass!
            batch_num = len(total_recipe_template_list) # 배치가 8개면 8개
            # if module_idx+1 != len(module_seq_list):
                # location_dict=getattr(self.ResourceManager_obj, self.schedule_mode)(module_type, module_seq_list[module_idx+1], jobID, total_recipe_template_list)
            allocated_location_dict=self.ResourceManager_obj.allocateLocation(module_idx, module_type, jobID, total_recipe_template_list)
            TaskLogger_obj.info(self.__module_name, "{} is started, allocate location: {}".format(module_type, allocated_location_dict))
            TaskLogger_obj.info(self.__module_name, "check location after allocation: {}".format(self.ResourceManager_obj.task_device_location_dict))
            
            """
            self._get_data_by_module --> modify
            """
            # print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            # print("module_seq_list", module_seq_list)
            # print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            execute_task_list=[]
            execute_task_list=self._get_data_by_module(module_idx, module_type, total_task_list)
            # print("execute_task_list", execute_task_list)

            # extract task depending on sequence --> allocate task to device
            total_task_name_list.append([execute_task_list[0][task_idx]["Task"]for task_idx in range(len(execute_task_list[0])) ])
            flattened_task_name_list = [task for sublist in total_task_name_list for task in sublist]
            batch_task_seq_num = len(execute_task_list[0]) # the number of task sequence
            for each_batch_task_seq_idx in range(batch_task_seq_num): # each batch task 시퀀스 대로 for문 돌려서 batch 합성 진행
                task_type=""
                task_dict_list=[]# each task을 choose
                for each_batch_num in range(batch_num): # each vial 합성 시작
                    # print(execute_task_list[each_batch_num][each_batch_task_seq_idx]["Task"])
                    if execute_task_list[each_batch_num][each_batch_task_seq_idx]["Task"] == "FlowSynthesis_AddSolution": # 시간 계산 용
                        injection_rate_list.append(execute_task_list[each_batch_num][each_batch_task_seq_idx]["Data"]["Injectionrate"]["Value"])
                    if  execute_task_list[each_batch_num][each_batch_task_seq_idx]["Task"] == "UV_GetAbs":
                        timer_obj = Timer(injection_rate_list)
                        print(self.__module_name,"Reaction is started, Wait for Detection: {}s".format(timer_obj.uv_time_sec))
                        if mode_type == "real":
                            timer_obj.waiting()
                        print('[UV] get UV spectrum')
                    if  execute_task_list[each_batch_num][each_batch_task_seq_idx]["Task"] == "PL_GetPl":
                        timer_obj = Timer(injection_rate_list)
                        if mode_type == "virtual":
                            if "UV_GetAbs" in flattened_task_name_list:
                                print(self.__module_name,"Reaction is started, Wait for Detection: {}s".format(timer_obj.pl_time_sec))
                            else:
                                print(self.__module_name,"Reaction is started, Wait for Detection: {}s".format(timer_obj.uv_time_sec))
                        if mode_type == "real":
                            if "UV_GetAbs" in flattened_task_name_list:
                                print(self.__module_name,"Reaction is started, Wait for Detection: {}s".format(timer_obj.pl_time_sec))
                                timer_obj.plwaiting()
                            else:
                                print(self.__module_name,"Reaction is started, Wait for Detection: {}s".format(timer_obj.uv_time_sec))
                                timer_obj.waiting()
                        print('[PL] get PL spectrum')
                    task_type=execute_task_list[each_batch_num][each_batch_task_seq_idx]["Task"]
                    task_dict_list.append(execute_task_list[each_batch_num][each_batch_task_seq_idx]["Data"])

                each_result_list=self._task2Device(task_type, task_dict_list, jobID, allocated_location_dict, TaskLogger_obj, mode_type)
                if type(each_result_list) == str: # return str excluding characterization & evaluation
                    pass
                elif type(each_result_list) == list: # return dict in list including characterization & evaluation
                    if len(each_result_list) > 0:
                        total_result_lists_in_list.append(each_result_list)
                    else: # nothing return
                        raise ValueError("There is no value in scheduler. Please check our node server.")
            TaskLogger_obj.info(self.__module_name, "{} is finished, location: {}".format(module_type, self.ResourceManager_obj.task_device_location_dict))
        self._shutdown(TaskLogger_obj,mode_type)
        
        for module_type in module_seq_list:
            self.ResourceManager_obj.refreshModuleLocation(module_type, jobID)
            TaskLogger_obj.info(self.__module_name, "{} is finished, location: {}".format(module_type, self.ResourceManager_obj.task_device_location_dict))
        return total_result_lists_in_list

    def scheduleAllTask(self, total_recipe_template_list:list, jobID:int, TaskLogger_obj:object, mode_type:str):
        """
        schdule all task using _task2Device func (큰 task들의 칸 수는 정해져있다고 가정... 나중에 병렬처리 가능할 때 새로운 scheduling 하는 function 만들기)

        :param total_recipe_template_list (list): total json in list // ex) if our batch size=8, it will be composed of [{},{},{},{},{},{},{},{}] each recipe

        --> total_result_lists_in_list (list (in dicts) of list)
        ex) [
                [{"GetAbs":{}},{"GetAbs":{}}, ...],
                [{"GetOverpotential":{}},{"GetOverpotential":{}} ...],...
            ]
        """
        total_result_lists_in_list=[] # 여기에 분석 결과를 저장

        count_experiments_num=0
        total_experiments_num=len(total_recipe_template_list) # total numbers of experiments
        copied_total_recipe_template_list=list(copy.deepcopy(total_recipe_template_list)) # popped version
        """
        closed-packing scheduling
        """
        while True:
            if count_experiments_num==total_experiments_num:
                break
            # calculate possibile numbers of tasks based on present task_device_location_dict
            throughput_num=self.ResourceManager_obj.notifyNumbersOfTasks(copied_total_recipe_template_list)
            if throughput_num==0:
                continue
            else:
                # set current experiment num
                TaskLogger_obj.currentExperimentNum=TaskLogger_obj.currentExperimentNum+throughput_num
                TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentExperimentNum, TaskLogger_obj.totalExperimentNum, TaskLogger_obj.current_module_name) # in execution system
                # pop possibile numbers of tasks based on present task_device_location_dict
                execute_recipe_list=[]
                for i in range(throughput_num):
                    popped_recipe=copied_total_recipe_template_list.pop(0)
                    execute_recipe_list.append(popped_recipe)
                return_result_lists_in_list=self._scheduleAllTask(execute_recipe_list, jobID, TaskLogger_obj, mode_type)
                if count_experiments_num!=0:
                    for module_idx, module_result_list in enumerate(return_result_lists_in_list):
                        total_result_lists_in_list[module_idx].extend(module_result_list)
                else:
                    total_result_lists_in_list=return_result_lists_in_list
                count_experiments_num+=throughput_num
        
                # # refresh location information of self.task_device_location_dict (0 or 1 or 2 ... (jobID) --> ?)            
                # self.ResourceManager_obj.refreshTotalLocation(jobID)
                # TaskLogger_obj.info(self.__module_name, "refresh location: {}".format(self.ResourceManager_obj.task_device_location_dict))

        # separate result data
        """
        ex) [
                [{"GetUVdata":{}},{"GetUVdata":{}}, ...],
                [{"GetElectrochemicaldata":{}},{"GetElectrochemicaldata":{}} ...],
                ...
            ]
        -->
            [
                [{"GetUVdata":{}},{"GetElectrochemicaldata":{}}, ...],
                [{"GetUVdata":{}},{"GetElectrochemicaldata":{}}, ...],
                ...
            ]
        """
        result_num=len(total_result_lists_in_list)
        batch_size=len(total_recipe_template_list)

        return_result_list_to_algorithm=[]
        for batch_idx in range(batch_size): # batch_size
            temp_dict={}
            for result_idx in range(result_num): # 분석 갯수
                temp_dict.update(total_result_lists_in_list[result_idx][batch_idx])
            return_result_list_to_algorithm.append(temp_dict)

        return return_result_list_to_algorithm


if __name__ == "__main__":
    from Resource.ResourceManager_Class import ResourceManager
    from Log.Logging_Class import TaskLogger
    metadata_dict={
        "subject":"Take_scneario",
        "group":"KIST_CSRC",
        "logLevel":"DEBUG",
        "modeType":"virtual",
        "todayIterNum":1,
        "userName":"NY",
        "jobID":0,
        "jobFileName":"USER/NY/job_script/20230516_autonomous_test.json",
        "batchSize":1
    }
    module_list=["AMR"]
    TaskLogger_obj=TaskLogger(metadata_dict,userName="NY")
    TaskLogger_obj.current_platform_name="AMR"
    ResourceManager_obj=ResourceManager(module_list)
    TaskScheduler_obj=TaskScheduler(TaskLogger_obj, ResourceManager_obj, schedule_mode="FCFS")
    recipe_list=[
   {'Synthesis': [{'Module': 'FlowSynthesis', 'Data': [{'Task': 'FlowSynthesis_AddSolution', 'Data': {'Solution': 'InP', 'Injectionrate': {'Value': 100, 'Dimension': 'μL/s'}, 'Device': {'solutionType': 'Metal', 'pumpPort': 'ns=5;i=7003', 'pumpClose': 'ns=5;i=7004', 'pumpFlush': 'ns=5;i=7002', 'pumpAddress': 'ns=1;i=54447', 'deviceName': 'Asia'}}}, {'Task': 'FlowSynthesis_AddSolution', 'Data': {'Solution': 'A', 'Injectionrate': {'Value': 100, 'Dimension': 'μL/s'}, 'Device': {'solutionType': 'Reductant', 'pumpPort': 'ns=5;i=7003', 'pumpClose': 'ns=5;i=7004', 'pumpFlush': 'ns=5;i=7002', 'pumpAddress': 'ns=1;i=54457', 'deviceName': 'Asia'}}}, {'Task': 'FlowSynthesis_preHeat', 'Data': {'Temperature': {'Value': 30, 'Dimension': 'ºC'}, 'Device': {'heaterAddress': 'ns=1;i=54428', 'temperatureAddress': 'ns=1;i=54425', 'checkerAddress': 'ns=1;i=54427', 'deviceName': 'Asia'}}}, {'Task': 'FlowSynthesis_Heat', 'Data': {'Temperature': {'Value': 150, 'Dimension': 'ºC'}, 'Device': {'heaterAddress': 'ns=1;i=54440', 'temperatureAddress': 'ns=1;i=54437', 'checkerAddress': 'ns=1;i=54439', 'deviceName': 'Asia'}}}]}], 'Characterization': [{'Module': 'UV', 'Data': [{'Task': 'UV_GetAbs', 'Data': {'Device': {'Spectrometer': {'DeviceName': 'USB2000+', 'DetectionRange': '200-850nm', 'Solvent': {'Solution': 'H2O', 'Value': 1, 'Dimension': 'μL'}}, 'LightSource': {'DeviceName': 'DH-2000-BAL', 'DetectionRange': '210-2500nm', 'Lamp': 'deuterium(25W) and halogen lamps(20W)'}}, 'Hyperparameter': {'WavelengthMin': {'Description': 'WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max', 'Value': 300, 'Dimension': 'nm'}, 'WavelengthMax': {'Description': 'WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max', 'Value': 849, 'Dimension': 'nm'}, 'BoxCarSize': {'Description': 'BoxCarSize=10 (int): smooth strength', 'Value': 10, 'Dimension': 'None'}, 'Prominence': {'Description': 'Prominence=0.01 (float): minimum peak Intensity for detection', 'Value': 0.01, 'Dimension': 'None'}, 'PeakWidth': {'Description': 'PeakWidth=20 (int): minumum peak width for detection', 'Value': 20, 'Dimension': 'nm'}}}}]}, {'Module': 'PL', 'Data': [{'Task': 'PL_GetPl', 'Data': {'Device': {'Spectrometer': {'DeviceName': 'SR4', 'DetectionRange': '200-850nm', 'Solvent': {'Solution': 'H2O', 'Value': 1, 'Dimension': 'μL'}}, 'LightSource': {'DeviceName': 'DH-2000-BAL', 'DetectionRange': '210-2500nm', 'Lamp': 'deuterium(25W) and halogen lamps(20W)'}}, 'Hyperparameter': {'WavelengthMin': {'Description': 'WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max', 'Value': 300, 'Dimension': 'nm'}, 'WavelengthMax': {'Description': 'WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max', 'Value': 849, 'Dimension': 'nm'}, 'BoxCarSize': {'Description': 'BoxCarSize=10 (int): smooth strength', 'Value': 10, 'Dimension': 'None'}, 'Prominence': {'Description': 'Prominence=0.01 (float): minimum peak Intensity for detection', 'Value': 0.01, 'Dimension': 'None'}, 'PeakWidth': {'Description': 'PeakWidth=20 (int): minumum peak width for detection', 'Value': 20, 'Dimension': 'nm'}}}}]}], 'Collection': [{'Module': 'Collector', 'Data': [{'Task': 'Collector_Collect', 'Data': {'Volume': {'Value': 1000, 'Dimension': 'μL/s'}, 'Time': {'Value': 420, 'Dimension': 's'}, 'Device': {'Asia': {'collectorPort': 'ns=1;i=58192', 'collectorMode': 'ns=1;i=54415', 'collectorPositionset': 'ns=5;i=7026', 'collectorPositionread': 'ns=1;i=54416', 'deviceName': 'Asia', 'x_start': 10, 'y_start': 10, 'x_increment': 13, 'y_increment': 13, 'columns': 18, 'total_vials': 80}}}}]}]}]
    #     {
    #         "Synthesis": [
    #             # {
    #             #     "Module": "AMR",
    #             #     "Data": [
    #             #         {
    #             #             "Task": "AMR_MoveContainer",
    #             #             "Data": {
    #             #                 "From": "Storage",
    #             #                 "To": "BatchSynthesis",
    #             #                 "Container": "vial",
    #             #                 "Device": {
    #             #                     "Id": "dsr01",
    #             #                     "Model": "m0609",
    #             #                     "NETWORK": "192.168.137.100",
    #             #                     "WorkRange": 900
    #             #                 }
    #             #             }
    #             #         }
    #             #     ]
    #             # },
    #             # {
    #             #     "Module": "AMR",
    #             #     "Data": [
    #             #         {
    #             #             "Task": "AMR_MoveContainer",
    #             #             "Data": {
    #             #                 "From": "RDE",
    #             #                 "To": "Storage",
    #             #                 "Container": "falcon",
    #             #                 "Device": {
    #             #                     "Id": "dsr01",
    #             #                     "Model": "m0609",
    #             #                     "NETWORK": "192.168.137.100",
    #             #                     "WorkRange": 900
    #             #                 }
    #             #             }
    #             #         }
    #             #     ]
    #             # }
    #             {
    #             "Module": "FlowSynthesis",
    #             "Data":[{'Task': 'FlowSynthesis_AddSolution', 
    #                      'Data': {'Solution': 'InP', 
    #                               'Injectionrate': {'Value': 100, 
    #                                                 'Dimension': 'μL/s'}, 
    #                               'Device': {'solutionType': 'Metal', 
    #                                          'pumpPort': 'ns=5;i=7003', 
    #                                          'pumpClose': 'ns=5;i=7004', 
    #                                          'pumpFlush': 'ns=5;i=7002', 
    #                                          'pumpAddress': 'ns=1;i=54435', 
    #                                          'deviceName': 'Asia'
    #                                          }
    #                               }
    #                      }, 
    #                     {'Task': 'FlowSynthesis_AddSolution', 
    #                      'Data': {'Solution': 'A', 
    #                               'Injectionrate': 
    #                                   {'Value': 100, 
    #                                    'Dimension': 'μL/s'}, 
    #                                'Device': {'solutionType': 'Reductant', 
    #                                           'pumpPort': 'ns=5;i=7003', 
    #                                           'pumpClose': 'ns=5;i=7004', 
    #                                           'pumpFlush': 'ns=5;i=7002', 
    #                                           'pumpAddress': 'ns=1;i=54445', 
    #                                           'deviceName': 'Asia'}
    #                                }
    #                      }, 
    #                     {'Task': 'FlowSynthesis_preHeat', 
    #                      'Data': {'Temperature': {'Value': 30, 
    #                                               'Dimension': 'ºC'}, 
    #                      'Device': {'devicePort': 'ns=5;i=7003', 
    #                                 'heaterAddress': 'ns=1;i=54415', 
    #                                 'deviceName': 'Asia'
    #                                 }
    #                         }
    #                     }, 
    #                     {'Task': 'FlowSynthesis_Heat', 
    #                      'Data': {'Temperature': {'Value': 150, 
    #                                               'Dimension': 'ºC'}, 
    #                      'Device': {'devicePort': 'ns=5;i=7003',
    #                                 'heaterAddress': 'ns=1;i=54427',
    #                                 'deviceName': 'Asia'
    #                                 }
    #                         }
    #                     }
    #                     ]
    #             }
    #         ],
    #         'Characterization': 
    #         [{
    #             'Module': 'UV', 
    #             'Data': [{'Task': 'UV_GetAbs', 
    #                     'Data': {
    #                     'Device': {
    #                         'UV': {'Spectrometer': {'DeviceName': 'USB2000+',
    #                                                 'DetectionRange': '200-850nm',
    #                                                 'Solvent': {'Solution': 'H2O', 
    #                                                             'Value': 2000, 
    #                                                             'Dimension': 'μL'}},
    #                                'LightSource': {'DeviceName': 'DH-2000-BAL',
    #                                                'DetectionRange': '210-2500nm',
    #                                                'Lamp': 'deuterium(25W) and halogen lamps(20W)'}
    #                                }
    #                         }, 
    #                     'Hyperparameter': {'WavelengthMin': {
    #                                             'Description': 'WavelengthMin=300 (int): slice wavlength section depending on wavelength_min and wavelength_max', 
    #                                             'Value': 300, 'Dimension': 'nm'}, 
    #                                         'WavelengthMax': {
    #                                             'Description': 'WavelengthMax=849 (int): slice wavlength section depending on wavelength_min and wavelength_max', 
    #                                             'Value': 849, 'Dimension': 'nm'}, 
    #                                         'BoxCarSize': {
    #                                             'Description': 'BoxCarSize=10 (int): smooth strength', 
    #                                             'Value': 10, 'Dimension': 'None'}, 
    #                                         'Prominence': {
    #                                             'Description': 'Prominence=0.01 (float): minimum peak Intensity for detection', 
    #                                             'Value': 0.01, 'Dimension': 'None'}, 
    #                                         'PeakWidth': {'Description': 'PeakWidth=20 (int): minumum peak width for detection', 
    #                                                       'Value': 20, 'Dimension': 'nm'}}}}]}]
    #         'Collection': [{'Module': 'Collector', 
    #                         'Data': [{'Task': 'Collect', 
    #                                 'Data': {'Volume': {'Value': 1000, 
    #                                                     'Dimension': 'μL/s'
    #                                                     }, 
    #                                         'Device': {'Asia': {'collectorPort': 'ns=1;i=58192',
    #                                                             'collectorMode': 'ns=1;i=54415',
    #                                                             'collectorPositionset': 'ns=5;i=7026',
    #                                                             'collectorPositionread': 'ns=1;i=54416',
    #                                                             'deviceName': 'Asia'}
    #                                                     }
    #                                         }
    #                                 }]
    #                         }]
    #         },
    # ]
    TaskScheduler_obj.scheduleAllTask(recipe_list, 0, TaskLogger_obj, mode_type="virtual")
