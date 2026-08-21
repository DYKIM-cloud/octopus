from datetime import datetime

class JobScriptError:

    def setBoundary(self):
        """
        constant.py를 통해 설정된 boundary가 존재함. 
        이를 반영해서, job script file을 잘 못 만들면 어떤 부분을 몇 미만으로 수정해라 이런식에 에러를 띄워야함
        """
        pass

    def checkJobScript(self, job_script_dict):
        pass

class JobScheduler(JobScriptError):
    """
    [JobScheduler] JobScheduler Class for scheduling job

    # function
    - qsub(client_socket, user_name, job_script_name, job_script):
    - qdel(client_socket, job_id)
    - qhold(client_socket, job_id)
    - qrestart(client_socket, job_id)
    - qstat(client_socket)
    """

    def __init__(self, server_logger:object, job_id_generator:object, job_script_queue:list, hold_job_script_queue:list, job_exec_queue:list, hold_job_exec_queue:list):
        JobScriptError.__init__(self)
        self.BUFF_SIZE = 4096
        self.the_number_of_job=99 # can change the CAPA of job_queue
        self.server_logger=server_logger
        self.job_id_generator=job_id_generator
        # job queue
        self.job_script_queue=job_script_queue
        self.hold_job_script_queue=hold_job_script_queue
        # exec queue
        self.job_exec_queue=job_exec_queue
        self.hold_job_exec_queue=hold_job_exec_queue
    
    def qsub(self, client_socket, user_name, job_script_filename, job_script, mode_type):
        """
        submit job script

        :param client_socket (object) : socket object
        :param user_name (str) : userName ex) HJ, NY...
        :param job_script_filename (str) : 20230516_automatic -> real path : "USER/{user_name}/job_script/{job_script_filename}.json"
        :param job_script (dict) : read job_script 
            -> job_script={
                "metadata":{}
                "recipe":{}
            }
        :param mode_type (str) : "real" or "virtual"
        """
        empty_true = self.job_id_generator.empty()
        if empty_true==True:
            for job_id in range(self.the_number_of_job):
                self.job_id_generator.put(job_id)
        job_id=self.job_id_generator.get()

        now = datetime.now()
        current_time = now.strftime("%m-%d %H:%M:%S")
        job_script["metadata"]["jobTime"]=current_time
        job_script["metadata"]["jobID"]=job_id
        job_script["metadata"]["jobFileName"]=job_script_filename
        job_script["metadata"]["userName"]=user_name
        job_script["metadata"]["modeType"]=mode_type
        job_script["metadata"]["status"]="Waiting..."
        self.job_script_queue.append(job_script)

        command_byte="succeed to submit job, userName:{}, jobID:{}".format(user_name, job_id)
        client_socket.sendall(command_byte.encode('utf-8'))

    def qdel(self, client_socket, user_name, job_id):
        """
        delete job script or job execution (wait and hold)

        :param client_socket (object) : socket object
        :param user_name (str) : userName ex) HJ, NY...
        :param job_id (int) : generated jobID ex) 1,2,...
        """
        # check job script queue
        # extract jobID from job_script_queue
        total_job_queue=self.job_script_queue+self.hold_job_script_queue+self.hold_job_exec_queue # exclude job_exec_queue
        job_id_list=[]
        for job_script in total_job_queue:
            job_script_id=job_script["metadata"]["jobID"]
            job_id_list.append(job_script_id)
        
        try:
            job_id_index=job_id_list.index(job_id)
            # match requested userName == submitted userName
            if user_name == total_job_queue[job_id_index]["metadata"]["userName"]:
                popped_job_script=total_job_queue.pop(job_id_index)
                # delete job script in job_script_queue
                if popped_job_script["metadata"]["status"] == "Waiting...":
                    self.job_script_queue.remove(popped_job_script)
                    command_byte="succeed to delete job (jobID:{})".format(job_id)
                # delete holded job script in hold_job_script_queue
                elif popped_job_script["metadata"]["status"] == "Holding...":
                    self.hold_job_script_queue.remove(popped_job_script)
                    command_byte="succeed to delete job (jobID:{})".format(job_id)
                # wrong status. unspecified status (Please check status from admin) 
                else:
                    command_byte="Wrong status:{}. Please check status from admin".format(job_id, popped_job_script["metadata"]["status"])
            # requested userName != submitted userName
            else:
                command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
        # ValueError --> job_id_index=job_id_list.index(job_id)
        # job_id isn't include in job_script_queue --> could inside in job_exec_queue
        except ValueError:
            command_byte="You cannot delete directly. Please hold job_id:{} exec file first & delete sequentially".format(job_id)
        # finally, always send command_byte although has error
        finally:
            client_socket.sendall(command_byte.encode('utf-8'))
        
    def qhold(self, client_socket, user_name, job_id): 
        """
        hold job script or job execution (wait and hold)

        :param client_socket (object) : socket object
        :param user_name (str) : userName ex) HJ, NY...
        :param job_id (int) : generated jobID ex) 1,2,...
        """
        # check job script queue
        # extract jobID from job_script_queue 
        job_id_list=[]
        for job_script in self.job_script_queue:
            job_script_id=job_script["metadata"]["jobID"]
            job_id_list.append(job_script_id)
        try:
            job_id_index=job_id_list.index(job_id)
            # match requested userName == submitted userName
            if user_name == self.job_script_queue[job_id_index]["metadata"]["userName"]:
                popped_job_script=self.job_script_queue.pop(job_id_index)
                popped_job_script["metadata"]["status"]="Holding..."
                self.job_script_queue.remove(popped_job_script)
                self.hold_job_script_queue.append(popped_job_script)
                command_byte="succeed to hold job (jobID:{})".format(job_id)
            else:
                command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
        # ValueError --> job_id_index=job_id_list.index(job_id)
        # job_id isn't include in job_script_queue --> could inside in job_exec_queue
        except ValueError:
            # extract jobID from job_exec_queue 
            job_id_exec_list=[]
            for job_exec in self.job_exec_queue:
                job_exec_id=job_exec.jobID
                job_id_exec_list.append(job_exec_id)
            try:
                job_id_index=job_id_exec_list.index(job_id)
                # match requested userName == submitted userName
                if user_name == self.job_exec_queue[job_id_index].userName:
                    poped_job_exec=self.job_exec_queue.pop(job_id_index)
                    poped_job_exec.status="Holding..."
                    poped_job_exec.hold()
                    self.hold_job_exec_queue.append(poped_job_exec)
                    command_byte="succeed to hold job (jobID: {})".format(job_id)
                else:
                    command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
            except ValueError as e:
                command_byte="It is not inside queue (user_name={}). please check your jobID:{}".format(user_name, job_id)
        # finally, always send command_byte although has error
        finally:
            client_socket.sendall(command_byte.encode('utf-8'))

    def qrestart(self, client_socket, user_name, job_id):
        """
        restart job script or job execution (wait and hold)

        :param client_socket (object) : socket object
        :param user_name (str) : userName ex) HJ, NY...
        :param job_id (int) : generated jobID ex) 1,2,...
        """
        # extract jobID from job_script_queue
        hold_job_id_list=[]
        for job_script in self.hold_job_script_queue:
            job_script_id=job_script["metadata"]["jobID"]
            hold_job_id_list.append(job_script_id)
        try:
            job_id_index=hold_job_id_list.index(job_id)
            if user_name == self.hold_job_script_queue[job_id_index]["metadata"]["userName"]:
                popped_job_script=self.hold_job_script_queue.pop(job_id_index)
                popped_job_script["metadata"]["status"]="Waiting..."
                self.hold_job_script_queue.remove(popped_job_script)
                self.job_script_queue.append(popped_job_script)
                command_byte="succeed to restart job (jobID:{})".format(job_id)
            else:
                command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
        # ValueError --> job_id_index=job_id_list.index(job_id)
        # job_id isn't include in job_script_queue --> could inside in job_exec_queue
        except ValueError:
            job_id_exec_list=[]
            for job_exec in self.job_exec_queue:
                job_exec_id=job_exec.jobID
                job_id_exec_list.append(job_exec_id)
            try:
                job_id_index=job_id_exec_list.index(job_id)
                # match requested userName == submitted userName
                if user_name == self.job_exec_queue[job_id_index].userName:
                    poped_job_exec=self.job_exec_queue.pop(job_id_index)
                    poped_job_exec.status="Submitted!..."
                    """
                    # 나중에 이 부분에 execution file에서 진행했던 사이클부터 다시 시작하는 코드 추가해야함
                    """
                    self.job_exec_queue.append(poped_job_exec)
                    command_byte="succeed to restart job (jobID: {})".format(job_id)
                else:
                    command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
            except ValueError as e:
                command_byte="It is not inside queue (user_name={}). please check your jobID:{}".format(user_name, job_id)
        # finally, always send command_byte although has error
        finally:
            client_socket.sendall(command_byte.encode('utf-8'))

    def qstat(self, client_socket):
        """
        check status of job script queue (wait and hold) & job execution queue (wait and hold)

        :param client_socket (object) : socket object
        """
        column_names_list = ["userName", "jobTime", "jobID", "jobFileName", "batchSize", "todayIterNum", "status", "modeType"]

        total_row_list=[]
        try:
            # Add rows from job execution file to status table
            total_queue_list=[]
            exec_queue_list=self.job_exec_queue+self.hold_job_exec_queue
            if len(exec_queue_list)!=0:
                for job_exec in exec_queue_list:
                    queue_info_dict={
                        "metadata":{},
                        "algorithm":{}
                    }
                    for column_name in column_names_list:
                        if column_name=="batchSize":
                            queue_info_dict["algorithm"][column_name]=getattr(job_exec, column_name)
                        elif column_name=="status":
                            queue_info_dict["metadata"][column_name]=job_exec.TaskLogger_obj.status
                        else:
                            queue_info_dict["metadata"][column_name]=getattr(job_exec, column_name)
                    total_queue_list.append(queue_info_dict)
            else:
                pass
            # Add rows from job script file to status table
            total_queue_list=self.job_script_queue+self.hold_job_script_queue+total_queue_list
            if len(total_queue_list)!=0:
                for job_script in total_queue_list:
                    row=[]
                    for column_name in column_names_list:
                        if column_name=="batchSize":
                            row.append(job_script["algorithm"][column_name])
                        else:
                            row.append(job_script["metadata"][column_name])
                    total_row_list.append(row)
            else:
                pass
        except TypeError as e:
            print("TypeError", e)

        client_socket.sendall(str(total_row_list).encode('utf-8'))