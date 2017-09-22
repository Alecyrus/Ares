# Copyright (c) 2016 NIST
# All Rights Reserved.
# Author: Junkai Huang



import os
import sys
import time
import sys
import requests
import json

#sys.path.append("/home/hjk/Ares")

import logging
import logging.config
from multiprocessing.dummy import Pool
from proxy import _Proxy
from auth import Connection
import cloghandler
from action import ServerAction

from pprint import pprint
from db_wrapper import execute
from db_wrapper import api as SQL
import models


POOL_SIZE=12

logging.config.fileConfig("logging.ini")
LOG=logging.getLogger("environment")


class EnvironmentManager(_Proxy):
    """Environment Management Service Interface

       Handler the RPC calls and responses
    """
    def __init__(self):
        super(EnvironmentManager, self).__init__()

        self.debug = False
        #self.conn = Connection()

        self.pool_size = POOL_SIZE

        # Reduce the database access times in the processing of handling errors
        self.network_id = None

        # The shared variable among the callback functions
        self.failed = False



    def _parser_param(self, id):
        """Generate the details of the environment by a template ID"""
        self.instance = [{'ip': '10.0.1.100',
                          'name': 'op_machine',
                          'network': 'net1'}]
        self.subnets = {"subnets":[{"name":"net1","cidr":"10.0.1.0/24"}]}
        subnets_two = {"subnets":[{"name":"net1","cidr":"10.0.1.0/24"},
                                  {"name":"net2","cidr":"10.0.3.0/24"}]}
        self.links = {"rr":[[]],"rh":[[1,1]]}
        links_two ={'rh': [[1, 1], [2, 2]], 'rr': [[1, 2]]}
        self.network_num = 1
        try:
            # Get the basic information of the environment that is as a template in the database
            images = eval(SQL.query_one(models.Template, id=id)['image_list'][self.region_id])
            image = SQL.query_one(models.ALLImage, id=images['host1'])
            self.instance[0]['image'] = image['mirror_op_id']
            self.instance[0]['flavor'] = image['flavor_op_id']
            if 'host2' in images:
                self.links = links_two
                self.network_num = 2
                self.subnets = subnets_two
                temp = {}
                image = SQL.query_one(models.ALLImage, id=images['host2'])
                temp['image'] = image['mirror_op_id']
                temp['flavor'] = image['flavor_op_id']
                temp['name'] = 'tg_machine'
                temp['network'] = 'net2'
                temp['ip'] = '10.0.3.100'
                self.instance.append(temp)
        except Exception as e:
            LOG.error("Failed to get template from database.template=%s"
                    % id)
            return False


        # Generate the middle subnets' details 
        self.subnets["mid_subnets"] = []
        count = 1
        try:
            for i in self.links["rr"]:
                body = {}
                body["name"] = "%d-%d" %(i[0],i[1])
                body["cidr"] = "100.0.%d.0/24" %(count)
                count = count + 1
                self.subnets["mid_subnets"].append(body)
        except Exception as e:
            pass
        # Generate the ports' details, including the compute interfaces and router interfaces
        self.ports={}
        for i in self.subnets["subnets"]:
            body = {}
            body[i["name"]] = i['cidr'][:-4]+"1"
            self.ports[i["name"]] = body

        # For a middle subnets that are used to connect two separated subnets, the 
        # ip addresses of the two ports on a middle subnet are X.X.X.11 and X.X.X.22
        for i in self.subnets["mid_subnets"]:
            body = {}
            body["net"+i['name'][2:]] = i['cidr'][:-4]+"11"
            body["net"+i['name'][:1]] = i['cidr'][:-4]+"22"
            self.ports[i["name"]] = body
        return True

    def _create_network(self):
        """the step to create network, subnets and routers in the way of threaded concurrency"""
        # Get the endpoint's url and essential header of the requests
        self.url, self.headers = self.conn._connect(self.network_service)

        self.network_name = "network_%d" %self.target
        network_body = {"network":{"name":self.network_name,
                                    "admin_state_up":True}}
        try:
            network = self._create("networks", network_body)
            self.network_id = network.json()["network"]["id"]
            SQL.update_one(models.Target, {"id":self.target}, {"net_op_id":self.network_id})
        except Exception as e:
            LOG.error(e)
            return True


        pool = Pool(self.pool_size)
        for subnet in self.subnets["subnets"]:
            pool.apply_async(create_subnet,args=(self.url,
                                                 self.headers,
                                                 subnet["cidr"],
                                                 self.network_id,
                                                 subnet["name"]),
                                           callback=self._subnet_callback,
                                           error_callback=self._error_callback)
            if self.subnets["mid_subnets"]:
                pool.apply_async(create_router, args=(self.url,
                                                      self.headers,
                                                      subnet["name"]),
                                                callback=self._router_callback,
                                                error_callback=self._error_callback)
        if self.subnets["mid_subnets"]:
            for mid_sub in self.subnets["mid_subnets"]:
                pool.apply_async(create_subnet,args=(self.url,
                                                     self.headers,
                                                     mid_sub["cidr"],
                                                     self.network_id,
                                                     mid_sub["name"]),
                                               callback=self._subnet_callback,
                                               error_callback=self._error_callback)
        pool.close()
        pool.join()
        pool.terminate()
        return self.failed

    def _create_ports(self):
        """the step to create ports in the way of threaded concurrency"""
        pool = Pool(self.pool_size)

        # Create the ports those are used for router interfaces
        if self.subnets["mid_subnets"]:
            for (subnet, ports) in self.ports.items():
                subnet_id = SQL.query_one(models.SubNet,
                                          deleted=0,
                                          target=self.target,
                                          name=subnet)['extra']
                for (name , ip) in ports.items():
                    pool.apply_async(create_port, args=(self.url,
                                                       self.headers,
                                                       self.network_id, ip,
                                                       subnet_id, name),
                                                  callback=self._interface_callback,
                                                  error_callback=self._error_callback)

        # Create the ports those are used for compute interfaces
        for instance in self.instance:
            subnet_id = SQL.query_one(models.SubNet,
                                      deleted=0,
                                      target=self.target,
                                      name=instance["network"])['extra']
            pool.apply_async(create_port, args=(self.url,
                                                self.headers,
                                                self.network_id,
                                                instance["ip"],
                                                subnet_id,
                                                instance["name"]),
                                          callback=self._port_callback,
                                          error_callback=self._error_callback)
        pool.close()
        pool.join()
        pool.terminate()
        return self.failed

    def _create_interfaces(self):
        """the step to create router interfaces in the way of threaded concurrency"""
        pool = Pool(self.pool_size)
        interfaces = SQL.query(models.Port,
                               deleted=0,
                               target=self.target,
                               is_interface=1)
        for interface in interfaces:
            router_id = SQL.query_one(models.Router,
                                      deleted=0,
                                      target=self.target,
                                      name=interface["name"])["rt_op_id"]
            port_id = interface["port_op_id"]
            pool.apply_async(add_interface, args=(self.url,
                                                  self.headers,
                                                  router_id,
                                                  port_id,
                                                  self.target),
                                            error_callback=self._error_callback)
        pool.close()
        pool.join()
        pool.terminate()
        return self.failed

    def _create_servers(self):
        """the step to create servers in the way of threaded concurrency"""
        self.url, self.headers = self.conn._connect(self.compute_service)
        pool = Pool(self.pool_size)
        for instance in self.instance:
            image_id = instance["image"]
            flavor_id = instance["flavor"]
            name = instance["name"]
            port_id = SQL.query_one(models.Port,
                                    deleted=0,
                                    target=self.target,
                                    name=name)["port_op_id"]
            pool.apply_async(create_server, args=(self.url,
                                                  self.headers,
                                                  image_id,
                                                  flavor_id,
                                                  port_id,
                                                  name),
                                            callback=self._server_callback,
                                            error_callback=self._error_callback)
        pool.close()
        pool.join()
        pool.terminate()
        return self.failed


    def _get_auth(self, user_id):
        try:
            userinfo = SQL.query_one(models.User, id=user_id)
            self.region_id = userinfo['region_id']
            self.conn = Connection(region=self.region_id, user_id=user_id)
        except Exception as e:
            LOG.error(e)
            return False
        return True


    def _insert_routes(self):
        index = int(self.network_num) + 1
        matrix = [[0 for i in range(index)] for i in range(index)]
        init = lambda x: x+1
        matrix[0] = [init(i) for i in matrix[0]]

        for router in self.links["rr"]:
           matrix[router[0]][router[1]] = 1
           matrix[router[1]][router[0]] = 1

        dest=[0]
        try:
            for i in range(1,index):
                dest.append(SQL.query_one(models.SubNet, name="net"+str(i), user=self.user, target=self.target, deleted=0)['cidr'])
        except Exception as e:
            LOG.warning(e)
            LOG.error("Cannot initialize the informafortion required")
            self.delete(self.message)
            self.failed = True
            return self.failed

        routes=[]

        for i in range(1, index):
            try:
                router_id = SQL.query_one(models.Router, name="net"+str(i), user=self.user, target=self.target, deleted=0)["rt_op_id"]
            except Exception as e:
                LOG.warning(e)
                LOG.error("Cannot get valid router_id.")
                self.delete(self.message)
                self.failed = True
                return self.failed

            nexthop_nodes = []
            matrix[0][i] = 0

            for row in range(1, index):
                if matrix[row][i]:
                    matrix[0][row] = 0
                    nexthop_nodes.append(row)

            for start in nexthop_nodes:
                to_visit_queue = []
                temp = "%d-%d" % (i, start)

                if i > 1:
                    temp = temp[::-1]
                nexthop = self.ports[temp]["net"+str(start)]
                routes.append({"dest": dest[start], "nexthop":nexthop, "r_id":router_id})

                for row in range(1, index):
                    if matrix[row][start] and  matrix[0][row]:
                            matrix[0][row] = 0
                            to_visit_queue.append(row)
                            routes.append({"dest": dest[row], "nexthop":nexthop, "r_id":router_id})

                while(to_visit_queue):
                    node = to_visit_queue.pop(0)
                    for row in range(1, index):
                        if matrix[row][node] and matrix[0][row]:
                            matrix[0][row] = 0
                            to_visit_queue.append(row)

            for i in range(index):
                matrix[0][i] = 1


        try:
            for route in routes:
                execute("insert into routerroutes (destination, nexthop, router_id) values \
                         ('%(dest)s','%(nexthop)s','%(r_id)s')" %route , region=self.region_id)
        except Exception as e:
            LOG.error(e)
            self.delete(self.message)
            self.failed = True
        finally:
            return self.failed


    def create(self, message):
        """Create a enviroment in the way of threaded concurrency

        :param`dict` message: The message for creating the environment. You must specific the
                              the id of the target required in the request, and the id of the
                              id of the user who own the resource. There is an example format
                              as follows:
                              ```
                              {"template_id:1
                               "user_id":1}
                              ```

        :returns: the staus of the proccessing, `True` or `False`
        """

        self.msg_success = "The environment is created successfully."
        self.msg_failed = "Failed to delete the environment."
        self.user = message['json_content']["user_id"]
        self.message = message['json_content']
        #pprint(message)
        #return self._response(self.msg_failed)

        if not self._get_auth(self.user):
            msg = "%s More info: Check whether the user_id is valid." % self.msg_failed
            LOG.error(msg)
            return self._response(msg)

        try:
            num = SQL.query(models.Target, user=self.user, deleted=0)
            pprint(num.__len__())
            if num.__len__() > 0:
                msg = " More info: You are not allowd to create more target on the condition that you have owned one.."
                LOG.error(msg)
                return self._response(msg)
            if SQL.query_one(models.Target, template=int(self.message["template_id"]), user=self.user, deleted=0):
                msg = " More info: You are not allowed to create the target on the condition that you have owned one. "
                LOG.error(msg)
                return self._response(msg)

            # Generate the essential details of the environment 
            if not self._parser_param(int(self.message["template_id"])):
                moreinfo = "Failed to create environment. You must specific the ID of template."
                LOG.error(moreinfo)
                self.delete(self.message)
                msg = "%s More info: %s" % (self.msg_failed, moreinfo)
                return self._response(msg)

            #self.target = message["target_id"]
            self.target = SQL.insert(models.Target, template=int(self.message["template_id"]), state=2, user=self.user)
            #self.target = SQL.query_one(models.Target, user=self.user, state=2)['id']
        except Exception as e:
            LOG.error(e)
            msg = "%s More info: failed to access Database" %self.msg_failed
            return self._response(msg)

        # If the errors occur in the processing of it, handle the errors and return `False`
        if self._create_network():
            msg = "%s More info: faild to create networks." % self.msg_failed
            return self._response(msg)
        if self._create_ports():
            msg = "%s More info: faild to create ports." % self.msg_failed
            return self._response(msg)
        if self.subnets["mid_subnets"]:
            if self._create_interfaces():
                msg = "%s More info: faild to create interfaces." % self.msg_failed
                return self._response(msg)
            if self._insert_routes():
                msg = "%s More info: faild to insert routes into dababases." % self.msg_failed
                return self._response(msg)
        if self._create_servers():
            msg = "%s More info: faild to create servers." % self.msg_failed
            return self._response(msg)


        try:
            SQL.update_one(models.Target, {"id":self.target}, {"state":1})
        except Exception as e:
            LOG.error(e)
            msg = "Failed to access the dabatase."
            return self._response(msg)
        LOG.info(self.msg_success)
        serverac = ServerAction()
        return self._response(serverac.get(self.message)["info"], True)

    def delete(self, message):
        """Delete a enviroment in the way of threaded concurrency

        :param`dict` message: The message for deleting the environment. An example format
                              would look as follows:
                              ```
                              {"user_id":10, "template_id":10}
                              ```
        :returns: the staus of the proccessing, `True` or `False`
        """
        self.msg_success = "The environment is deleted successfully."
        self.msg_failed = "Failed to delete the environment. Check whether request is valid.  "
        if 'url_content' in message.keys():
            message = message['url_content']
            message['user_id'] = message['user_id'][0]
            message['template_id'] = message['template_id'][0]
        self.user = message["user_id"]
        try:
            self._get_auth(self.user)

            self.target = SQL.query_one(models.Target, user=self.user, template=message["template_id"], deleted=0)['id']
        except Exception as e:
            msg = "%s More info: Target is unaccessable." % self.msg_failed
            LOG.error(msg)
            return self._response(msg)

        try:
            for router in SQL.query(models.Router, target=self.target, deleted=0):
                execute("delete from routerroutes where router_id = '%s'" % router["rt_op_id"], region=self.region_id)

        except Exception as e:
            LOG.warning(e)
            moreinfo = "Cannot remove routes, Please check whether the request is valid and resend the request."
            LOG.error(moreinfo)
            msg = "%s More info: %s" % (self.msg_failed, moreinfo)
            return self._response(msg)


        self.url, self.headers = self.conn._connect(self.compute_service)

        # Delete the servers
        pool = Pool(self.pool_size)
        servers = SQL.query(models.VM,
                            target=self.target,
                            deleted=0)
        for server in servers:
            pool.apply_async(_delete, args=("servers",
                                      self.url,self.headers,
                                      server["vm_op_id"]))
        pool.close()
        pool.join()
        pool.terminate()

        LOG.info("The servers of the target(%s) have been deleted." % self.target)
        # remove the router interfaces (every involved ports is deleted at the same time)
        self.url, self.headers = self.conn._connect(self.network_service)
        pool = Pool(self.pool_size)
        interfaces = SQL.query(models.Port,
                               target=self.target,
                               is_interface=1,
                               deleted=0)
        for interface in interfaces:
            try:
                router_id = SQL.query_one(models.Router,
                                          name=interface["name"],
                                          target=self.target,
                                          deleted=0)["rt_op_id"]
                pool.apply_async(remove_interface, args=(self.url, self.headers, router_id, interface["port_op_id"]))
            except Exception as e:
                Log.warning(e)
        pool.close()
        pool.join()
        pool.terminate()
        LOG.info("The interfaces of the routers of the target(%s) have been deleted." % self.target)

        # delete the all the ports (Actually, it's enough to delete the compute interfaces
        # when no error occurs)
        pool = Pool(self.pool_size)
        ports = SQL.query(models.Port, target=self.target, deleted=0)
        for port in ports:
            pool.apply_async(_delete, args=("ports",
                                            self.url,
                                            self.headers,
                                            port["port_op_id"]))
        pool.close()
        pool.join()
        pool.terminate()
        LOG.info("The ports of the routers of the target(%s) have been deleted." % self.target)

        # delete the subnets and routers (Actually, subnets will be deleted when the network is deleted)
        pool=Pool(self.pool_size)
        try:
            subnets = SQL.query(models.Router, target=self.target, deleted=0)
        except Exception as e:
            LOG.warning(e)
        for subnet in subnets:
            pool.apply_async(_delete, args=("subnets",
                                            self.url,
                                            self.headers,
                                            subnet["extra"]))
        routers = SQL.query(models.Router, target=self.target, deleted=0)
        for router in routers:
            pool.apply_async(_delete, args=("routers",
                                            self.url,
                                            self.headers,
                                            router["rt_op_id"]))
        pool.close()
        pool.join()
        pool.terminate()
        LOG.info("The subnets of the target(%s) have been deleted." % self.target)

        # delete the network
        try:
            network_id = SQL.query_one(models.Target, id=self.target, deleted=0)["net_op_id"]
            self.delete_network(network_id)
            # delete all the information about the environment in the database
            SQL.soft_delete(models.SubNet, target = self.target, deleted=0)
            SQL.soft_delete(models.VM, target=self.target, deleted=0)
            SQL.soft_delete(models.Port, target=self.target, deleted=0)
            SQL.soft_delete(models.Router, target=self.target, deleted=0)
            SQL.soft_delete(models.Target, id=self.target, deleted=0)
        except Exception as e:
            LOG.error(e)
            LOG.warning(e)
            msg = "%s More info: failed to delete the target(id:%s). Please delete the target manually" % (self.msg_failed, self.target)
            return self._response(msg)

        LOG.info("The network of the target(%s) have been deleted." % self.target)


        return self._response(self.msg_success, True)

    def _insert(self, *args,  **kwargs):
        """The base callback function.

        If the thread runs smoothyly, the callbacks will be invoked to take some database
        operations.

        :param `tube` args: the variable parameters from the superior function.
        :param `dict` kwargs: the keyword parameters from the superior function.
        """
        if self.failed:
            _delete(args[0], self.url, self.headers, args[1]['id'])
            return
        SQL.insert(args[2], **kwargs)

    def _subnet_callback(self, resp):
        """The callback for subnets"""
        return self._insert("subnets", resp, models.SubNet,
                    name=resp["name"],
                    target=self.target,
                    net_op_id=resp["network_id"],
                    cidr=resp["cidr"],
                    user=self.user,
                    extra=resp["id"])

    def _router_callback(self, resp):
        """The callback for routers"""
        return self._insert("routers", resp, models.Router,
                   target=self.target,
                   user=self.user,
                   name=resp["name"],
                   rt_op_id=resp["id"])

    def _port_callback(self, resp):
        """The callback for ports"""
        return self._insert("ports", resp, models.Port,
                   target=self.target,
                   name=resp["name"],
                   ip_address=resp["fixed_ips"][0]["ip_address"],
                   port_op_id=resp["id"],
                   is_interface=0)

    def _interface_callback(self, resp):
        """The callback for interfaces"""
        return self._insert("ports", resp, models.Port,
                   target=self.target,
                   name=resp["name"],
                   ip_address=resp["fixed_ips"][0]["ip_address"],
                   port_op_id=resp["id"],
                   is_interface=1)

    def _server_callback(self, resp):
        """The callback for servers"""
        return self._insert("server", resp, models.VM,
                   target=self.target,
                   user=self.user,
                   ip_address=resp['addresses'][self.network_name][0]['addr'],
                   name=resp["name"],
                   vm_op_id=resp["id"],
                   state=1)

    def _error_callback(self, e):
        """If some thread get blocked, the error_callback will be invoked immediately """
        if self.failed:
            return
        self.failed = True
        self.delete(self.message)

    def delete_network(self, id):
        """Delete a network."""
        try:
            self._delete(["networks"], value=id)
            LOG.warning("Network(id:%(id)s) is deleted.", {"id":id})
        except Exception as e:
            LOG.error(e)

