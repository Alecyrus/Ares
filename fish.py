# -*-coding:utf-8-*-
#!/usr/bin/env python

# Copyright (c) 2017 NIST
# All Rights Reserved.
# Author: Zhaohuie
import configparser
import copy
import json
import logging
import logging.config
import os
import os.path
import re
import shutil
import subprocess
import uuid
import math
from multiprocessing import Process
from pprint import pprint

import requests

import progressbar 
import guestfs
from auth import Connection
from proxy import _Proxy
from db_wrapper import db
from db_wrapper import api as SQL
from models import ALLImage, Image, Software, Template, Flavor, User

logging.config.fileConfig("logging.ini")
LOG = logging.getLogger("template")


class ImageInfo(object):
    def __init__(self, filename, format=None, protocol=None, server=None, username=None, secret=None, name=None, label=None):
        self.filename = filename
        self.format = format
        self.protocol = protocol
        self.name = name
        self.label = label
        self.server = server
        self.username = username
        self.secret = secret


class Fish(object):
    """A Fish object has only one guestfs handle."""
    def __init__(self):
        self._drive_reset()

    def _drive_reset(self):
        try:
            self._umount()
            self._guestfs.close()
        except AttributeError:
            pass

        self._guestfs = guestfs.GuestFS(python_return_dict=True)
        self._image = None
        self._launched = False
        self._mounted = False
        self._mount_path = False

    def _add_drive(self, image, format=None, protocol=None, server=None, username=None, secret=None, name=None, label=None):
        if type(image) is ImageInfo:
            if self._image:
                if not (self._image.filename == image.filename and self._image.server == image.server):
                    self._drive_reset()
                else:
                    return
            kwargs = image.__dict__
            filename = kwargs.pop('filename')
            try:
                self._guestfs.add_drive(filename, **kwargs)
            except RuntimeError:
                raise
            self._image = image
        else:
            if self._image:
                if not (self._image.filename == image and self._image.server == server):
                    self._drive_reset()
                else:
                    return
            try:
                self._guestfs.add_drive(image, format=format, protocol=protocol, server=server, username=username, secret=secret, name=name, label=label)
            except RuntimeError:
                raise
            self._image = ImageInfo(image, format, protocol, server, username, secret, name, label)

    def _launch(self):
        self._guestfs.launch()
        self._launched = True

    def _mount(self, drive_letter=None):
        '''
            drive_letter is used only when the image has a windows OS installed on.
            Be aware that this doesn't support multi-os image.
            '''

        root = self._guestfs.inspect_os()
        if (len(root) > 1):
            raise Exception("This function does not support multi operation system image!")

        root = root[0]

        product_name = self._guestfs.inspect_get_product_name(root)
        version = (self._guestfs.inspect_get_major_version(root), self._guestfs.inspect_get_minor_version(root))
        os_type = self._guestfs.inspect_get_type(root)
        distro = self._guestfs.inspect_get_distro(root)

        if os_type.startswith('windows'):
            # Drive_mappings is a dict, like,
            # for example: {'C': '/dev/sda2', 'D': '/dev/sda3'}
            drive_mappings = self._guestfs.inspect_get_drive_mappings(root)
            if not drive_letter:
                # default to mount C drive
                drive_letter = 'C'
            try:
                self._guestfs.mount(drive_mappings[drive_letter], '/')
            except RuntimeError as e:
                raise

        else:
            mps = self._guestfs.inspect_get_mountpoints(root)

            # Sort keys by length, shortest first
            # Note: Python 2 and Python 3 have different usage of sorted() method.
            for device in sorted(mps, key=lambda s: len(s)):
                try:
                    self._guestfs.mount(mps[device], device)
                except RuntimeError as e:
                    raise

        self._mounted = True

        if drive_letter:
            self._mount_path = (drive_letter, '/')
        else:
            self._mount_path = '/'

    def _umount(self):
        try:
            self._guestfs.umount_all()
        except:
            pass
        self._mounted = None
        self._mount_path = None

    @staticmethod
    def convert_path(remote_path):
        ''' This method convert a Windows style path into unix style and split it's drive letter out.
            For example, "C:\\Program Files\\Python" convert into a tuple ('C', "/Programs Files/Python").'''
        if remote_path.startswith(':', 1):
            drive_letter = remote_path[0]
            remote_path = re.sub(r'\\', '/', remote_path[2:])
        else:
            drive_letter = None
        # 这里要添加一个判断来检查路径是否是合法的Unix路径
        return (drive_letter, remote_path)

    def _check_drive_correctness(self, remote_path='/', image=None, format=None, protocol=None, server=None, username=None, secret=None, name=None, label=None):
        '''This function is executed before read or write files on the image
        to ensure that that the image has been added, the GuestFS has launched
        and the partition has been mounted on the root directory "/" of the
        GuestFS filesystem.'''
        (drive_letter, remote_path) = self.convert_path(remote_path)
        if image:
            try:
                self._add_drive(image, format, protocol, server, username, secret, name, label)
            except:
                raise
        if self._image:
            if not self._launched:
                self._launch()
            if not self._mounted:
                self._mount(drive_letter)
        else:
            raise Exception("No image has been specified!")

    def copy_in(self, local_path, remote_path, **kwargs):
        self._check_drive_correctness(remote_path, **kwargs)
        try:
            (local_dir, filename) = os.path.split(local_path)
            remote_filename = os.path.join(remote_path, filename)
            r = self._guestfs.upload(local_path, remote_filename)
            # r = self._guestfs.copy_in(local_path, remote_path)
        except RuntimeError as e:
            raise
        return r

    def copy_out(self, remote_path, local_path, **kwargs):
        self._check_drive_correctness(remote_path, **kwargs)
        try:
            (remote_dir, filename) = os.path.split(remote_path)
            local_filename = os.path.join(local_path, filename)
            r = self._guestfs.download(remote_path, local_filename)
            # r = self._guestfs.copy_out(remote_path, local_path)
        except RuntimeError as e:
            raise
        return r

    def read_file(self, remote_path, **kwargs):
        self._check_drive_correctness(remote_path, **kwargs)
        if self._guestfs.is_file(remote_path):
            try:
                return self._guestfs.cat(remote_path)
            except RuntimeError as e:
                raise
        else:
            raise RuntimeError("%s is not a file!" % remote_path)

    def create_file(self, remote_path, content, **kwargs):
        self._check_drive_correctness(remote_path, **kwargs)
        if self._guestfs.is_file(remote_path):
            raise RuntimeError("This file already exists."
                               "Try use write_file directly if you want to update it.")

    def write_file(self, remote_path, content, **kwargs):
        self._check_drive_correctness(remote_path, **kwargs)
        append = kwargs.get('append', False)
        if append:
            try:
                r = self._guestfs.write_append(remote_path, content)
            except RuntimeError as e:
                raise
        else:
            try:
                r = self._guestfs.write(remote_path, content)
            except RuntimeError as e:
                raise
        return r

    def sys_prep(self, image):
        self._drive_reset()
        subprocess.call("virt-sysprep -a %s" % image, shell=True)

    def read_cloud_init(self, **kwargs):
        self._check_drive_correctness('/', **kwargs)
        if self._guestfs.is_file('/etc/cloud/cloud.cfg'):
            return self._guestfs.cat('/etc/cloud/cloud.cfg')
        else:
            raise RuntimeError("Can not find the configure file of cloud-init."
                               "Please check if /etc/cloud/cloud.cfg exist and check if cloud-init has installed on the image.")

    def write_cloud_init(self, config, **kwargs):
        if os.path.isfile(config):
            config = os.path.abspath(config)
            renamed = os.path.join(os.path.dirname(config), 'cloud.cfg')
            os.rename(config, renamed)
            self.copy_in(renamed, '/etc/cloud/', **kwargs)
        else:
            self.write_file(config, '/etc/cloud/cloud.cfg', **kwargs)


