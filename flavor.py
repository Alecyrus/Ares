# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang

import os
import sys

import time
import logging
import logging.config
import uuid

from pprint import pprint

from proxy import _Proxy
from auth import Connection
import cloghandler


from db_wrapper import api as SQL
import models

logging.config.fileConfig("logging.ini")
LOG=logging.getLogger("template")

class FlavorsManager(_Proxy):
    def __init__(self):
        super(FlavorsManager, self).__init__()


    def get_auth(self, message):
        try:
            self.region_id = message['url_content']['region_id'][0]
            conn = Connection(region=self.region_id)
            self.url, self.headers = conn._connect(self.compute_service)
        except Exception as e:
            raise

    def create(self, message):
        # Get authentication
        try:
            self.get_auth(message)
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to get authentication.")
        # Get the image's id and Get the infomation of the flavor to be created
        self.image_id = int(message['url_content']["image_id"][0])
        try:
            flavor_info = SQL.query_one(models.ALLImage, id = self.image_id)
            name = "%s%s" % (flavor_info['name'], str(uuid.uuid1()).replace("-","")[:10])
            request = {"flavor":{"name":name,"ram":flavor_info['ram'],"vcpus":flavor_info['cpu'],"disk":flavor_info['disk']}}
            if not flavor_info:
                raise AttributeError
        except Exception as e:
            failed_msg = "Failed to get the information of the image(id:%s).s flavor.Please check the parameters and try it again."
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return self._response(failed_msg)

        # Create a flavor for the image
        try:
            resp =  self._create("flavors", request)
            if not resp.ok:
                LOG.error(str(resp.content))
                raise AttributeError
        except Exception as e:
            failed_msg = "Failed to get the information of the image.s flavor."
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return self._response(failed_msg)
        # Write the flavor's id into the AllImage table
        try:
            SQL.update_one(models.ALLImage, {'id':self.image_id}, {'flavor_op_id':resp.json()['flavor']['id']})
            msg = "Flavor(image_id:%s) is created successfully" % self.image_id
            LOG.info(msg)
            return self._response(msg, True)
        except Exception as e:
            failed_msg = "Failed to create the image.s(id:%s) flavor." % self.image_id
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return self._response(failed_msg)

    def delete(self, message):
        # Get Authentication
        try:
            self.get_auth(message)
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to get authentication.")


        # Get the image's id and get the flavor's id, and delete the flavor later
        self.image_id = int(message['url_content']["image_id"][0])
        try:
            flavor_id = SQL.query_one(models.ALLImage, id = self.image_id)['flavor_op_id']
            #request = {"flavor":{"name":flavor_info['name']}}
            if self._delete(["flavors"], value=flavor_id):

                # Erase the favor's id
                msg = "Flavor(image_id:%s) is deleted successfully" % self.image_id
                SQL.update_one(models.ALLImage,{'id':self.image_id}, {"flavor_op_id":''})
                LOG.info(msg)
                return self._response(msg, True)
        except Exception as e:
            failed_msg = "Failed to delete flavor(image_id:%s)." % self.image_id
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return self._response(failed_msg)

    def update(self, message):
        # Get Authentication
        try:
            self.get_auth(message)
        except Exception as e:
            LOG.error(e)
            return self._response("Failed to get authentication.")

        # Get the image's id, and update the flavor
        self.image_id = int(message['url_content']["image_id"][0])
        try:
            self.delete(message)
            self.create(message)
            msg = "Flavor(image_id:%s) is updated successfully" % self.image_id
            LOG.info(msg)
            return self._response(msg, True)
        except Exception as e:
            failed_msg = "Failed to update flavor(image_id:%s)." % self.image_id
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return self._response(failed_msg)

if __name__ == "__main__":
    service = FlavorsManager()
    #service.update({"image_id":12})
    service.delete({"image_id":15})
    #service.create({"image_id":15})


