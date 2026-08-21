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
import socket
import numpy as np
import threading
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Master.Task.TCP import TCP_Class
from Analysis import AnalysisUV
from Log.All_Integrated_Messenger import AlertMessage


class RobotMovPlatform(TCP_Class):
    """
    [RobotMovPlatform] RobotMovPlatform inherited doosan robot library

    # Variable
    :param platform_name="Robot Platform" (str): set robot platform name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. __initVialNum(self):
    2. _popVialNum(self):
    3. MoveContainer(self, action_info_list):
    """
    def __init__(self, platform_name="Robot", total_hardware_status_dict={}):

        self.robot_platform_name = "{}".format(platform_name) 
        TCP_Class.__init__(self,)
        self.robot_queue = Queue()
        self.the_number_of_vial = 80
        self.__initVialNum()
        self.total_hardware_status_dict=total_hardware_status_dict

    def __initVialNum(self):
        """
        initialize vial number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_vial):
            self.robot_queue.put(num)  

    def __popVialNum(self):
        """
        pop vial number depending on Queue.

        :return: vial_num (int): get vial number in robot_queue
        """
        # print("previous : ",self.robot_queue.qsize())
        empty_true = self.robot_queue.empty()
        # print("empty_true : ",empty_true)
        if empty_true==True:
            self.__initVialNum()
        vial_num=self.robot_queue.get()
        # print("later : ",self.robot_queue.qsize())

        return vial_num

    def __alertVialNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.robot_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] vial number is not enough, please fill vial".format(self.robot_platform_name), 
            key_path="./Log", message_platform_list=["line"], mode_type=mode_type)
        else:
            pass
    
    def __countVialNum_LineNum(self, vial_num):
        """
        counts on vial_num and line_num depending on the number of TaskLogger_obj.

        :return: None 
        """
        # count the number of vials in robot_queue
        vial_num_list=[]
        line_num_list=[]
        for _ in range(vial_num): # for each vial
            vial_num=self.__popVialNum()
            vial_num_list.append(vial_num)
            line_num_list.append(vial_num//16) # same with previous "cycle_num"

        return vial_num_list, line_num_list

    def __changeStatus(self, hardware_name_list:list, status:bool):
        for hardware_name in hardware_name_list:
            self.total_hardware_status_dict[hardware_name]=status # UV_RoboticArm is okay. (not disturb in AddSolution action)

    def MoveContainer(self, action_info_list, jobID, location_dict, TaskLogger_obj, mode_type="virtual"):
        """
        allocate MoveContainer depending on action_info_list.

        :param action_info_list (list): "Action":"MoveContainer","Data":[] <- action_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        action_info_list = [
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                }
            ]
        """
        res_msg=""
        vial_num_list=[]
        line_num_list=[]
        
        # DON'T MIX EACH EXPERIMENT VIALS
        while True:
            if self.total_hardware_status_dict["Batch_RoboticArm"]==False and self.total_hardware_status_dict["Batch_LinearAcutator"]==False and self.total_hardware_status_dict["Batch_VialStorage"]==False and self.total_hardware_status_dict["UV_RoboticArm"]==False :
                break
        
        self.total_hardware_status_dict["Batch_RoboticArm"]==True # Already use !
        self.total_hardware_status_dict["Batch_VialStorage"]==True # Already use !
        self.total_hardware_status_dict["UV_RoboticArm"]==True # Already use !
        self.total_hardware_status_dict["Batch_LinearAcutator"]==True # Don't move!
        
        for action_idx, move_dict in enumerate(action_info_list): # for each vial
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.robot_platform_name, "MoveContainer"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            move_type="{}_to_{}".format(move_dict["From"], move_dict["To"])
            msg = "Batch motion ({}) is started.".format(move_type)
            TaskLogger_obj.info(self.robot_platform_name, "Start Robot Queue : "+msg)

            msg = "{} is started.".format(move_type)   
            TaskLogger_obj.debug(self.robot_platform_name, debug_msg=msg)

            # separate robot action
            # if move_type == "storage_empty_to_stirrer":
            #     command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",self.line_num_list[action_idx],mode_type))
            #     res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            #     time.sleep(2)
            #     command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type,self.line_num_list[action_idx],location_dict["Stirrer"][action_idx],mode_type))
            #     res_msg = self.callServer_DS_B(command_byte=command_bytes)
            
            # elif move_type == "stirrer_to_holder":
            #     command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type, location_dict["Stirrer"][action_idx], location_dict["vialHolder"][action_idx],mode_type))
            #     res_msg=self.callServer_DS_B(command_byte=command_bytes)
            
            if move_type == "holder_to_storage_filled":
                if action_idx==0:
                    vial_num_list, line_num_list= self.__countVialNum_LineNum(len(action_info_list))
                    TaskLogger_obj.info(self.robot_platform_name, "vial_num_list:{}".format(vial_num_list))
                    TaskLogger_obj.info(self.robot_platform_name, "line_num_list:{}".format(line_num_list))
                    TaskLogger_obj.info(self.robot_platform_name, "vialHolder_list:{}".format(location_dict["vialHolder"]))
                if action_idx == 0: # vial 채우기 전, stepper motor initialize
                    time.sleep(2)
                    command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
                    time.sleep(2)
                
                command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type))
                res_msg=self.callServer_LA(command_byte=command_bytes)

                command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type,location_dict["vialHolder"][action_idx],line_num_list[action_idx],mode_type))
                res_msg=self.callServer_DS_B(command_byte=command_bytes)    
                
                if action_idx+1 == len(action_info_list): # vial 채울 때는 마지막 action이 끝날 때만 vial storage 모터 내리기
                    time.sleep(2)
                    command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            
            # elif move_type == "cuvette_storage_to_cuvette_holder":
            #     command_bytes=str.encode("{}/{}/{},{}/{}".format("DS_B","cuvette_storage_to_cuvette_holder", self.vial_num_list[action_idx],action_idx, mode_type))
            #     res_msg=self.callServer_DS_B(command_byte=command_bytes)
            
            msg = "Batch motion ({}) is done.".format(move_type)   
            TaskLogger_obj.info(self.robot_platform_name, "Finish Robot Queue : "+msg)

        self.total_hardware_status_dict["Batch_RoboticArm"]==False
        self.total_hardware_status_dict["Batch_LinearAcutator"]==False
        self.total_hardware_status_dict["Batch_VialStorage"]==False
        self.total_hardware_status_dict["UV_RoboticArm"]==False

        self.__alertVialNum(TaskLogger_obj)

        return res_msg


class BatchSynthesisPlatform(TCP_Class):
    """
    [BatchSynthesisPlatform] BatchSynthesisPlatform inherited Linear actuator, stirrer, syringe pump class

    # Variable
    :param platform_name="Batch Synthesis Platform" (str): set log name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _initializeDevice():
    2. _AllocateTecanAddress(solution_dict):
    3. _AllocateTecanUSBAddress(tecan_addr):
    4. _allocateAddress(stirrer_name):
    5. AddSolution(action_info_list):
    6. Stir(action_info_list):
    7. Heat(action_info_list):
    8. Wait(action_info_list):
    9. React(action_info_list):
    """
    def __init__(self,platform_name="BatchSynthesis", total_hardware_status_dict={}):
        TCP_Class.__init__(self,)
        self.batch_platform_name= "{}".format(platform_name)
        self.robot_queue = Queue()
        self.the_number_of_vial = 80
        self.__initVialNum()
        self.total_hardware_status_dict=total_hardware_status_dict
    
    def _allocateAddress(self, stirrer_hole_location):
        """
        allocate pump bus usb address depending on soluition_dict

        :param device_name (str): "Stirrer_0-0" or "Stirrer_1-7"...etc (depending on stirrer addreess in IKA RET)

        return int(stirrer_hole_location//8)
        """
        return int(stirrer_hole_location//8)

    def __initVialNum(self):
        """
        initialize vial number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_vial):
            self.robot_queue.put(num)  

    def __popVialNum(self):
        """
        pop vial number depending on Queue.

        :return: vial_num (int): get vial number in robot_queue
        """
        empty_true = self.robot_queue.empty()
        if empty_true==True:
            self.__initVialNum()
        vial_num=self.robot_queue.get()

        return vial_num

    def __alertVialNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.robot_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] vial number is not enough, please fill vial".format(self.robot_platform_name), 
            key_path="./Log", message_platform_list=["dooray"], mode_type=mode_type)
        else:
            pass
    
    def __countVialNum_LineNum(self, vial_num):
        """
        counts on vial_num and line_num depending on the number of TaskLogger_obj.
        :return: None 
        """
        # count the number of vials in robot_queue
        vial_num_list=[]
        line_num_list=[]
        for _ in range(vial_num): # for each vial
            vial_num=self.__popVialNum()
            vial_num_list.append(vial_num)
            line_num_list.append(vial_num//16) # same with previous "cycle_num"
        
        return vial_num_list, line_num_list

    def __changeStatus(self, hardware_name_list:list, status:bool):
        for hardware_name in hardware_name_list:
            self.total_hardware_status_dict[hardware_name]=status # UV_RoboticArm is okay. (not disturb in AddSolution action)

    def PrepareContainer(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        allocate MoveContainer depending on action_info_list.

        :param action_info_list (list): "Action":"MoveContainer","Data":[] <- action_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        action_info_list = [
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                },
                {
                    "Container":"Vial",
                    "Type":"storage_empty_to_stirrer"
                }
            ]
        """
        res_msg=""
        vial_num_list=[]
        line_num_list=[]
        
        for action_idx, move_dict in enumerate(action_info_list): # for each vial
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "PrepareContainer"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            move_type="{}_to_{}".format(move_dict["From"], move_dict["To"])
            msg = "Batch motion ({}) is started.".format(move_type)
            TaskLogger_obj.info(self.batch_platform_name, "Start Robot Queue : "+msg)

            msg = "{} is started.".format(move_type)   
            TaskLogger_obj.debug(self.batch_platform_name, debug_msg=msg)

            while True:
                if self.total_hardware_status_dict["Batch_RoboticArm"]==False and self.total_hardware_status_dict["Batch_LinearAcutator"]==False and self.total_hardware_status_dict["Batch_VialStorage"]==False and self.total_hardware_status_dict["UV_RoboticArm"]==False :
                    break

            self.total_hardware_status_dict["Batch_RoboticArm"]=True # Already use !
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True # Already use !
            self.total_hardware_status_dict["Batch_VialStorage"]=True # Already use !
            self.total_hardware_status_dict["UV_RoboticArm"]==True # Don't move !
            
            # separate robot action
            if action_idx==0:
                vial_num_list, line_num_list= self.__countVialNum_LineNum(len(action_info_list))
                TaskLogger_obj.info(self.batch_platform_name, "vial_num_list: {}".format(vial_num_list))
                TaskLogger_obj.info(self.batch_platform_name, "line_num_list: {}".format(line_num_list))
                TaskLogger_obj.info(self.batch_platform_name, "vialHolder_list: {}".format(location_dict["vialHolder"]))

            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type)) # initialize LinearActuator
            res_msg=self.callServer_LA(command_byte=command_bytes)
            
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx],mode_type))
            res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            time.sleep(2)
            command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type,line_num_list[action_idx],location_dict["Stirrer"][action_idx],mode_type))
            res_msg = self.callServer_DS_B(command_byte=command_bytes)
            
            msg = "Batch motion ({}) is done.".format(move_type)   
            TaskLogger_obj.info(self.batch_platform_name, "Finish Robot Queue : "+msg)

            self.total_hardware_status_dict["Batch_RoboticArm"]=False
            self.total_hardware_status_dict["Batch_LinearAcutator"]=False
            self.total_hardware_status_dict["Batch_VialStorage"]=False
            self.total_hardware_status_dict["UV_RoboticArm"]==False

        self.__alertVialNum(TaskLogger_obj)

        return res_msg

    def AddSolution(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Add solution depending on action_info_list. This list included 1 cycle batch synthesis process.

        :param action_info_list (list): "Action":"AddSolution","Data":[] <- action_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        :(inside) pump_dict : { "To":"Stirrer_1","Data":[] }
        :(inside) pump_dict["Data"] : 
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
            ]
        """
        res_msg=""
        for vial_action_idx, pump_dict in enumerate(action_info_list): # for each vial
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "AddSolution"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, vial_action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # check status of hardware
            while True: # if robotic arm or Linear actuator or pump status is on? --> wait
                if self.total_hardware_status_dict["Batch_RoboticArm"]==False and self.total_hardware_status_dict["Batch_LinearAcutator"]==False and self.total_hardware_status_dict["Batch_Pump"]==False:
                    break
            
            self.total_hardware_status_dict["Batch_RoboticArm"]=True # UV_RoboticArm is okay. (not disturb in AddSolution action)
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["Batch_Pump"]=True

            total_solution_queue = [pump_dict]
            process_number = len(total_solution_queue)
            # Preparing
            """
            total_solution_queue :  [
                {'Solution': 'H2O2', 
                'Volume': {'Value': 1200, 'Dimension': 'μL'}, 
                'Concentration': {'Value': 0.375, 'Dimension': 'mM'}, 
                'Injectionrate': {'Value': 200, 'Dimension': 'μL/s'}, 
                'Setting': {'SolutionType': 'Oxidant', 'PumpAddress': 3, 'PumpUsbAddr': '/dev/ttyUSB0', 'Resolution': 1814000, 
                'Concentration': 0.75, 'Density': 1.45, 'MolarMass': 34.0147, 'SyringeVolume': 5000, 'DeviceName': 'CavroCentris'}}]
            """
            # execute action
            for _,solution_dict in enumerate(total_solution_queue) : # matching 1 vial --> 1 action
                action_type="single" # 1개의 용액 (not 1개의 pump)
                solution_name=solution_dict["Solution"]
                concentration=solution_dict["Concentration"]["Value"]
                flush_volume = 5000 # modify later
                flush_inecjtion_rate= 200
                mode_type=mode_type
                TaskLogger_obj.info(self.batch_platform_name, "Prepare Injection Queue --> {},{}mM,{}uL,{}uL/s".format(solution_name, concentration, flush_volume, flush_inecjtion_rate))
                command_bytes=str.encode("{}/{}/{}/{},{},{},{}/{}".format(jobID,"PUMP",action_type,solution_name,flush_volume,concentration,flush_inecjtion_rate,mode_type))
                res_msg=self.callServer_PUMP(command_byte=command_bytes)
            
            self.total_hardware_status_dict["Batch_RoboticArm"]=True # UV_RoboticArm is okay. (not disturb in AddSolution action)
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["Batch_Pump"]=True
            
            # Real Injection
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","down",location_dict["Stirrer"][vial_action_idx],mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)
            # if process_number==1: # 만약 process number=1, 즉 solution 1개만 토출할 경우
            for _,solution_dict in enumerate(total_solution_queue) : # matching 1 vial --> 1 action
                action_type="single" # 1개의 용액 (not 1개의 pump)
                solution_name=solution_dict["Solution"]
                concentration=solution_dict["Concentration"]["Value"]
                concentration_dimension=solution_dict["Concentration"]["Dimension"]
                volume=solution_dict["Volume"]["Value"]
                volume_dimension=solution_dict["Volume"]["Dimension"]
                injection_rate=solution_dict["Injectionrate"]["Value"]
                injection_rate_dimension=solution_dict["Injectionrate"]["Dimension"]
                mode_type=mode_type
                TaskLogger_obj.info(self.batch_platform_name, "Start Injection Queue --> {},{}{},{}{},{}{}".format(solution_name, concentration, concentration_dimension, volume, volume_dimension, injection_rate, injection_rate_dimension))
                command_bytes=str.encode("{}/{}/{}/{},{},{},{}/{}".format(jobID,"PUMP",action_type,solution_name,volume,concentration,injection_rate,mode_type))
                res_msg=self.callServer_PUMP(command_byte=command_bytes)
            
            self.total_hardware_status_dict["Batch_RoboticArm"]=True # UV_RoboticArm is okay. (not disturb in AddSolution action)
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["Batch_Pump"]=True
            
            # elif process_number>1: # 만약 process number>1, 즉 solution 2개 이상 토출할 경우
            #     action_type="multi" # 여러개의 용액 (not 여러개의 pump)
            #     solution_name_list=[]
            #     volume_list=[]
            #     flow_rate_list=[]
            #     mode_type=mode_type
            #     for action_idx,solution_dict in enumerate(total_solution_queue): # matching 1 vial --> 1 action
            #         solution_name_list.append(solution_dict["Solution"])
            #         volume_list.append(solution_dict["Volume"]["Value"])
            #         flow_rate_list.append(solution_dict["Injectionrate"]["Value"])
            #     solution_name_str=""
            #     for i, solution_name in enumerate(solution_name_list):
            #         solution_name_str+=solution_name
            #         if i+1 == len(solution_name_list):
            #             break
            #         solution_name_str+=","
            #     volume_list_str=str(volume_list)[1:-1]
            #     flow_rate_list_str=str(flow_rate_list)[1:-1]
            #     command_bytes=str.encode("{}/{}/{}/{},{},{}/{}".format(jobID,"PUMP",action_type,solution_name_str,volume_list_str,flow_rate_list_str,mode_type))
            #     res_msg=self.callServer_PUMP(command_byte=command_bytes)

            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","up",location_dict["Stirrer"][vial_action_idx],mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)

            self.total_hardware_status_dict["Batch_RoboticArm"]=True # UV_RoboticArm is okay. (not disturb in AddSolution action)
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["Batch_Pump"]=True
            
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)

            self.total_hardware_status_dict["Batch_RoboticArm"]=True # UV_RoboticArm is okay. (not disturb in AddSolution action)
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["Batch_Pump"]=True
            
            TaskLogger_obj.info(self.batch_platform_name, "Finish Injection Queue")
            # initialize status of hardware
            self.total_hardware_status_dict["Batch_RoboticArm"]=False
            self.total_hardware_status_dict["Batch_LinearAcutator"]=False
            self.total_hardware_status_dict["Batch_Pump"]=False
            
            time.sleep(2)

        return res_msg

    def Stir(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Stir our stirrer depending on stir_queue

        {
            "Action":"Stir",
            "Data":
            // action_dict is here!
            {
                "Data":
                [
                    {
                        "StirRate":400,
                    }
                ]
            }
        }

        :param action_info_list (list): queue of stiirer stir work

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode
        """
        res_msg=""
        for action_idx,action_dict in enumerate(action_info_list):
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Stir"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            TaskLogger_obj.info(self.batch_platform_name, "Start Stir Queue {} (Stirrer)".format(action_idx))
            stirrer_addr = self._allocateAddress(location_dict["Stirrer"][action_idx])
            stir_rate = action_dict["StirRate"]["Value"] # StirRate : rpm
            command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"STIRRER","stir",stirrer_addr,stir_rate,mode_type))
            res_msg = self.callServer_STIRRER(command_byte=command_bytes)
        for action_idx,action_dict in enumerate(action_info_list): # log 따로 작성하려고 일부러 만듬
            TaskLogger_obj.info(self.batch_platform_name, "Finish Stir Queue {} (Stirrer)".format(action_idx))

        return res_msg

    def Heat(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        Heat our stirrer depending on action_info_list

        {
            "Action":"Heat",
            "Data":

            // this part is action_info_list //
                [
                    {
                        "Temperature":60,
                    }
                ]
            // this part is action_info_list //
        }

        :param action_info_list (list): queue of stiirer heat work

        return res_msg (str): response message from Windows10 // str == real mode, bool == virtual mode
        """
        res_msg=""
        for action_idx,action_dict in enumerate(action_info_list):
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Heat"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            TaskLogger_obj.info(self.batch_platform_name, "Start Heat Queue {} (Stirrer)".format(action_idx))
            stirrer_addr = self._allocateAddress(location_dict["Stirrer"][action_idx])
            temperature = action_dict["Temperature"]["Value"] # Temperature : Celsius
            command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"STIRRER","heat",stirrer_addr,temperature,mode_type))
            res_msg = self.callServer_STIRRER(command_byte=command_bytes)
        for action_idx,action_dict in enumerate(action_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Finish Heat Queue {} (Stirrer)".format(action_idx))

        return res_msg

    def Wait(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        wait for secondes depending on wait queue

        {
            "Action": "Wait",
            "Data": 
            // this part is action_info_list //
            [
                {
                    "To": "Stirrer_0",
                        // this part is wait queue
                    "Data": {
                        "Time": 300
                    }
                }
            ]
            // this part is action_info_list //
        }

        :param action_info_list (list): queue of stiirer heat work

        :return res_msg (str): response message from Windows10 
        """
        res_msg=""
        wait_time=0
        # define waitTime function
        def waitTime(input_TaskLogger_obj, input_platform_name, input_wait_time, input_action_idx, input_mode_type):
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Wait"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, input_action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            input_TaskLogger_obj.info(input_platform_name, "Start Wait:{}s".format(input_wait_time))
            if input_mode_type == "real":
                time.sleep(input_wait_time)
            elif input_mode_type == "virtual":
                input_TaskLogger_obj.info(input_platform_name, "check Wait:{}s".format(input_wait_time))
            input_TaskLogger_obj.info(input_platform_name, "Finish Wait:{}s".format(input_wait_time))
        # generate thread
        thread_list=[]
        for action_idx, action_dict in enumerate(action_info_list):
            wait_time = action_dict["Time"]["Value"]
            thread = threading.Thread(target=waitTime, args=(TaskLogger_obj, self.batch_platform_name, wait_time, action_idx, mode_type))
            thread_list.append(thread)
        # start thread
        for thread in thread_list: 
            thread.start()
        # main thread wait thread termination
        for thread in thread_list:
            thread.join()

        res_msg = "Finish Wait action"
        
        return res_msg

    def React(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        React for secondes depending on react queue

        {
            "Action": "React",
            "Data": 
            // this part is action_info_list //
            [
                {
                    "To": "Stirrer_0",
                        // this part is react queue
                    "Data": {
                        "Time": 300
                    }
                }
            ]
            // this part is action_info_list //
        }

        :param action_info_list (list): queue of stiirer heat work

        :return res_msg (str): response message from Windows10 
        """
        res_msg=""

        # define Start jobExecution function
        def startReact(input_TaskLogger_obj, input_platform_name, input_react_time, input_jobID, input_location_dict, input_action_idx, input_mode_type):
            # update status of hardware every batch
            input_TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "React"))
            input_TaskLogger_obj.status="{}_{}/{}:{}".format(input_TaskLogger_obj.currentIterNum, input_action_idx, input_TaskLogger_obj.todayIterNum, input_TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            input_TaskLogger_obj.info(input_platform_name, "Start React:{}s".format(input_react_time))
            # stirrer_addr = self._allocateAddress(input_location_dict["Stirrer"][input_action_idx])
            if mode_type == "real":
                time.sleep(input_react_time)
            elif input_mode_type == "virtual":
                time.sleep(20)
                input_TaskLogger_obj.info(input_platform_name, "check React:{}s".format(input_react_time))
            
            # check status of hardware
            while True:
                if self.total_hardware_status_dict["Batch_RoboticArm"]==False and self.total_hardware_status_dict["Batch_LinearAcutator"]==False and self.total_hardware_status_dict["UV_RoboticArm"]==False:
                    break
            
            self.total_hardware_status_dict["Batch_RoboticArm"]=True
            self.total_hardware_status_dict["Batch_LinearAcutator"]=True
            self.total_hardware_status_dict["UV_RoboticArm"]=True
            
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)

            input_command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(input_jobID,"DS_B",'stirrer_to_holder',input_location_dict["Stirrer"][input_action_idx],input_location_dict["vialHolder"][input_action_idx],mode_type))
            _ =self.callServer_DS_B(command_byte=input_command_bytes)
            
            input_TaskLogger_obj.info(self.batch_platform_name, "Finish React:{}s".format(input_react_time))
            
            # initialize status of hardware
            self.total_hardware_status_dict["Batch_RoboticArm"]=False
            self.total_hardware_status_dict["Batch_LinearAcutator"]=False
            self.total_hardware_status_dict["UV_RoboticArm"]=False
        
        # generate thread
        thread_list=[]
        for action_idx, action_dict in enumerate(action_info_list):
            reaction_time = action_dict["Time"]["Value"]
            thread = threading.Thread(target=startReact, args=(TaskLogger_obj, self.batch_platform_name, reaction_time, jobID, location_dict, action_idx, mode_type))
            thread_list.append(thread)
        # start thread
        for thread in thread_list: 
            thread.start()
        # main thread wait thread termination
        for thread in thread_list:
            thread.join()

        # command_bytes=str.encode("{}/{}/{}/{}".format("STIRRER","stop",stirrer_addr,mode_type))
        # res_msg=self.callServer_STIRRER(command_byte=command_bytes)

        return res_msg


