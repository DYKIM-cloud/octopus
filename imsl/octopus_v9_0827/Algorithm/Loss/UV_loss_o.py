#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [Loss] UV target (lambdamax or FWHM) file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-01
# TEST 2022-04-11
class LossFunctionSelf:
    def __init__(self, result_dict, target_condition_dict):
        self.target_condition_dict=target_condition_dict
        self.result_dict= result_dict
        
    def asymmetric_custom_score(self,lambdamax_bounds=(300, 850)):
        result = self.result_dict["UV_GetUVdata"]["Data"]["Property"]
        target = self.target_condition_dict["GetUVdata"]["Property"]
        ratio = self.target_condition_dict["GetUVdata"]["Ratio"]

        lambda_real = result["lambdamax"]
        lambda_target = target["lambdamax"]

        pv_real = result["p_v_ratio"]
        print(pv_real)
        pv_target = target["p_v_ratio"]

        lambda_weight = ratio["lambdamax"]
        pv_weight = ratio["p_v_ratio"]

        # λmax 정규화 비율 계산 (비대칭)
        left_span = lambda_target - lambdamax_bounds[0]
        right_span = lambdamax_bounds[1] - lambda_target

        if abs(lambda_target - lambda_real) == 0:
            lambda_term = 0.0
        elif lambda_real < lambda_target:
            lambda_term = abs(lambda_target - lambda_real) / left_span
        else:
            lambda_term = abs(lambda_target - lambda_real) / right_span

        lambda_term *= lambda_weight

        # Peak/Valley Ratio 오차 계산 (대칭 방식)
        pv_term = (pv_target - pv_real) * pv_weight

        # 전체 score
        score = -(lambda_term + pv_term)

        # 최솟값 제한
        return max(-1.0, score)
class LossFunction:
    def __init__(self, result_dict, target_condition_dict):
        self.target_condition_dict=target_condition_dict
        self.result_dict= result_dict
        """
        def lambdamaxFWHMintensityLoss(self, result_dict, target_condition_dict):
        """
    


    def lambdamaxpvLoss(self):

        """
        calculate loss value

        result_dict (dict): {"GetAbs":{"Wavelength":[...],"RawSpectrum":[...],"Property":{'lambdamax': 667.901297, 'intensity': 0.754869663, 'FWHM': 252.874914}}}
        target_condition_dict (dict): {"GetAbs":{"Property":{"lambdamax":500},"Ratio":{"lambdamax":0.9,"FWHM":0.03, "intenisty":0.07}}}

        :return optimal_value (float) and property_tuple (tuple): optimal_value
        :return total_property_dict (dict)
        """
        total_property_dict={}
        for key, each_action_target_condition_dict in self.target_condition_dict.items():
            optimal_value=0
            # key --> "GetAbs"
            # each_action_target_condition_dict --> {"Property":{"lambdamax":500,"FWHM":100},"Ratio":{"lambdamax":0.8,"FWHM":0.2}}
            target_type_list = list(each_action_target_condition_dict["Ratio"].keys()) # target_type_list --> ["lambdamax"]
            target_optimal_ratio_list = list(each_action_target_condition_dict["Ratio"].values()) # [0.9, 0.03, 0.07]
            # target_value_list = list(each_action_target_condition_dict["Property"].values()) # target_value_list --> [500]
            for target_idx, each_target_type in enumerate(target_type_list): # property 별로 loss 계산하고, optimal_value에 통합
                # target_idx --> 0, 1, 2(lambdamax or FWHM, intensity)
                # each_target_type --> "lambdamax", "FWHM", "intensity"
                if self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]==0:
                    optimal_value += -1*target_optimal_ratio_list[target_idx]
                    optimal_value=float(optimal_value)
                else:
                    if each_target_type == "lambdamax":
                        lambdamax_scaling_factor_left = each_action_target_condition_dict["Property"][each_target_type]-300
                        lambdamax_scaling_factor_right = 850-each_action_target_condition_dict["Property"][each_target_type]
                        
                        if lambdamax_scaling_factor_left>lambdamax_scaling_factor_right:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_left)*target_optimal_ratio_list[target_idx]
                        else:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_right)*target_optimal_ratio_list[target_idx]
                    elif each_target_type == "p_v_ratio":
                        optimal_value -= abs(1-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*target_optimal_ratio_list[target_idx]
                total_property_dict[each_target_type]=self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]

        return optimal_value, total_property_dict

  
