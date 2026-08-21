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
    3. MoveContainer(self, task_info_list):
    """
    def __init__(self, platform_name="Robot"):

        self.robot_platform_name = "{}".format(platform_name) 
        TCP_Class.__init__(self,)
        self.robot_queue = Queue()
        self.the_number_of_vial = 80
        self.__initVialNum()

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
        self.vial_num_list=[]
        self.line_num_list=[]
        for _ in range(vial_num): # for each vial
            vial_num=self.__popVialNum()
            self.vial_num_list.append(vial_num)
            self.line_num_list.append(vial_num//16) # same with previous "cycle_num"

    def MoveContainer(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        allocate MoveContainer depending on task_info_list.

        :param task_info_list (list): "Task":"MoveContainer","Data":[] <- task_info_list

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode

        task_info_list = [
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
        
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.robot_platform_name, "MoveContainer"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        
        for task_idx, move_dict in enumerate(task_info_list): # for each vial
            move_type="{}_to_{}".format(move_dict["From"], move_dict["To"])
            msg = "Batch motion ({}) is started.".format(move_type)
            TaskLogger_obj.info(self.robot_platform_name, "Start Robot Queue : "+msg)

            msg = "{} is started.".format(move_type)   
            TaskLogger_obj.debug(self.robot_platform_name, debug_msg=msg)

            # separate robot task
            if move_type == "storage_empty_to_stirrer":
                if task_idx==0:
                    self.__countVialNum_LineNum(len(task_info_list))
                    print("vial_num_list: ",self.vial_num_list)
                    print("line_num_list: ",self.line_num_list)
                command_bytes=str.encode("{}/{}/{}/{}".format("STORAGE","open",self.line_num_list[task_idx],mode_type))
                res_msg=self.callServer_STORAGE(command_byte=command_bytes)
                time.sleep(2)
                command_bytes=str.encode("{}/{}/{},{}/{}".format("DS_B",move_type,self.line_num_list[task_idx],task_idx,mode_type))
                res_msg = self.callServer_DS_B(command_byte=command_bytes)
            
            elif move_type == "stirrer_to_holder":
                command_bytes =str.encode("{}/{}/{},{}/{}".format("DS_B",move_type, task_idx, task_idx,mode_type))
                res_msg=self.callServer_DS_B(command_byte=command_bytes)
            
            elif move_type == "holder_to_storage_filled":
                if task_idx == 0: # vial 채우기 전, stepper motor initialize
                    time.sleep(2)
                    command_bytes=str.encode("{}/{}/{}/{}".format("STORAGE","open",self.line_num_list[task_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
                    time.sleep(2)
                command_bytes=str.encode("{}/{}/{},{}/{}".format("DS_B",move_type,task_idx,self.line_num_list[task_idx],mode_type))
                res_msg=self.callServer_DS_B(command_byte=command_bytes)    
                if task_idx+1 == len(task_info_list): # vial 채울 때는 마지막 task이 끝날 때만 vial storage 모터 내리기
                    time.sleep(2)
                    command_bytes=str.encode("{}/{}/{}/{}".format("STORAGE","open",self.line_num_list[task_idx]+5,mode_type))
                    res_msg=self.callServer_STORAGE(command_byte=command_bytes)
            
            # elif move_type == "cuvette_storage_to_cuvette_holder":
            #     command_bytes=str.encode("{}/{}/{},{}/{}".format("DS_B","cuvette_storage_to_cuvette_holder", self.vial_num_list[task_idx],task_idx, mode_type))
            #     res_msg=self.callServer_DS_B(command_byte=command_bytes)
            
            msg = "Batch motion ({}) is done.".format(move_type)   
            TaskLogger_obj.info(self.robot_platform_name, "Finish Robot Queue : "+msg)

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
    5. AddSolution(task_info_list):
    6. Stir(task_info_list):
    7. Heat(task_info_list):
    8. Wait(task_info_list):
    9. React(task_info_list):
    """
    def __init__(self,platform_name="BatchSynthesis"):
        self.batch_platform_name= "{}".format(platform_name)
        self.robot_obj=RobotMovPlatform(platform_name="RoboticArm")
        TCP_Class.__init__(self,)
    
    def _allocateAddress(self, device_name):
        """
        allocate pump bus usb address depending on soluition_dict

        :param device_name (str): "Stirrer_0-0" or "Stirrer_1-7"...etc (depending on stirrer addreess in IKA RET)

        return int(device_type), int(device_hole)
        """
        _, total_device_info=device_name.split("_")
        device_address, device_hole=total_device_info.split("_")
        return int(device_address), int(device_hole)

    def AddSolution(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        Add solution depending on task_info_list. This list included 1 cycle batch synthesis process.

        :param task_info_list (list): "Task":"AddSolution","Data":[] <- task_info_list

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
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "AddSolution"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        for vial_task_idx, pump_dict in enumerate(task_info_list): # for each vial
            total_solution_queue = [pump_dict]
            process_number = len(total_solution_queue)
            # Preparing
            TaskLogger_obj.info(self.batch_platform_name, "Prepare Injection Queue (LA, Pump)")
            
            if process_number==1: # 만약 process number=1, 즉 solution 1개만 토출할 경우
                for task_idx,solution_dict in enumerate(total_solution_queue) : # matching 1 vial --> 1 task
                    task_type="single" # 1개의 용액 (not 1개의 pump)
                    solution_name=solution_dict["Solution"]
                    concentration=solution_dict["Concentration"]["Value"]
                    flush_volume = 5000
                    flush_inecjtion_rate= 200
                    mode_type=mode_type
                    
                    command_bytes=str.encode("{}/{}/{},{},{},{}/{}".format("PUMP",task_type,solution_name,flush_volume,concentration,flush_inecjtion_rate,mode_type))
                    res_msg=self.callServer_PUMP(command_byte=command_bytes)
            
            # Real Injection
            TaskLogger_obj.info(self.batch_platform_name, "Start Injection Queue (LA, Pump)")
            command_bytes=str.encode("{}/{}/{},{}/{}".format("LA","down",pump_dict["To"],vial_task_idx,mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)
            if process_number==1: # 만약 process number=1, 즉 solution 1개만 토출할 경우
                for task_idx,solution_dict in enumerate(total_solution_queue) : # matching 1 vial --> 1 task
                    task_type="single" # 1개의 용액 (not 1개의 pump)
                    solution_name=solution_dict["Solution"]
                    volume=solution_dict["Volume"]["Value"]
                    concentration=solution_dict["Concentration"]["Value"]
                    injection_rate=solution_dict["Injectionrate"]["Value"]
                    mode_type=mode_type
                    
                    command_bytes=str.encode("{}/{}/{},{},{},{}/{}".format("PUMP",task_type,solution_name,volume,concentration,injection_rate,mode_type))
                    res_msg=self.callServer_PUMP(command_byte=command_bytes)
            
            elif process_number>1: # 만약 process number>1, 즉 solution 2개 이상 토출할 경우
                task_type="multi" # 여러개의 용액 (not 여러개의 pump)
                solution_name_list=[]
                volume_list=[]
                flow_rate_list=[]
                mode_type=mode_type
                for task_idx,solution_dict in enumerate(total_solution_queue): # matching 1 vial --> 1 task
                    solution_name_list.append(solution_dict["Solution"])
                    volume_list.append(solution_dict["Volume"]["Value"])
                    flow_rate_list.append(solution_dict["Injectionrate"]["Value"])
                solution_name_str=""
                for i, solution_name in enumerate(solution_name_list):
                    solution_name_str+=solution_name
                    if i+1 == len(solution_name_list):
                        break
                    solution_name_str+=","
                volume_list_str=str(volume_list)[1:-1]
                flow_rate_list_str=str(flow_rate_list)[1:-1]
                command_bytes=str.encode("{}/{}/{},{},{}/{}".format("PUMP",task_type,solution_name_str,volume_list_str,flow_rate_list_str,mode_type))
                res_msg=self.callServer_PUMP(command_byte=command_bytes)

            # time.sleep(5)
            command_bytes=str.encode("{}/{}/{},{}/{}".format("LA","up",pump_dict["To"],vial_task_idx,mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)
            
            command_bytes=str.encode("{}/{}/{},{}/{}".format("LA","home",pump_dict["To"],vial_task_idx,mode_type))
            res_msg=self.callServer_LA(command_byte=command_bytes)
            
            # command_bytes=str.encode("{}/{}/{}/{}".format("LA","flush","null",mode_type)) # add flush later
            # res_msg=self.callServer_LA(command_byte=command_bytes)

            TaskLogger_obj.info(self.batch_platform_name, "Finish Injection Queue (LA, Pump)")

        return res_msg

    def Stir(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        Stir our stirrer depending on stir_queue

        {
            "Task":"Stir",
            "Data":
            // task_dict is here!
            {
                "To":"Stirrer_1",
                "Data":
                [
                    {
                        "StirRate":400,
                    }
                ]
            }
        }

        :param task_info_list (list): queue of stiirer stir work

        :return res_msg (str) : response message from Windows10 // str == real mode, bool == virtual mode
        """
        res_msg=""
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Stir"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        for idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Start Stir Queue {} (Stirrer)".format(idx))
            stirrer_name=task_dict["To"]
            stirrer_addr = self._allocateAddress(stirrer_name)
            stir_rate = task_dict["StirRate"]["Value"] # StirRate : rpm
            command_bytes=str.encode("{}/{}/{},{}/{}".format("STIRRER","stir",stirrer_addr,stir_rate,mode_type))
            res_msg = self.callServer_STIRRER(command_byte=command_bytes)
            # if idx==0:
            #     break
        for idx,task_dict in enumerate(task_info_list): # log 따로 작성하려고 일부러 만듬
            TaskLogger_obj.info(self.batch_platform_name, "Finish Stir Queue {} (Stirrer)".format(idx))

        return res_msg

    def Heat(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
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
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Heat"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        for idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Start Heat Queue (Stirrer)".format(idx))
            stirrer_name=task_dict["To"]
            stirrer_addr = self._allocateAddress(stirrer_name)
            temperature = task_dict["Temperature"]["Value"] # Temperature : Celsius
            command_bytes=str.encode("{}/{}/{},{}/{}".format("STIRRER","heat",stirrer_addr,temperature,mode_type))
            res_msg = self.callServer_STIRRER(command_byte=command_bytes)
            if idx==0:
                break
        for idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Finish Heat Queue {} (Stirrer)".format(idx))

        return res_msg

    def Wait(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        wait for secondes depending on wait queue

        {
            "Task": "Wait",
            "Data": 
            // this part is task_info_list //
            [
                {
                    "To": "Stirrer_0",
                        // this part is wait queue
                    "Data": {
                        "Time": 300
                    }
                }
            ]
            // this part is task_info_list //
        }

        :param task_info_list (list): queue of stiirer heat work

        :return res_msg (str): response message from Windows10 
        """
        res_msg=""
        wait_time=0
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "Wait"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        for idx,task_dict in enumerate(task_info_list):
            wait_time = task_dict["Time"]["Value"]
            TaskLogger_obj.info(self.batch_platform_name, "Start Wait Queue {}".format(idx))
        if mode_type == "real":
            time.sleep(wait_time)
        elif mode_type == "virtual":
            pass
        for idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Finish Wait Queue {}".format(idx))

        res_msg = "Finish Wait task"
        
        return res_msg


    def React(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        React for secondes depending on react queue

        {
            "Task": "React",
            "Data": 
            // this part is task_info_list //
            [
                {
                    "To": "Stirrer_0",
                        // this part is react queue
                    "Data": {
                        "Time": 300
                    }
                }
            ]
            // this part is task_info_list //
        }

        :param task_info_list (list): queue of stiirer heat work

        :return res_msg (str): response message from Windows10 
        """
        res_msg=""
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.batch_platform_name, "React"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        
        command_bytes=str.encode("{}/{}/{}/{}".format("LA","home","null",mode_type))
        res_msg=self.callServer_STIRRER(command_byte=command_bytes)

        retask_time=0
        stirrer_addr=0
        for idx,task_dict in enumerate(task_info_list):
            retask_time = task_dict["Time"]["Value"]
            TaskLogger_obj.info(self.batch_platform_name, "Start React Queue {}".format(idx))
            stirrer_name=task_dict["To"]
            stirrer_addr=self._allocateAddress(stirrer_name)
        
        if mode_type == "real":
            time.sleep(retask_time)
        elif mode_type == "virtual":
            pass
        
        command_bytes=str.encode("{}/{}/{}/{}".format("STIRRER","stop",stirrer_addr,mode_type))
        res_msg=self.callServer_STIRRER(command_byte=command_bytes)
        for idx,task_dict in enumerate(task_info_list):
            TaskLogger_obj.info(self.batch_platform_name, "Finish React Queue {}".format(idx))

        return res_msg


class UVPlatform(TCP_Class):
    """
    [UVPlatform] UVPlatform Class inherited UV and Pipette class

    # Variable
    :param platform_name="UV Characterization Platform" (str): set UV Characterization platform name (log name)
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _Cuvette2ExtractSolution(cycle_num, vialHolder_loc=0):
    2. GetUVdata(task_info_list):
    """
    def __init__(self,platform_name="UV"):
        self.uv_platform_name = "{}".format(platform_name) 
        self.robot_obj = RobotMovPlatform(platform_name="Doosan robot")

        TCP_Class.__init__(self,)

        self.UV_queue = Queue()
        self.the_number_of_tip = 96
        self.__initTipNum()

    def __initTipNum(self):
        """
        initialize tip number depending on Queue.

        :return: None: 
        """
        for num in range(self.the_number_of_tip):
            self.UV_queue.put(num)  

    def _popTipNum(self):
        """
        pop tip number depending on Queue.

        :return: vial_num (int): get vial number in UV_queue
        """
        empty_true = self.UV_queue.empty()
        if empty_true==True:
            self.__initTipNum()
        tip_num=self.UV_queue.get()

        return tip_num    

    def _alertTipNum(self, TaskLogger_obj, mode_type="virtual"):
        if self.UV_queue.qsize() <=10:
            AlertMessage(TaskLogger_obj, 
            text_content="[{}] tip number is not enough, please fill tip".format(self.uv_platform_name), 
            key_path="./Log", message_platform_list=["line"], mode_type=mode_type)

    def _Cuvette2ExtractSolution(self, vialHolder_loc, tip_num, TaskLogger_obj, mode_type="virtual"):
        """
        extract solution into vial to cuvette

        :param vialHolder_loc (int): vialHolder's locations Number
        :param tip_num (int): tip_line//8 Number
        
        :(previous) param row_num (int): tip_line//8 Number
        :(previous) param column_num (int): tip_line%8 Number

        :return: res (str)
        """
        TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Start UV sample preparation")
        command_bytes=str.encode("{}/{}/{},{},{},{},{},{}/{}".format("UVPIPETTE", "sample", "20-200", 2, tip_num, vialHolder_loc, 0, 3, mode_type))
        res_msg=self.callServer_PIPETTE(command_byte=command_bytes)
        TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Finish UV sample preparation")
        # TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Start UV sample preparation")
        # row_num=tip_num//8 # same  cycle_num
        # column_num=tip_num%8
        # command_bytes=str.encode("{}/{}/{},{}/{}".format("PIPETTE","sample",vialHolder_loc,str(chr(ord('A') + column_num) + str(row_num+1+1)),mode_type))
        # res_msg=self.callServer_PIPETTE(command_byte=command_bytes)
        # TaskLogger_obj.debug(self.uv_platform_name, debug_msg="Finish UV sample preparation")

        return res_msg

    def GetAbs(self, task_info_list, TaskLogger_obj, mode_type="virtual"):
        """
        get UV data included _Cuvette2ExtractSolution() func

        :param task_info_list =
        [
            {
                "Task": "GetUVdata",
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
        TaskLogger_obj.setCurrentPlatformName("{}-->{}".format(self.uv_platform_name, "GetAbs"))
        TaskLogger_obj.status="{}/{}:{}".format(TaskLogger_obj.currentIterNum, TaskLogger_obj.todayIterNum, TaskLogger_obj.current_platform_name) # in execution system
        
        result_list=[]
        for each_vial_loc, _ in enumerate(task_info_list):
            TaskLogger_obj.info(self.uv_platform_name, "Start UV Characterization")
            # calculate tip_num & column_num (=cycle_num)
            tip_num=self._popTipNum()
            row_num=tip_num//8 # same  cycle_num
            column_num=tip_num%8

            # move cuvette_storage_to_cuvette_holder
            command_bytes =str.encode("{}/{}/{},{}/{}".format("DS_B",'cuvette_storage_to_cuvette_holder', tip_num, each_vial_loc, mode_type))
            res_msg =self.callServer_DS_B(command_byte=command_bytes)

            # move Cuvette_holder_to_UV
            command_bytes =str.encode("{}/{}/{},{}/{}".format("DS_B",'cuvette_holder_to_UV',each_vial_loc,0,mode_type))
            res_msg= self.callServer_DS_B(command_byte=command_bytes)

            # # Get Reference peaks
            command_bytes=str.encode("{}/{}/{}/{}".format("ABS","Reference","H2O",mode_type))
            reference_str=self.callServer_ABS(command_byte=command_bytes)
            reference_dict=json.loads(reference_str)

            # Sampling solution using pipetting machine
            self._Cuvette2ExtractSolution(vialHolder_loc=each_vial_loc, tip_num=tip_num, TaskLogger_obj=TaskLogger_obj)

            # Get Absorbance peaks
            command_bytes=str.encode("{}/{}/{}/{}".format("ABS","Abs","AgNP",mode_type))
            absorbance_str=self.callServer_ABS(command_byte=command_bytes)
            absorbance_dict=json.loads(absorbance_str)

            # move UV_to_Cuvette_storage
            command_bytes =str.encode("{}/{}/{},{}/{}".format("DS_B",'UV_to_cuvette_storage',0,tip_num,mode_type))
            _ =self.callServer_DS_B(command_byte=command_bytes)

            # Caculate peaks
            UV_result, each_calculate_res_dict=AnalysisUV.calculateUV_Data(absorbance_dict, reference_dict, experiment_num=each_vial_loc, mode_type=mode_type) 
            # UV_result --> OrderedDict([('lambdamax', [391.39295]), ('Intensity', [0.01058083862181636]), ('FWHM', [49.33331611590667])])"""
            TaskLogger_obj.info(self.uv_platform_name, "{} result : {}".format(each_vial_loc, UV_result))
            result_list.append(each_calculate_res_dict)

            TaskLogger_obj.info(self.uv_platform_name, "Finish UV Characterization")
        self._alertTipNum(TaskLogger_obj, mode_type)

        return result_list


class TaskScheduler(RobotMovPlatform, BatchSynthesisPlatform, UVPlatform):
    """
    TaskScheduler class read recipe file (json), and allocate & link each task to proper devices
    
    # Variable
    :param TaskLogger_obj (TaskLogger_obj s in list): set logging object
    :param mode_type="virtual" (str): set virtual or real mode

    # function
    1. _extractProcessType (total_recipe_template_list):
    2. _extracttaskInfo (task_dict_list):
    3. _task2Device (task_type, task_info_list):
    4. scheduleAlltask (total_recipe_template_list):
    5. remakeResult2AlgorithmInput (total_characterization_result_dicts_in_list):
    
    # BatchSynthesis
    - AddSolution
    - Stir
    - Heat
    - Wait
    - React
    - Mix (later)
    - Gas (later)
    - Pipette (later)

    # Washing
    - DrySolid (later)
    - DrySolution (later)
    - Centrifuge (later)
    - Calcine (later)
    - Sinter (later)
    - Filter (later)
    - Sonicate (later)

    - Coat (later)
    - Grind (later)
    - Press (later)
    - Microwave (later)
    - Support (later)
    - Deposition (later)

    # Characterization
    - UV
    - Thermalchemical (later)
    - Electrochemical (later)
    - XRD (later)
    """
    def __init__(self):
        RobotMovPlatform.__init__(self, platform_name="RoboticArm")
        # MobilePlatform.__init__(self, platform_name="Mobile Robot Platform") # change later
        BatchSynthesisPlatform.__init__(self, platform_name="Batch")
        UVPlatform.__init__(self, platform_name="UV")
        self.platform_name="TaskScheduler"

    def _extractProcessType(self, total_recipe_template_list):
        """
        extract process inside total_json (kind of process recipe)

        :param total_recipe_template_list (list): total json list has recipe of synthesiss total process
        
        :return total_process_dict (lists in dict): 
        
        ex) total_process_dict={
            "Synthesis":[
                [{"BatchSynthesis"}, {"FlowSynthesis}],
                [{"BatchSynthesis"}, {"FlowSynthesis}]
            ], 
            "Preprocess":[], 
            "Characterization":[], 
            "Evaluation":[], 
        } 
        """
        total_process_dict={
            "Synthesis":[], 
            "Preprocess":[], 
            "Characterization":[],
            "Evaluation":[], 
        }
        for each_total_json in total_recipe_template_list:
            temp_total_json=copy.deepcopy(each_total_json) 
            big_task_type_list=total_process_dict.keys()
            for big_task_type in big_task_type_list:
                big_aciton_dict=temp_total_json[big_task_type]
                total_process_dict[big_task_type].append(big_aciton_dict)

        return total_process_dict

    def _extracttaskInfo(self, task_dict_list):
        """
        extract task type and task data

        :param task_dict_list:[
                                    key:"Task",Value:"Data",
                                    key:"Task",Value:"Data", ...
                                ]
        
        :return (str, list): task_type, task_info_list
                            task_type=queue_dict["Task"]
                            task_info_list=queue_dict["Data"]
        """
        task_info_list=[]
        for task_dict in task_dict_list:
            task_type=task_dict["Task"]
            task_info_list.append(task_dict["Data"])
        return task_type, task_info_list
        # except KeyError as e:
        #     raise KeyError("Empty process, please check this part!")

    def _task2Device(self, task_type, task_info_list, TaskLogger_obj, mode_type):
        """
        allocate task to each hardware depending on task_info_list
        ***Caution : initialize syringe pump before we start*** 
        
        :param task_type (str): ex) "AddSolution", "Heat"...
        :param task_info_list (dicts in list): 

        :return: list(empty) or list(in characterization cases)
        """
        return_value = getattr(self, task_type)(task_info_list, TaskLogger_obj, mode_type)
        if type(return_value) == str: # if task_type don't return some chemical data (AddSolution, Stir...)
            return return_value
        elif type(return_value) == list: # if task_type return some chemical data (measurement, calcination, UV...),
            return_result_list=[]
            for result_dict in return_value:
                temp_dict = {task_type:result_dict}
                return_result_list.append(temp_dict)
            return return_result_list
    
    # def find_key(self, recipe_data, target_key):
    #     if isinstance(recipe_data, dict):
    #         if target_key in recipe_data:
    #             return recipe_data[target_key]
    #         else:
    #             for key, value in recipe_data.items():
    #                 result = self.find_key(value, target_key)
    #                 if result is not None:
    #                     return result
    #     elif isinstance(recipe_data, list):
    #         for item in recipe_data:
    #             result = self.find_key(item, target_key)
    #             if result is not None:
    #                 return result
    #     return None

    def scheduleAlltask(self, total_recipe_template_list, TaskLogger_obj, mode_type):
        """
        schdule all task using _task2Device func (큰 task들의 칸 수는 정해져있다고 가정... 나중에 병렬처리 가능할 때 새로운 scheduling 하는 function 만들기)

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
        Process_name_list=["BatchSynthesis", "FlowSynthesis", "Washing", "Ink", "UV", "RDE", "Electrode"]
        
        total_process_dict = self._extractProcessType(total_recipe_template_list) # big task == Before, Synthesis, Preprocess, Characterization, After를 의미
        for big_task_type, big_task_process_list in total_process_dict.items():
            if len(big_task_process_list[0])==0: # Batch, Flow, Preprocess, Characterization, After 이 없는 경우 아예 빈칸으로! pass
                pass
            else:
                """
                # platform의 status 어떤지 물어보기 해당하는 부분 busy로 전환하기 
                """
                
                """
                # platform의 status busy로 전환하기 
                """
                batch_num = len(big_task_process_list) # 배치가 8개면 8개
                batch_task_seq_num = len(big_task_process_list[0][0]["Data"]) # each batch task 시퀀스가 12개면 12

                # each_process_dict는 each batch로 8개 존재 --> each batch 안에 task 시퀀스가 12개, 13개 등등 존재
                for each_batch_task_seq_idx in range(batch_task_seq_num): # each batch task 시퀀스 대로 for문 돌려서 batch 합성 진행
                    task_dict_list=[]# each task을 choose
                    for each_batch_num in range(batch_num): # each vial 합성 시작
                        task_dict_list.append(big_task_process_list[each_batch_num][0]["Data"][each_batch_task_seq_idx])
                    task_type, task_info_list=self._extracttaskInfo(task_dict_list)
                    each_characterization_result_list=self._task2Device(task_type, task_info_list, TaskLogger_obj, mode_type)
                    # characterization 외 모두는 []을 return
                    # characterization는 항상 결과 데이터 dict를 포함한 list로 return
                    if type(each_characterization_result_list) == str: 
                        pass
                    elif type(each_characterization_result_list) == list:
                        if len(each_characterization_result_list) > 0:
                            total_characterization_result_lists_in_list.append(each_characterization_result_list)
                            # characterization이 결과 데이터 dict를 포함한 list로 return 못한 경우
                        else: 
                            raise ValueError("There is no value in scheduler. Please check our node server.")
                """
                platform의 status==available로 변환하는 코드 만들기
                """
        
        """
        Remake result depending on Algorithm input (recipe --> db format)

        :param total_characterization_result_dicts_in_list (list (in dicts) of list): 
        [
            [{"GetAbs":{}},{"GetAbs":{}}, ...],
            [{"GetOverpotential":{}},{"GetOverpotential":{}}, ...]
        ]

        :return: return_result_list_to_algorithm
        [
            {"GetAbs":{}, "GetOverpotential":{}}, ...
            {"GetAbs":{}, "GetOverpotential":{}}, ...
        ]
        """
        # total_result_value_list=[]
        # for characterization_result_list in total_characterization_result_lists_in_list:
        #     total_result_value_list.extend(list(characterization_result_dict.values()))
        
        characterization_num=len(total_characterization_result_lists_in_list)
        batch_size=len(total_characterization_result_lists_in_list[0])

        return_result_list_to_algorithm=[]
        for batch_idx in range(batch_size): # batch_size
            temp_dict={}
            for characterziation_idx in range(characterization_num): # 분석 갯수
                temp_dict.update(total_characterization_result_lists_in_list[characterziation_idx][batch_idx])
            return_result_list_to_algorithm.append(temp_dict)

        return return_result_list_to_algorithm