class UVPlatform(TCP_Class):
    """
    [UVPlatform] UVPlatform Class inherited UV and Pipette class

    # Variable
    :param platform_name="UV Characterization Platform" (str): set UV Characterization platform name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _Cuvette2ExtractSolution(cycle_num, vialHolder_loc=0):
    2. GetUVdata(action_info_list):
    """
    def __init__(self,platform_name="UV", total_hardware_status_dict={}):
        self.uv_platform_name = "{}".format(platform_name) 
        TCP_Class.__init__(self,)
        self.UV_queue = Queue()
        self.the_number_of_tip = 96
        self.__initTipNum()
        self.total_hardware_status_dict=total_hardware_status_dict

    def __initTipNum(self):
        """
        initialize tip number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_tip):
            self.UV_queue.put(num)  

    def __popTipNum(self):
        """
        pop tip number depending on Queue.

        :return: vial_num (int): get vial number in UV_queue
        """
        empty_true = self.UV_queue.empty()
        if empty_true==True:
            self.__initTipNum()
        tip_num=self.UV_queue.get()

        return tip_num    

    def __alertTipNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.UV_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] tip number is not enough, please fill tip".format(self.uv_platform_name), 
            key_path="./Log", message_platform_list=["dooray"], mode_type=mode_type)

    def __changeStatus(self, hardware_name_list:list, status:bool):
        for hardware_name in hardware_name_list:
            self.total_hardware_status_dict[hardware_name]=status # UV_RoboticArm is okay. (not disturb in AddSolution action)

    def _Cuvette2ExtractSolution(self, jobID, vialHolder_loc, tip_num, TaskLogger_obj, mode_type="virtual"):
        """
        extract solution into vial to cuvette

        :param vialHolder_loc (int): vialHolder's locations Number
        :param tip_num (int): tip_line//8 Number
        
        :(previous) param row_num (int): tip_line//8 Number
        :(previous) param column_num (int): tip_line%8 Number

        :return: res (str)
        """
        TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Start UV sample preparation")
        command_bytes=str.encode("{}/{}/{}/{},{},{},{},{},{}/{}".format(jobID, "UVPIPETTE", "sample", "20-200", 2, tip_num, vialHolder_loc, 0, 3, mode_type))
        res_msg=self.callServer_PIPETTE(command_byte=command_bytes)
        TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Finish UV sample preparation")
        # TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Start UV sample preparation")
        # row_num=tip_num//8 # same  cycle_num
        # column_num=tip_num%8
        # command_bytes=str.encode("{}/{}/{},{}/{}".format("PIPETTE","sample",vialHolder_loc,str(chr(ord('A') + column_num) + str(row_num+1+1)),mode_type))
        # res_msg=self.callServer_PIPETTE(command_byte=command_bytes)
        # TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Finish UV sample preparation")

        return res_msg

    def GetAbs(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        get UV data included _Cuvette2ExtractSolution() func

        :param action_info_list =
        [
            {
                "Action": "GetUVdata",
                "Data": [
                    "lambdamax": [],
                    "Intensity": [],
                    "FWHM": []
                ]
            },
            ...
        ]
        :return: result_list (dict in list) ex) [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        """
        # [{'Property': ['MaxAbsorbance', 'FWHM']}, ...]
        res_msg=""
        result_list=[]
        
        for action_idx, _ in enumerate(action_info_list):
            # check status of hardware
            while True: # wait until finish Batch_RoboticArm, UV_Pipette, UV_Spectroscopy
                if self.total_hardware_status_dict["Batch_RoboticArm"]==False:
                    break
            
            # we have to finish characterizatio first although we left some actions in synthesis (priority: characterization >> synthesis becaues of aging time)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)
            # self.total_hardware_status_dict["Batch_RoboticArm"]=True
            # self.total_hardware_status_dict["UV_RoboticArm"]=True
            # self.total_hardware_status_dict["UV_Pipette"]=True
            # self.total_hardware_status_dict["UV_Spectroscopy"]=True
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.uv_platform_name, "GetAbs"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            TaskLogger_obj.info(self.uv_platform_name, "Start UV Characterization")
            # calculate tip_num & column_num (=cycle_num)
            tip_num=self.__popTipNum()
            row_num=tip_num//8 # same  cycle_num
            column_num=tip_num%8

            # move cuvette_storage_to_cuvette_holder
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'cuvette_storage_to_cuvette_holder', tip_num, location_dict["vialHolder"][action_idx], mode_type))
            res_msg =self.callServer_DS_B(command_byte=command_bytes)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # move Cuvette_holder_to_UV
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'cuvette_holder_to_UV',location_dict["vialHolder"][action_idx],0,mode_type))
            res_msg= self.callServer_DS_B(command_byte=command_bytes)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # # Get Reference peaks
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"ABS","Reference","H2O",mode_type))
            reference_str=self.callServer_ABS(command_byte=command_bytes)
            reference_dict=json.loads(reference_str)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # Sampling solution using pipetting machine
            self._Cuvette2ExtractSolution(jobID=jobID,vialHolder_loc=location_dict["vialHolder"][action_idx], tip_num=tip_num, TaskLogger_obj=TaskLogger_obj)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # Get Absorbance peaks
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"ABS","Abs","AgNP",mode_type))
            absorbance_str=self.callServer_ABS(command_byte=command_bytes)
            absorbance_dict=json.loads(absorbance_str)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # move UV_to_Cuvette_storage
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'UV_to_cuvette_storage',0,tip_num,mode_type))
            _ =self.callServer_DS_B(command_byte=command_bytes)
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], True)

            # Caculate peaks
            UV_result, each_calculate_res_dict=AnalysisUV.calculateUV_Data(absorbance_dict, reference_dict, experiment_num=action_idx, mode_type=mode_type) 
            # UV_result --> OrderedDict([('lambdamax', [391.39295]), ('Intensity', [0.01058083862181636]), ('FWHM', [49.33331611590667])])"""
            TaskLogger_obj.info(self.uv_platform_name, "{} result : {}".format(action_idx, UV_result))
            result_list.append(each_calculate_res_dict)

            TaskLogger_obj.info(self.uv_platform_name, "Finish UV Characterization")

            # initialize status of hardware
            self.__changeStatus(["Batch_RoboticArm", "UV_RoboticArm", "UV_Pipette", "UV_Spectroscopy"], False)
        self.__alertTipNum(TaskLogger_obj, mode_type)

        return result_list


