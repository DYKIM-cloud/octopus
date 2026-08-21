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
import pickle
import pandas as pd
import copy

from Algorithm.Bayesian.BOdiscreteTest import ASLdiscreteBayesianOptimization
# from Algorithm.ReactionSpace.ReactionSpace import Reactionspace
# from Algorithm.Automatic.Automatic import Automatic
from Algorithm.Loss.UV_loss import Loss
from Master.Recipe.RecipeGenerator_Class import RecipeGenerator
from Log.All_Integrated_Messenger import AlertMessage
from Log.Logging_Class import TaskLogger
from DB.DB_Class import MongoDB_Class


class JobExecution(object):
    '''
    '''
    def __init__(self, jobScript):
        # generate class variable
        self.jobScript = jobScript
        self.metadata_dict = self.jobScript["metadata"]
        self.recipe_dict = self.jobScript["recipe"]
        self.algorithm_dict = self.jobScript["algorithm"]
        
        self.TaskLogger_obj=TaskLogger(self.metadata_dict)
        self.RecipeGenerator_obj=RecipeGenerator(self.TaskLogger_obj, self.metadata_dict)
        self.DB_obj = MongoDB_Class(self.TaskLogger_obj)
        
        ### 이 부분은 jobscheduler를 위한 정의 부분 ###
        self.platform_name="JobExecution"
        self.userName=self.jobScript["metadata"]["userName"]
        self.jobTime=self.jobScript["metadata"]["jobTime"]
        self.jobID=self.jobScript["metadata"]["jobID"]
        self.jobFileName=self.jobScript["metadata"]["jobFileName"]
        self.batchSize=self.jobScript["algorithm"]["batchSize"]
        self.todayIterNum=self.jobScript["metadata"]["todayIterNum"]
        self.modeType=self.jobScript["metadata"]["modeType"]
        self.TaskLogger_obj.setCurrentPlatformName("Waiting...") # while experiment, TaskScheduler will update every process done!
        self.TaskLogger_obj.status="{}".format(self.TaskLogger_obj.current_platform_name) # in execution system
        ### 여기까지는 jobscheduler를 위한 정의 부분 ###

        # Algorithm

        # Make each model
        # Autonomous:BayesianOptimization
        if self.algorithm_dict["model"] == "BayesianOptimization": #YOO -> 이름 
            bo_obj=ASLdiscreteBayesianOptimization(self.algorithm_dict)
            self.Algorithm_obj=bo_obj
            message="[jobID={0}] Algorithm, model : {1}, batchSize : {2}".format(self.jobID, self.algorithm_dict["model"], self.algorithm_dict["batchSize"])
            self.TaskLogger_obj.info(self.platform_name, message)
        # Autonomous:ReactionSpace
        # elif self.algorithm_dict["model"] == "ReactionSpace":
        #     RS_obj = Reactionspace(self.algorithm_dict)
        #     self.Algorithm_obj=RS_obj
        #     message="[jobID={0}] Algorithm, model : {1}, batchSize : {2}".format(self.jobID, self.algorithm_dict["model"], self.algorithm_dict["batchSize"])
        #     self.TaskLogger_obj.info(self.platform_name, message)
        # Automatic
        # elif self.algorithm_dict["model"] == "Automatic":
        #     automatic_obj=Automatic(self.algorithm_dict)
        #     self.Algorithm_obj=automatic_obj
        #     message="[jobID={0}] Algorithm, model : {1}, batchSize : {2}".format(self.jobID, self.algorithm_dict["model"], self.algorithm_dict["batchSize"])
        #     self.TaskLogger_obj.info(self.platform_name, message)
        # load previous model
        elif self.algorithm_dict["previousModel"] == True:
            previous_obj=self.loadModel(self.algorithm_dict["previousModel"])
            self.Algorithm_obj=previous_obj
            message="[jobID={0}] Algorithm, model : {1}, batchSize : {2}".format(self.jobID, self.algorithm_dict["model"], self.algorithm_dict["batchSize"])
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
    
    def __writeJsonFile(self, json_path:str, recipe_template_dict:dict):
        """
        :params: json_path (str): json path

        :return: None
        """
        with open(json_path,'w') as f:
            json.dump(recipe_template_dict, f, indent=5)

    def _extractProperty(self,result_dict):
        """
        Description
        ===============
        extract property value depending on all property & intergrate inside single dict

        Params
        ---------------------
        result_dict (single dict): {"GetUVdata":{"Wavelength":[...],"RawSpectrum":[...],"Property":{'lambdamax': 300.214759, 'FWHM': 549.221933, 'intensity':0.422215354}}}
        
        Return
        -------------------
        result_list : [{'lambdamax': 300.214759, 'FWHM': 549.221933, 'intensity':0.422215354, 'overpotential':-0.542213}....]
        """
        temp_result_dict={}
        for evaluation_name, result in result_dict.items():
            temp_result_dict.update(result["Property"])
        
        return temp_result_dict

    def _extractSynthesisCondition(self, filename, iter_num, batchSize):
        start_idx=self.recipe_dict_list[0]["start_idx"]
        df=pd.read_csv(filename)
        df=df[start_idx+iter_num*batchSize: start_idx+(iter_num+1)*batchSize]
        synthesis_conidtion_list=df.to_dict('records')

        return synthesis_conidtion_list

    def _addResult(self, synthesis_condition_list, result_list):
        for idx in range(len(result_list)):
            total_result_dict=dict(synthesis_condition_list[idx], **result_list[idx])
            self.total_result_df=self.total_result_df.append(total_result_dict, ignore_index=True)

    def _saveResult(self, dirname, filename):
        if os.path.isdir(dirname) == False:
            os.makedirs(dirname)
        fname = os.path.join(dirname, filename+".csv")
        if os.path.isfile(fname):
            os.remove(fname)
        else:
            self.total_result_df.to_csv(fname)

    def _changeCurrentIterNum(self):
        """
        :params: None
        
        :return current_iter_num (int)

        current_iter_num = int(len(self.Algorithm_obj_list.res)/self.Algorithm_obj_list.batchSize)
        """
        if len(self.Algorithm_obj.res) > 0:
            current_iter_num = int(len(self.Algorithm_obj.res)/self.Algorithm_obj.batchSize)
        else:
            current_iter_num=0
        return current_iter_num
    
    def changeBatchSize(self,num):
        """
        :params num (int): set batch size
        
        :return None (int)

        self.Algorithm_obj_list.batchSize=num
        """
        self.Algorithm_obj.batchSize=num ## YOO 
    
    def RemakeResult2DBinput(self, total_characterization_result_lists_in_list):
        """
        2개 이상의 property 얻은 것을 하나의 dict로 묶어서 배치갯수만큼 

        :param total_characterization_result_lists_in_list (list) : result data list through "SchedulAllAction" via Scheduler
            ex) [
                    [{"GetUVdata":{}},{"GetUVdata":{}}, ...],
                    [{"GetElectrochemicaldata":{}},{"GetElectrochemicaldata":{}} ...],
                    ...
                ]

        :return return_result_list_to_db (list)
            ex) [
                    [{"GetUVdata":{}},{"GetElectrochemicaldata":{}}, ...],
                    [{"GetUVdata":{}},{"GetElectrochemicaldata":{}}, ...],
                    ...
                ]
        """
        characterization_num=len(total_characterization_result_lists_in_list)
        batchSize=len(total_characterization_result_lists_in_list[0])
        return_result_list_to_db=[]
        for batch_idx in range(batchSize): # batchSize
            temp_dict={}
            for characterization_idx in range(characterization_num): # 분석 갯수
                temp_dict.update(total_characterization_result_lists_in_list[characterization_idx][batch_idx])
            return_result_list_to_db.append(temp_dict)
        return return_result_list_to_db
    
    def saveDictToJSON(self, dict_obj:dict, TOTAL_DATA_FOLDER:str, file_name:str, mode_type:str):
        """
        extract action type and action data

        :param dict_obj (dict): recipe dict
        :param file_name (str): time_str=time.strftime("%Y%m%d_%H%M")
        :param mode (args): 
            if bool(mode) == False: --> just 
            elif bool(mode) == True: --> add mode[0](str, sub_dir) in path
        
        :return TOTAL_DATA_FOLDER/file_name (str): {dir}/{filename}.json
        """
        new_path = TOTAL_DATA_FOLDER+"/"+mode_type
        if os.path.isdir(new_path) == False:
            os.makedirs(new_path)
        with open(new_path+"/"+file_name, 'w') as outfile:
            json.dump(dict_obj, outfile, indent=5)

        return new_path

    def MakeAllDataforMulti(self, idx, metadata_dict, recipe_dict, result, algorithm_dict={}):
        """
        allocate synthesis sequence process in json file (recipe) depending on metadata, recipe, real_data
        
        :param metadata_dict (dict) : metadata for explaining experiment's information ( ex). StartTime, Experiment, Element, Humidity, Temperature...etc)
        :param recipe_dict (dict) : recipe information included Synthesis, Preprocess, Characterization, After
        :param result_list (dict in list) : real_data information
        :param algorithm_dict={} (dict) : algorithm information, hyparameter
            - if automaticSynthesis --> algorithm_dict == {}
            - elif autonomousSynthesis --> algorithm_dict == {...}

        :return all_data_template (dict): all_data_template
        
        all_data_template_list={
            "metadata":metadata_dict,
            "algorithm":algorithm_dict, # depending on automaticSynthesis func or autonomousSynthesis func
            "recipe":recipe_dict,
            "result":result
            // [{'MaxAbsorbance': [300.214759], 'CenterWavelength': [574.825725], 'FWHM': [549.221933], 'Integral': [0.0]}...]
        }
        """
        all_data_template={}
        copy_metadata_dict=copy.deepcopy(metadata_dict)
        copy_metadata_dict["currentBatchNum"]=idx
        all_data_template["metadata"]=copy_metadata_dict
        all_data_template["algorithm"]=algorithm_dict
        all_data_template["recipe"]=recipe_dict
        all_data_template["result"]=result
        return all_data_template
            
    def __checkIterNum(self, iter_num:int, total_iter_num:int):
        if iter_num != total_iter_num:
            pass
        elif iter_num == total_iter_num:
            Algorithm_obj_index=self.todayIterNum_list.index(iter_num)
            self.metadata_dict_list.pop(Algorithm_obj_index)
            self.Algorithm_obj_list.pop(Algorithm_obj_index)
            self.recipe_dict_list.pop(Algorithm_obj_index)
            self.algorithm_dict_list.pop(Algorithm_obj_index)
            self.config_data_list.pop(Algorithm_obj_index)
            self.TaskLogger_obj_list.pop(Algorithm_obj_index)
            self.DB_obj_list.pop(Algorithm_obj_index)
            
    def execute(self, TaskScheduler_obj):
        
        # run cycle
        self.TaskLogger_obj.info(self.platform_name, info_msg="######### Cycle start #########")
        total_iter_num=0
        # just check only in one cycle
        if self.modeType=="virtual":
            self.todayIterNum=1
        else:
            pass
            
        for iter_num in range(self.todayIterNum):
            # Modify metadata
            start_date=time.strftime("%Y%m%d_%H%M")
            start_dir_name=time.strftime("%Y%m%d")
            
            each_cycle_num=int(len(self.Algorithm_obj.res)/self.Algorithm_obj.batchSize) # reaction space 도 체커 만들어서 같은 이름으로 함수 만들고 넣으면 될듯 
            self.metadata_dict["currentIterNum"]=iter_num
            self.TaskLogger_obj.setCurrentIterNum(iter_num+1)
            self.metadata_dict["startDate"]=start_date
            
            # Suggest Next Step
            self.TaskLogger_obj.setCurrentPlatformName("Algorithm-->suggest next step")
            self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentIterNum, self.TaskLogger_obj.todayIterNum, self.TaskLogger_obj.current_platform_name) # in execution system
            
            total_next_points =[]
            total_norm_next_points=[]
            self.TaskLogger_obj.info("Algorithm", info_msg="utility_type={}, iter_num={}, batchSize={}".format(self.Algorithm_obj.utilityType, each_cycle_num, self.batchSize))
            real_next_points, norm_next_points = self.Algorithm_obj.suggestNextStep(utility_type=self.Algorithm_obj.utilityType, iter_num=each_cycle_num)# reaction space 이런 format 으로 바꾸기 
            total_next_points.extend(real_next_points)
            total_norm_next_points.extend(norm_next_points)
            
            for idx, next_point in enumerate(total_next_points):
                self.TaskLogger_obj.info("Algorithm [{}]".format(idx), info_msg="next_point {}: {}".format(idx, next_point))
            
            # Generate Recipe depending on action_sequence_list
            self.TaskLogger_obj.setCurrentPlatformName("RecipeGenerator-->generate recipe")
            self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentIterNum, self.TaskLogger_obj.todayIterNum, self.TaskLogger_obj.current_platform_name) # in execution system
            
            RecipeGenerator_obj=RecipeGenerator(self.TaskLogger_obj,self.metadata_dict)
            proc_total_recipe_template_list=[]
            for batch_idx in range(self.Algorithm_obj.batchSize):
                each_recipe=RecipeGenerator_obj.generateRecipe(self.recipe_dict, input_next_point=total_next_points[batch_idx])
                proc_total_recipe_template_list.append(each_recipe)
                self.__writeJsonFile("Test_batch_idx_{}.json".format(batch_idx), each_recipe)
                
            # Allocate hardware --> Cycle running
            self.TaskLogger_obj.setCurrentPlatformName("TaskScheduler-->schedule all action")
            self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentIterNum, self.TaskLogger_obj.todayIterNum, self.TaskLogger_obj.current_platform_name) # in execution system
            
            done_message="######### Cycle {}/{} is running #########".format(iter_num+1+each_cycle_num, self.todayIterNum+each_cycle_num)
            self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
            AlertMessage(self.TaskLogger_obj, text_content=done_message, key_path="./Log",message_platform_list=["dooray"], mode_type=self.modeType)
            return_result_type=TaskScheduler_obj.addressTask(proc_total_recipe_template_list, self.jobID, self.TaskLogger_obj, self.modeType)
            return_result_list_to_db=TaskScheduler_obj.returnResult(self.TaskLogger_obj,self.jobID)

            # generate total_data_dict (to integrate metadata_dict, algorithm_dict, recipe_dict_list, result_list)
            total_data_dict_list=[]
            for batch_idx in range(self.Algorithm_obj.batchSize):
                total_data_dict_list.append(self.MakeAllDataforMulti(idx=batch_idx, metadata_dict=self.metadata_dict,algorithm_dict=self.algorithm_dict, 
                                                recipe_dict=proc_total_recipe_template_list[batch_idx], result=return_result_list_to_db[batch_idx]))

            # save total data dict in RecipsJson folder
            self.TaskLogger_obj.setCurrentPlatformName("DB-->store in DB")
            for idx, total_data_dict in enumerate(total_data_dict_list):
                dirname="{}/DB/{}/{}/{}".format(self.metadata_dict["userName"], self.metadata_dict["subject"], start_dir_name, self.modeType)
                filename="{}_multi{}_{}_data".format(start_date, idx, iter_num)
                # for code debugging
                self.saveDictToJSON(total_data_dict, dirname, filename, self.modeType) 

            # Add DB later
            # for idx in range(len(self.DB_obj_list)):
            #     self.DB_obj.sendDocument(db_name="Data", collection_name=self.metadata_dict["element"], document=total_data_dict_list[idx])

            # Evaluation --> Loss
            # extract data to dict
            optimal_value_list=[]
            # Calculate Loss, register point and save point to csv file : Yoo 이부분 Reaction space 따로 만들어야 할듯
            self.TaskLogger_obj.setCurrentPlatformName("Loss-->calculate loss")
            self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentIterNum, self.TaskLogger_obj.todayIterNum, self.TaskLogger_obj.current_platform_name) # in execution system
            
            for batch_idx, result_dict in enumerate(return_result_list_to_db):
                Loss_obj=Loss(result_dict, self.Algorithm_obj.targetConditionDict)
                optimal_value, property_dict = getattr(Loss_obj, self.Algorithm_obj.loss)()
                optimal_value_list.append(optimal_value)
                self.TaskLogger_obj.info("Algorithm", info_msg="{} optimal_value : {}".format(batch_idx, optimal_value))

                dirname="USER/{}/DB/{}/{}/{}".format(self.metadata_dict["userName"], self.metadata_dict["subject"], start_dir_name, self.modeType)
                filename="{}_multi{}_{}_data".format(start_date, batch_idx, iter_num)
                # if self.algorithm_dict_list[idx]['model'] != "ReactionSpace":
                # self.Algorithm_obj_list[idx].registerPoint(input_next_points=[total_next_points[idx]], norm_input_next_points=[total_norm_next_points[idx]], property_list=[property_dict], input_result_list=[optimal_value_list[idx]])
                # self.Algorithm_obj_list[idx].output_space(dirname+"/loss_norm", filename)
                # self.Algorithm_obj_list[idx].output_space_realCondition(dirname+"/loss_real", filename)
                # self.Algorithm_obj_list[idx].output_space_property(dirname+"/property", filename)

            done_message="######### Cycle {}/{} is done #########".format(iter_num+1+each_cycle_num, self.todayIterNum+each_cycle_num)
            self.TaskLogger_obj.info(self.platform_name, info_msg=done_message)
            AlertMessage(self.TaskLogger_obj, done_message,key_path="./Log", message_platform_list=["dooray"], mode_type=self.modeType)
            
            finish_date=time.strftime("%Y%m%d_%H%M")
            self.metadata_dict["finishDate"]=finish_date

            # Save our model : 수정하기 
            self.TaskLogger_obj.setCurrentPlatformName("Algorithm-->save model")
            self.TaskLogger_obj.status="{}/{}:{}".format(self.TaskLogger_obj.currentIterNum, self.TaskLogger_obj.todayIterNum, self.TaskLogger_obj.current_platform_name) # in execution system
            
            self.savedModel(directory_path="USER/{}/SaveModel/{}/{}/{}".format(self.metadata_dict["userName"], self.metadata_dict["subject"], start_dir_name, self.modeType), 
                                                filename="{}_multi{}_{}_obj".format(start_date, idx, each_cycle_num), mode_type=self.modeType)
            self.TaskLogger_obj.info("Algorithm", info_msg="Save our model object, filename={}".format("{}_multi{}_{}_obj".format(start_date, idx, each_cycle_num)))

        # All cycle is done
        self.TaskLogger_obj.info(self.platform_name, info_msg="######### All Cycle is done #########")
        AlertMessage(self.TaskLogger_obj, text_content="All Cycle is done", key_path="./Log", message_platform_list=["dooray"], mode_type=self.modeType)
        
        return True
    
    def hold(self):
        pass

    def savedModel(self, directory_path, filename='bo_obj', mode_type="virtual"):
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
        if mode_type=="real":
            if os.path.isdir(directory_path) == False:
                os.makedirs(directory_path)
            fname = os.path.join(directory_path, filename+".pickle")
            with open(fname, 'wb') as f:
                pickle.dump(self.Algorithm_obj, f)
        else:
            if os.path.isdir(directory_path) == False:
                os.makedirs(directory_path)
            fname = os.path.join(directory_path, filename+".pickle")
            with open(fname, 'wb') as f:
                pickle.dump(self.Algorithm_obj, f)

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