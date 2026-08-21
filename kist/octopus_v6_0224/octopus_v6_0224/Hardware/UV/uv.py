import sys, os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from OceanOptics.UV.QEPro2192 import QEPro2192
from Log.Logging_Class import Logger
import json
import time
class UVParameter:
    """
    Linear Actuator IP, PORT, location dict, move_z

    :param self.WINDOWS1_HOST = '161.122.22.146'  # The server's hostname or IP address
    :param self.PORT_UV = 54011       # The port used by the UV server (54011)
    """
    def __init__(self):
        self.HOST_UV="127.0.0.1"
        self.PORT_UV=54010
        self.UV_info={
            "Spectrometer":{
                "DeviceName":"USB2000+",
                "DetectionRange":"200-850nm",
                "Solvent":
                {
                    "Solution":"H2O",
                    "Value": 1,
                    "Dimension": "μL"
                }
            },
            "LightSource":{
                "DeviceName":"DH-2000-BAL",
                "DetectionRange":"210-2500nm",
                "Lamp":"deuterium(25W) and halogen lamps(20W)"
            }
        }

class UV(UVParameter):
    def __init__(self, NodeLogger, device_name, mode_type):
        super(UV,self).__init__()
        self.device_name_only = self.UV_info["Spectrometer"]["DeviceName"]
        self.device_name = device_name
        self.NodeLogger_obj = NodeLogger
        self.mode_type = mode_type

        self.UV_obj = QEPro2192()
        self.UV_obj.set_integration_time(0.0045)

    def getAbs(self):
        max_attempts = 30  
        attempt_count = 0  
    
        while attempt_count < max_attempts:
            spectrum_dict = {}
            uv_spectrum = self.UV_obj.obtain_spectrum()
        
            spectrum_dict["Wavelength"] = uv_spectrum['Wavelength'].tolist()
            spectrum_dict["RawSpectrum"] = uv_spectrum['RawSpectrum'].tolist()
        
            max_intensity = max(spectrum_dict["RawSpectrum"])
            attempt_count += 1  
        
        # 측정된 intensity가 범위를 벗어나는지 확인
            if max_intensity < 30000 or max_intensity > 55000:
                if attempt_count >= max_attempts:
                    return spectrum_dict  
                time.sleep(3)  # 5초 대기
                print(attempt_count+1, end=' ')
                continue  
            else:
                return spectrum_dict
    
    def loadRef(self):
        with open('Hardware\\UV\\reference.json','r') as file:
            real_spectrum_dict = json.load(file)
        return real_spectrum_dict

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import numpy as np
    metadata_dict={
        "subject":"Take_scneario",
        "group":"KIST_CSRC",
        "logLevel":"DEBUG",
        "modeType":"virtual",
        "todayIterNum":1,
        "userName":"NY",
        "jobID":0,
        "jobFileName":"USER/NY/job_script/20230516_autonomous_test.json",
        "batchSize":1
    }
    # 이거 확인 
    TaskLogger_obj=Logger()
    uv_obj = UV(TaskLogger_obj, device_name="UV", mode_type="virtual")

    ref_dict=uv_obj.loadRef()
    
    spectrum_dict=uv_obj.getAbs()
    absorbances = []
    abs_dict = {}
    for ref, measured  in zip (ref_dict['RawSpectrum'], spectrum_dict['RawSpectrum']):
        try:
            if ref == 0 or measured-3000 == 0:
                absorbances.append(0)
                continue
            absorbances.append(np.log10(abs(ref/measured-3000)))
        except:
            break
    abs_dict['Wavelength'] = spectrum_dict["Wavelength"]
    abs_dict['RawSpectrum'] = absorbances
    
    plt.plot(ref_dict["Wavelength"], ref_dict["RawSpectrum"])
    plt.plot(spectrum_dict["Wavelength"], spectrum_dict["RawSpectrum"])
    #plt.plot(abs_dict["Wavelength"], abs_dict["RawSpectrum"])
    plt.show()