def create_server(url, headers, image_id, flavor_id, port_id, name):
    """Create servers in the opensatck.

    :param`string` url: The auth url for accessing to the OpenStack's service. Generally,
                        it is the endpoint url of the service required.
    :param`dict` headers: The HTTP request's headers, including the `Content-Type` and
                             the `X-Auth-Token`.

    :param`string` flavor_id: The flavor reference, as a UUID, for the flavor for the server
    :param`string` port_id: To provison the server with a existing port, specific the uuid
                            of a availiable and vaild port.
    :param`string` name: Hunman-readable name for the server.


    :raises: Exception.AttributeError
    :returns`dict`: the server's details.
    """
    instance_body = {"server":{"name":name,
                             "imageRef":image_id,
                             "flavorRef":flavor_id,
                               "networks":[{"port":port_id}]}}
    #FIXME(HJK) check  whether the resource is vaild 
    try:
        resp = _create("servers", url, headers, instance_body)
    except Exception as e:
        LOG.error(e)
    check_url = "%s/servers/%s" % (url, resp.json()["server"]["id"])
    resp1 = requests.request("GET", check_url, headers=headers)
    while(resp1.json()["server"]["status"] != "ACTIVE"):
        resp1 = requests.request("GET", check_url, headers=headers)
        if resp1.json()["server"]["status"] == "ERROR":
            LOG.error(resp1.json()['server'])
            LOG.error("failed to create server(id:%s)"
                      % resp1.json()["server"]["id"])
            _delete("servers", url, headers, resp1.json()["server"]['id'])
            raise AttributeError
    LOG.info("Server(name:%s) is created.(code:%s)"
             % (name, resp.status_code))
    return resp1.json()["server"]

