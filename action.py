# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang

#!/usr/bin/env python

import os
import sys

import time
import logging
import logging.config

from pprint import pprint

from proxy import _Proxy
from auth import Connection
#import cloghandler

from db_wrapper import api as SQL
import models



logging.config.fileConfig("logging.ini")
LOG=logging.getLogger("user")



class ServerAction(_Proxy):
    def __init__(self):
        super(ServerAction, self).__init__()


    def get_auth(self, user_id):
        try:
            userinfo = SQL.query_one(models.User, id=user_id)
            self.region_id = userinfo['region_id']
            self.controller_ip = self.region_config[self.region_id]['controller_ip']
            self.conn = Connection(region=self.region_id)
            self.url, self.headers = self.conn._connect(self.compute_service)
        except Exception as e:
            LOG.error(e)
            raise AttributeError("Failed to get authentication")


    def _update_target(self, target):
        # Update the target's state
        servers = SQL.query(models.VM, target=target)
        flag = 0
        for server in servers:
           if server['state']:
               flag = 1
               break
        SQL.update_one(models.Target, {"id":target}, {"state":flag})

    def _action(self, message, optype):
        # Get parameters
        if 'json_content' in message.keys():
            message = message['json_content']
        body={"os-start":None, "os-stop":None}
      
        # Single machine
        single = message.get("server_id", False)
        if optype:
            body.pop("os-stop")
        else:
            body.pop("os-start")
        try:
            if not single:
                target_info = SQL.query_one(models.Target, user=message["user_id"], template=message["template_id"], deleted=0)
                target_id = target_info['id']
            else:
                target_id = SQL.query_one(models.VM, id=message['server_id'][0], deleted=0)['target']
                target_info = SQL.query_one(models.Target, id=target_id, deleted=0)


            if (not single) and (target_info['deleted'] == 1 or target_info['state'] == optype):
                if optype:
                    callback = "The target(id:%s) is deleted or is already running." % target_id
                else:
                    callback = "The target(id:%s) is deleted or is already stopped." % target_id
                LOG.error(callback)
                return self._response(callback, True)

            servers = SQL.query(models.VM, target=target_id)

            # Get authentication
            try:
                self.user_id = message['user_id']
                self.get_auth(self.user_id)
            except Exception as e:
                LOG.error(e)
                return self._response("Failed to get authentication.")

            # Start or Shutdown machines
            for server in servers:
                url = "%s/servers/%s/action" % (self.url, server['vm_op_id'])
                try:
                    if not  single:
                        resp = self._send_request("POST", url, json=body, headers=self.headers)
                        SQL.update_one(models.VM, {"vm_op_id":server['vm_op_id']}, {"state":optype})
                    elif server["id"] in message["server_id"]:
                        resp = self._send_request("POST", url, json=body, headers=self.headers)
                        SQL.update_one(models.VM, {"vm_op_id":server['vm_op_id']}, {"state":optype})
                except Exception as e:
                    LOG.error(e)
                    pass
            self._update_target(target_id)
        except Exception as e:
            LOG.warning(e)
            LOG.error("The Object is unaccessable.")
            msg = "Failed to complete the operation. More info: Target is unaccessable."
            return self._response(msg, True)
            #if optype:
                #return self._response(msg, True)
            #return self._response(msg)
        if optype:
            callback = "Target(id:%s)  is started." % target_id
        else:
            callback = "Target(id:%s)  is stopped." % target_id
        if single:
            head = "The host(id:%s)" % single
            callback = "%s%s" % (head, callback[14:])

        LOG.info(callback)

        return self._response(callback, True)

    def _get_user_template(self, template_id_list):
       result = dict()
       for template_id in template_id_list:
           users = SQL.query(models.Target, deleted=0, template=template_id)
           if not users:
               continue
           result[str(template_id)] = []
           for user in users:
               result[str(template_id)].append(user['user'])
       LOG.info("Get Users and Templates successfully")
       return self._response(result, True)

    def get(self, message):
        if 'json_content' in message.keys():
            message = message['json_content']
        try:
            if not ("user_id" in message):
                return self._get_user_template(message['template_id'])
        except Exception as e:
            LOG.error(e)
            callback = "No Vaild Parameters."
            return self._response(callback)
        vnc_list=[]
        body = {"os-getVNCConsole": {"type": "novnc"}}


        # Get authentication
        try:
            self.user_id = message['user_id']
            self.get_auth(self.user_id)
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to get authentication.")
 
        try:
            target = SQL.query_one(models.Target, user=message["user_id"], template=message["template_id"], deleted=0)['id']
            servers = SQL.query(models.VM, target=target)
            for server in servers:
                url = "%s/servers/%s/action" % (self.url, server['vm_op_id'])
                resp = self._send_request("POST", url, json=body, headers=self.headers)
                url = resp.json()['console']['url'].replace("controller", self.controller_ip)
                vnc_list.append({"id":server['id'], "server_name":server["name"], "uri":url, "ip_address":server['ip_address']})

        except Exception as e:
            callback = "Failed to get the vnc console."
            LOG.error(e)
            pprint(e)
            return self._response(callback)
        LOG.info("Get Console successfully")
        return self._response(vnc_list, True)

    def stop(self, message):
        return self._action(message, 0)

    def start(self,message):
        return self._action(message, 1)

if __name__ == "__main__":
    service = ServerAction()
    #service.shutdown({"server_id":[54]})
    #service.shutdown({"user_id":1, "template_id":2})
    #time.sleep(5)
    #service.start({"user_id":1, "template_id":2})
    service.start({"server_id":[54]})

    #print(service.get({"template_id":[1,2,3]}))
    #print(service.get({"user_id":2,"template_id":2}))


