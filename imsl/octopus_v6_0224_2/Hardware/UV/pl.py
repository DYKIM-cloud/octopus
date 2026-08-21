import sys, os
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
import seabreeze
seabreeze.use('pyseabreeze')
import seabreeze.spectrometers as sb
from Log.Logging_Class import Logger
class PLParameter:
    """
    Linear Actuator IP, PORT, location dict, move_z

    :param self.WINDOWS1_HOST = '161.122.22.146'  # The server's hostname or IP address
    :param self.PORT_PL = 54011       # The port used by the PL server (54011)
    """
    def __init__(self):
        self.PL_info={
            "Spectrometer":{
                "DeviceName":"SR4",
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

class PL(PLParameter):
    def __init__(self, NodeLogger, device_name, mode_type):
        super(PL,self).__init__()
        self.device_name_only = self.PL_info["Spectrometer"]["DeviceName"]
        self.device_name = device_name
        self.NodeLogger_obj = NodeLogger
        self.mode_type = mode_type
        
        self.device = self._initialize_and_list_devices()[0]
        self.spec = sb.Spectrometer(self.device)
        self.spec.integration_time_micros(6000)
    
    def _initialize_and_list_devices(self):
        try:
            devices = sb.list_devices()
            return devices
        except Exception as e:
            print(f"Error during listing devices: {e}")
            return []


    def getPl(self):
        
        self.device.open()
        
    
        # 파장 및 세기 값 읽기
        wavelengths = self.device.f.spectrometer.get_wavelengths()
        intensities = self.device.f.spectrometer.get_intensities()
        self.device.close()

        spectrum_dict={}
        spectrum_dict["Wavelength"]=wavelengths.tolist()
        spectrum_dict["RawSpectrum"]=intensities.tolist()
        return spectrum_dict

    

if __name__ == "__main__":

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

    TaskLogger_obj=Logger()
    pl_obj = PL(TaskLogger_obj, device_name="PL", mode_type="virtual")
    print(pl_obj.getPl())
        

        