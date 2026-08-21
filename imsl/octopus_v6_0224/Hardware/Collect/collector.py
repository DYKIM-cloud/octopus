import sys, time, os
from opcua import Client, ua
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from Log.Logging_Class import Logger
from TimeCheker import Timer

class CollectorParameter:
    def __init__(self,):
        self.collector_info = {
            "Asia" : {
                "collectorPort" : "ns=1;i=58192",
                "collectorMode" : "ns=1;i=54415",
                "collectorPositionset" : "ns=5;i=7027",
                "collectorPositionreadX" : "ns=1;i=54414",
                "collectorPositionreadY" : "ns=1;i=54413",
                "deviceName" : "Asia",
                
            }
        }



class AsiaCollector(CollectorParameter):
    def __init__(self, NodeLogger, device_name, mode_type):
        super(AsiaCollector, self).__init__()
        self.device_name_only = device_name
        self.url = "opc.tcp://localhost:5000"
        self.NodeLogger_obj = NodeLogger
        self.mode_type = mode_type
        self.COLLECT = "COLLECT"
        self.WASTE = "WASTE"
        
        if mode_type == "real":
            self.client_obj=self.__connectPump()
        
            self.collector_port = self.client_obj.get_node(self.collector_info[device_name]["collectorPort"])
            self.collector_mode = self.client_obj.get_node(self.collector_info[device_name]["collectorMode"])
            self.collector_positionset = self.client_obj.get_node(self.collector_info[device_name]["collectorPositionset"])
            self.collector_positionreadX = self.client_obj.get_node(self.collector_info[device_name]["collectorPositionreadX"])
            self.collector_positionreadY = self.client_obj.get_node(self.collector_info[device_name]["collectorPositionreadY"])
            self.collector_obj = self.__makeCollectorObj()
            self.collector_mode.set_value(self.WASTE)
    def __connectPump(self):
        try:
            client = Client(self.url)
            client.session_timeout = 3600000
            client.connect()
        except Exception as err:
            # self.NodeLogger_obj.info(device_name=self.device_name, info_msg = "Connection error")
            sys.exit(1)

        return client

    def __makeCollectorObj(self):
        
        collector_address = self.collector_port
        collector_obj = self.client_obj.get_node(collector_address)

        return collector_obj
    
    def _volumeChekcer(self, volume):
        if float(volume) <= 1500:
            return True
        else: 
            return False


    def get_vial_position(self, index):
        if index < 0 or index >= 80:
            raise ValueError("Index out of range")
        
        row = index // 5
        col = index % 5
        x_position = 9 + row * 12.98
        y_position = 30 + col * 12.98
        
        return x_position, y_position
    
    def collect(self, vial_num, volume, collecting_time):        
        if self._volumeChekcer(volume) == True:
            if self.mode_type == "real":
                x_position, y_position=self.get_vial_position(vial_num)
                xPosition = ua.Variant(x_position, ua.VariantType.Double)
                yPosition = ua.Variant(y_position, ua.VariantType.Double)
                self.collector_port.call_method(self.collector_positionset, xPosition, yPosition)
                self.collector_mode.set_value(self.COLLECT)
                time.sleep(collecting_time)
                self.waste()
            res_cmd = "[Asia Collector] : Collect - {} vial ({} ul)".format(vial_num, volume)
            return res_cmd
        else: 
            print("Volume must be less than 1500ul.")

    
    def waste(self):
        if self.mode_type == "real":
            self.collector_mode.set_value(self.WASTE)
        res_cmd = "[Asia Collector] :Waste"
        return res_cmd
    
if __name__ == '__main__': 
    NodeLogger_obj=Logger()
    collector_obj = AsiaCollector(NodeLogger=NodeLogger_obj, device_name="Asia", mode_type="real")
    collector_obj.collect(vial_num=0, volume = 1000, collecting_time = 5)
    collector_obj.waste()

#     # collector node
#     Collector = client.get_node("ns=1;i=58192") # Collector의 node
#     Valve = client.get_node("ns=1;i=54415")  # valve (WASTER or COLLECT) 모드를 설정하는 node
#     Positionset = client.get_node("ns=5;i=7026") # collecting되는 vial의 위치를 선택하는 node (OPCUA에서의 MoveToVial)
#     Positionread = client.get_node("ns=1;i=54416") # 현재 collecting되는 vial의 위치를 읽는 node

#     COLLECT = "COLLECT"
#     WASTE = "WASTE"

#     Valve.set_value(WASTE) # 실험 중 실제 샘플 이외의 용액을 버리도록 WASTE로 설정
#     print("Waste!")
#     time.sleep(3)

#     Valve.set_value(COLLECT) # Collecting되는 시간동안 collector의 valve가 COLLECT로 설정
#     print("Collect!")
#     time.sleep(3)

#     print("Collting in #1") #샘플이 몇 번 vial에 collecting되었는지 표시
#     Position = ua.Variant(1, ua.VariantType.UInt32)
#     out = Collector.call_method(Positionset, Position) # 샘플이 원하는 vial에 collecting되도록 collector의 position 변경
#     time.sleep(3)

#     Valve.set_value(WASTE) #S ample collecting 후 다시 WASTE로 변경
#     print("Waste!")
#     time.sleep(3)

# client.disconnect()