def add_interface(url, headers, router_id, port_id, target_id):
    """Attach interfaces to the routers.

    :param`string` url: The auth url for accessing to the OpenStack's service(Neutron).
    :param`dict` headers: the request's headers for accessing to the OpenStack API
    :param`string` router_id: the uuid of the target router.
    :param`string` port_id: the port reference, as a UUID.
    :param`int` target_id: the id of the target.

    :raises: Exception.AttributeError
    :returns: None
    """
    url = "%s/routers/%s/add_router_interface" %(url, router_id)
    body = {"port_id":port_id}
    resp = requests.request("PUT",url,json=body, headers=headers)
    if resp.ok:
        LOG.info("Add port(%s) to router(%s), (code:%s)"
                 % (port_id, router_id, resp.status_code))
    else:
        LOG.error("Failed to add port(%(port_id)s) to router(%(router_id)s). (code: %(code)s) Info: %(reason)s",
                  {"port_id":port_id,
                   "code":resp.status_code,
                   "router_id":router_id,
                   "reason":resp.content})
        raise AttributeError

def remove_interface(url, headers, router_id, port_id):
    """Detach the interfaces from the routers

    You can read more on the section of `add_interface`function. The only difference is that `target_id` is not
    required.
    """
    url = "%s/routers/%s/remove_router_interface" %(url, router_id)
    body = {"port_id":port_id}
    resp = requests.request("PUT",url,json=body, headers=headers)
    if resp.ok:
        LOG.info("Remove port(%s) to router(%s)(code:%s)"
                 % (port_id, router_id, resp.status_code))
    else:
        LOG.error("Failed to remove port(%(port_id)s) to router(%(router_id)s). (code: %(code)s) Info: %(reason)s",
                  {"port_id":port_id,
                   "code":resp.status_code,
                   "router_id":router_id,
                   "reason":resp.content})
        raise AttributeError

