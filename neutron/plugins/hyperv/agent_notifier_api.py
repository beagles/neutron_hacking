# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Cloudbase Solutions SRL
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
# @author: Alessandro Pilotti, Cloudbase Solutions Srl

from oslo import messaging

from neutron.common import rpc
from neutron.common import topics
from neutron.openstack.common import log as logging

from neutron.plugins.hyperv.common import constants

LOG = logging.getLogger(__name__)


class AgentNotifierApi(object):
    '''Agent side of the openvswitch rpc API.

    API version history:
        1.0 - Initial version.

    '''

    def __init__(self, topic):
        super(AgentNotifierApi, self).__init__()
        target = messaging.Target(topic=topic, version='1.0')
        self.client = rpc.get_client(target)

        self.topic_network_delete = topics.get_topic_name(topic,
                                                          topics.NETWORK,
                                                          topics.DELETE)
        self.topic_port_update = topics.get_topic_name(topic,
                                                       topics.PORT,
                                                       topics.UPDATE)
        self.topic_port_delete = topics.get_topic_name(topic,
                                                       topics.PORT,
                                                       topics.DELETE)
        self.topic_tunnel_update = topics.get_topic_name(topic,
                                                         constants.TUNNEL,
                                                         topics.UPDATE)

    def network_delete(self, context, network_id):
        cctxt = self.client.prepare(fanout=True,
                                    topic=self.topic_network_delete)
        cctxt.cast(context, 'network_delete', network_id=network_id)

    def port_update(self, context, port, network_type, segmentation_id,
                    physical_network):
        cctxt = self.client.prepare(fanout=True,
                                    topic=self.topic_port_update)
        cctxt.cast(context, 'port_update',
                   port=port,
                   network_type=network_type,
                   segmentation_id=segmentation_id,
                   physical_network=physical_network)

    def port_delete(self, context, port_id):
        cctxt = self.client.prepare(fanout=True,
                                    topic=self.topic_port_delete)
        cctxt.cast(context, 'port_delete', port_id=port_id)

    def tunnel_update(self, context, tunnel_ip, tunnel_id):
        cctxt = self.client.prepare(fanout=True,
                                    topic=self.topic_tunnel_update)
        cctxt.cast(context, 'tunnel_update',
                   tunnel_ip=tunnel_ip,
                   tunnel_id=tunnel_id)