class TaskScheduler(RobotMovPlatform, BatchSynthesisPlatform, UVPlatform):
    """
    TaskScheduler class read recipe file (json), and allocate & link each action to proper devices
    
    # function
    1. _extractProcessType (total_recipe_template_list):
    2. _extractActionInfo (action_dict_list):
    3. _action2Device (action_type, action_info_list):
    4. scheduleAllAction (total_recipe_template_list):
    """
    def __init__(self, serverLogger_obj:object, total_hardware_status_dict:dict, location_dict:dict, task_schedule_mode:str):
        # self.total_hardware_status_dict={
        #     "Batch_RoboticArm":False,
        #     "Batch_VialStorage":False,
        #     "Batch_LinearAcutator":False,
        #     "Batch_Pump":False,
        #     "UV_RoboticArm":False,
        #     "UV_Pipette":False,
        #     "UV_Spectroscopy":False
        # }
        self.serverLogger_obj=serverLogger_obj
        self.total_hardware_status_dict=total_hardware_status_dict
        self.location_dict=location_dict
        self.task_schedule_mode=task_schedule_mode

        self.platform_name="TaskScheduler"
        RobotMovPlatform.__init__(self, "RobotArm", self.total_hardware_status_dict)
        BatchSynthesisPlatform.__init__(self, "Batch", self.total_hardware_status_dict)
        UVPlatform.__init__(self, "UV", self.total_hardware_status_dict)
        # MobilePlatform.__init__(self, "Mobile Robot Platform") # change later

        self.task_hardware_info_dict = self.__requestHardwareInfo()

    def __requestHardwareInfo(self):
        """
        request to all of platform to get detailed information about each devices.
        We use this function to map recipe based on config file. 
        (config file--> only set "AddSolution_Metal", recipe file 
            --> write more detail, ex) "AddSolution":{"Solution":"AgNO3"}
        
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
                    ...
                },
                "Pipette", {
                    "PVP55":
                        {"SolutionType":"CA",
                        "PumpAddress":5,
                        "PumpUsbAddr":"COM7",
                        "DeviceName":"20-200μL"}
                },
                "Stirrer:{
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
            self.serverLogger_obj.info(self.platform_name,"receive BATCH_INFO")
            total_hardware_info_dict["UV"]=self.callServer_UV_INFO()
            self.serverLogger_obj.info(self.platform_name,"receive UV_INFO")
            # total_hardware_info_dict["FLOW"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Washing"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Preprocess"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["RDE"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["Electrode"] = self.callServer_BATCH_INFO()
            # total_hardware_info_dict["UV"] = self.callServer_BATCH_INFO()
        except Exception as e:
            self.serverLogger_obj.info(self.platform_name,"Each hardware server cannot connect each device --> error message : {}".format(e))
            raise ConnectionError("Each hardware server cannot connect each device --> error message : {}".format(e))
        
        return total_hardware_info_dict
    
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
        np_lst = np.array(lst)
        indexes = np.where(np_lst == value)[0]
        return indexes.tolist()

    def dynamic(self, process_type:str, next_process_type:str, jobID:int, total_recipe_template_list:list):
        """
        :param process_type: "BatchSynthesis", "FlowSynthesis", "UV" ... 
        :param jobID: allocate jobID in location_dict
        :param total_recipe_template_list: reflect recipe information in hardware location
        """
        # allocate location information in self.location_dict depending on temperature 
        if process_type == "BatchSynthesis":

            Stirrer_set_temperature_list=[]
            for stirrer_value in list(self.task_hardware_info_dict["BatchSynthesis"]["Stirrer"].values()): # upload tempearture setting of stirrer
                Stirrer_set_temperature_list.append(stirrer_value["Temperature"])

            # search each temperature and stirrate setting in total_recipe_template_list
            temperature_in_recipe_list=[]
            # stirrate_list=[] # if we control stir, activate this
            for recipe in total_recipe_template_list:
                action_dict_list=[]
                for process_info in recipe["Synthesis"]:
                    if process_info["Process"]=="BatchSynthesis": # if locate BatchSynthesis in first
                        action_dict_list=process_info["Data"]
                for action_dict in action_dict_list:
                    if action_dict["Action"]=="Heat": # we split depending on temperature (differenet temperature --> different stirrer)
                        temperature_in_recipe_list.append(action_dict["Data"]["Temperature"]["Value"])
                    # if action_dict["Action"]!="Stir": # if we control stir, activate this
                    #     stirrate_list.append(action_dict["Data"]["StirRate"]["Value"])
                    else: # exclude AddSolution, Wait, React, Pipette...
                        pass

            if 50 in temperature_in_recipe_list: # mix some temperature include 50
                empty_stirrer_0_hole_index=[]
                empty_stirrer_1_hole_index=[]
                empty_vialHolder_index=[]
                while True: # while satisfy "if" condition
                    empty_stirrer_0_hole_index=self.__find_indexes(self.location_dict[process_type]["Stirrer"][:8], "?") # "?" == empty, calculate "?" or not
                    empty_stirrer_1_hole_index=self.__find_indexes(self.location_dict[process_type]["Stirrer"][8:], "?") # "?" == empty, calculate "?" or not
                    empty_vialHolder_index=self.__find_indexes(self.location_dict[process_type]["vialHolder"],"?") # "?" == empty
                    # match recipe information with spare location of stirrer
                    if temperature_in_recipe_list.count(25) <= len(empty_stirrer_0_hole_index) and \
                        temperature_in_recipe_list.count(50) <= len(empty_stirrer_1_hole_index) and \
                        len(temperature_in_recipe_list) <= len(empty_vialHolder_index):
                        break
                popped_stirrer_hole_index_list=[]
                popped_vialHolder_index_list=[]
                for idx, temperature in enumerate(temperature_in_recipe_list):
                    if temperature == 25:
                        popped_stirrer_hole_index=empty_stirrer_0_hole_index.pop(0) # pop first element in list
                        self.location_dict[process_type]["Stirrer"][popped_stirrer_hole_index]=jobID
                        popped_stirrer_hole_index_list.append(popped_stirrer_hole_index)
                    elif temperature == 50:
                        popped_stirrer_hole_index=empty_stirrer_1_hole_index.pop(0) # pop first element in list
                        self.location_dict[process_type]["Stirrer"][popped_stirrer_hole_index]=jobID
                        popped_stirrer_hole_index_list.append(popped_stirrer_hole_index) 
                    popped_vialHolder_index=empty_vialHolder_index.pop(0) # pop first element in list
                    self.location_dict[process_type]["vialHolder"][popped_vialHolder_index]=jobID
                    popped_vialHolder_index_list.append(popped_vialHolder_index)
            
            else: # all temperature set 25 (RT)
                empty_stirrer_hole_index=[]
                empty_vialHolder_index=[]
                while True: # while satisfy "if" condition
                    empty_stirrer_hole_index=self.__find_indexes(self.location_dict[process_type]["Stirrer"], "?") # "?" == empty
                    empty_vialHolder_index=self.__find_indexes(self.location_dict[process_type]["vialHolder"],"?") # "?" == empty
                    if temperature_in_recipe_list.count(25) <= len(empty_stirrer_hole_index) and len(temperature_in_recipe_list) <= len(empty_vialHolder_index):
                        break
                popped_stirrer_hole_index_list=[]
                popped_vialHolder_index_list=[]
                for idx in range(len(temperature_in_recipe_list)):

                    popped_stirrer_hole_index=empty_stirrer_hole_index.pop(0) # pop first element in list
                    self.location_dict[process_type]["Stirrer"][popped_stirrer_hole_index]=jobID
                    popped_stirrer_hole_index_list.append(popped_stirrer_hole_index)

                    popped_vialHolder_index=empty_vialHolder_index.pop(0) # pop first element in list
                    self.location_dict[process_type]["vialHolder"][popped_vialHolder_index]=jobID
                    popped_vialHolder_index_list.append(popped_vialHolder_index)

            location_dict={
                "Stirrer":popped_stirrer_hole_index_list,
                "vialHolder":popped_vialHolder_index_list
            }
            self.location_dict[next_process_type]["vialHolder"]=self.location_dict[process_type]["vialHolder"]
            print(self.location_dict)

        elif process_type=="UV":
            popped_vialHolder_index_list=self.__find_indexes(self.location_dict["vialHolder"], jobID)
            location_dict={
                "vialHolder":popped_vialHolder_index_list
            }
            print(self.location_dict)

        return location_dict

    def normal(self, process_type:str, jobID:int, total_recipe_template_list:list):
        """
        :param process_type: "BatchSynthesis", "FlowSynthesis", "UV" ... 
        :param jobID: allocate jobID in location_dict
        :param total_recipe_template_list: reflect recipe information in hardware location
        """
        location_dict={}
        if process_type == "BatchSynthesis":
            pass
        elif process_type=="UV":
            pass
        return location_dict
    
    def _refreshLocation(self, jobID:int):
        for platform_type, platform_values in self.location_dict.items():
            for device_type, device_values in platform_values.items():
                location_index_list=self.__find_indexes(device_values, jobID)
                for location_index in location_index_list:
                    self.location_dict[platform_type][device_type][location_index]="?"

    def _action2Device(self, action_type:str, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type:str):
        """
        allocate action to each hardware depending on action_info_list
        ***Caution : initialize syringe pump before we start*** 
        
        :param action_type (str): ex) "AddSolution", "Heat"...
        :param action_info_list (dicts in list): 

        :return: list(empty) or list(in characterization cases)
        """
        return_value = getattr(self, action_type)(action_info_list, jobID, location_dict, TaskLogger_obj, mode_type)
        if type(return_value) == str: # if action_type don't return some chemical data (AddSolution, Stir...)
            return return_value
        elif type(return_value) == list: # if action_type return some chemical data (measurement, calcination, UV...),
            return_result_list=[]
            for result_dict in return_value:
                temp_dict = {action_type:result_dict}
                return_result_list.append(temp_dict)
            return return_result_list
    
    def _get_data_by_process(self,process_key, process_dict):
        for process_list in process_dict.values():
            for process_item in process_list:
                if process_item["Process"] == process_key:
                    return process_item["Data"]
        return None

    def scheduleAllAction(self, total_recipe_template_list:list, jobID:int, TaskLogger_obj:object, mode_type:str):
        """
        schdule all action using _action2Device func (큰 action들의 칸 수는 정해져있다고 가정... 나중에 병렬처리 가능할 때 새로운 scheduling 하는 function 만들기)

        :param total_recipe_template_list (list): total json in list // ex) if our batch size=8, it will be composed of [{},{},{},{},{},{},{},{}] each recipe

        --> total_characterization_result_lists_in_list (list (in dicts) of list)
        ex) [
                [{"GetAbs":{}},{"GetAbs":{}}, ...],
                [{"GetOverpotential":{}},{"GetOverpotential":{}} ...],...
            ]
        """
        total_characterization_result_lists_in_list=[] # 여기에 분석 결과를 저장
        """
        ex) total_process_dict={
            "Synthesis":[
                [{"BatchSynthesis":[...]}, {"FlowSynthesis":[]}],
                [{"BatchSynthesis":[...]}, {"FlowSynthesis":[]}]
            ], 
            "Preprocess":[], 
            "Characterization":[
                [{"UV":[]}],
                [{"UV"}]
            ], 
            "Evaluation":[]
        } 
        """
        process_seq_list = [] # location_dict에 할당할 때 필요함.
        for key, values in total_recipe_template_list[0].items():
            for value in values:
                if "Process" in value:
                    process_seq_list.append(value["Process"])

        for process_idx, process_type in enumerate(process_seq_list):
            # process_type : Batch, Flow, Washing, Ink, UV, RDE, Electrode // if not --> pass!
            batch_num = len(total_recipe_template_list) # 배치가 8개면 8개
            if process_idx+1 != len(process_seq_list):
                location_dict=getattr(self, self.task_schedule_mode)(process_type, process_seq_list[process_idx+1], jobID, total_recipe_template_list)
            TaskLogger_obj.info(self.platform_name, "{} allocate location: {}".format(process_type, location_dict))
            
            # integrate and make matrix of recipe
            total_action_list=[]
            for each_recipe in total_recipe_template_list:
                each_action_list=self._get_data_by_process(process_type, each_recipe)
                total_action_list.append(each_action_list)

            # extract action depending on sequence --> allocate action to device
            batch_action_seq_num = len(total_action_list[0]) # the number of action sequence
            for each_batch_action_seq_idx in range(batch_action_seq_num): # each batch action 시퀀스 대로 for문 돌려서 batch 합성 진행
                action_type=""
                action_dict_list=[]# each action을 choose
                for each_batch_num in range(batch_num): # each vial 합성 시작
                    action_type=total_action_list[each_batch_num][each_batch_action_seq_idx]["Action"]
                    action_dict_list.append(total_action_list[each_batch_num][each_batch_action_seq_idx]["Data"])
                each_characterization_result_list=self._action2Device(action_type, action_dict_list, jobID, location_dict, TaskLogger_obj, mode_type)
                if type(each_characterization_result_list) == str: # return str excluding characterization & evaluation
                    pass
                elif type(each_characterization_result_list) == list: # return dict in list including characterization & evaluation
                    if len(each_characterization_result_list) > 0:
                        total_characterization_result_lists_in_list.append(each_characterization_result_list)
                    else: # nothing return
                        raise ValueError("There is no value in scheduler. Please check our node server.")
        
        self._refreshLocation(jobID) # refresh location information of self.location_dict (0 or 1 or 2 ... (jobID) --> ?)
        TaskLogger_obj.info(self.platform_name, "refresh location: {}".format(self.location_dict))
        
        characterization_num=len(total_characterization_result_lists_in_list)
        batch_size=len(total_characterization_result_lists_in_list[0])

        return_result_list_to_algorithm=[]
        for batch_idx in range(batch_size): # batch_size
            temp_dict={}
            for characterziation_idx in range(characterization_num): # 분석 갯수
                temp_dict.update(total_characterization_result_lists_in_list[characterziation_idx][batch_idx])
            return_result_list_to_algorithm.append(temp_dict)

        return return_result_list_to_algorithm