def _create(resource, url, headers, body):
    """The base function for creating resource.

    It will be invoked when some resources required to be created.

    :param`string` resource: The resource's name, e.g. `subnets`, `ports`, `servers`...
    :param`string` url: The auth url for accessing to the OpenStack API.
    :param`dict` headers: The request's headers for calling  OpenStack API.
    :param`dict` body: the request's body for invoking the OpenStack.

    :raises: Exception.AttributeError
    :returns`request.Reponse` resp. If anything runs smoothly, the `resp` will be returns.
    """
    url = "%s/%s" %(url, resource)
    resp =  requests.request("POST",url,json=body, headers=headers)
    if resp.ok:
        return resp
    LOG.error("Failed to create %(resource)s.(code: %(code)s) Info: %(reason)s",
             {"resource":resource,
              "code":resp.status_code,
              "reason":list(resp.json().values())[0]["message"]})
    raise AttributeError

def create_subnet(url, headers, cidr, network_id, name):
    """Create subnets in the OpenStack.

    :param`string` url: The auth url for accessing to the OpenStack's service(Neutron).
    :param`dict` headers: The request's headers for accessing to the OpenStack API
    :param`string` cidr: The subnet's CIDR.
    :param`string` network_id: the UUID of the parent network.
    :param`string` name: Hunman-readable name for the subnet.

    :raises: Exception.AttributeError
    :returns`dict`: the details of the subnet created.
    """
    network_body = {"subnet":{"name":name,
                                "network_id":network_id,
                                "ip_version":"4",
                                "cidr":cidr}}
    try:
        resp = _create("subnets", url, headers, network_body)
    except Exception as e:
        raise
    LOG.info("Subnet(name:%s) is created.(code:%s)"
             % (name, resp.status_code))
    return resp.json()['subnet']

