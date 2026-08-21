import sys, time, os
from opcua import Client, ua
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from Log.Logging_Class import Logger

class PumpParameter:
    def __init__(self,):
        self.pump_info = {
            "InP" : {
                "solutionType":"Metal",
                "pumpPort" : "ns=5;i=7003",
                "pumpClose" : "ns=5;i=7004",
                "pumpFlush" : "ns=5;i=7002",
                "pumpAddress" : "ns=1;i=54447",
                "deviceName" : "Asia"  
            },
            "A" : {
                "solutionType":"Reductant",
                "pumpPort" : "ns=5;i=7003",
                "pumpClose" : "ns=5;i=7004",
                "pumpFlush" : "ns=5;i=7002",
                "pumpAddress" : "ns=1;i=54457",
                "deviceName" : "Asia"  
            },
            "A" : {
                "solutionType":"Reductant",
                "pumpPort" : "ns=5;i=7003",
                "pumpClose" : "ns=5;i=7004",
                "pumpFlush" : "ns=5;i=7002",
                "pumpAddress" : "ns=1;i=54457",
                "deviceName" : "Asia"  
            }
        }
class DillutePumpParamter:
    def __init__(self,):
        self.pump_info = {
            "Solvent" : {
                "solutionType":"Solvent",
                "pumpPort" : "ns=5;i=7003",
                "pumpClose" : "ns=5;i=7004",
                "pumpFlush" : "ns=5;i=7002",
                "pumpAddress" : "ns=1;i= ",
                "deviceName" : "Asia"  
            }
        }

class AsiaPump(PumpParameter, DillutePumpParamter):
    def __init__(self, NodeLogger, device_name, solution_name, mode_type):
        super(AsiaPump, self).__init__()
        self.device_name_only = device_name
        self.solution_name=solution_name
        self.device_name = "{} pump {}".format(self.device_name_only, self.pump_info[solution_name]["pumpAddress"])
        self.url = "opc.tcp://localhost:5000"
        self.NodeLogger_obj = NodeLogger
        self.mode_type = mode_type
        if mode_type == "real":
            self.client_obj=self.__connectPump()
        
            self.pump_port = self.client_obj.get_node(self.pump_info[self.solution_name]["pumpPort"])
            self.pump_close = self.client_obj.get_node(self.pump_info[self.solution_name]["pumpClose"])
            self.pump_flush = self.client_obj.get_node(self.pump_info[self.solution_name]["pumpFlush"])
            self.pump_obj = self.__makePumpObj()


    def __connectPump(self):
        try:
            client = Client(self.url)
            client.seesion_timeout = 3600000
            client.connect()
        except Exception as err:
            # self.NodeLogger_obj.info(device_name=self.device_name, info_msg = "Connection error")
            sys.exit(1)

        return client
    
    def __makePumpObj(self):
        
        pump_address = self.pump_info[self.solution_name]["pumpAddress"]
        pump_obj = self.client_obj.get_node(pump_address)

        return pump_obj
    
    def addSolution(self, flowrate):
        if self.mode_type == "real":
            cmd = ua.Variant(int(flowrate), ua.VariantType.UInt16)
            res_cmd = self.pump_obj.call_method(self.pump_port, cmd)
        elif self.mode_type == "virtual":
            res_cmd = "[Asia Pump] : {} ({} ul/s)".format(self.solution_name, flowrate)
        return res_cmd
    
    def flush(self):
        if self.mode_type == "real":
            inp1 = ua.Variant(1000, ua.VariantType.UInt16)
            res_cmd = self.pump_obj.call_method(self.pump_flush, inp1)
        elif self.mode_type == "virtual":
            res_cmd = "[Asia Pump] : flush (1000ul/s)"
        return res_cmd
    
    def stop(self):
        if self.mode_type == 'real':
            res_cmd = self.pump_obj.call_method(self.pump_close)
        else: 
            res_cmd = "stop_pump"
        return res_cmd
        
class Pump_total(PumpParameter):
    def __init__(self, NodeLogger, mode_type):
        super(Pump_total, self).__init__()
        self.solution_list=self.pump_info.keys()
        self.NodeLogger = NodeLogger
        self.mode_type = mode_type
    def shutdown(self):
        for solution_name in self.solution_list:
            heat_inst_obj=AsiaPump(self.NodeLogger, "Asia", solution_name, mode_type=self.mode_type)
            heat_inst_obj.stop()
            heat_inst_obj.flush()

if __name__ == '__main__': 
    print(AsiaPump.__mro__)
    NodeLogger_obj=Logger()
    InP_pump=AsiaPump(NodeLogger=NodeLogger_obj, device_name="Asia", solution_name="InP", mode_type="real")
    A_pump=AsiaPump(NodeLogger=NodeLogger_obj, device_name="Asia", solution_name="A", mode_type="real")
    Solvent_pump=AsiaPump(NodeLogger=NodeLogger_obj, device_name="Asia", solution_name="Solvent", mode_type="real")
    A_pump.addSolution(flowrate=1000)
    InP_pump.addSolution(flowrate=1000)
    time.sleep(5)
    
    InP_pump.flush()
    A_pump.flush()
    A_pump.stop()
    InP_pump.stop()
    # 끄기 
    Solvent_pump.addSolution(flowrate=1000)
    pump_total_obj=Pump_total(NodeLogger_obj, mode_type="real")
    pump_total_obj.shutdown()
    
    
