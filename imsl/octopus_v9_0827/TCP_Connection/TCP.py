#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##
# @brief    [TCP_Connection] TCP Class for controlling another computer (windows, ubuntu)
# @author   Hyuk Jun Yoo (yoohj9475@kist.re.kr)
# @version  2_1      
# TEST 2021-09-23 // 2022-01-17

import socket, json
import os, sys
import time


class ParamterTCP:
    """
    TCP information : to protect our system due to hacker
    
    - (ROBOT_HOST : Doosan robot) 
    - (BATCH_HOST : Batch synthesis) 
    - (OPTICS_HOST : UV analysis) 
    - (DB_HOST : Database (MongoDB)) 
    - (FLOW_HOST : Flow synthesis) 
    """
    def __init__(self):
        self.ROBOT_HOST = "161.122.22.174" # (UBUNTU : Robot (Doosan robot)) The server's hostname or IP address
        self.BATCH_HOST = "161.122.22.146"  # (WINDOWS : Batch synthesis) The server"s hostname or IP address (231: linux)
        self.OPTICS_HOST = "161.122.22.80"  # (WINDOWS : UV analysis) The server"s hostname or IP address
        self.DB_HOST = "161.122.22.79"  # (WINDOWS : Database (MongoDB)) The server's hostname or IP address
        # self.FLOW_HOST = "161.122.22.146"  # (WINDOWS : Flow synthesis) The server"s hostname or IP address --> add later

        self.ROBOT_PORT = 54009 # Ubuntu Server
        self.BATCH_PORT = 54009 # Windows Server
        self.OPTICS_PORT = 54009 # Windows Server
        self.DB_PORT = 27017 # The port used by the mongodb server (27017)
        # self.FLOW_PORT = 54009


