# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang

#!/usr/bin/env python

import os
import sys

import requests

from pprint import pprint

from db_wrapper import api as SQL
import models

from proxy import _Proxy



class Connection(_Proxy):
    def __init__(self, region=None, user_id=None, admin=False):
        super(Connection, self).__init__()

        self.headers = {"Content-Type":"application/json"}
        if not region and not user_id:
            raise AttributeError("Please specific the region")
       
        self.url = "http://%s:35357/v3/auth/tokens" % self.region_config[region]['controller_ip'] 
        self.controller_ip = self.region_config[region]['controller_ip']
        self.identity_url = "http://%s" % self.region_config[region]['controller_ip']
        if not user_id:
            admin = True
            self.username =  self.region_config[region]['username']
            self.password = self.region_config[region]['password']
            self.project = self.region_config[region]['project_id']
        try:
            if not admin:
                user_info = SQL.query_one(models.User, id=user_id)
                self.username = user_info["op_username"]
                self.password = user_info["op_passwd"]
                self.project = user_info["op_project"]
            json = {"auth":{
                            "identity":{
                                    "methods":["password"],
                                    "password":{
                                     "user":{"name":self.username,
                                             "domain":{"name":"default"},
                                             "password":self.password
                                    }}},
                            "scope":{"project":{"id":self.project}}
                    }
            }

            resp =  self._send_request("POST", url=self.url, json=json, headers=self.headers)
        except Exception as e:
            raise
        self.endpoints = resp.json()['token']['catalog']
        self.token = resp.headers['X-Subject-Token']

    def _connect(self, service):
        if service not in self.service_list:
            pprint("SERVICE ERROR")
            return
        for endpoint in self.endpoints:
                if endpoint["name"] == service:
                    url = endpoint['endpoints'][1]["url"]
        self.headers["X-Auth-Token"] = self.token

        if service in self.service_version:
            url = "%s/%s" % (url, self.service_version[service])

        return url.replace("controller", self.controller_ip), self.headers



if __name__ == "__main__":
        conn = Connection()
        url, headers = conn._connect("keystone")
        resp = conn._send_request("GET", url=url+"/users",headers=headers)
        pprint(resp.json())





