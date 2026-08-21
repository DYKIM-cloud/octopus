from datetime import datetime
from Master.Job.JobExecution_Class import JobExecution

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

    def __init__(self, server_logger:object, job_id_generator:object, job_wait_queue:list, job_exec_queue:list, job_hold_queue:list, task_hardware_status_dict:dict):
        JobScriptError.__init__(self)
        self.BUFF_SIZE = 4096
        self.the_number_of_job=99 # can change the CAPA of job_queue
        self.server_logger=server_logger
        self.job_id_generator=job_id_generator
        # job queue
        self.job_wait_queue=job_wait_queue
        self.job_exec_queue=job_exec_queue
        self.job_hold_queue=job_hold_queue
        # hardware status
        self.task_hardware_status_dict=task_hardware_status_dict
    
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
        
        job_execution_obj=JobExecution(job_script) # convert job script file to job execution object
        self.job_wait_queue.append(job_execution_obj)

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
        total_job_queue=self.job_wait_queue+self.job_hold_queue # exclude job_exec_queue
        try:
            job_id_list=[]
            for job_exec in total_job_queue:
                job_exec_id=job_exec.jobID
                job_id_list.append(job_exec_id)
            job_id_index=job_id_list.index(job_id)
            # match requested userName == submitted userName
            if user_name == total_job_queue[job_id_index].userName:
                popped_job_exec=total_job_queue.pop(job_id_index)
                # delete job script in job_script_queue
                if popped_job_exec.TaskLogger_obj.status == "Waiting...":
                    self.job_wait_queue.remove(popped_job_exec)
                    command_byte="succeed to delete job (jobID:{})".format(job_id)
                    client_socket.sendall(command_byte.encode('utf-8'))
                # delete holded job script in hold_job_script_queue
                elif popped_job_exec.TaskLogger_obj.status == "Holding...":
                    self.job_hold_queue.remove(popped_job_exec)
                    command_byte="succeed to delete job (jobID:{})".format(job_id)
                    client_socket.sendall(command_byte.encode('utf-8'))
                # wrong status. unspecified status (Please check status from admin) 
                else:
                    command_byte="Wrong status:{}. Please check status from admin".format(job_id, popped_job_exec.TaskLogger_obj.status)
                    client_socket.sendall(command_byte.encode('utf-8'))
            # requested userName != submitted userName
            else:
                command_byte='JobExecution object is not subscriptable'
                client_socket.sendall(command_byte.encode('utf-8'))
        # ValueError --> job_id_index=job_id_list.index(job_id)
        # job_id isn't include in job_script_queue --> could inside in job_exec_queue
        except ValueError:
            command_byte="You cannot delete directly. Please hold job_id:{} exec file first & delete sequentially".format(job_id)
            client_socket.sendall(command_byte.encode('utf-8'))
        except TypeError:
            command_byte="You cannot delete directly. Please hold job_id:{} exec file first & delete sequentially".format(job_id)
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
        job_id_exec_list=[]
        try:
            for job_exec in self.job_exec_queue:
                job_exec_id=job_exec.jobID
                job_id_exec_list.append(job_exec_id)
            job_id_index=job_id_exec_list.index(job_id)
            # match requested userName == submitted userName
            if user_name == self.job_exec_queue[job_id_index].userName:
                popped_job_exec=self.job_exec_queue.pop(job_id_index)
                popped_job_exec.TaskLogger_obj.status="Holding..."
                self.job_hold_queue.append(popped_job_exec)
                res_msg=popped_job_exec.hold()
                command_byte="succeed to hold job (jobID: {})".format(job_id)
                client_socket.sendall(command_byte.encode('utf-8'))
                for hardware_name in self.task_hardware_status_dict.keys():
                    self.self.task_hardware_status_dict[hardware_name]=False
            else:
                command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
                client_socket.sendall(command_byte.encode('utf-8'))
        except ValueError as e:
            command_byte="ValueError:{}. It is not inside queue (user_name={}). please check your jobID:{}".format(e, user_name, job_id)
            client_socket.sendall(command_byte.encode('utf-8'))

    def qrestart(self, client_socket, user_name, job_id):
        """
        restart job script or job execution (wait and hold)

        :param client_socket (object) : socket object
        :param user_name (str) : userName ex) HJ, NY...
        :param job_id (int) : generated jobID ex) 1,2,...
        """
        # extract jobID from job_script_queue
        job_id_exec_list=[]
        for job_exec in self.job_hold_queue:
            job_exec_id=job_exec.jobID
            job_id_exec_list.append(job_exec_id)
        try:
            job_id_index=job_id_exec_list.index(job_id)
            # match requested userName == submitted userName
            if user_name == self.job_hold_queue[job_id_index].userName:
                poped_job_hold=self.job_hold_queue.pop(job_id_index)
                poped_job_hold.TaskLogger_obj.status="Restart..."
                self.job_exec_queue.append(poped_job_hold)
                res_msg=poped_job_hold.restart()
                command_byte="succeed to restart job (jobID: {})".format(job_id)
                client_socket.sendall(command_byte.encode('utf-8'))
            else:
                command_byte="It is not your job (user_name={}). please check your jobID".format(user_name)
                client_socket.sendall(command_byte.encode('utf-8'))
        except ValueError as e:
            command_byte="ValueError:{}.It is not inside queue (user_name={}). please check your jobID:{}".format(e, user_name, job_id)
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
            exec_queue_list=self.job_wait_queue+self.job_exec_queue+self.job_hold_queue
            if len(exec_queue_list)!=0:
                for job_exec in exec_queue_list:
                    row=[]
                    for column_name in column_names_list:
                        if column_name=="status":
                            row.append(job_exec.TaskLogger_obj.status)
                        else:
                            row.append(getattr(job_exec, column_name))
                    total_row_list.append(row)
            else:
                pass # return total_row_list=[]
        except TypeError as e:
            print("TypeError", e)

        client_socket.sendall(str(total_row_list).encode('utf-8'))