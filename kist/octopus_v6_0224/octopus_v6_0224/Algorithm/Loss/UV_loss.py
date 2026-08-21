#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [Loss] UV target (lambdamax or FWHM) file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-01
# TEST 2022-04-11
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
            print(self.result_dict)
            target_lambdamax_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-each_action_target_condition_dict["Property"]["lambdamax"]))
            target_nearlambdamax_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-(each_action_target_condition_dict["Property"]["lambdamax"]-20)))
            left_limit_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-410))
            right_limit_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-600))
            target_lambdamax_rawspectrum = self.result_dict["UV_"+key]["Data"]["RawSpectrum"][self.result_dict["UV_"+key]["Data"]["Wavelength"].index(target_lambdamax_wavelength)]
            target_nearlambdamax_rawspectrum = self.result_dict["UV_"+key]["Data"]["RawSpectrum"][self.result_dict["UV_"+key]["Data"]["Wavelength"].index(target_nearlambdamax_wavelength)]
            left_limit_rawspectrum = self.result_dict["UV_"+key]["Data"]["RawSpectrum"][self.result_dict["UV_"+key]["Data"]["Wavelength"].index(left_limit_wavelength)]
            right_limit_rawspectrum = self.result_dict["UV_"+key]["Data"]["RawSpectrum"][self.result_dict["UV_"+key]["Data"]["Wavelength"].index(right_limit_wavelength)]
            rawspectrum_ratio = (target_nearlambdamax_rawspectrum-target_lambdamax_rawspectrum)/(left_limit_rawspectrum-right_limit_rawspectrum)
            for target_idx, each_target_type in enumerate(target_type_list): # property 별로 loss 계산하고, optimal_value에 통합
                # target_idx --> 0, 1, 2(lambdamax or FWHM, intensity)
                # each_target_type --> "lambdamax", "FWHM", "intensity"
                if self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]==0:
                    
                    # 전체 abs 증가량, 즉 410~600nm 사이의 증가량과 lambdamax~lambdamax-20 nm 사이의 증가량을 비교
                    
                    if rawspectrum_ratio > 0.2 or left_limit_rawspectrum == right_limit_rawspectrum: #그 동안의 결과들로 보아, 해당 값이 0.2 이상이면 최적값과 가까운 condition이 아니라고 판단
                        optimal_value += -1.5
                    else:
                        optimal_value += -1-2.5*rawspectrum_ratio
                    
                    optimal_value=float(optimal_value)
                else:
                    if each_target_type == "lambdamax":
                        lambdamax_scaling_factor_left = each_action_target_condition_dict["Property"][each_target_type]-300
                        lambdamax_scaling_factor_right = 850-each_action_target_condition_dict["Property"][each_target_type]
                        
                        if lambdamax_scaling_factor_left>lambdamax_scaling_factor_right:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_left)*(1-target_optimal_ratio_list[target_idx])
                        else:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_right)*(1-target_optimal_ratio_list[target_idx])
                    elif each_target_type == "p_v_ratio'":
                        optimal_value -= abs(1-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*(1-target_optimal_ratio_list[target_idx])
                total_property_dict[each_target_type]=self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]

        return optimal_value, total_property_dict