# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import itertools

from oslo.config import cfg
from oslo import messaging

from neutron.common import rpc
from neutron.common import topics

from neutron.openstack.common import log as logging
from neutron.openstack.common import timeutils


LOG = logging.getLogger(__name__)


def create_servers(endpoints, prefix, topic_details):
    """Create agent RPC servers.

    :param endpoints: A list of RPC endpoints to serve messages.
    :param prefix: Common prefix for the plugin/agent message queues.
    :param topic_details: A list of topics. Each topic has a name, an
                          operation, and an optional host param keying the
                          subscription to topic.host for plugin calls.

    :returns: A list of RPCServer objects.
    """

    rpc_servers = []

    for details in topic_details:
        topic, operation, node_name = itertools.islice(
            itertools.chain(details, [None]), 3)

        topic_name = topics.get_topic_name(prefix, topic, operation)
        if not node_name:
            node_name = cfg.CONF.host

        target = messaging.Target(topic=topic_name, server=node_name)
        server = rpc.get_server(target, endpoints=endpoints)
        server.start()
        rpc_servers.append(server)

    return rpc_servers


class PluginReportStateAPI(object):

    def __init__(self, topic):
        super(PluginReportStateAPI, self).__init__()
        target = messaging.Target(topic=topic, version='1.0')
        self.client = rpc.get_client(target)

    def report_state(self, context, agent_state, use_call=False):
        fun = self.client.call if use_call else self.client.cast
        return fun(context, 'report_state',
                   agent_state={'agent_state': agent_state},
                   time=timeutils.strtime())


class PluginApi(object):
    '''Agent side of the rpc API.

    API version history:
        1.0 - Initial version.

    '''

    def __init__(self, topic):
        super(PluginApi, self).__init__()
        target = messaging.Target(topic=topic, version='1.1')
        self.client = rpc.get_client(target)

    def get_device_details(self, context, device, agent_id):
        return self.client.call(context, 'get_device_details',
                                device=device,
                                agent_id=agent_id)

    def update_device_down(self, context, device, agent_id, host=None):
        return self.client.call(context, 'update_device_down',
                                device=device,
                                agent_id=agent_id,
                                host=host)

    def update_device_up(self, context, device, agent_id, host=None):
        return self.client.call(context, 'update_device_up',
                                device=device,
                                agent_id=agent_id,
                                host=host)

    def tunnel_sync(self, context, tunnel_ip, tunnel_type=None):
        return self.client.call(context, 'tunnel_sync',
                                tunnel_ip=tunnel_ip,
                                tunnel_type=tunnel_type)
