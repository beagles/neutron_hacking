# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012, Red Hat, Inc.
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

"""
Unit Tests for linuxbridge rpc
"""

import mock
from oslo.config import cfg

from neutron.agent import rpc as agent_rpc
from neutron.common import topics
from neutron.openstack.common import context
from neutron.plugins.linuxbridge import lb_neutron_plugin as plb
from neutron.tests import base


class rpcApiTestCase(base.BaseTestCase):
    def _test_lb_api(self, rpcapi, topic, method, rpc_method, fanout,
                     expected_msg=None, **kwargs):
        ctxt = context.RequestContext('fake_user', 'fake_project')
        expected_retval = 'foo' if method == 'call' else None
        if not expected_msg:
            expected_msg = kwargs.copy()

        with mock.patch.object(rpcapi.client, 'prepare') as mock_prepare:
            rpc_method_mock = getattr(mock_prepare.return_value, rpc_method)
            rpc_method_mock.return_value = expected_retval

            retval = getattr(rpcapi, method)(ctxt, **kwargs)

            self.assertEqual(expected_retval, retval)

            expected_prepare_args = {}
            if fanout:
                expected_prepare_args['fanout'] = fanout
            if topic != topics.PLUGIN:
                expected_prepare_args['topic'] = topic

            mock_prepare.assert_called_with(**expected_prepare_args)

            rpc_method_mock = getattr(mock_prepare.return_value, rpc_method)
            rpc_method_mock.assert_called_with(
                ctxt,
                method,
                **expected_msg)

    def test_delete_network(self):
        rpcapi = plb.AgentNotifierApi(topics.AGENT)
        self._test_lb_api(rpcapi,
                          topics.get_topic_name(topics.AGENT,
                                                topics.NETWORK,
                                                topics.DELETE),
                          'network_delete', rpc_method='cast', fanout=True,
                          network_id='fake_request_spec')

    def test_port_update(self):
        cfg.CONF.set_override('rpc_support_old_agents', False, 'AGENT')
        rpcapi = plb.AgentNotifierApi(topics.AGENT)
        expected_msg = {'port': 'fake_port',
                        'network_type': 'vlan',
                        'physical_network': 'fake_net',
                        'segmentation_id': 'fake_vlan_id'}
        self._test_lb_api(rpcapi,
                          topics.get_topic_name(topics.AGENT,
                                                topics.PORT,
                                                topics.UPDATE),
                          'port_update', rpc_method='cast', fanout=True,
                          expected_msg=expected_msg,
                          port='fake_port',
                          physical_network='fake_net',
                          vlan_id='fake_vlan_id')

    def test_port_update_old_agent(self):
        cfg.CONF.set_override('rpc_support_old_agents', True, 'AGENT')
        rpcapi = plb.AgentNotifierApi(topics.AGENT)
        expected_msg = {'port': 'fake_port',
                        'network_type': 'vlan',
                        'physical_network': 'fake_net',
                        'segmentation_id': 'fake_vlan_id',
                        'vlan_id': 'fake_vlan_id'}
        self._test_lb_api(rpcapi,
                          topics.get_topic_name(topics.AGENT,
                                                topics.PORT,
                                                topics.UPDATE),
                          'port_update', rpc_method='cast', fanout=True,
                          expected_msg=expected_msg,
                          port='fake_port',
                          physical_network='fake_net',
                          vlan_id='fake_vlan_id')

    def test_device_details(self):
        rpcapi = agent_rpc.PluginApi(topics.PLUGIN)
        self._test_lb_api(rpcapi, topics.PLUGIN,
                          'get_device_details', rpc_method='call',
                          fanout=False,
                          device='fake_device',
                          agent_id='fake_agent_id')

    def test_update_device_down(self):
        rpcapi = agent_rpc.PluginApi(topics.PLUGIN)
        self._test_lb_api(rpcapi, topics.PLUGIN,
                          'update_device_down', rpc_method='call',
                          fanout=False,
                          device='fake_device',
                          agent_id='fake_agent_id',
                          host='fake_host')

    def test_update_device_up(self):
        rpcapi = agent_rpc.PluginApi(topics.PLUGIN)
        self._test_lb_api(rpcapi, topics.PLUGIN,
                          'update_device_up', rpc_method='call',
                          fanout=False,
                          device='fake_device',
                          agent_id='fake_agent_id',
                          host='fake_host')
