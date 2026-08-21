import sys
import os
from opcua import Client, ua
import time
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from Log.Logging_Class import Logger
class HeaterParameter:
    def __init__(self,):
        self.heater_info = {
            "preHeater" : {
                "heaterAddress" : "ns=1;i=54440",
                "temperatureAddress" : "ns=1;i=54437",
                "checkerAddress" :"ns=1;i=54439", 
                "deviceName" : "Asia"  
            },
            "Heater" : {
                "heaterAddress" : "ns=1;i=54428",
                "temperatureAddress" : "ns=1;i=54425",
                "checkerAddress" :"ns=1;i=54427", 
                "deviceName" : "Asia"  
            }
        }

class AsiaHeaterCooler(HeaterParameter):
    def __init__(self, NodeLogger, device_name, mode_type):
        super(AsiaHeaterCooler, self).__init__()
        self.device_name_only = self.heater_info[device_name]
        self.device_name = device_name
        self.url = "opc.tcp://localhost:5000" 
        self.NodeLogger_obj = NodeLogger
        self.mode_type = mode_type
        if self.mode_type == 'real':
            self.client_obj=self.__connectHeater()
            self.heater_port = self.client_obj.get_node(self.heater_info[device_name]["heaterAddress"])
            self.heater_port.set_value(True)
            self.heater_obj , self.checker_obj= self.__makeHeaterObj()

    def __connectHeater(self):
        try:
            client = Client(self.url)
            client.seesion_timeout = 3600000
            client.connect()
        except Exception as err:
            # self.NodeLogger_obj.info(self.deviceq_name, "Connection error")
            sys.exit(1)

        return client
    
    def __makeHeaterObj(self):
        
        heater_address = self.heater_info[self.device_name]["temperatureAddress"]
        check_address = self.heater_info[self.device_name]["checkerAddress"]
        heater_obj = self.client_obj.get_node(heater_address)
        checker_obj = self.client_obj.get_node(check_address)


        return heater_obj, checker_obj

    def controlHeater(self, temperature):
        if self.mode_type == 'real':
            # self.NodeLogger_obj.debug(self.device_name, "Target Temperature is {}℃. The current temperature is {}℃".format(self.heater_obj.get_value(),temperature))
            if float(self.checker_obj.get_value()) < float(temperature): # 목표 온도보다 낮을 경우
                self.heater_obj.set_value(ua.Variant(int(temperature), ua.VariantType.Int16))
                while float(self.checker_obj.get_value()) < float(temperature): # 온도 올라갈 때까지 기다리기  
                    print('[{}] Temperature setting : target({}ºC), real({}ºC)'.format(self.device_name, temperature, self.checker_obj.get_value()))
                    time.sleep(10)
            else: 
                self.heater_obj.set_value(ua.Variant(int(temperature), ua.VariantType.Int16))
                while float(self.checker_obj.get_value()) > float(temperature):
                    print('[{}] Temperature setting : target({}ºC), real({}ºC)'.format(self.device_name, temperature, self.checker_obj.get_value()))
                    time.sleep(10)
            res_cmd = "[Asia Heater] : {} Temperature ({} ºC)".format(self.device_name,temperature)
        elif self.mode_type == "virtual":    
            res_cmd=self.NodeLogger_obj.debug(self.device_name, "The temperature setting has been completed (Target Temperature : {})".format(temperature))
            # res_cmd = "[Asia Heater] : {} Temperature ({} ºC)".format(self.device_name,temperature)
        return res_cmd
    def cooling(self):
        if self.mode_type == 'real':
            self.heater_port.set_value(False)
        elif self.mode_type == 'virtual':
            pass

class Heater_total(HeaterParameter):
    def __init__(self, NodeLogger, mode_type):
        super(Heater_total, self).__init__()
        self.device_list=self.heater_info.keys()
        self.NodeLogger = NodeLogger
        self.mode_type = mode_type
    def shutdown(self):
        for device_name in self.device_list:
            heat_inst_obj=AsiaHeaterCooler(self.NodeLogger, device_name, mode_type=self.mode_type)
            heat_inst_obj.cooling()





if __name__ == '__main__': 
    NodeLogger_obj=Logger()
    # real or virtual
    preheater_obj = AsiaHeaterCooler(NodeLogger=NodeLogger_obj, device_name="preHeater", mode_type="real")
    heater_obj = AsiaHeaterCooler(NodeLogger=NodeLogger_obj, device_name="Heater", mode_type="real")
    # print(heater_obj.device_name)
    # print(heater_obj.controlHeater(temperature=25))
    # heater_obj.cooling()
    # # print(preheater_obj.controlHeater(temperature=25))
    # print(preheater_obj.device_name)
    # preheater_obj.cooling()
    # 끄기 
    total_heater_obj = Heater_total(NodeLogger_obj,mode_type="real")
    total_heater_obj.shutdown()

