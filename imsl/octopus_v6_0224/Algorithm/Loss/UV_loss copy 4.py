#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [Loss] UV target (lambdamax or FWHM) file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-01
# TEST 2022-04-11
import numpy as np
class LossFunctionSelf:
    def __init__(self, result_dict, target_condition_dict):
        self.target_condition_dict=target_condition_dict
        self.result_dict= result_dict
        
    def asymmetric_custom_score_Abs(self,lambdamax_bounds=(300, 850)):
        result = self.result_dict["UV_GetUVdata"]["Data"]["Property"]
        target = self.target_condition_dict["GetUVdata"]["Property"]
        ratio = self.target_condition_dict["GetUVdata"]["Ratio"]

        lambda_real = result["lambdamax"]
        lambda_target = target["lambdamax"]

        pv_real = result["p_v_ratio"]
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
    
    def asymmetric_custom_score_pl(self, lambdamax_bounds=(300, 850)):
        result = self.result_dict["PL_GetPl"]["Data"]["Property"]
        target = self.target_condition_dict["PL_GetPl"]["Property"]
        ratio = self.target_condition_dict["PL_GetPl"]["Ratio"]

        score = 0.0

        # ========== λmax 항목 ==========
        lambda_real = result.get("lambdamax", 0)
        lambda_target = target.get("lambdamax", 0)
        lambda_weight = ratio.get("lambdamax", 0)

        if lambda_real == 0:
            lambda_term = 1.0  # 최대 패널티
        else:
            left_span = lambda_target - lambdamax_bounds[0]
            right_span = lambdamax_bounds[1] - lambda_target
            span = left_span if lambda_real < lambda_target else right_span
            lambda_term = abs(lambda_target - lambda_real) / span
        print(f'lambda:{lambda_term}')
        score += lambda_term * lambda_weight

        # ========== Intensity 항목 ==========
        intensity_real = result.get("intensity", 0)
        intensity_target = target.get("intensity", 1)  # 기본값 1으로 두는 게 일반적
        intensity_weight = ratio.get("intensity", 0)

        if intensity_real == 0:
            intensity_term = 1.0
        else:
            intensity_term = abs(intensity_target - intensity_real) / intensity_target
        print(f'intensity:{intensity_term}')
        score += intensity_term * intensity_weight

        # ========== FWHM 항목 ==========
        fwhm_real = result.get("FWHM", 0)
        fwhm_target = target.get("FWHM", 1)
        fwhm_weight = ratio.get("FWHM", 0)

        if fwhm_real == 0:
            fwhm_term = 1.0
        elif fwhm_real <= fwhm_target:
            fwhm_term = 0.0  # 목표보다 작거나 같으면 완벽
        else:
            fwhm_term = (fwhm_real - fwhm_target) / ((lambdamax_bounds[1]-lambdamax_bounds[0]) / 2)
        print(f'fwhm:{fwhm_term}')
        score += fwhm_term * fwhm_weight

        # ========= 총합 및 범위 제한 =========
        final_score = -score  
        return max(-1.0, final_score)