def create_router(url, headers, name):
    """Create routers in the OpenStack.

    :param`string` url: The auth url for accessing to the OpenStack's service(Neutron).
    :param`dict` headers: The request's headers for accessing to the OpenStack API.
    :param`string` name: Hunman-readable name for the router.

    :raises: Exception.AttributeError
    :returns`dict`: The details of the router created.
    """
    router_body = {"router":{"name":name}}
    try:
        resp = _create("routers", url, headers, router_body)
    except ProcessingError as e:
        raise
    LOG.info("Router(name:%s) is created.(code:%s)"
             % (name, resp.status_code))
    return resp.json()['router']

def create_port(url, headers, network_id, ip_address, subnet_id, name):
    """Create routers in the OpenStack.

    :param`string` url: The auth url for accessing to the OpenStack's service(Neutron).
    :param`dict` headers: The request's headers for accessing to the OpenStack API.
    :param`string` network_id: The uuid for the network.
    :param`string` ip_addrss: The specific ip address.
    :param`string` subnet_id: The uuid of the subnet.
    :param`string` name: Hunman-readable name for the port.

    :raises: Exception.AttributeError
    :returns`dict`: The details of the port created.
    """
    port_body = {"port":{"network_id":network_id,
                         "name":name,
                         "admin_state_up":True,
                         "fixed_ips":[{"subnet_id":subnet_id,
                                        "ip_address":ip_address}]}}
    try:
        resp = _create("ports", url, headers, port_body)
    except Exception as e:
        raise
    LOG.info("Port(name:%s) is created.(code:%s)"
             % (name, resp.status_code))
    return resp.json()["port"]