class FishManager(_Proxy):
    def __init__(self):
        super(FishManager, self).__init__()
        self.fish = Fish()
        self.api_cfg = configparser.ConfigParser()
        self.api_cfg.read('api.ini')
        self.api_url = "%s:%s" % (self.api_cfg["basic"]["bind_host"], self.api_cfg["basic"]["bind_port"])

    @db
    def _query_template_info(self, template_id, session, outer):
        LOG.info("Querying from database of template %d" % template_id)
        template = session.query(Template).filter_by(id=template_id).first()
        LOG.info("template: %r" % template)
        if not template:
            LOG.info('Template %d not found!' % template_id)
            LOG.error('Template not found!')
            self._response('Template not found!')
            return None
        if template.state == 'MAKING':
            LOG.error('Template is being made!')
            LOG.info('Template %d is being made!')
            self._response('Template is being made! Unable to change it now.')
            return 'MAKING'
        image_software_mappings = []
        LOG.info("Template %d found!" % template.id)
        image_list = json.loads(template.image_list)
        LOG.info(image_list)
        sw_lists = json.loads(template.sw_list)
        LOG.info(sw_lists)
        flavor_list = json.loads(template.flavor_list)
        LOG.info(flavor_list)
        image_software_mappings.append({"image": image_list["host1"], "softwares": sw_lists["host1"]})
        if "host2" in image_list and "host2" in sw_lists:
            image_software_mappings.append({"image": image_list['host2'], "softwares": sw_lists["host2"]})
        # 返回的参数为四个字典
        LOG.info("state 2 %r" % image_software_mappings)
        return (image_software_mappings, image_list, sw_lists, flavor_list)

    @db
    def _get_image_software_location(self, image_software_mappings, session, outer):
        for m in image_software_mappings:
            image_info = session.query(Image).filter_by(id=m["image"]).first()
            if not image_info:
                LOG.warns('Unable to find image %d!' % m["image"])
                m["image"] = None
                m["softwares"] = None
                continue
            image_path = image_info.resource_path
            if not image_path:
                m["softwares"] = None
                m["image"] = None
                LOG.warns('Unalbe to query resource_path of image %d!' % m["image"])
                continue

            # m["softwares"] is a list, not a str! 
            softwares = m["softwares"]
            software_paths = []
            for software in softwares:
                try:
                    # Turn str into integer to get the id of software
                    software = int(software.strip())
                    # pprint(software)
                except:
                    LOG.warns('Some software do not exist in software database!')
                    self._response('Some software do not exist in software database!')
                    continue
                software_info = session.query(Software).filter_by(id=software).first()
                if not software_info:
                    LOG.warns('Unable to find software %d!' % software)
                    continue
                software_path = software_info.resource_path
                if not software_path:
                    LOG.warns('Unable to query resource_path of software %d!' % software)
                    continue
                software_paths.append(software_path)
            m["image"] = image_path
            m["softwares"] = software_paths
        return image_software_mappings

    @staticmethod
    @db
    def _query_base_image(base_image_id, session, outer):
        base_image = session.query(Image).filter_by(id=base_image_id).first()
        res = {}
        res["container_format"] = base_image.container_format
        res["disk_format"] = base_image.disk_format
        res["resource_path"] = base_image.resource_path
        LOG.info("Base image info get! Base image id %d" % base_image.id)
        LOG.info("Base image info:\n %s" % res)
        return res

    @staticmethod
    @db
    def _add_modified_image(name, author, mirror_op_id, resource_path, disk, cpu, ram, session, outer, flavor_op_id=None, container_format=None, disk_format=None):
        # 如果要获取新生成的镜像的id的话，需要先进行session.flush()，而后方能获取到id
        # 不过这个功能能不能实现，还要测试，如果不行的话就比较麻烦了
        # base_image = session.query(Image).filter_by(id=base_image_id).first()
        new_image = ALLImage(name=name, author=author, mirror_op_id=mirror_op_id, resource_path=resource_path,
                             disk=disk,
                             cpu=cpu,
                             ram=ram)
        if container_format:
            new_image.container_format = container_format
        if disk_format:
            new_image.disk_format = disk_format
        try:
            LOG.info(new_image)
            session.add(new_image)
            session.flush()
        except Exception as e:
            # pprint(e)
            LOG.info(e)
            raise
        id = new_image.id
        if id:
            return id
        return None

    @staticmethod
    @db
    def _update_modified_image(id, session, outer, **kwargs):
        instance = session.query(ALLImage).filter_by(id=id).first()
        for key, value in kwargs.items():
            setattr(instance, key, value)
        session.add(instance)

    @staticmethod
    @db
    def _lock_template_status(template, session, outer):
        template = session.query(Template).filter_by(id=template).first()
        template.state = 'MAKING'
        session.add(template)

    @staticmethod
    @db
    def _update_template_status(template, session, outer, image_list=None, state=None):
        # After making images with software, change template's state to the modified images.
        template = session.query(Template).filter_by(id=template).first()
        if image_list:
            if type(image_list) is dict:
                template.image_list = json.dumps(image_list)
            else:
                template.image_list = image_list
        if state:
            template.state = state
        session.add(template)

    @staticmethod
    @db
    def _query_modified_image_existence(image_name, session, outer):
        instance = session.query(ALLImage).filter_by(name=image_name).first()
        if instance:
            return (instance.mirror_op_id, instance.resource_path)
        else:
            return (None, None)

    def _copy_image_cur_dir(self, image_path):
        (dir, name) = os.path.split(image_path)
        (root, ext) = os.path.splitext(name)
        new_name = root + '_' + uuid.uuid4().__str__() + ext
        new_image_path = os.path.join(dir, new_name)
        shutil.copyfile(image_path, new_image_path)
        return new_image_path

    @staticmethod
    @db
    def _get_flavor_info(flavor_id, disk_size, session, outer):
        LOG.info("Querying flavor info of flavor")
        instance = session.query(Flavor).filter_by(id=flavor_id).first()
        cpu = instance.cpu
        ram = instance.ram

        flavor_info = dict()
        flavor_info["cpu"] = cpu
        flavor_info["ram"] = ram
        flavor_info["disk"] = disk_size
        LOG.info("Flavor info: %s" % flavor_info)

        return flavor_info
        # return {"cpu": 1, "ram": 2, "disk": 1024}


    #TODO
    def _get_image_disk_size(self, path):
        return 20
        cmd = "qemu-img info %s" % path
        resp = subprocess.check_output(cmd, shell=True).decode("utf-8")
        disk_size = re.findall(r'virtual\ssize:\s\d*\S', resp)[0]
        disk_size = re.findall(r'\d+\.*d*[MG]', disk_size)[0]
        num_disk_size = float(re.findall(r'\d+\.*d*', disk_size)[0])
        if disk_size.endswith('G'):
            num_disk_size = math.ceil(num_disk_size)
        if disk_size:
            LOG.info("Disk size of image: %d M" % num_disk_size)
        else:
            LOG.info("Unable to get disk size of image.")
        return num_disk_size

    def _check_argument(self, message):
        try:
            template = message["fish"]["template"]
        except Exception as e:
            LOG.error('The argument "template" was not passed!')
            return None
        try:
            region = message["fish"]["region"]
        except Exception as e:
            LOG.error("The argument 'region' was not passed!")
            return None
        # self._response('Sucessfully receive argument template and user.', success=True)
        LOG.info("Template %d, Region %d" % (template, region))
        return (template, region)

    def _get_template_info(self, template):
        template_info = self._query_template_info(template)
        LOG.info("query template complete")
        if not template_info:
            LOG.info("Unable to get the template")
            return None
        elif template_info == 'MAKING':
            return 'MAKING'
        else:
            LOG.info("Get the template %d, lock it's state." % template)
            self._lock_template_status(template)
        return template_info

    def _get_location(self, image_software_mappings, template):
        try:
            LOG.info("query locations of images and softwares of template %d." % template)
            image_software_location = self._get_image_software_location(image_software_mappings)
            return image_software_location
        except Exception as e:
            LOG.error('Unable to query the resource path of image or softwares!')
            LOG.info("Unable to query the resource path of image or softwares!")
            LOG.error(e)
            return None

    def _generate_new_image_name(self, i, image_list, sw_lists):
        base_image_id = image_list["host%d" % (i + 1)]
        LOG.info("base_image_id %d" % base_image_id)
        new_image_name = str(base_image_id) + '+' + '+'.join(sw_lists["host%d" % (i + 1)])
        LOG.info("new image name %s" % new_image_name)
        return new_image_name

    def get_auth(self, region):
        try:
            #userinfo = SQL.query_one(User, id=user_id)
            #self.region_id = userinfo['region_id']
            self.region_id = region
            self.controller_ip = self.region_config[self.region_id]['controller_ip']
            self.conn = Connection(region=self.region_id)
            self.url, self.headers = self.conn._connect(self.image_service)
        except Exception as e:
            LOG.error(e)
            raise AttributeError("Failed to get authentication")

    def build(self, message):
        new_image_list = {}
        message = message["json_content"]
        arguments = self._check_argument(message)
        if not arguments:
            return self._response("Argument's was not correctly passed!")
        (template, region) = arguments
        try:
            self.get_auth(region)
        except Exception as e:
            LOG.error(e)
            return self._response('Failed to get authentication')
        template_info = self._get_template_info(template)
        if not template_info:
            return self._response("Unable to get the template's info.")
        #elif template_info == 'MAKING':
        #    return self._response("Template is being made. Unable to change it now.")
        (image_software_mappings, image_list, sw_lists, flavor_list) = template_info

        image_software_location = self._get_location(image_software_mappings, template)
        if not image_software_location:
            return self._response('Unable to query the resource path of image or softwares!')
        image_amount = len(image_software_location)

        for i in range(image_amount):
            # 上传到glance
            # 创建openstack flavor
            # 更新all_image表
            item = image_software_location[i]
            new_image_name = self._generate_new_image_name(i, image_list, sw_lists)
            base_image_info = self._query_base_image(image_list["host%d" % (i + 1)])
            disk_size = self._get_image_disk_size(base_image_info["resource_path"])
            image_info = copy.deepcopy(base_image_info)
            image_info["name"] = new_image_name

            # 创建镜像
            # 在这里查询现有库存，如果已经有满足条件的镜像，就不再创建镜像。
            (new_image_op_id, new_image_file_path) = self._query_modified_image_existence(new_image_name)

            # 现有glance库存中没有符合条件的镜像，则制作并上传镜像。
            if (not new_image_op_id) or (not self._check_existence("images", new_image_op_id)):
                # 拷贝镜像到同一目录下
                LOG.info("create new image")
                new_image_file_path = self._copy_image_cur_dir(item["image"])
                # 为新镜像复制软件



                self._copy_software_into_image(item, new_image_file_path)
                # 上传image到glance,并获取image的openstack_id
                new_image_op_id = self._upload_image_to_glance(new_image_file_path, image_info, template, new_image_name)
                if not new_image_op_id:
                    self._error_clean_up(template)
                    return self._response("Upload image to OpenStack Glance failed!")
            #  现有glance库存中存在符合条件的镜像，则不再制作和上传镜像
            else:
                LOG.info("Image %s exists in glance already." % new_image_name)

            # 无论是否已经存在相应的镜像，由于启动镜像的硬件配置不同，都要创建新的flavor
            flavor_id = int(flavor_list["host%d" % (i + 1)])
            LOG.info("To query flavor info %d" % flavor_list["host%d" % (i + 1)])
            flavor_info = self._get_flavor_info(flavor_id, disk_size)
            # 更新all_image表
            new_image_id = self._add_modified_image(new_image_name, region, new_image_op_id, new_image_file_path,
                                                    flavor_info["disk"],
                                                    flavor_info["cpu"],
                                                    flavor_info["ram"],
                                                    container_format=image_info["container_format"],
                                                    disk_format=image_info["disk_format"])
            LOG.info("New image Added, id: %d" % new_image_id)

            # 通过flavor.py提供的RESTful API创建flavor目前会出错，原因不明。现在先直接调用代码创建flavor
            # LOG.info('POST to http://%s/v1/template/flavor/%d' % (self.api_url, new_image_id))
            LOG.info("Adding OpenStack flavor...")
            resp = requests.post("http://%s/flavor?image_id=%d&region_id=%s" % (self.api_url, new_image_id, self.region_id))
            # 为什么在这里resp不能解析成json?
            if not resp.ok:
                LOG.error(resp.content)
                self._error_clean_up()
                return self._response("Failed to create the flavor.")
            #res = eval(resp.json())
            if not resp.json()["state"]:
                LOG.error("Create flavor for image %s failed!" % new_image_id)
                self._error_clean_up()
                return self._response("Create flavor for image %s failed!" % new_image_id)
            # resp = self._create_flavor(new_image_id)
            # if resp != 'Success':
            #     self._error_clean_up()
            #     return self._response('Failed to create flavor for image.')

            # 更新Template表
            new_image_list[self.region]["host%d" % (i + 1)] = new_image_id
            if i == (image_amount - 1):
                LOG.info("Update template state DONE(%s)" %self.region)
                #self._update_template_status(template, image_list=new_image_list, state='DONE')
                self._update_template_status(template, image_list=new_image_list)
                if new_image_list.keys() == ["RegionOne", "RegionTwo"]:
                    self._update_template_status(template, state='DONE')
                msg = "Successfully create template's images."
                return self._response(msg, success=True)

    def _upload_image_to_glance(self, new_image_file_path, image_info, template, new_image_name):
        # image_info是一个字典，包含四个key： name, container_format, disk_format, visibility
        image_file_obj = open(new_image_file_path, 'rb')
        mirror_op_id = self._create("images", image_info).json()['id']
        LOG.info("Image(name:%s) is uploading." % new_image_file_path)
        try:
            filesize = self._get_data_size(image_file_obj)
            if filesize is not None:
                image_file_obj = progressbar.VerboseFileWrapper(image_file_obj, filesize)
            url = "%s/images/%s/file" % (self.url, mirror_op_id)
            self.headers['Content-Type'] = "application/octet-stream"
            requests.put(url, data=image_file_obj, headers=self.headers)
            LOG.info("Image(name:%s) is uploaded." % new_image_file_path)
        except Exception as e:
            # if self._check_existence("images", new_image_name):
            url = "%s/images/%s" % (self.url, mirror_op_id)
            self.headers['Content-Type'] = "application/json"
            resp = self._send_request("GET", url, headers=self.headers)
            if resp.json()['status'] == 'active':
                LOG.info("Image(name:%s) is uploaded." % new_image_name)
            else:
                self._delete(["images"], value=mirror_op_id)
                LOG.info("Image(name:%s) upload failed." % new_image_name)
                LOG.info(e)
                if os.path.isfile(new_image_file_path):
                    os.remove(new_image_file_path)
                self._update_template_status(template, state='ERROR_UP_GLANCE')
                return None
        return mirror_op_id

    @db
    def _create_flavor(self, image_id, session, outer):
        try:
            if not flavor_info:
                raise AttributeError
            flavor_info = session.query(ALLImage).filter_by(id=image_id)
            request = {"flavor":{"name":uuid.uuid4().__str__(),"ram":flavor_info['ram'],"vcpus":flavor_info['cpu'],"disk":flavor_info['disk']}}

        except Exception as e:
            failed_msg = "Failed to get the information of the image(id:%s).s flavor. Please check the parameters and try it again."
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return
        try:
            resp = self._create("flavors", request)
            if not resp.ok:
                LOG.error(str(resp.content))
                raise AttributeError
        except Exception as e:
            failed_msg = "Failed to get the information of the image.s flavor."
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return
        try:
            instance = session.query(ALLImage).filter_by(id=image_id).first()
            instance.flavor_op_id = resp.json()['flavor']['id']
            msg = "Flavor(image_id:%s) is created successfully" % message["image_id"]
            LOG.info(msg)
            return 'Success'
        except Exception as e:
            failed_msg = "Failed to create the image.s(id:%s) flavor." % message['image_id']
            LOG.error("%s info: %s" % (failed_msg, str(e)))
            return 'Fail'
            


    def _copy_software_into_image(self, item, new_image_file_path):
        for software in item["softwares"]:
            LOG.info("to copy software %s" % software)
            # 默认写到根目录下，如果是windows系统的话，根目录代表当前挂载的盘符的根目录，默认C盘
            self.fish.copy_in(software, '/', image=new_image_file_path)
            LOG.info("software copied %s" % software)

    @db
    def _error_clean_up(self, template, image_list, session, outer):
        template = session.query(Template).filter_by(id=template).first()
        if template.state == 'MAKING':
            template.state == 'INIT'
            session.add(template)
        if template.state == 'ERROR_UP_GLANCE':
            for new_image_id in image_list.values():
                new_image = session.query(ALLImage).filter_by(id=new_image_id).first()
                resource_path = new_image.resource_path
                try:
                    LOG.info("Deleting remaining image files in file system...")
                    os.remove(resource_path)
                except:
                    pass
                LOG.info("Deleting failed image records in database...")
                session.delete(new_image)


if __name__ == '__main__':
    fm = FishManager()
    # fm.create({"fish":{"template":1, "user":2}})
