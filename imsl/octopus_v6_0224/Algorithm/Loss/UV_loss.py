#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [Loss] UV target (lambdamax or FWHM) file
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)   
# @version  1_2   
# TEST 2021-11-01
# TEST 2022-04-11
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths
from scipy.optimize import curve_fit

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

    # ------------------------------------------------------------------
    # 내부 전처리: calculateUV_Data_clean_csv 와 동일한 방식
    # result_dict 의 원본 데이터는 절대 수정하지 않음
    # ------------------------------------------------------------------
    def _preprocess_spectrum(self, wl_raw, rs_raw):
        """
        calculateUV_Data_clean_csv 와 동일한 파이프라인으로
        raw 스펙트럼을 내부에서만 전처리한다. 반환값은 지역 변수뿐이며
        result_dict 의 어떤 키도 수정하지 않는다.

        파이프라인:
          1) 균일 그리드 보간  350–950 nm, 20000 pts
          2) Boxcar 스무딩  box_size=250 (~7.5 nm)
          3) 절삭  360–700 nm
          4) Savitzky-Golay  window=51, polyorder=3
          5) Polynomial fit  degree=19
          6) 최종 절삭  420–550 nm
          7) analysisPickVelly  prominence=0.0005, width_threshold=8

        :return: (pv_ratio, lambdamax, x_eval, y_smooth, resid_full)
            pv_ratio   : peak-valley 비 (미검출 시 0.0)
            lambdamax  : 검출된 피크 파장 (미검출 시 0.0)
            x_eval     : 균일 파장 그리드 (20000 pts, Boxcar 스무딩 기준)
            y_smooth   : Boxcar-smoothed 스펙트럼 (x_eval 에 대응)
            resid_full : 사용하지 않음 (zeros)
        """
        from Analysis.AnalysisUV_poly import (smooth_Boxcar, getSliceSpectrum,
                                              selective_noise_correction,
                                              smooth_polyfit, analysisPickVelly)

        # 1) 파장 오름차순 정렬 → 균일 그리드 보간
        order    = np.argsort(wl_raw)
        x_eval   = np.linspace(350.0, 950.0, 20000)
        y_interp = np.interp(x_eval, wl_raw[order], rs_raw[order])
        raw      = np.array([x_eval, y_interp], dtype=float)

        # 2) Boxcar 스무딩 (~7.5 nm)
        smoothed = smooth_Boxcar(rawSpectrum=raw, box_size=250)
        x_eval   = smoothed[0]
        y_smooth = smoothed[1]

        # 3) 절삭 360–700 nm
        sliced = getSliceSpectrum(rawSpectrum=smoothed, min_wl=360, max_wl=700)

        # 4) Savitzky-Golay
        savgoled = selective_noise_correction(
            sliced, noise_range=(360, 700), window_length=51, polyorder=3
        )

        # 5) Polynomial fit degree=19
        poly_wl, poly_ab = smooth_polyfit(savgoled[0], savgoled[1], degree=19)

        # 6) 최종 절삭 420–550 nm
        sliced2 = getSliceSpectrum(rawSpectrum=(poly_wl, poly_ab), min_wl=420, max_wl=550)

        # 7) 피크 검출
        pv_ratio, lambdamax = analysisPickVelly(
            rawSpectrum=sliced2, prominence=0.0005, width_threshold=8
        )

        resid_full = np.zeros_like(x_eval)

        return float(pv_ratio), float(lambdamax), x_eval, y_smooth, resid_full

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
        InP QD UV 합성 Bayesian Optimization loss. 범위: [-1.5, 0]

        ── 피크 검출 성공 (lambdamax > 0, p_v_ratio > 0) → [-0.3, 0] ──
            검출 자체가 희귀하므로 범위를 0에 가깝게 압축.
            lambdamax/p_v_ratio 편차가 커도 최대 -0.3까지만 패널티.

        ── 피크 미검출 → [-1.5, -0.3] ──
            y_norm_470 = (ab_470 - ab_550) / (ab_420 - ab_550) 로 스펙트럼 형태 평가.
            이 값은 순수 scattering 법칙과 비교한 '완만한 감소' 정도를 반영.

            구간별 매핑 (실측 데이터 기반):
              < 0.35            : 가파른 감소 (Rayleigh보다 가파름)     → -1.5
              0.35 ~ 0.45       : Rayleigh(1/λ^4) 수준               → -1.5 ~ -1.2
              0.45 ~ 0.55       : 1/λ^4 ~ 1/λ^1 사이, QD 형성 신호   → -1.2 ~ -0.6
              0.55 ~ 0.65       : 1/λ^1보다 완만 = QD 가능성 높음     → -0.6 ~ -0.3
              >= 0.65           : 검출 직전 수준 (ceiling)            → -0.3

        :return optimal_value (float): loss in [-1.5, 0]
        :return total_property_dict (dict): lambdamax, p_v_ratio 값
        """
        # y_norm_470 구간 경계 (실측 데이터 기반)
        Y_STEEP    = 0.35   # 25th percentile: Rayleigh보다 가파른 경계
        Y_RAYLEIGH = 0.45   # 1/λ^4 이론값 (0.451)
        Y_GRADUAL  = 0.55   # 1/λ^1 이론값 (0.550) → '완만한 감소' 기준
        Y_QD_LIKE  = 0.65   # 검출된 피크 샘플 수준 (Sample_49: 0.641)

        # 각 구간의 loss 경계값
        L_WORST    = -1.5
        L_RAYLEIGH = -1.2
        L_GRADUAL  = -0.6
        L_NO_PEAK_CEIL = -0.3  # 미검출 최대값 = 검출 최소값

        # 검출 성공 시 스케일 (최대 패널티 = 0.3 → 범위 [-0.3, 0])
        PEAK_SCALE = 0.3

        total_property_dict = {}

        for key, each in self.target_condition_dict.items():
            target_lm = each["Property"]["lambdamax"]
            target_pv = each["Property"]["p_v_ratio"]
            w_lm      = each["Ratio"]["lambdamax"]
            w_pv      = each["Ratio"]["p_v_ratio"]

            wl_raw = np.array(self.result_dict["UV_" + key]["Data"]["Wavelength"])
            rs_raw = np.array(self.result_dict["UV_" + key]["Data"]["RawSpectrum"])

            # ── 내부 csv-스타일 전처리 (result_dict 원본 불변) ──────────────
            pv_ratio, lambdamax, x_eval, rs_smooth, _ = self._preprocess_spectrum(
                wl_raw, rs_raw
            )

            total_property_dict["lambdamax"] = lambdamax
            total_property_dict["p_v_ratio"]  = pv_ratio

            idx_420 = int(np.argmin(np.abs(x_eval - 420.0)))
            idx_tgt = int(np.argmin(np.abs(x_eval - float(target_lm))))
            idx_550 = int(np.argmin(np.abs(x_eval - 550.0)))
            ab_420  = float(rs_smooth[idx_420])
            ab_tgt  = float(rs_smooth[idx_tgt])
            ab_550  = float(rs_smooth[idx_550])

            denom = ab_420 - ab_550
            if denom <= 0.0 or ab_420 <= 0.0:
                y_norm = 0.0
            else:
                y_norm = float(np.clip((ab_tgt - ab_550) / denom, 0.0, 1.0))

            if lambdamax > 0 and pv_ratio > 0:
                # ── 피크 검출 성공: [-0.3, 0] ────────────────────────────────
                # lambdamax: 비대칭 정규화 거리
                if lambdamax <= target_lm:
                    scale = float(max(target_lm - float(wl_raw.min()), 1.0))
                else:
                    scale = float(max(float(wl_raw.max()) - target_lm, 1.0))
                lm_loss = float(np.clip(abs(target_lm - lambdamax) / scale, 0.0, 1.0))

                # p_v_ratio: 비대칭 (target 이상 → 패널티 없음)
                if pv_ratio >= target_pv:
                    pv_loss = 0.0
                else:
                    pv_loss = float(np.clip((target_pv - pv_ratio) / target_pv, 0.0, 1.0))

                optimal_value = -(lm_loss * w_lm + pv_loss * w_pv) * PEAK_SCALE

            else:
                # ── 피크 미검출: y_norm 구간별 선형 매핑 [-1.5, -0.3] ─────────
                if y_norm <= Y_STEEP:
                    optimal_value = L_WORST

                elif y_norm <= Y_RAYLEIGH:
                    t = (y_norm - Y_STEEP) / (Y_RAYLEIGH - Y_STEEP)
                    optimal_value = L_WORST + (L_RAYLEIGH - L_WORST) * t  # -1.5 ~ -1.2

                elif y_norm <= Y_GRADUAL:
                    t = (y_norm - Y_RAYLEIGH) / (Y_GRADUAL - Y_RAYLEIGH)
                    optimal_value = L_RAYLEIGH + (L_GRADUAL - L_RAYLEIGH) * t  # -1.2 ~ -0.6

                elif y_norm <= Y_QD_LIKE:
                    t = (y_norm - Y_GRADUAL) / (Y_QD_LIKE - Y_GRADUAL)
                    optimal_value = L_GRADUAL + (L_NO_PEAK_CEIL - L_GRADUAL) * t  # -0.6 ~ -0.3

                else:
                    optimal_value = L_NO_PEAK_CEIL  # -0.3 ceiling

        return float(optimal_value), total_property_dict
    
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

    # ------------------------------------------------------------------
    # Method 2: 2nd-derivative curvature loss
    # ------------------------------------------------------------------
    def lambdamaxpvLoss_deriv(self, smooth_sigma=5, position_bandwidth=40.0,
                              w_curv=0.6, w_pos=0.4):
        """
        2차 미분 기반 loss. 범위: [-1.5, 0]

        ── 피크 검출 성공 (lambdamax > 0, p_v_ratio > 0) → [-0.3, 0] ──
            lambdamaxpvLoss와 동일한 PEAK_SCALE(0.3) 적용.
            lambdamax/p_v_ratio 편차가 커도 최대 -0.3까지만 패널티.

        ── 피크 미검출 → [-1.5, -0.3] ──
            curvature_score : target_lm 위치의 -d²A/dλ² 를 전체 최대 음곡률로 정규화
                              → 해당 파장에 날카로운 피크 특성이 있을수록 1에 가까움
            position_score  : 2차 미분 최솟값 위치가 target_lm에 가까울수록 1
                              → Gaussian 폭 position_bandwidth(nm)으로 제어
            combined = curvature_score * w_curv + position_score * w_pos  ∈ [0, 1]
            loss = -1.5 + 1.2 * combined  → combined=0 : -1.5, combined=1 : -0.3

        :param smooth_sigma       : Gaussian smoothing 강도 (데이터 포인트 단위, 기본 5)
        :param position_bandwidth : 위치 보상 Gaussian 반폭 (nm, 기본 40)
        :param w_curv             : curvature_score 가중치 (기본 0.6)
        :param w_pos              : position_score 가중치 (기본 0.4)
        :return: (optimal_value float, total_property_dict dict)
        """
        PEAK_SCALE = 0.3

        total_property_dict = {}

        for key, each in self.target_condition_dict.items():
            target_lm = float(each["Property"]["lambdamax"])
            target_pv = float(each["Property"]["p_v_ratio"])
            w_lm      = float(each["Ratio"]["lambdamax"])
            w_pv      = float(each["Ratio"]["p_v_ratio"])

            data      = self.result_dict["UV_" + key]["Data"]
            wl_raw    = np.array(data["Wavelength"], dtype=float)
            rs_raw    = np.array(data["RawSpectrum"], dtype=float)
            lambdamax = data["Property"]["lambdamax"]
            pv_ratio  = data["Property"]["p_v_ratio"]

            total_property_dict["lambdamax"] = lambdamax
            total_property_dict["p_v_ratio"]  = pv_ratio

            # 파장 오름차순 정렬 후 균일 그리드로 보간 (미분 정확도 확보)
            order  = np.argsort(wl_raw)
            wl_s   = wl_raw[order]
            rs_s   = rs_raw[order]
            wl_uni = np.linspace(float(wl_s[0]), float(wl_s[-1]), len(wl_s))
            rs_uni = np.interp(wl_uni, wl_s, rs_s)

            # Gaussian smoothing → 1차·2차 미분
            rs_sm = gaussian_filter1d(rs_uni, sigma=smooth_sigma)
            dy    = np.gradient(rs_sm, wl_uni)
            d2y   = np.gradient(dy,   wl_uni)

            # curvature score: target_lm 위치의 -d²A/dλ²
            idx_tgt   = int(np.argmin(np.abs(wl_uni - target_lm)))
            d2_at_tgt = float(d2y[idx_tgt])
            d2_min    = float(np.min(d2y))
            if d2_min >= 0.0:
                curvature_score = 0.0
            else:
                curvature_score = float(np.clip(-d2_at_tgt / (-d2_min + 1e-9), 0.0, 1.0))

            # position score: 2차 미분 최솟값 위치가 target_lm에 가까울수록 1
            lm_sharp       = float(wl_uni[int(np.argmin(d2y))])
            position_score = float(
                np.exp(-0.5 * ((lm_sharp - target_lm) / position_bandwidth) ** 2)
            )

            combined = float(np.clip(curvature_score * w_curv + position_score * w_pos, 0.0, 1.0))

            if lambdamax > 0 and pv_ratio > 0:
                # ── 피크 검출 성공: [-0.3, 0] ────────────────────────────────
                if lambdamax <= target_lm:
                    scale = float(max(target_lm - float(wl_raw.min()), 1.0))
                else:
                    scale = float(max(float(wl_raw.max()) - target_lm, 1.0))
                lm_loss = float(np.clip(abs(target_lm - lambdamax) / scale, 0.0, 1.0))
                pv_loss = 0.0 if pv_ratio >= target_pv else float(
                    np.clip((target_pv - pv_ratio) / target_pv, 0.0, 1.0))
                optimal_value = -(lm_loss * w_lm + pv_loss * w_pv) * PEAK_SCALE

            else:
                # ── 피크 미검출: combined → [-1.5, -0.3] 선형 매핑 ───────────
                # combined=0 → -1.5 (신호 없음), combined=1 → -0.3 (강한 QD 신호)
                optimal_value = -1.5 + 1.2 * combined

        return float(np.clip(optimal_value, -1.5, 0.0)), total_property_dict

    # ------------------------------------------------------------------
    # Method 3: 1/lambda^n background decomposition + FWHM loss
    # ------------------------------------------------------------------
    def lambdamaxpvLoss_decomp(self, smooth_sigma=4,
                               peak_exclude_half=80.0,
                               fwhm_range=550.0,
                               peak_amp_ref=0.3,
                               prominence=0.005,
                               width_nm=10.0):
        """
        1/lambda^n 배경 분리 후 잔류 피크 분석. 범위: [-1.5, 0]

        ── 피크 검출 성공 (lambdamax > 0, p_v_ratio > 0) → [-0.3, 0] ──
            lambdamaxpvLoss와 동일한 PEAK_SCALE(0.3) 적용.
            p_v_ratio 비대칭 패널티: pv ≥ target → pv_loss = 0.

        ── 피크 미검출 (3단계) ─────────────────────────────────────────
          잔류 피크 발견 (배경 제거 후)  → [-0.5, -0.3]
            quality = 1 - (lm_loss*w_lm + fwhm_loss*w_fwhm + amp_loss*w_amp)
            loss = -0.5 + 0.2 * quality
          잔류 피크 없음                → [-1.5, -0.5]
            amp_proxy = max(resid) / peak_amp_ref  clipped [0,1]
            loss = -1.5 + 1.0 * amp_proxy

        배경 피팅: A(λ) = a*(λ_min/λ)^n  (피크 예상 영역 ±peak_exclude_half nm 제외)
        curve_fit 실패 시 양 끝점 선형 보간으로 대체.

        가중치 분배:
          Ratio["lambdamax"] → lambdamax loss
          Ratio["p_v_ratio"] → FWHM(70%) + 진폭(30%)  (잔류 피크 발견 시)
                             → p_v_ratio loss          (실제 피크 검출 시)

        :param smooth_sigma      : Gaussian smoothing 강도 (기본 4)
        :param peak_exclude_half : 배경 피팅 제외 구간 반폭 (nm, 기본 80)
        :param fwhm_range        : FWHM loss 정규화 분모 (nm, 기본 550)
        :param peak_amp_ref      : 정상 피크 진폭 기준값 (기본 0.3)
        :param prominence        : find_peaks prominence threshold (기본 0.005)
        :param width_nm          : find_peaks 최소 폭 (nm, 기본 10)
        :return: (optimal_value float, total_property_dict dict)
        """
        PEAK_SCALE = 0.3

        total_property_dict = {}

        for key, each in self.target_condition_dict.items():
            target_lm   = float(each["Property"]["lambdamax"])
            target_pv   = float(each["Property"]["p_v_ratio"])
            w_lm        = float(each["Ratio"]["lambdamax"])
            w_pv        = float(each["Ratio"]["p_v_ratio"])
            w_fwhm      = w_pv * 0.7
            w_amp       = w_pv * 0.3
            target_fwhm = each["Property"].get("FWHM", None)  # 선택 사항

            data      = self.result_dict["UV_" + key]["Data"]
            wl_raw    = np.array(data["Wavelength"], dtype=float)
            rs_raw    = np.array(data["RawSpectrum"], dtype=float)
            lambdamax = data["Property"]["lambdamax"]
            pv_ratio  = data["Property"]["p_v_ratio"]

            total_property_dict["lambdamax"] = lambdamax
            total_property_dict["p_v_ratio"]  = pv_ratio

            # ── 실제 피크 검출 성공: [-0.3, 0] ──────────────────────────────
            if lambdamax > 0 and pv_ratio > 0:
                if lambdamax <= target_lm:
                    scale = float(max(target_lm - float(wl_raw.min()), 1.0))
                else:
                    scale = float(max(float(wl_raw.max()) - target_lm, 1.0))
                lm_loss = float(np.clip(abs(target_lm - lambdamax) / scale, 0.0, 1.0))
                pv_loss = 0.0 if pv_ratio >= target_pv else float(
                    np.clip((target_pv - pv_ratio) / target_pv, 0.0, 1.0))
                optimal_value = -(lm_loss * w_lm + pv_loss * w_pv) * PEAK_SCALE

            else:
                # 파장 오름차순 정렬 + 균일 그리드 보간
                order  = np.argsort(wl_raw)
                wl_s   = wl_raw[order]
                rs_s   = rs_raw[order]
                wl_uni = np.linspace(float(wl_s[0]), float(wl_s[-1]), len(wl_s))
                rs_uni = np.interp(wl_uni, wl_s, rs_s)
                rs_sm  = gaussian_filter1d(rs_uni, sigma=smooth_sigma)

                # 배경 피팅: 피크 예상 영역 제외
                mask = (wl_uni < target_lm - peak_exclude_half) | \
                       (wl_uni > target_lm + peak_exclude_half)
                if mask.sum() < 10:
                    mask = np.ones(len(wl_uni), dtype=bool)

                wl_fit = wl_uni[mask]
                rs_fit = np.maximum(rs_sm[mask], 1e-6)
                wl_ref = float(wl_uni[0])

                def power_law(x, a, n):
                    return a * (wl_ref / x) ** n

                try:
                    popt, _ = curve_fit(power_law, wl_fit, rs_fit,
                                        p0=[1.0, 2.0],
                                        bounds=([0.0, 0.3], [20.0, 6.0]),
                                        maxfev=3000)
                    bg = np.maximum(power_law(wl_uni, *popt), 0.0)
                except Exception:
                    bg = np.interp(wl_uni,
                                   [wl_uni[0], wl_uni[-1]],
                                   [rs_sm[0],  rs_sm[-1]])

                resid = np.maximum(rs_sm - bg, 0.0)

                dx        = float(wl_uni[1] - wl_uni[0]) if len(wl_uni) > 1 else 1.0
                width_pts = max(int(width_nm / dx), 1)
                peaks, props = find_peaks(resid, prominence=prominence, width=width_pts)

                if len(peaks) == 0:
                    # 잔류 피크 없음: [-1.5, -0.5]
                    max_resid     = float(np.max(resid))
                    amp_proxy     = float(np.clip(max_resid / peak_amp_ref, 0.0, 1.0))
                    optimal_value = -1.5 + 1.0 * amp_proxy  # -1.5 ~ -0.5

                else:
                    # 잔류 피크 발견 (배경 제거 후): [-0.5, -0.3]
                    best      = peaks[int(np.argmax(props["prominences"]))]
                    lm_found  = float(wl_uni[best])
                    amp_found = float(resid[best])

                    pw         = peak_widths(resid, [best], rel_height=0.5)
                    fwhm_found = float(pw[0][0]) * dx

                    if lm_found < target_lm:
                        span = max(target_lm - float(wl_uni[0]), 1.0)
                    else:
                        span = max(float(wl_uni[-1]) - target_lm, 1.0)
                    lm_loss = float(np.clip(abs(target_lm - lm_found) / span, 0.0, 1.0))

                    if target_fwhm is None or fwhm_found <= target_fwhm:
                        fwhm_loss = 0.0
                    else:
                        fwhm_loss = float(np.clip(
                            (fwhm_found - target_fwhm) / fwhm_range, 0.0, 1.0))

                    amp_loss = float(np.clip(1.0 - amp_found / peak_amp_ref, 0.0, 1.0))

                    # quality ∈ [0, 1]: 1 = best
                    quality = float(np.clip(
                        1.0 - (lm_loss * w_lm + fwhm_loss * w_fwhm + amp_loss * w_amp),
                        0.0, 1.0))
                    optimal_value = -0.5 + 0.2 * quality  # -0.5 ~ -0.3

        return float(np.clip(optimal_value, -1.5, 0.0)), total_property_dict