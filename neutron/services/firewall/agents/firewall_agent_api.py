# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 OpenStack Foundation
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
#
# @author: Sumit Naiksatam, sumitnaiksatam@gmail.com, Big Switch Networks, Inc.
# @author: Sridar Kandaswamy, skandasw@cisco.com, Cisco Systems, Inc.
# @author: Dan Florea, dflorea@cisco.com, Cisco Systems, Inc.

from oslo.config import cfg
from oslo import messaging

from neutron.common import rpc
from neutron.openstack.common import log as logging


LOG = logging.getLogger(__name__)

FWaaSOpts = [
    cfg.StrOpt(
        'driver',
        default='',
        help=_("Name of the FWaaS Driver")),
    cfg.BoolOpt(
        'enabled',
        default=False,
        help=_("Enable FWaaS")),
]
cfg.CONF.register_opts(FWaaSOpts, 'fwaas')


class FWaaSPluginApiMixin(object):
    """Agent side of the FWaaS agent to FWaaS Plugin RPC API."""

    def __init__(self, topic, host):
        super(FWaaSPluginApiMixin, self).__init__()
        target = messaging.Target(topic=topic, version='1.0')
        self.client = rpc.get_client(target)
        self.host = host

    def set_firewall_status(self, context, firewall_id, status):
        """Make a RPC to set the status of a firewall."""
        return self.client.call(context, 'set_firewall_status',
                                host=self.host,
                                firewall_id=firewall_id,
                                status=status)

    def firewall_deleted(self, context, firewall_id):
        """Make a RPC to indicate that the firewall resources are deleted."""
        return self.client.call(context, 'firewall_deleted',
                                host=self.host,
                                firewall_id=firewall_id)


class FWaaSAgentRpcCallbackMixin(object):
    """Mixin for FWaaS agent Implementations."""

    def __init__(self, host):

        super(FWaaSAgentRpcCallbackMixin, self).__init__(host)

    def create_firewall(self, context, firewall, host):
        """Handle RPC cast from plugin to create a firewall."""
        pass

    def update_firewall(self, context, firewall, host):
        """Handle RPC cast from plugin to update a firewall."""
        pass

    def delete_firewall(self, context, firewall, host):
        """Handle RPC cast from plugin to delete a firewall."""
        pass
