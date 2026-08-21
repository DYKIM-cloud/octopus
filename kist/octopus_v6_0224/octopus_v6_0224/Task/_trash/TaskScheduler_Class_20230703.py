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
    1. __initVialTop(self):
    2. _popVialNum(self):
    3. MoveContainer(self, action_info_list):
    """
    def __init__(self, platform_name="Robot", ResourceManager_obj={}):

        self.robot_platform_name = "{}".format(platform_name) 
        TCP_Class.__init__(self,)
        self.vial_top_queue = Queue()
        self.the_number_of_vial = 80
        self.__initVialTop()
        self.ResourceManager_obj=ResourceManager_obj

    def __initVialTop(self):
        """
        initialize vial number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_vial):
            self.vial_top_queue.put(num)  

    def __popVialNum(self):
        """
        pop vial number depending on Queue.

        :return: vial_num (int): get vial number in vial_top_queue
        """
        # print("previous : ",self.vial_top_queue.qsize())
        empty_true = self.vial_top_queue.empty()
        # print("empty_true : ",empty_true)
        if empty_true==True:
            self.__initVialTop()
        vial_num=self.vial_top_queue.get()
        # print("later : ",self.vial_top_queue.qsize())

        return vial_num

    def __alertVialNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.vial_top_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] vial number is not enough, please fill vial".format(self.robot_platform_name), 
            key_path="./Log", message_platform_list=["line"], mode_type=mode_type)
        else:
            pass
    
    def __countVialTop_LineTopNum(self, vial_num):
        """
        counts on vial_num and line_num depending on the number of TaskLogger_obj.

        :return: None 
        """
        # count the number of vials in vial_top_queue
        vial_num_list=[]
        line_num_list=[]
        for _ in range(vial_num): # for each vial
            vial_num=self.__popVialNum()
            vial_num_list.append(vial_num)
            line_num_list.append(vial_num//16) # same with previous "cycle_num"

        return vial_num_list, line_num_list

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
        current_func_name=sys._getframe().f_code.co_name
        vial_num_list=[]
        line_num_list=[]
        
        # check & update status of hardware --> DON'T MIX EACH EXPERIMENT VIALS
        self.ResourceManager_obj.checkStatus(current_func_name) # wait until not busy
        self.ResourceManager_obj.updateStatus(current_func_name, True) # Already use !
        
        for action_idx, move_dict in enumerate(action_info_list): # for each vial
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.robot_platform_name, "MoveContainer"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            move_type="{}_to_{}".format(move_dict["From"], move_dict["To"])
            msg = "Batch motion ({}) is started.".format(move_type)
            TaskLogger_obj.info(self.robot_platform_name, "Start Robot Queue : "+msg)
            
            if move_type == "holder_to_storage_filled":
                if action_idx==0:
                    vial_num_list, line_num_list= self.__countVialTop_LineTopNum(len(action_info_list))
                    TaskLogger_obj.info(self.robot_platform_name, "vial_num_list:{}".format(vial_num_list))
                    TaskLogger_obj.info(self.robot_platform_name, "line_num_list:{}".format(line_num_list))
                    TaskLogger_obj.info(self.robot_platform_name, "vialHolder_list:{}".format(location_dict["vialHolder"]))
                if action_idx == 0: # vial 채우기 전, stepper motor initialize
                    time.sleep(2)
                    command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
                    time.sleep(2)
                
                self.ResourceManager_obj.updateStatus(current_func_name, True) # Already use !
                command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type))
                res_msg=self.callServer_LA(command_byte=command_bytes)

                self.ResourceManager_obj.updateStatus(current_func_name, True) # Already use !
                command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type,location_dict["vialHolder"][action_idx],line_num_list[action_idx],mode_type))
                res_msg=self.callServer_DS_B(command_byte=command_bytes)    
                
                if action_idx+1 == len(action_info_list): # vial 채울 때는 마지막 action이 끝날 때만 vial storage 모터 내리기
                    time.sleep(2)
                    self.ResourceManager_obj.updateStatus(current_func_name, True) # Already use !
                    command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            
            # elif move_type == "cuvette_storage_to_cuvette_holder":
            #     command_bytes=str.encode("{}/{}/{},{}/{}".format("DS_B","cuvette_storage_to_cuvette_holder", self.vial_num_list[action_idx],action_idx, mode_type))
            #     res_msg=self.callServer_DS_B(command_byte=command_bytes)
            
            msg = "Batch motion ({}) is done.".format(move_type)   
            TaskLogger_obj.info(self.robot_platform_name, "Finish Robot Queue : "+msg)

        self.ResourceManager_obj.updateStatus(current_func_name, False) # Already use !

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
    def __init__(self,platform_name="BatchSynthesis", ResourceManager_obj={}):
        TCP_Class.__init__(self,)
        self.batch_platform_name= "{}".format(platform_name)
        self.vial_bottom_queue = Queue()
        self.the_number_of_vial = 80
        self.__initVialBottom()
        self.ResourceManager_obj=ResourceManager_obj
    
    def _allocateAddress(self, stirrer_hole_location):
        """
        allocate pump bus usb address depending on soluition_dict

        :param device_name (str): "Stirrer_0-0" or "Stirrer_1-7"...etc (depending on stirrer addreess in IKA RET)

        return int(stirrer_hole_location//8)
        """
        return int(stirrer_hole_location//8)

    def __initVialBottom(self):
        """
        initialize vial number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_vial):
            self.vial_bottom_queue.put(num)  

    def __popVialBottom(self):
        """
        pop vial number depending on Queue.

        :return: vial_num (int): get vial number in vial_bottom_queue
        """
        empty_true = self.vial_bottom_queue.empty()
        if empty_true==True:
            self.__initVialBottom()
        vial_num=self.vial_bottom_queue.get()

        return vial_num

    def __alertVialNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.vial_bottom_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] vial number is not enough, please fill vial".format(self.robot_platform_name), 
            key_path="./Log", message_platform_list=["dooray"], mode_type=mode_type)
        else:
            pass
    
    def __countVialBottom_LineBottomNum(self, vial_num):
        """
        counts on vial_num and line_num depending on the number of TaskLogger_obj.
        :return: None 
        """
        # count the number of vials in robot_queue
        vial_num_list=[]
        line_num_list=[]
        for _ in range(vial_num): # for each vial
            vial_num=self.__popVialBottom()
            vial_num_list.append(vial_num)
            line_num_list.append(vial_num//16) # same with previous "cycle_num"
        
        return vial_num_list, line_num_list

    def PrepareContainer(self, action_info_list:list, jobID:int, location_dict:dict, TaskLogger_obj:object, mode_type="virtual"):
        """
        allocate MoveContainer depending on action_info_list.

        :param action_info_list (list): "Action":"MoveContainer","Data":[] <- action_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        action_info_list = [
               {
                    "Action": "PrepareContainer",
                    "Data": {
                        "From": "storage_empty",
                        "To": "stirrer",
                        "Container": "Vial",
                        "Setting": {
                            "Id": "dsr01",
                            "Model": "m0609",
                            "NETWORK": "192.168.137.100",
                            "WorkRange": 900
                        }
                },
                {
                    "Action": "PrepareContainer",
                    "Data": {
                        "From": "storage_empty",
                        "To": "stirrer",
                        "Container": "Vial",
                        "Setting": {
                            "Id": "dsr01",
                            "Model": "m0609",
                            "NETWORK": "192.168.137.100",
                            "WorkRange": 900
                        }
                    }
                },
                ...
            ]
        """
        res_msg=""
        current_func_name=sys._getframe().f_code.co_name
        vial_num_list=[]
        line_num_list=[]
        
        for action_idx, move_dict in enumerate(action_info_list): # for each vial
            # check & update status of hardware
            self.ResourceManager_obj.checkStatus(current_func_name)
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "PrepareContainer"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            move_type="{}_to_{}".format(move_dict["From"], move_dict["To"])
            msg = "{} is started.".format(move_type)
            TaskLogger_obj.info(self.batch_platform_name, msg)
            # separate robot action
            if action_idx==0:
                vial_num_list, line_num_list= self.__countVialBottom_LineBottomNum(len(action_info_list))
                TaskLogger_obj.info(self.batch_platform_name, "vial_num_list: {}".format(vial_num_list))
                TaskLogger_obj.info(self.batch_platform_name, "line_num_list: {}".format(line_num_list))
                TaskLogger_obj.info(self.batch_platform_name, "vialHolder_list: {}".format(location_dict["vialHolder"]))
            # execute real action
            TaskLogger_obj.info(self.batch_platform_name, "Start Robot Queue : "+msg)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type)) # initialize LinearActuator
            TaskLogger_obj.debug("LA", "move center-->Start!")
            res_msg=self.callServer_LA(command_byte=command_bytes)
            TaskLogger_obj.debug("LA", "move center-->Done!")
            
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"STORAGE","open",line_num_list[action_idx],mode_type))
            TaskLogger_obj.debug("STORAGE", "open-->Start!")
            res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            TaskLogger_obj.debug("STORAGE", "open-->Done!")
            time.sleep(2) # due to delay of vial storage

            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",move_type,line_num_list[action_idx],location_dict["Stirrer"][action_idx],mode_type))
            TaskLogger_obj.debug("DS_B", "prepare container-->Start!")
            res_msg = self.callServer_DS_B(command_byte=command_bytes)
            TaskLogger_obj.debug("DS_B", "prepare container-->Done!")
            
            msg = "{} is done.".format(move_type)   
            TaskLogger_obj.info(self.batch_platform_name, "Finish Robot Queue : "+msg)

            # initialize status of hardware
            self.ResourceManager_obj.updateStatus(current_func_name, False)

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
        for vial_action_idx, pump_dict in enumerate(action_info_list): # for each vial
            # check & update status of hardware
            self.ResourceManager_obj.checkStatus(current_func_name)
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "AddSolution"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, vial_action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system

            total_solution_queue = [pump_dict]
            process_number = len(total_solution_queue)

            # execute Preparing action
            for _,solution_dict in enumerate(total_solution_queue) : # matching 1 vial --> 1 action
                action_type="single" # 1개의 용액 (not 1개의 pump)
                solution_name=solution_dict["Solution"]
                concentration=solution_dict["Concentration"]["Value"]
                flush_volume = 5000 # modify later
                flush_inecjtion_rate= 200
                mode_type=mode_type
                TaskLogger_obj.info(self.batch_platform_name, "Prepare Injection Queue --> {},{}mM,{}uL,{}uL/s".format(solution_name, concentration, flush_volume, flush_inecjtion_rate))
                command_bytes=str.encode("{}/{}/{}/{},{},{},{}/{}".format(jobID,"PUMP",action_type,solution_name,flush_volume,concentration,flush_inecjtion_rate,mode_type))
                TaskLogger_obj.debug("PUMP", "prepare solution-->Start!")
                res_msg=self.callServer_PUMP(command_byte=command_bytes)
                TaskLogger_obj.debug("PUMP", "prepare solution-->Done!")
            
            # Real Injection
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","down",location_dict["Stirrer"][vial_action_idx],mode_type))
            TaskLogger_obj.debug("LA", "move down-->Start!")
            res_msg=self.callServer_LA(command_byte=command_bytes)
            TaskLogger_obj.debug("LA", "move down-->Done!")
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
                self.ResourceManager_obj.updateStatus(current_func_name, True)
                TaskLogger_obj.info(self.batch_platform_name, "Start Injection Queue --> {},{}{},{}{},{}{}".format(solution_name, concentration, concentration_dimension, volume, volume_dimension, injection_rate, injection_rate_dimension))
                command_bytes=str.encode("{}/{}/{}/{},{},{},{}/{}".format(jobID,"PUMP",action_type,solution_name,volume,concentration,injection_rate,mode_type))
                TaskLogger_obj.debug("PUMP", "prepare solution-->Start!")
                res_msg=self.callServer_PUMP(command_byte=command_bytes)
                TaskLogger_obj.debug("PUMP", "prepare solution-->Done!")
            
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

            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","up",location_dict["Stirrer"][vial_action_idx],mode_type))
            TaskLogger_obj.debug("LA", "move up-->Start!")
            res_msg=self.callServer_LA(command_byte=command_bytes)
            TaskLogger_obj.debug("LA", "move up-->Done!")
            
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"LA","center","null",mode_type))
            TaskLogger_obj.debug("LA", "move center-->Start!")
            res_msg=self.callServer_LA(command_byte=command_bytes)
            TaskLogger_obj.debug("LA", "move center-->Done!")

            TaskLogger_obj.info(self.batch_platform_name, "Finish Injection Queue")
            
            # initialize status of hardware
            self.ResourceManager_obj.updateStatus(current_func_name, False)
            
            # # have some time interval to receive another jobs' action
            # time.sleep(2)
            
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
        current_func_name=sys._getframe().f_code.co_name
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
        current_func_name=sys._getframe().f_code.co_name
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
        current_func_name=sys._getframe().f_code.co_name
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

        res_msg = "Finish Wait:{}s".format(wait_time)
        
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
        current_func_name=sys._getframe().f_code.co_name

        # define Start jobExecution function
        def startReact(input_TaskLogger_obj, input_platform_name, input_reaction_time_list, input_react_time, input_jobID, input_location_dict, input_action_idx, input_mode_type):
            # update status of hardware every batch
            input_TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "React"))
            input_TaskLogger_obj.status="{}_{}/{}:{}".format(input_TaskLogger_obj.currentIterNum, input_action_idx, input_TaskLogger_obj.todayIterNum, input_TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            input_TaskLogger_obj.info(input_platform_name, "Start React:{}s".format(input_react_time))
            # stirrer_addr = self._allocateAddress(input_location_dict["Stirrer"][input_action_idx])
            if mode_type == "real":
                time.sleep(input_react_time)
            elif input_mode_type == "virtual":
                time.sleep(10)
                input_TaskLogger_obj.info(input_platform_name, "check React:{}s".format(input_react_time))
            
            # check & update status of hardware
            # if input_react_time == min(input_reaction_time_list):
            self.ResourceManager_obj.checkStatus(current_func_name)
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(input_jobID,"LA","center","null",input_mode_type))
            TaskLogger_obj.debug("LA", "move center-->Start!")
            res_msg=self.callServer_LA(command_byte=command_bytes)
            TaskLogger_obj.debug("LA", "move center-->Done!")

            self.ResourceManager_obj.updateStatus(current_func_name, True)
            input_command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(input_jobID,"DS_B",'stirrer_to_holder',input_location_dict["Stirrer"][input_action_idx],input_location_dict["vialHolder"][input_action_idx],input_mode_type))
            TaskLogger_obj.debug("DS_B", "stirrer_to_holder-->Start!")
            res_msg = self.callServer_DS_B(command_byte=command_bytes)
            TaskLogger_obj.debug("DS_B", "stirrer_to_holder-->Done!")
            
            input_TaskLogger_obj.info(self.batch_platform_name, "Finish React:{}s".format(input_react_time))

            # initialize status of hardware
            self.ResourceManager_obj.updateStatus(current_func_name, False)
        
        # generate thread
        thread_list=[]
        reaction_time_list=[]
        for action_idx, action_dict in enumerate(action_info_list):
            reaction_time = action_dict["Time"]["Value"]
            reaction_time_list.append(reaction_time)
        for action_idx, reaction_time in enumerate(reaction_time_list):
            thread = threading.Thread(target=startReact, args=(TaskLogger_obj, self.batch_platform_name, reaction_time_list, reaction_time, jobID, location_dict, action_idx, mode_type))
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
    def __init__(self,platform_name="UV", ResourceManager_obj={}):
        self.uv_platform_name = "{}".format(platform_name) 
        TCP_Class.__init__(self,)
        self.UV_queue = Queue()
        self.the_number_of_tip = 96
        self.__initTipNum()
        self.ResourceManager_obj=ResourceManager_obj

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
        
        for action_idx, _ in enumerate(action_info_list):
            # check & update status of hardware
            self.ResourceManager_obj.checkStatus(current_func_name)
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            # update status of hardware every batch
            TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.uv_platform_name, "GetAbs"))
            TaskLogger_obj.status="{}_{}/{}:{}".format(TaskLogger_obj.currentIterNum, action_idx, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
            # execute action
            TaskLogger_obj.info(self.uv_platform_name, "Prepare UV-VIS container")
            # calculate tip_num & column_num (=cycle_num)
            tip_num=self.__popTipNum()
            row_num=tip_num//8 # same  cycle_num
            column_num=tip_num%8

            # move cuvette_storage_to_cuvette_holder
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'cuvette_storage_to_cuvette_holder', tip_num, location_dict["vialHolder"][action_idx], mode_type))
            TaskLogger_obj.debug("DS_B", "stirrer_to_holder-->Start!")
            res_msg=self.callServer_DS_B(command_byte=command_bytes)
            TaskLogger_obj.debug("DS_B", "stirrer_to_holder-->Done!")

            # move Cuvette_holder_to_UV
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'cuvette_holder_to_UV',location_dict["vialHolder"][action_idx],0,mode_type))
            TaskLogger_obj.debug("DS_B", "cuvette_holder_to_UV-->Start!")
            res_msg=self.callServer_DS_B(command_byte=command_bytes)
            TaskLogger_obj.debug("DS_B", "cuvette_holder_to_UV-->Done!")

            # # Get Reference peaks
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"ABS","Reference","H2O",mode_type))
            TaskLogger_obj.debug("DS_B", "UV-VIS Characterization-->Start!")
            reference_str=self.callServer_ABS(command_byte=command_bytes)
            reference_dict=json.loads(reference_str)
            TaskLogger_obj.debug("DS_B", "UV-VIS Characterization-->Start!")

            # Sampling solution using pipetting machine
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            TaskLogger_obj.debug("DS_B", "Cuvette2ExtractSolution-->Start!")
            self._Cuvette2ExtractSolution(jobID=jobID,vialHolder_loc=location_dict["vialHolder"][action_idx], tip_num=tip_num, TaskLogger_obj=TaskLogger_obj)
            TaskLogger_obj.debug("DS_B", "Cuvette2ExtractSolution-->Start!")

            # Get Absorbance peaks
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            TaskLogger_obj.info(self.uv_platform_name, "Start UV-VIS Characterization")
            command_bytes=str.encode("{}/{}/{}/{}/{}".format(jobID,"ABS","Abs","AgNP",mode_type))
            TaskLogger_obj.debug("DS_B", "UV-VIS Characterization-->Start!")
            absorbance_str=self.callServer_ABS(command_byte=command_bytes)
            absorbance_dict=json.loads(absorbance_str)
            TaskLogger_obj.debug("DS_B", "UV-VIS Characterization-->Start!")

            # move UV_to_Cuvette_storage
            self.ResourceManager_obj.updateStatus(current_func_name, True)
            command_bytes =str.encode("{}/{}/{}/{},{}/{}".format(jobID,"DS_B",'UV_to_cuvette_storage',0,tip_num,mode_type))
            TaskLogger_obj.debug("DS_B", "UV_to_cuvette_storage-->Start!")
            res_msg=self.callServer_DS_B(command_byte=command_bytes)
            TaskLogger_obj.debug("DS_B", "UV_to_cuvette_storage-->Done!")

            # Caculate peaks
            UV_result, each_calculate_res_dict=AnalysisUV.calculateUV_Data(absorbance_dict, reference_dict, experiment_num=action_idx, mode_type=mode_type) 
            # UV_result --> OrderedDict([('lambdamax', [391.39295]), ('Intensity', [0.01058083862181636]), ('FWHM', [49.33331611590667])])"""
            TaskLogger_obj.info(self.uv_platform_name, "{} result : {}".format(action_idx, UV_result))
            result_list.append(each_calculate_res_dict)

            TaskLogger_obj.info(self.uv_platform_name, "Finish UV-VIS Characterization")

            # initialize status of hardware
            self.ResourceManager_obj.updateStatus(current_func_name, False)
        
        self.__alertTipNum(TaskLogger_obj, mode_type)

        return result_list


class TaskScheduler(RobotMovPlatform, BatchSynthesisPlatform, UVPlatform):
    """
    TaskScheduler class read recipe file (json), and allocate & link each action to proper devices
    
    # function
    3. _action2Device (action_type, action_info_list):
    4. scheduleAllAction (total_recipe_template_list):
    """
    def __init__(self, serverLogger_obj:object, ResourceManager_obj:object, task_schedule_mode:str):
        self.serverLogger_obj=serverLogger_obj
        self.ResourceManager_obj=ResourceManager_obj

        self.platform_name="TaskScheduler"
        self.task_schedule_mode=task_schedule_mode

        RobotMovPlatform.__init__(self, "RobotArm", self.ResourceManager_obj)
        BatchSynthesisPlatform.__init__(self, "Batch", self.ResourceManager_obj)
        UVPlatform.__init__(self, "UV", self.ResourceManager_obj)

        # MobilePlatform.__init__(self, "Mobile Robot Platform") # change later

        # print("self.task_hardware_status_dict",id(self.task_hardware_status_dict))
        # print("self.ResourceManager_obj.task_hardware_status_dict",id(self.ResourceManager_obj.task_hardware_status_dict))

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
        process_seq_list = [] # need this var to implement in location_dict
        for key, values in total_recipe_template_list[0].items():
            for value in values:
                if "Process" in value:
                    process_seq_list.append(value["Process"])

        TaskLogger_obj.info(self.platform_name, "check location: {}".format(self.ResourceManager_obj.task_location_dict))
        for process_idx, process_type in enumerate(process_seq_list):
            # process_type : Batch, Flow, Washing, Ink, UV, RDE, Electrode // if not --> pass!
            batch_num = len(total_recipe_template_list) # 배치가 8개면 8개
            if process_idx+1 != len(process_seq_list):
                location_dict=getattr(self.ResourceManager_obj, self.task_schedule_mode)(process_type, process_seq_list[process_idx+1], jobID, total_recipe_template_list)
                # location_dict=self.ResourceManager_obj.dynamic(process_type, process_seq_list[process_idx+1], jobID, total_recipe_template_list)
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
        
        self.ResourceManager_obj.refreshLocation(jobID) # refresh location information of self.task_hardware_location_dict (0 or 1 or 2 ... (jobID) --> ?)
        TaskLogger_obj.info(self.platform_name, "refresh location: {}".format(self.ResourceManager_obj.task_location_dict))

        characterization_num=len(total_characterization_result_lists_in_list)
        batch_size=len(total_characterization_result_lists_in_list[0])

        return_result_list_to_algorithm=[]
        for batch_idx in range(batch_size): # batch_size
            temp_dict={}
            for characterziation_idx in range(characterization_num): # 분석 갯수
                temp_dict.update(total_characterization_result_lists_in_list[characterziation_idx][batch_idx])
            return_result_list_to_algorithm.append(temp_dict)

        return return_result_list_to_algorithm