# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang

#!/usr/bin/env python

import os
import sys

import time
import pika
import logging
import logging.config
#import cloghandler

from pprint import pprint

from common.proxy import _Proxy
from common.auth import Connection
from common import cloghandler


logging.config.fileConfig("logging.ini")
LOG=logging.getLogger("user")



class QuotasManager(_Proxy):
    def __init__(self):
        super(QuotasManager, self).__init__()

        self.conn = Connection()
        self.url, self.headers = self.conn._connect(self.compute_service)



    def _get_id(self, message):
        url, headers = self.conn._connect(self.identity_service)
        return self._check_existence("projects", message['quota_set']['name'], url=url)

    def get(self, message):
        if not message.get("detail", False):
            url = "%s/os-quota-sets/%s" % (self.url, self._get_id(message))
        else:
            url = "%s/os-quota-sets/%s/detail" % (self.url, self._get_id(message))
        resp = self._send_request("GET", url, headers=self.headers)
        LOG.info("Account's(id=%s) quotas: %s" %(self._get_id(message), str(resp.json())))
        return True

    def create(self, message):
        id = self._get_id(message)
        url = "%s/os-quota-sets/%s" %(self.url, id)
        message['quota_set'].pop("name")
        resp = self._send_request("PUT", url, json=message, headers=self.headers)
        LOG.info("Account's(id=%s) quota is updated: %s " % (id, str(resp.json())))

        return True


    def delete(self, message):
        url = "%s/os-quota-sets/%s" %(self.url, self._get_id(message))
        resp = self._send_request("DELETE", url, headers=self.headers)
        LOG.info("Account's(id=%s) quota is restored" %(self._get_id(message)))
        return True

if __name__ == "__main__":
    service = QuotasManager()
    service.get({"quota_set":{"name":"test"},"detail":False})
    #time.sleep(5)
    service.create({"quota_set":{"name":"admin","force":True, "instances":100}})
    #time.sleep(5)
    service.delete({"quota_set":{"name":"admin"}})


