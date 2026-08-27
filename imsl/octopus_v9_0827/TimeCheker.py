import time 
import math

class TimeParameter:
    def __init__(self,):
        self.time_info = {
            "total_flow_volume":17759.34, # 전체 관 길이
            "until_dillute_volume": 0, # 희석 시키는 펌프와 연결된 선 까지 길이 - 수정 요망 
            "uv_pl_volume" : 100, # UV부터 PL 까지 관 길이
            "Collecting_volume" : 1000 # collect volume - 수정 요망 
        }

class Timer(TimeParameter):
    def __init__(self, rate_list:list):
        TIME_CONSTANT = 70
        super(Timer, self).__init__()
        self.rate_list = rate_list
        self.uv_time_min = (self.time_info["total_flow_volume"]-self.time_info["until_dillute_volume"])/(sum(rate_list))
        self.uv_time_sec = math.ceil(self.uv_time_min * TIME_CONSTANT +10)
        
        self.pl_time_min = (self.time_info["uv_pl_volume"])/(sum(rate_list))
        self.pl_time_sec = math.ceil(self.pl_time_min * 60)
        
        self.dillute_time_min = self.time_info["until_dillute_volume"]/(sum(rate_list))
        self.dillute_time_sec = math.ceil(self.dillute_time_min * TIME_CONSTANT +10)
        
        self.collect_time_min = self.time_info["Collecting_volume"]/(sum(rate_list))
        self.collect_time_sec = math.ceil(self.collect_time_min * TIME_CONSTANT)   

    def waiting(self):
        time.sleep(self.uv_time_sec)

    def plwaiting(self):
        time.sleep(self.pl_time_sec)
    
    def collecting(self):
        time.sleep(self.collect_time_sec)
        
    def dillute_waiting(self):
        time.sleep(self.dillute_time_sec)
    def volume_timer(self, volume):
        volume_min = volume/(sum(self.rate_list))
        volume_sec = math.ceil(volume_min * 84)
        return volume_sec