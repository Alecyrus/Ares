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
import common.progressbar as progressbar

logging.config.fileConfig("/home/hjk/oesbackground/logging.ini")
LOG=logging.getLogger("template")

IMAGES_DIR="images/"

class ImagesManager(_Proxy):
    def __init__(self):
        super(ImagesManager, self).__init__()

        conn = Connection()
        self.url, self.headers = conn._connect(self.image_service)


    def _get_data_file(self, filename):
        # path = "%s/%s" % (self.image_dir, filename)
        path = filename
        if os.path.exists(path):
            return open(path, 'rb')
        else:
            pprint("ERROR 1356")
            return None


    def create(self, message, debug=True):
        if self._check_existence("images", message['image']['name']):
            pprint("It exists")
            return False
        image_id = self._create("images", message['image']).json()['id']
        image_data = self._get_data_file(message['filename'])
        LOG.info("Image(name:%s) is uploading." % message['image']['name'])
        if debug:
            filesize = self._get_data_size(image_data)
            if filesize is not None:
                image_data = progressbar.VerboseFileWrapper(image_data, filesize)
        url = "%s/images/%s/file" % (self.url, image_id)
        self.headers['Content-Type'] = "application/octet-stream"
        self._send_request("PUT", url, data=image_data, headers=self.headers)
        LOG.info("Image(name:%s) is uploaded." % message['image']['name'])
        url = "%s/images/%s" % (self.url, image_id)
        resp = self._send_request("GET", url, headers=self.headers)
        print(resp.json())

        return image_id

    def delete(self, message):
        if self._delete(["images"], message):
            LOG.info("Image(name:%s) is deleted." % message['image']['name'])
        return True

    def update(self, message):
        """para name is nessceary """
        image = self._check_existence("images", message["name"])
        if not image:
            pprint("NOT EXIST")
            return False
        self.headers['Content-Type'] = "application/openstack-images-v2.1-json-patch"
        body = {"content":[],"id":image}
        for key, value in message['image'].items():
            new = {"op":"replace","path":"/"+key,"value":value}
            body["content"].append(new)
        if self._update("images", body):
            LOG.info("Image(name:%s) is updated." % message['image']['name'])

        return True




if __name__ == "__main__":
    service = ImagesManager()
    #service.create({"image":{"name":"2033","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"2009","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"2010","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"2011","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"2012","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"2013","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"/home/hjk/upload/media/os/winxp_1489478228722_b49b362b-1c22-4c49-bad7-9fb4fb3faac5.qcow2"})
    #service.create({"image":{"name":"20173151803","container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"ubuntu_server.img"})
    #time.sleep(5)
    #service.update({"image":{"name":"test2"},"name":"test1"})
    #time.sleep(5)
    #service.delete({"image":{"name":"test2", "container_format":"bare","disk_format":"qcow2","visibility":"public"},"filename":"cirros.img"})