class LossFunction:
    def __init__(self, result_dict, target_condition_dict):
        self.target_condition_dict=target_condition_dict
        self.result_dict= result_dict
        """
        def lambdamaxFWHMintensityLoss(self, result_dict, target_condition_dict):
        """
    
    def getxmax(self, rawSpectrum):
        """
        Find max Y in [min_wl, min_wl+150]
        """
        wavelengths = np.array(rawSpectrum[0])
        intensities = np.array(rawSpectrum[1])

        # Step 1: 찾기
        mask1 = (wavelengths >= 350) & (wavelengths <= 500)
        if not np.any(mask1):
            raise ValueError("No data points in first search window.")

        sub_wl = wavelengths[mask1]
        sub_int = intensities[mask1]
        max_idx = np.argmax(sub_int) 
        x_max = sub_wl[max_idx]

        return x_max

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
            #print(self.result_dict)
            target_lambdamax_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-each_action_target_condition_dict["Property"]["lambdamax"]))
            target_nearlambdamax_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-(each_action_target_condition_dict["Property"]["lambdamax"]-20)))
            rawSpectrum = [self.result_dict["UV_"+key]["Data"]["Wavelength"],self.result_dict["UV_"+key]["Data"]["RawSpectrum"]]
            x_max = self.getxmax(rawSpectrum)
            left_limit_wavelength = min(self.result_dict["UV_"+key]["Data"]["Wavelength"], key= lambda x:abs(x-x_max))
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
                    
                    # 전체 abs 증가량, 즉 절삭한 곳~600nm 사이의 증가량과 lambdamax~lambdamax-20 nm 사이의 증가량을 비교
                    
                    if rawspectrum_ratio > 0.2 or left_limit_rawspectrum == right_limit_rawspectrum: #그 동안의 결과들로 보아, 해당 값이 0.2 이상이면 최적값과 가까운 condition이 아니라고 판단
                        optimal_value += -1.5*target_optimal_ratio_list[target_idx]
                        #print('1')
                    elif rawspectrum_ratio <= 0:
                        optimal_value = -1.5
                        #print('2')
                    else:
                        optimal_value += -0.25-5*rawspectrum_ratio*target_optimal_ratio_list[target_idx]
                        #print('3')

                    if optimal_value < -1.5:
                        optimal_value = -1.5
                        #print('4')
                    
                    optimal_value=float(optimal_value)
                else:
                    if each_target_type == "lambdamax":
                        lambdamax_scaling_factor_left = each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Wavelength"][0]
                        lambdamax_scaling_factor_right = self.result_dict["UV_"+key]["Data"]["Wavelength"][len(self.result_dict["UV_"+key]["Data"]["Wavelength"])-1]-each_action_target_condition_dict["Property"][each_target_type]
                        lambda_value =0
                        if (each_action_target_condition_dict["Property"][each_target_type] - self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]) == 0:
                            optimal_value -= 0
                            #print('5')

                        elif self.result_dict["UV_"+key]["Data"]["Property"][each_target_type] < each_action_target_condition_dict["Property"][each_target_type]:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type] - self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]) / lambdamax_scaling_factor_left*(target_optimal_ratio_list[target_idx])
                            #print('6')
                            #optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_right)*(1-target_optimal_ratio_list[target_idx])
                        else:
                            #print('7')
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type] - self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]) / lambdamax_scaling_factor_right*(target_optimal_ratio_list[target_idx])
                    elif each_target_type == "p_v_ratio":
                        #optimal_value -= abs((each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]))**2/self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]*(1-target_optimal_ratio_list[target_idx])
                        #optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*(1-target_optimal_ratio_list[target_idx])
                        #optimal_value -= abs(((each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]))/self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*(1-target_optimal_ratio_list[target_idx])
                        #optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*(target_optimal_ratio_list[target_idx])
                        optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/each_action_target_condition_dict["Property"][each_target_type]*(target_optimal_ratio_list[target_idx])
                        #print('8')
                        #optimal_value -= target_optimal_ratio_list[target_idx]
                total_property_dict[each_target_type]=self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]
        return optimal_value, total_property_dict
    '''
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
                        
                        if each_action_target_condition_dict["Property"][each_target_type] == self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]:
                            pass
                        elif each_action_target_condition_dict["Property"][each_target_type] < self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_left)*target_optimal_ratio_list[target_idx]
                        else:
                            optimal_value -= abs(each_action_target_condition_dict["Property"][each_target_type]-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])/(lambdamax_scaling_factor_right)*target_optimal_ratio_list[target_idx]
                    elif each_target_type == "p_v_ratio":
                        optimal_value -= abs(1-self.result_dict["UV_"+key]["Data"]["Property"][each_target_type])*target_optimal_ratio_list[target_idx]
                total_property_dict[each_target_type]=self.result_dict["UV_"+key]["Data"]["Property"][each_target_type]

        return optimal_value, total_property_dict

'''  
    def lambdamaxFWHMIntensityLoss(self):
        """
        Calculate weighted loss value from lambdamax, intensity, and FWHM.

        result_dict (dict): 
            {"GetAbs":{"Wavelength":[...],
                    "RawSpectrum":[...],
                    "Property":{'lambdamax': 667.9, 'intensity': 0.75, 'FWHM': 252.8}}}

        target_condition_dict (dict): 
            {"GetAbs":{
                "Property":{"lambdamax":500, "intensity":1.0, "FWHM":100},
                "Ratio":{"lambdamax":0.9, "intensity":0.07, "FWHM":0.03}
            }}

        :return: optimal_value (float), total_property_dict (dict)
        """
        total_property_dict = {}
        for key, each_action_target_condition_dict in self.target_condition_dict.items():
            optimal_value = 0
            target_type_list = list(each_action_target_condition_dict["Ratio"].keys())
            target_optimal_ratio_list = list(each_action_target_condition_dict["Ratio"].values())

            for target_idx, each_target_type in enumerate(target_type_list):
                result_value = self.result_dict["PL_GetPl"]["Data"]["Property"].get(each_target_type, 0)
                target_value = each_action_target_condition_dict["Property"].get(each_target_type, 0)
                weight = target_optimal_ratio_list[target_idx]

                # 0인 경우 패널티
                if result_value == 0:
                    optimal_value += -1 * weight
                else:
                    if each_target_type == "lambdamax":
                        lambdamax_scaling_left = target_value - 300
                        lambdamax_scaling_right = 850 - target_value
                        #scale = lambdamax_scaling_left if lambdamax_scaling_left > lambdamax_scaling_right else lambdamax_scaling_right
                        scale = lambdamax_scaling_left if target_value > result_value else lambdamax_scaling_right
                        loss = abs(target_value - result_value) / scale
                        #print(loss)
                        optimal_value -= loss * weight

                    elif each_target_type == "intensity":
                        # normalized absolute error
                        loss = abs(target_value - result_value) / target_value
                        #print(loss)
                        optimal_value -= loss * weight

                    elif each_target_type == "FWHM":
                        # normalized absolute error
                        loss = abs(target_value - result_value) / ((self.result_dict["PL_GetPl"]["Data"]["Wavelength"][len(self.result_dict["PL_GetPl"]["Data"]["Wavelength"])-1] - self.result_dict["PL_GetPl"]["Data"]["Wavelength"][0])/2)
                        #print(loss)
                        optimal_value -= loss * weight

                total_property_dict[each_target_type] = result_value

        return float(optimal_value), total_property_dict