class TCP_Class(ParamterTCP):
    """
    [TCP_Connection] TCP Class for controlling another computer

    # (MAIN : Main)
    - RecipeGenerator
    - Scheduler
    - MasterMasterLogger
    - Algorithm
    # (ROBOT : Doosan robot)
    - Robot
    - NodeMasterLogger
    # (BATCH : Batch synthesis)
    - Science Town (Linear Actuator) 
    - Centris, XCaliburD (Syringe pump)
    - IKA RET (Stirrer_1) 
    - NodeMasterLogger
    # (OPTICS : Optical analysis)
    - USB2000+ (UV) 
    - Pipette machine
    - NodeMasterLogger
    # (DB : Database (MongoDB))
    - MongoDB 
    # (FLOW : Flow synthesis) --> add later
    - Centris, XCaliburD (Syringe pump)
    - NodeMasterLogger

    # function
    - callServer_LA(command_byte=b'LA,home,virtual')
    - callServer_STIRRER(command_byte=b'STIRRER,heat,0,25,virtual')
    - callServer_PUMP(command_byte=b'PUMP,single,AgNO3,1500,2000,virtual')
    - callServer_STORAGE(command_byte=b'STORAGE,1,virtual')
    - callServer_UV(command_byte=b"UV,Ag,virtual")
    - callServer_PIPETTE(command_byte=b'PIPETTE,sample,0,A1,virtual')
    - callServer_BATCH(command_byte=b'PIPETTE,sample,0,A1,virtual')
    - callServer_OPTICS(command_byte=b'PIPETTE,sample,0,A1,virtual')
    """

    def __init__(self):
        self.BUFF_SIZE = 4096
        ParamterTCP.__init__(self,)

    def callServer_LA(self, command_byte=b'LA/down/Stirrer_0,3/real'):
        """
        receive command_byte & send tcp packet using socket 

        :param command_byte=b'LA/home/virtual' (byte) : input command string type
        
        if action type == "home" --> 'LA/home/null/virtual'
            - hardware_name=LA (str) : set hardware name in batch platform
            - action_type = home or stirrer_0... (str): set action type
            - action_info="0" (str): set action info
            - mode_type = "virtual" (str): set mode type --> real, virtual 
        
        elif action type == "stirrer_0" --> 'LA/down/Stirrer_0,0/virtual'
            - hardware_name=LA (str) : set hardware name in batch platform
            - action_type = "up" or "down"... (str): set action type
            - action_info="{},{}" (str): set action info
                - stirrer_address = "stirrer_0"
                - location_number = 0,1,2..... depending on stirrer
            - mode_type = "virtual" (str): set mode type --> real, virtual 

        :return: status_message
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.BATCH_HOST, self.BATCH_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break
            return message_recv.decode("utf-8")

    def callServer_STIRRER(self, command_byte=b'STIRRER/heat/0,25/virtual'):
        """
        receive command_byte & send tcp packet using socket

        :param command_byte = b'STIRRER/heat/0/25/virtual' (byte) : input command string type 
            - hardware_name="STIRRER" (str) : (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type="heat" (str) : (heat, stir, stop)
            - action_info="{},{}" (str): set action info
                - stirrer_address = 0 or 1... (int): set stirrer address (Address number) 
                - action_info = 50 or 800 (int): set temperature or stir rate (Celsius or rpm) 
            - mode_type = "virtual" (str): set mode type --> real, virtual

        :return: status_message (str)
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.BATCH_HOST, self.BATCH_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break

            return message_recv.decode("utf-8")

    def callServer_PUMP(self, command_byte=b'PUMP/single/AgNO3,1500,20,2000/virtual'):
        """
        receive command_byte & send tcp packet using socket

        :param command_byte=b'PUMP/single/AgNO3,1500,2000/virtual' (byte) or
               command_byte=b'PUMP/multi/AgNO3,1500,2000-NaBH4,1500,2000/real'): input command string type 
               command_byte=b'PUMP/info/real'): request pump information (solution_name_list, solution_addr_list, solution_type_list)
            
            - hardware_name="PUMP" (str) (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type="single" or "multi" (str): set action type
            - action_info="{},{},{}" (str): set action info
                - solution_name (str or list): set solution name (AgNO3, H2O, Citrate, PVP...) 
                - volume (int or list) : set volume (ul)
                - concentration (int or list) : set concentration (mM)
                - injection_rate (int or list) : set flow rate (ul/s)
            - mode_type = "virtual" (str): set mode type --> real, virtual

        :return: status_message (str)
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.BATCH_HOST, self.BATCH_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break

            return message_recv.decode("utf-8")

    def callServer_STORAGE(self, command_byte=b'STORAGE/open/1/virtual'):
        """
        receive command_byte & send tcp packet using socket

        :param command_byte=b'STORAGE/1/virtual' (byte) : input command string type 
            - hardware_name="STORAGE" (str) (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type="open" (str): set action type
            - action_info="{}" (str): set action info
                - entrance_num = 1 (int): set entrance number of storage
            - mode_type = "virtual" (str): set mode type --> real, virtual

        :return: status_message (str)
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.BATCH_HOST, self.BATCH_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break

            return message_recv.decode("utf-8")

    def callServer_ABS(self, command_byte=b"ABS/Abs/AgNP/virtual"):
        """
        receive command_byte & send tcp packet using socket 

        :param command_byte=b"UV/Ag/virtual" (str) : input command string type 
            - hardware_name="UV" (str) (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type="Abs" or "Ref" (str) ... (str): set action type
            - action_info="AgNP" (str) ... (str): set action info
            - mode_type = "virtual" (str): set mode type --> real, virtual

        :return: status_message
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.OPTICS_HOST, self.OPTICS_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                if part.decode() in "finish":
                    s.close()
                    break
                elif part.decode() != "finish":
                    message_recv += part
                else:
                    raise ConnectionError("Wrong tcp message")
            return message_recv.decode("utf-8")

    def callServer_PIPETTE(self, command_byte=b'PIPETTE/sample/20-200,2,A2,2,0,3/virtual'):
        """
        receive command_byte & send tcp packet using socket

        "20-200", 2, str(chr(ord('A') + column_num) + str(row_num+1+1)), vialHolder_loc, 3, 

        :param command_byte = 'PIPETTE/sample/0/A1/virtual' (byte) : input command string type 
            - hardware_name="PIPETTE" (str): (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type="sample" (str): set action type (ex) "sample", "synthesis"
            - action_info="{},{},{},{},{},{}" (str): set action info
                - pipette_volume="20-200" (str): set type of pipette (ex) 2-20, 20-200, 100-1000 ...
                - inject_volume=2 (int): set volume of injection
                - tip_loc="A1" or "H12"... (str): set pipette tip's position idx
                - pump_in_loc=0 (int): set pump in location
                - pump_out_loc=3 (int): set pump out location
                - mixing_time=3 (int): set mixing time
            - mode_type="virtual" (str): set mode type --> real, virtual

        :return: status_message (str)
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # s.connect((self.OPTICS_HOST, self.OPTICS_PORT))
            s.connect((self.ROBOT_HOST, self.ROBOT_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break

            return message_recv.decode("utf-8")

    def callServer_DS_B(self, command_byte=b'DS_B/storage_empty_to_stirrer/pick_num,place_num/virtual'):
        """
        receive command_byte & send tcp packet using socket

        :param command_byte = DS_B/cycle_num/action_idx/action_type/virtual' (byte) : input command string type 
            - hardware_name="DS_B" (str): (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE, DS_B)
            - action_type="storage_empty_to_stirrer" (str) : ex) "storage_empty_to_stirrer"
            - action_info="{},{}" (str): set action info
                - pick_num=0 (int): pick vial or pick cuvette
                - place_num=1 (int): set place_num
            - mode_type="virtual" (str): set mode type --> real, virtual

        :return: status_message (str)
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.ROBOT_HOST, self.ROBOT_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                message_recv += part
                if len(part) < self.BUFF_SIZE:
                    s.close()
                    break

            return message_recv.decode("utf-8")

    def callServer_BATCH_INFO(self, command_byte=b"BATCH/INFO/all/virtual"):
        """
        receive command_byte & send tcp packet using socket 

        :param command_byte=b"BATCH/INFO/all/virtual" (str) : input command string type 
            - hardware_name="BATCH" (str) (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type=info (str) ... (str): get self.{}_info
            - action_info=all (str) ... (str): get self.{}_info
            - mode_type = "virtual" (str): set mode type --> real, virtual

        :return each_info_dict (dict): has BATCH's hardware information
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.BATCH_HOST, self.BATCH_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                if part.decode() in "finish":
                    s.close()
                    break
                elif part.decode() != "finish":
                    message_recv += part
                else:
                    raise ConnectionError("Wrong tcp message")
            each_res_dict=json.loads(message_recv.decode("utf-8"))
            return each_res_dict

    def callServer_UV_INFO(self, command_byte=b"OPTICS/INFO/all/virtual"):
        """
        receive command_byte & send tcp packet using socket 

        :param command_byte=b"OPTICS/INFO/all/virtual" (str) : input command string type 
            - hardware_name="OPTICS" (str) (LA, UV, STIRRER, PUMP, STORAGE, PIPETTE)
            - action_type=INFO (str) ... (str): get self.{}_info
            - action_info=all (str) ... (str): get self.{}_info
            - mode_type="virtual" (str): set mode type --> real, virtual

        :return each_info_dict (dict): has OPTICS's hardware information
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.OPTICS_HOST, self.OPTICS_PORT))
            time.sleep(1)
            s.sendall(command_byte)
            message_recv = b''
            while True:
                part = s.recv(self.BUFF_SIZE)
                if part.decode() in "finish":
                    s.close()
                    break
                elif part.decode() != "finish":
                    message_recv += part
                else:
                    raise ConnectionError("Wrong tcp message")
            each_res_dict=json.loads(message_recv.decode("utf-8"))
            return each_res_dict

if __name__ == '__main__':
    tcp_object = TCP_Class()
    print(tcp_object.callServer_DS_B(command_byte=b'DS_B/storage_empty_to_stirrer/0,0/real'))
    """
    print(tcp_object.callServer_STORAGE(command_byte=b'STORAGE/open/0/real'))
    time.sleep(1)
    time.sleep(1)
    print(tcp_object.callServer_PUMP(command_byte=b'PUMP/single/H2O,2000,4000/real'))
    time.sleep(1)
    print(tcp_object.callServer_LA(command_byte=b'LA/up/Stirrer_0,0/real'))
    print(tcp_object.callServer_LA(command_byte=b'LA/home/null/real'))
    print(tcp_object.callServer_DS_B(command_byte=b'DS_B/stirrer_to_holder/0,0/real'))
    print(tcp_object.callServer_DS_B(command_byte=b'DS_B/cuvette_storage_to_cuvette_holder/0,0/real'))
    print(tcp_object.callServer_DS_B(command_byte=b'DS_B/cuvette_holder_to_UV/0,0/real'))
    print(tcp_object.callServer_PIPETTE(command_byte=b'PIPETTE/sample/20-200,2,A2,0,0,3/real'))
    print(tcp_object.callServer_DS_B(command_byte=b'DS_B/UV_to_cuvette_storage/0,7/real'))
    """
    """
    time.sleep(1)
    time.sleep(1)
    print(tcp_object.callServer_PIPETTE(command_byte=command_bytes))
    
    """
    # print(tcp_object.callServer_PUMP(command_byte=b'PUMP/single/AgNO3,2000,5,5000/real'))
    # print(tcp_object.callServer_DS_B(command_byte=b'DS_B/holder_to_storage_filled/7,0/real'))
    # time.sleep(1)
    # print(tcp_object.callServer_STORAGE(command_byte=b'STORAGE/open/5/real'))
    
    # print(tcp_object.callServer_LA(command_byte=b'LA/up/Stirrer_0/3/virtual'))
    # print(tcp_object.callServer_LA(command_byte=b'STIRRER/stir/0/600/real'))
    # print(tcp_object.callServer_LA(command_byte=b'STIRRER/stop/real'))

    # print(tcp_object.callServer_PUMP(command_byte=b'PUMP/multi/NaBH4,H2O/1500,2000/2000,2000/real'))
    
    # for i in range(8):
    #     print(11)
    #     Reference_result = tcp_object.callServer_UV(command_byte=b"UV/Reference/real")
    #     Reference_dict=json.loads(Reference_result)
    #     with open("Reference_UV.json", 'w') as outfile:
    #         json.dump(Reference_dict, outfile)
    #     tcp_object.callServer_PIPETTE(b'PIPETTE/sample/0/A5/real')

    #     Abs_result = tcp_object.callServer_UV(command_byte=b"UV/Abs/real")
    #     Abs_dict=json.loads(Abs_result)
    #     with open("Abs_UV.json", 'w') as outfile:
    #         json.dump(Abs_dict, outfile)

    # import time

    # time.sleep(10)
    


        
    # print(type(result))