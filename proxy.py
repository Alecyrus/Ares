# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang


import os
import sys

import requests
import socket
import six
from threading import Thread
from multiprocessing import Process
from pprint import pprint
import configparser


INI_FILE_PATH= 'setting.conf'


class _Proxy(Process):
        def __init__(self):
                super(_Proxy, self).__init__()
                try:
                    self._parser_config()
                except Exception as e:
                    raise

                self.session = requests.Session()

        def _parser_config(self):
                config = configparser.ConfigParser()
                config.read(INI_FILE_PATH)

                self.region_config = config
                self.region_list = config['basic']['region'].replace(' ','').split(',')

                self.image_dir = config["basic"]["image_dir"]
                self.identity_service = config["provider"]["identity_provider"]
                self.image_service = config["provider"]["image_provider"]
                self.compute_service = config["provider"]["compute_provider"]
                self.network_service = config["provider"]["network_provider"]

                self.service_version = eval(config["auth"]["service_version"])
                self.service_list = config["auth"]["service_list"].replace(' ','').split(',')


        def _get_auth(self, region, service):
                try:
                    conn = Connection(region=region)
                    self.url, self.header = conn._connect(service)
                except Exception as e:
                    raise



        def _check_existence(self, resource_type, value, url=None):
                if not url:
                    #raisr AttributeError("Missing the url parameter")
                    url = self.url
                url = "%s/%s" % (url, resource_type)
                obj = self._send_request("GET", url, headers=self.headers)
                for result in obj.json()[resource_type]:
                        if result["name"] == value or result["id"] == value:
                                return result["id"]
                return None

        def _send_request(self, method, url, json=None, data=None, headers=None):
                try:
                        resp = self.session.request(method,
                                                    url,
                                                    json=json,
                                                    data=data,
                                                    headers=headers)
                except Exception as e:
                    if resp:
                        resp.raise_for_status()
                        raise AttributeError("Failed to finish the operation. code: %s Info: %s  url: %s" % (str(resp.status_code, resp.content, url)))
                    raise AttributeError("Failed to finish the operation.")
                return resp

        def _create(self, resource_type, message):
                url = "%s/%s" %(self.url, resource_type)
                return self._send_request("POST", url, json=message, headers=self.headers)

        def _delete(self, resource_type, message=None, value=None):
                for reso in resource_type:
                        if value:
                                obj_id = self._check_existence(reso, value)
                        else:
                                obj_id = self._check_existence(reso, message[reso[:-1]]["name"])
                        if obj_id:
                                url = "%s/%s/%s" %(self.url, reso, obj_id)
                                self._send_request("DELETE", url, headers=self.headers)
                return True


        def _update(self, resource_type, message):
                url = "%s/%s/%s" % (self.url, resource_type, message["id"])
                self._send_request("PATCH", url, json=message["content"], headers=self.headers)
                return True

        def _response(self, msg, success=False):
                response = {"state":0}
                if success:
                        response["state"] = 1
                response["info"] = msg
                return response


        def _get_data_size(self, file_obj):
                if (hasattr(file_obj, "seek") and hasattr(file_obj, "tell") and
                            (six.PY2 or six.PY3 and file_obj.seekable())):
                        try:
                                current = file_obj.tell()
                                file_obj.seek(0, os.SEEK_END)
                                size = file_obj.tell()
                                file_obj.seek(current)
                                return size
                        except IOError as e:
                                if e.errno == errno.ESPIPE:
                                        return
                                else:
                                    raise
if __name__ == "__main__":
        a = _Proxy()
