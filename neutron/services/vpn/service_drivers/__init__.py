# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013, Nachi Ueno, NTT I3, Inc.
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

import abc
from oslo import messaging
import six

from neutron.common import rpc
from neutron import manager
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class VpnDriver(object):

    def __init__(self, service_plugin):
        self.service_plugin = service_plugin

    @property
    def service_type(self):
        pass

    @abc.abstractmethod
    def create_vpnservice(self, context, vpnservice):
        pass

    @abc.abstractmethod
    def update_vpnservice(
        self, context, old_vpnservice, vpnservice):
        pass

    @abc.abstractmethod
    def delete_vpnservice(self, context, vpnservice):
        pass


class BaseIPsecVpnAgentApi(object):
    """Base class for IPSec API to agent."""

    def __init__(self, to_agent_topic, topic, default_version):
        super(BaseIPsecVpnAgentApi, self).__init__()
        target = messaging.Target(topic=topic, version=default_version)
        self.client = rpc.get_client(target)
        self.to_agent_topic = to_agent_topic

    def _agent_notification(self, context, method, router_id,
                            version=None, **kwargs):
        """Notify update for the agent.

        This method will find where is the router, and
        dispatch notification for the agent.
        """
        admin_context = context.is_admin and context or context.elevated()
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.L3_ROUTER_NAT)
        if not version:
            version = self.target.version
        l3_agents = plugin.get_l3_agents_hosting_routers(
            admin_context, [router_id],
            admin_state_up=True,
            active=True)
        for l3_agent in l3_agents:
            LOG.debug(_('Notify agent at %(topic)s.%(host)s the message '
                        '%(method)s'),
                      {'topic': self.to_agent_topic,
                       'host': l3_agent.host,
                       'method': method,
                       'args': kwargs})
            cctxt = self.client.prepare(
                version=version,
                topic='%s.%s' % (self.to_agent_topic, l3_agent.host))
            cctxt.cast(context, method, **kwargs)

    def vpnservice_updated(self, context, router_id):
        """Send update event of vpnservices."""
        self._agent_notification(context, 'vpnservice_updated', router_id)
