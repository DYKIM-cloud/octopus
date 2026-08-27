#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @brief    [Execution file] 
# @version  1_1: 
#   author  Nayeon Kim (kny@kist.re.kr) // TEST    2023-04-01
# @version  2_1: 
#   author  Hyuk Jun Yoo (yoohj9475@kist.re.kr) // TEST    2023-xx-xx

import os, sys
import json
import time
import datetime
import pickle
import pandas as pd
import copy

from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization
# from Algorithm.ReactionSpace.ReactionSpace import Reactionspace
from Algorithm.Automatic.Automatic import Automatic
from Algorithm.Loss.UV_loss import Loss
from Log.DigitalSecretary import AlertMessage
from Log.Logging_Class import TaskLogger
from DB.DB_Class import MongoDB_Class
from Master.Task.TCP import TCP_Class


# def alertError(func):
#     def wrapper():
#         try:
#             func()
#         except Exception as error_message:
#             AlertMessage(text_content=error_message, key_path="./Log",message_platform_list=["dooray"], mode_type="real")
#             raise Exception(error_message)
#     return wrapper

class JobExecution(object):
    '''
    '''
    def __init__(self, jobScript):
        # generate class variable
        self.jobScript = jobScript
        self.metadata_dict = self.jobScript["metadata"]
        self.algorithm_dict = self.jobScript["algorithm"]
        self.process_dict = self.jobScript["process"]
        
        ### 이 부분은 jobscheduler를 위한 정의 부분 ###
        self.platform_name="JobExecution"
        
        self.metadata_dict["jobStatus"]="Waiting..."
        self.metadata_dict["temperature"]=25
        self.metadata_dict["humidity"]="68%"
        # check submission time
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M:%S")
        self.metadata_dict["jobSubmitTime"]=current_time
        self.jobSubmissionTime=time.time()

        # for key, value in self.metadata_dict.items():
        #     setattr(self, key, value)
        # for key, value in self.algorithm_dict.items():
        #     setattr(self, key, value)
        # # self.userName=self.jobScript["metadata"]["userName"]
        # # self.jobTime=self.jobScript["metadata"]["jobTime"]
        # # self.jobID=self.jobScript["metadata"]["jobID"]
        # # self.jobFileName=self.jobScript["metadata"]["jobFileName"]
        # # self.totalCycleNum=self.jobScript["metadata"]["totalCycleNum"]
        # # self.modeType=self.jobScript["metadata"]["modeType"]
        # # self.batchSize=self.jobScript["algorithm"]["batchSize"]
        # # self.model=self.jobScript["algorithm"]["model"]

        ### 여기까지는 jobscheduler를 위한 정의 부분 ###
        self.TaskLogger_obj=TaskLogger(self.metadata_dict, self.metadata_dict.userName)
        self.TaskLogger_obj.setCurrentPlatformName("JobExecution-->Submitted & Waiting") # while experiment, TaskScheduler will update every process done!
        self.TaskLogger_obj.status="{}".format(self.TaskLogger_obj.current_platform_name) # in execution system
        self.metadata_dict["jobStatus"]="{}".format(self.TaskLogger_obj.current_platform_name) # in execution system
        self.DB_obj = MongoDB_Class(self.TaskLogger_obj)
        self.tcp_obj=TCP_Class()

        # Algorithm

        # Make each model
        # Autonomous:BayesianOptimization
        if self.model == "BayesianOptimization": #YOO -> 이름 
            self.Algorithm_obj=ASLdiscreteBayesianOptimization(self.algorithm_dict)
            message="[jobID={0}] Algorithm, model : {1}".format(self.metadata_dict.jobID, self.algorithm_dict.model)
            self.TaskLogger_obj.info(self.platform_name, message)
        # Autonomous:ReactionSpace
        # elif self.algorithm_dict.model == "ReactionSpace":
        #     RS_obj = Reactionspace(self.algorithm_dict)
        #     self.Algorithm_obj=RS_obj
        #     message="[jobID={0}] Algorithm, model : {1}".format(self.metadata_dict.jobID, self.algorithm_dict.model)
        #     self.TaskLogger_obj.info(self.platform_name, message)
        # load previous model
        elif self.algorithm_dict.model == "PreviousModel":
            self.Algorithm_obj=self.loadModel(self.algorithm_dict.modelPath)
            message="[jobID={0}] Algorithm, model : {1}".format(self.metadata_dict.jobID, self.algorithm_dict.model)
            self.TaskLogger_obj.info(self.platform_name, message)
        elif self.algorithm_dict.model == "Automatic":
            self.Algorithm_obj=Automatic(self.algorithm_dict)
            message="[jobID={0}] Algorithm, model : {1}".format(self.metadata_dict.jobID, self.algorithm_dict.model)
            self.TaskLogger_obj.info(self.platform_name, message)
        else:
            raise ValueError("job script file error")

    def __openJsonFile(self, json_path:str):
        """
        :params json_path (str): json path

        :return json_data (dict) json_data
        """
        with open(json_path, "r") as f:
            json_data = json.load(f)
        return json_data
    
    def __writeJsonFile(self, json_path:str, process_template_dict:dict):
        """
        :params: json_path (str): json path

        :return: None
        """
        with open(json_path,'w') as f:
            json.dump(process_template_dict, f, indent=5)

    # def _extractProperty(self,result_dict:dict):
    #     """
    #     Description
    #     ===============
    #     extract property value depending on all property & intergrate inside single dict

    #     Params
    #     ---------------------
    #     result_dict (single dict): {"GetUVdata":{"Wavelength":[...],"RawSpectrum":[...],"Property":{'lambdamax': 300.214759, 'FWHM': 549.221933, 'intensity':0.422215354}}}
        
    #     Return
    #     -------------------
    #     result_list : [{'lambdamax': 300.214759, 'FWHM': 549.221933, 'intensity':0.422215354, 'overpotential':-0.542213}....]
    #     """
    #     temp_result_dict={}
    #     for evaluation_name, result in result_dict.items():
    #         temp_result_dict.update(result["Property"])
        
    #     return temp_result_dict

    # def _extractSynthesisCondition(self, filename, iter_num, batchSize):
    #     start_idx=self.process_dict_list[0]["start_idx"]
    #     df=pd.read_csv(filename)
    #     df=df[start_idx+iter_num*batchSize: start_idx+(iter_num+1)*batchSize]
    #     synthesis_conidtion_list=df.to_dict('records')

    #     return synthesis_conidtion_list

    # def _addResult(self, synthesis_condition_list, result_list):
    #     for idx in range(len(result_list)):
    #         total_result_dict=dict(synthesis_condition_list[idx], **result_list[idx])
    #         self.total_result_df=self.total_result_df.append(total_result_dict, ignore_index=True)

    # def _saveResult(self, dirname, filename):
    #     if os.path.isdir(dirname) == False:
    #         os.makedirs(dirname)
    #     fname = os.path.join(dirname, filename+".csv")
    #     if os.path.isfile(fname):
    #         os.remove(fname)
    #     else:
    #         self.total_result_df.to_csv(fname)
    
    def saveDictToJSON(self, dict_obj:dict, TOTAL_DATA_FOLDER:str, file_name:str):
        """
        extract task type and task data

        :param dict_obj (dict): process dict
        :param file_name (str): time_str=time.strftime("%Y%m%d_%H%M")
        :param mode (args): 
            if bool(mode) == False: --> just 
            elif bool(mode) == True: --> add mode[0](str, sub_dir) in path
        
        :return TOTAL_DATA_FOLDER/file_name (str): {dir}/{filename}.json
        """
        if os.path.isdir(TOTAL_DATA_FOLDER) == False:
            os.makedirs(TOTAL_DATA_FOLDER)
        with open(TOTAL_DATA_FOLDER+"/"+file_name+".json", 'w') as outfile:
            json.dump(dict_obj, outfile, indent=5)
        print(TOTAL_DATA_FOLDER)

        return TOTAL_DATA_FOLDER

    def MakeAllDataforMulti(self, idx:int, metadata_dict:dict, process_dict:dict, result:list, algorithm_dict:dict):
        """
        allocate synthesis sequence process in json file (process) depending on metadata, process, real_data
        
        :param metadata_dict (dict) : metadata for explaining experiment's information ( ex). StartTime, Experiment, Element, Humidity, Temperature...etc)
        :param process_dict (dict) : process information included Synthesis, Preprocess, Characterization
        :param result_list (dict in list) : real_data information
        :param algorithm_dict={} (dict) : algorithm information, hyparameter
            - if automaticSynthesis --> algorithm_dict == {}
            - elif autonomousSynthesis --> algorithm_dict == {...}

        :return all_data_template (dict): all_data_template
        
        all_data_template_list={
            "metadata":metadata_dict,
            "algorithm":algorithm_dict, # depending on automaticSynthesis func or autonomousSynthesis func
            "process":process_dict,
            "result":result
            // [{'MaxAbsorbance': [300.214759], 'CenterWavelength': [574.825725], 'FWHM': [549.221933], 'Integral': [0.0]}...]
        }
        """
        all_data_template={}
        copy_metadata_dict=copy.deepcopy(metadata_dict)
        copy_metadata_dict["currentBatchNum"]=idx
        all_data_template["metadata"]=copy_metadata_dict
        all_data_template["algorithm"]=algorithm_dict
        all_data_template["process"]=process_dict
        all_data_template["result"]=result
        return all_data_template

    # @alertError    
    def execute(self, TaskScheduler_obj:object, ProcessGenerator_obj:object, ResourceManager_obj:object):
        # run cycle
        self.TaskLogger_obj.info(self.platform_name, info_msg="######### Cycle start #########")
        # total_iter_num=0
        # just check only in one cycle
        # if self.modeType=="virtual":
        #     self.totalCycleNum=1
        # else:
        #     pass
        if self.model != "Automatic":
            for iter_num in range(self.totalCycleNum):
                # Modify metadata
                self.totalExperimentNum=self.batchSize*self.totalCycleNum
                self.TaskLogger_obj.setTotalExperimentNum(self.totalExperimentNum)
                # start_date=time.strftime("%Y%m%d_%H%M%S")
                # start_dir_name=time.strftime("%Y%m%d")
                # self.metadata_dict["startDate"]=start_date
                start_date=time.time()
                self.metadata_dict["waitingTime"]=start_date-self.jobSubmissionTime
                self.metadata_dict[]=time.strftime("%Y%m%d_%H%M%S")
                
                # Suggest Next Step
                self.TaskLogger_obj.setCurrentPlatformName("{}-->suggest next step".format(self.model))
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                self.jobStatus="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                
                self.TaskLogger_obj.info(self.model, info_msg="batchSize={}".format(self.batchSize))
                total_next_points, total_norm_next_points = self.Algorithm_obj.suggestNextStep()# reaction space 이런 format 으로 바꾸기 
                
                for idx, next_point in enumerate(total_next_points):
                    self.TaskLogger_obj.info("Algorithm [{}]".format(idx), info_msg="next_point {}: {}".format(idx, next_point))
                
                # Generate Recipe depending on Task_sequence_list
                self.TaskLogger_obj.setCurrentPlatformName("ProcessGenerator-->generate process")
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                self.jobStatus="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                
                total_process_template_list=[]
                for batch_idx, total_next_point in enumerate(total_next_points):
                    each_process=ProcessGenerator_obj.generateRecipe(self.process_dict, input_next_point=total_next_point)
                    total_process_template_list.append(each_process)
                    self.__writeJsonFile("Test_{}_idx_{}.json".format(self.model, batch_idx), each_process)
                self.TaskLogger_obj.info("ProcessGenerator", info_msg="Allocate all of process based on job script!")
                    
                # Allocate hardware --> Cycle running
                self.TaskLogger_obj.setCurrentPlatformName("TaskScheduler-->schedule all Task")
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                self.jobStatus="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                
                done_message="######### [{}-{}] Cycle {}/{} is running #########".format(self.subject, self.userName, iter_num+1, self.totalCycleNum)
                self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
                AlertMessage(text_content=done_message, key_path="./Log",message_platform_list=["dooray"], mode_type=self.modeType)
                return_result_list_to_db=TaskScheduler_obj.scheduleAllTask(total_process_template_list, self.jobID, self.TaskLogger_obj, self.modeType)

                # generate total_data_dict (to integrate metadata_dict, algorithm_dict, process_dict_list, result_list)
                total_data_dict_list=[]
                for batch_idx in range(len(total_process_template_list)):
                    total_data_dict_list.append(self.MakeAllDataforMulti(idx=batch_idx, metadata_dict=self.metadata_dict,algorithm_dict=self.algorithm_dict, 
                                                    process_dict=total_process_template_list[batch_idx], result=return_result_list_to_db[batch_idx]))

                # save total data dict in RecipsJson folder
                self.TaskLogger_obj.setCurrentPlatformName("DB-->store in DB")
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                self.jobStatus="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                for idx, total_data_dict in enumerate(total_data_dict_list):
                    dirname="USER/{}/DB/{}/{}/{}".format(self.userName, self.subject, start_dir_name, self.modeType)
                    filename="{}_{}_{}_data".format(start_date, idx, iter_num)
                    # for code debugging
                    self.saveDictToJSON(total_data_dict, dirname, filename) 

                # Add DB later
                # for idx in range(len(self.DB_obj_list)):
                #     self.DB_obj.sendDocument(db_name="Data", collection_name=self.metadata_dict["element"], document=total_data_dict_list[idx])

                # Evaluation --> Loss
                # extract data to dict
                optimal_value_list=[]
                property_dict_list=[]
                # Calculate Loss, register point and save point to csv file : Yoo 이부분 Reaction space 따로 만들어야 할듯
                self.TaskLogger_obj.setCurrentPlatformName("Loss-->calculate loss")
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                self.jobStatus="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                
                for batch_idx, result_dict in enumerate(return_result_list_to_db):
                    Loss_obj=Loss(result_dict, self.Algorithm_obj.targetConditionDict)
                    optimal_value, property_dict = getattr(Loss_obj, self.Algorithm_obj.loss)()
                    optimal_value_list.append(optimal_value)
                    property_dict_list.append(property_dict)
                    self.TaskLogger_obj.info("Algorithm", info_msg="{} optimal_value : {}".format(batch_idx, optimal_value))

                dirname="USER/{}/DB/{}/{}/{}".format(self.userName, self.subject, start_dir_name, self.modeType)
                filename="{}_{}_data".format(start_date, iter_num)
                self.Algorithm_obj.registerPoint(input_next_points=total_next_points, norm_input_next_points=total_norm_next_points, property_list=property_dict_list, input_result_list=optimal_value_list)
                self.Algorithm_obj.output_space(dirname+"/loss_norm", filename)
                self.Algorithm_obj.output_space_realCondition(dirname+"/loss_real", filename)
                self.Algorithm_obj.output_space_property(dirname+"/property", filename)

                done_message="######### [{}-{}] Cycle {}/{} is done #########".format(self.subject, self.userName, iter_num+1, self.totalCycleNum)
                self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
                AlertMessage(done_message,key_path="./Log", message_platform_list=["dooray"], mode_type=self.modeType)
                
                finish_date=time.time()
                self.metadata_dict["jobTurnAroundTime(sec)"]=finish_date-start_date

                # Save our model : 수정하기 
                self.TaskLogger_obj.setCurrentPlatformName("Algorithm-->save model")
                self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentExperimentNum, self.TaskLogger_obj.totalExperimentNum, self.TaskLogger_obj.current_platform_name) # in execution system
                each_cycle_num=int(len(self.Algorithm_obj.res)/self.batchSize) # reaction space 도 체커 만들어서 같은 이름으로 함수 만들고 넣으면 될듯 
                self.savedModel(directory_path="USER/{}/SaveModel/{}/{}/{}".format(self.userName, self.subject, start_dir_name, self.modeType), 
                                                    filename="{}_{}_obj".format(start_date, each_cycle_num))
                self.TaskLogger_obj.info("Algorithm", info_msg="Save our model object, filename={}".format("{}_{}_obj".format(start_date, each_cycle_num)))

            # All cycle is done
            done_message="######### [{}-{}] All Cycle is done #########".format(self.subject, self.userName)
            self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
            AlertMessage(done_message, key_path="./Log", message_platform_list=["dooray"], mode_type=self.modeType)
            current_time = now.strftime("%Y-%m-%d %H:%M:%S")
            
        
        elif self.model=="Automatic":
            # Modify metadata
            start_date=time.time()
            start_dir_name=time.strftime("%Y%m%d")
            # self.metadata_dict["startDate"]=start_date
            # Suggest Next Step
            total_next_points= self.Algorithm_obj.suggestNextStep()# reaction space 이런 format 으로 바꾸기 
            currentExperimentNum=0
            self.TaskLogger_obj.setCurrentExperimentNum(currentExperimentNum)
            self.TaskLogger_obj.setTotalExperimentNum(self.totalExperimentNum)
            self.TaskLogger_obj.info(self.model, info_msg="total experiments={}".format(self.totalExperimentNum))
            self.TaskLogger_obj.setCurrentPlatformName("{}-->suggest next step".format(self.model))
            self.TaskLogger_obj.status="{}:{}".format(self.TaskLogger_obj.current_platform_name, self.totalExperimentNum) # in execution system
            # log our total_next_points
            for idx, next_point in enumerate(total_next_points):
                self.TaskLogger_obj.info("{} [{}]".format(self.model, idx), info_msg="next_point {}: {}".format(idx, next_point))
            # Generate Recipe depending on task_sequence_list
            self.TaskLogger_obj.setCurrentPlatformName("ProcessGenerator-->generate recipe")
            self.TaskLogger_obj.status="{}:{}".format(self.TaskLogger_obj.current_platform_name, self.totalExperimentNum) # in execution system
            # generate recipe
            total_process_template_list=[]
            for batch_idx in range(self.totalExperimentNum):
                next_point={}
                try:
                    next_point=total_next_points[batch_idx]
                except Exception as e:
                    pass
                each_process=ProcessGenerator_obj.generateRecipe(self.process_dict, input_next_point=next_point)
                total_process_template_list.append(each_process)
                self.__writeJsonFile("Test_{}_idx_{}.json".format(self.model, batch_idx), each_process)
            self.TaskLogger_obj.info("ProcessGenerator", info_msg="Allocate all of process based on job script!")
            # Allocate hardware --> Cycle running
            self.TaskLogger_obj.setCurrentPlatformName("TaskScheduler-->schedule all task")
            self.TaskLogger_obj.status="{}:{}".format(self.TaskLogger_obj.current_platform_name, self.totalExperimentNum) # in execution system
            
            done_message="######### [{}-{}] Experiment {} is running #########".format(self.subject, self.userName, self.totalExperimentNum)
            self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
            AlertMessage(text_content=done_message, key_path="./Log",message_platform_list=["dooray"], mode_type=self.modeType)
            return_result_list_to_db=TaskScheduler_obj.scheduleAllTask(total_process_template_list, self.jobID, self.TaskLogger_obj, self.modeType)

            # generate total_data_dict (to integrate metadata_dict, algorithm_dict, process_dict_list, result_list)
            total_data_dict_list=[]
            for batch_idx in range(len(total_process_template_list)):
                total_data_dict_list.append(self.MakeAllDataforMulti(idx=batch_idx, metadata_dict=self.metadata_dict,algorithm_dict=self.algorithm_dict, 
                                                process_dict=total_process_template_list[batch_idx], result=return_result_list_to_db[batch_idx]))

            # save total data dict in RecipsJson folder
            self.TaskLogger_obj.setCurrentPlatformName("DB-->store in DB")
            for idx, total_data_dict in enumerate(total_data_dict_list):
                dirname="USER/{}/DB/{}/{}/{}".format(self.metadata_dict["userName"], self.metadata_dict["subject"], start_dir_name, self.modeType)
                filename="{}_{}_data".format(start_date, idx)
                # for code debugging
                self.saveDictToJSON(total_data_dict, dirname, filename) 

            # Add DB later
            # self.DB_obj.sendDocument(db_name="Data", collection_name=self.metadata_dict["element"], document=total_data_dict_list[idx])

            done_message="######### [{}-{}] Experiment {} is done #########".format(self.subject, self.userName, self.totalExperimentNum)
            self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
            AlertMessage(done_message,key_path="./Log", message_platform_list=["dooray"], mode_type=self.modeType)
            
            finish_date=time.time()
            self.metadata_dict["turnAroundTime(sec)"]=finish_date-start_date

        return True
    
    # @alertError
    def delete(self):
        command_bytes =str.encode("qdel/{}".format(self.jobID))
        res_msg=self.tcp_obj.callServer_qcommand(command_bytes)
        
        return res_msg

    # @alertError
    def hold(self):
        command_bytes =str.encode("qhold/{}".format(self.jobID))
        res_msg=self.tcp_obj.callServer_qcommand(command_bytes)
        
        return res_msg
    
    # @alertError
    def restart(self):
        command_bytes =str.encode("qrestart/{}".format(self.jobID))
        res_msg=self.tcp_obj.callServer_qcommand(command_bytes)
        
        return res_msg

    # @alertError
    def savedModel(self, directory_path, filename='bo_obj'):
        """
        save ML model to use already fitted model later.
        
        Arguments
        ---------
        directory_path (str)
        model_index (int) : order of model object
        filename='bo_obj' (str)
        
        Returns
        -------
        return None
        """
        if os.path.isdir(directory_path) == False:
            os.makedirs(directory_path)
        fname = os.path.join(directory_path, filename+".pickle")
        with open(fname, 'wb') as f:
            pickle.dump(self.Algorithm_obj, f)

    # @alertError
    def loadModel(self, path):
        """
        load ML model to use already fitted model later depending on filename.
        
        Arguments
        ---------
        path (str)
        
        Returns
        -------
        return model_obj : loaded_model
        """

        try:
            with open(path, 'rb') as f:
                model_obj = pickle.load(f)
        except FileNotFoundError:
            raise FileNotFoundError("File is not existed")

        return model_obj
    
if __name__=="__main__":
    config_json_path = ["/home/sdl-main/catkin_ws/src/doosan-robot/config/config_example/Automatic_RS.json"]
    
    platform_name = "[KIST CSRC] Autonomous Laboratory"
    mode_type="real"
    asl_obj = JobExecution()
    asl_obj.execute()