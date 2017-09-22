# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang


import os
import sys

import requests
import uuid
import time
import logging
import logging.config
from pprint import pprint

from proxy import _Proxy
from auth import Connection
import cloghandler

from db_wrapper import api as SQL
import models


logging.config.fileConfig("logging.ini")
LOG=logging.getLogger("user")


class AccountsManager(_Proxy):
    def __init__(self):
        super(AccountsManager, self).__init__()

        self.msg_success = "Operation completed."
        self.msg_failed = "Failed to complete the operation."


    def assign_region(self, user_id):
        try:
            self.region_id = self.region_list[int(user_id)%len(self.region_list)]
        except Exception as e:
            raise

    def _param_message(self, message):
        try:
            self.user_id = int(message['url_content']["user_id"][0])
            
            userinfo = SQL.query_one(models.User, id=self.user_id)
            if not userinfo:
                raise AttributeError("Failed to get the information of the account in the database")
            pre = userinfo['id']
            self.username = "%s%s" % (pre, str(uuid.uuid1()).replace("-","")[:10])
            return {"user":{"name":self.username}}
        except Exception as e:
            msg_failed = "The accout(id:%s) does not exit. " % self.user_id
            LOG.error(msg_failed+str(e))
            return False

    def _create_user(self, message):
        message['user']['domain_id'] = self.domain_id
        return self._create("users", message).json()["user"]["id"]


    def _create_project(self, message):
        body = {"project":{"domain_id":self.domain_id,"name":message["user"]["name"]}}
        return self._create("projects", body).json()['project']['id']


    def get_auth(self, service):
        try:
            conn = Connection(region=self.region_id)
            self.url, self.headers = conn._connect(service)
        except Exception as e:
            raise

    def create(self, message_r):
        # Check whether the request is valid or not
        message = self._param_message(message_r)
        if not message:
            return self._response("The accout(id:%s) does not exit." % self.user_id)

        # Assign a region to the account
        try:
            self.assign_region(self.user_id)
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to assign region") 

        # Get authrntication
        try:
            self.get_auth(self.identity_service)
            self.admin_role_id = self.region_config[self.region_id]['admin_role_id']
            self.domain_id = self.region_config[self.region_id]['domain_id']
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to get authentication.")

        # Check whether the account is duplicated or not
        if self._check_existence("users", message["user"]['name']) \
            or self._check_existence("projects", message["user"]):
            moreinfo = "The user has owned a opensatck account."
            LOG.error(moreinfo)
            msg = "%s More info:%s" % (self.msg_failed, moreinfo)
            return self._response(msg, True)

        # Generate the password
        message['user']['password'] = "%s" %  str(uuid.uuid1()).replace("-","")

        # Create a project and a user for the account
        user_id = self._create_user(message)
        project_id = self._create_project(message)

        # Assign the admin role to the user for the project
        url = "%s/projects/%s/users/%s/roles/%s" % (self.url, project_id, user_id, self.admin_role_id)
        self._send_request("PUT", url, headers=self.headers)

        # Write into the database 
        try:
            SQL.update_one(models.User,
                       {'id':self.user_id},
                       {'op_user':user_id, 'op_project':project_id, 'op_passwd':message['user']['password'],'op_username':self.username,'region_id':self.region_id})
        except Exception as e:
            LOG.error(e)
            msg = "%s More info: Failed to create the openstack account. %s" % (self.msg_failed, str(e))
            return self._response(msg, True)


        # Callback
        response = "Account(username:%s) is created." % message["user"]["name"]
        LOG.info(response)
        msg = "%s. %s" % (self.msg_success, response)
        return self._response(msg, True)

    def delete(self, message):
        print(message['json_content']['user_id_list'])
        try:
            for m in  message['json_content']['user_id_list']:
                try:
                    print('one')
                    temp = {"url_content":{"user_id":[int(m)]}}
                    self.delete_user(temp)
                except Exception as e: 
                    LOG.error(e)
                    pass
        except Exception as e:
            LOG.error(e)
            msg = "%s More info: Failed to delete the openstack accounts. %s" % (self.msg_failed, str(e))
            return self._response(msg, True)
        response = "Accounts are deleted succennfully.  %s" % str(message['json_content']['user_id_list'])
        msg = "%s. %s" % (self.msg_success, response)
        LOG.info(msg)
        return self._response(msg, True)
                 
    def delete_user(self, message_r):
        # Check whether the request is valid or not
        check = self._param_message(message_r)
        if not check:
            msg_failed = "The accout(id:%s) does not exit." % self.user_id
            LOG.error(msg_failed)
            raise
            #return self._response(msg_failed, True)
        try:
            # Get username
            username = SQL.query_one(models.User, id=self.user_id)['op_username']

            # Get region and get authentication
            self.region_id = SQL.query_one(models.User, id=self.user_id)['region_id']
            try:
                self.get_auth(self.identity_service)
                self.admin_role_id = self.region_config[self.region_id]['admin_role_id']
            except Exception as e:
                LOG.error(e)
                raise
                #return self._response("Failed to get authentication.")
            # Delete user and project, and update the database
            message =  {"user":{"name":username}}
            message["project"] = message["user"]
            if self._delete(["projects", "users"], message):
                SQL.update_one(models.User,{'id':self.user_id}, {"op_user":'',"op_project":'',"op_passwd":'','op_username':''})
                LOG.info("Account(username:%s) is deleted." % message["user"]["name"])
        except Exception as e:
            LOG.error(e)
            msg = "%s More info: Failed to detele the openstack account. %s" % (self.msg_failed, str(e))
            raise
            #return self._response(msg)
        # Callback
        #response = "Account(username:%s) is deleted." % message["user"]["name"]
        #msg = "%s. %s" % (self.msg_success, response)
        #return self._response(msg, True)

if __name__ == "__main__":
    service = AccountsManager()
    service.create({'url_content':{"user_id":[4]}})
    #time.sleep(5)
    #pprint(service.create({"user_id":6}))
    #pprint(service.delete({"user_id":6}))