def _delete(resource, url, headers, id):
    """The base function for creating resource.

    It will be invoked when some resources required to be deleted.

    :param`string` resource: The resource's name, e.g. `subnets`, `ports`, `servers`...
    :param`string` url: The auth url for accessing to the OpenStack API.
    :param`dict` headers: The request's headers for calling  OpenStack API.
    :param`string` id: The uuid of thr resource.

    :raises: Exception.AttributeError
    :returns: None
    """
    url = "%s/%s/%s" %(url, resource, id)
    resp = requests.request("DELETE", url, headers=headers)
    if resp.ok:
        LOG.info("%s(id:%s) is deleted.(status_code:%s)"
                 % (resource, id, resp.status_code))
    else:
        LOG.error("Failed to delete %(resource)s(id:%(id)s). (code:%(code)s) ). Info: %(reason)s",
            {"resource":resource,
             "code":resp.status_code,
             "id":id,
             "reason":list(resp.json().values())[0]["message"]})


if __name__ == "__main__":
    test = EnvironmentManager()
    ##test.create({"template_id":2, "user_id":2})
    #test.create({"template_id":4, "user_id":1})
    #print("WARNING WARNING WARNING WARNING")
    #time.sleep(5)
    #test.delete({"user_id":7})
    test.delete({"template_id":2, "user_id":2})

    #test.create({"template_id":4, "user_id":1})
    #test.create({"template_id":4, "user_id":1})
    #test.create({"template_id":1, "user_id":1})
    #test.create({"template_id":5, "user_id":1})
    #test.create({"template_id":35, "user_id":42})
    test.delete({"template_id":45, "user_id":44})
    #test.delete({"template_id":1, "user_id":1})
    #test.create({"template_id":32, "user_id":42})
    #test.delete({"template_id":1, "user_id":1})




