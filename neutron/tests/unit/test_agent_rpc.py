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

from contextlib import nested
import mock
from oslo.config import cfg

from neutron.agent import rpc
from neutron.openstack.common import context
from neutron.tests import base


class AgentRPCPluginApi(base.BaseTestCase):
    def _test_rpc_call(self, method):
        agent = rpc.PluginApi('fake_topic')
        ctxt = context.RequestContext('fake_user', 'fake_project')
        expect_val = 'foo'
        with mock.patch('oslo.messaging.RPCClient.call') as rpc_call:
            rpc_call.return_value = expect_val
            func_obj = getattr(agent, method)
            if method == 'tunnel_sync':
                actual_val = func_obj(ctxt, 'fake_tunnel_ip')
            else:
                actual_val = func_obj(ctxt, 'fake_device', 'fake_agent_id')
        self.assertEqual(actual_val, expect_val)

    def test_get_device_details(self):
        self._test_rpc_call('get_device_details')

    def test_update_device_down(self):
        self._test_rpc_call('update_device_down')

    def test_tunnel_sync(self):
        self._test_rpc_call('tunnel_sync')


class AgentPluginReportState(base.BaseTestCase):

    strtime = 'neutron.openstack.common.timeutils.strtime'

    def test_plugin_report_state_use_call(self):
        topic = 'test'
        reportStateAPI = rpc.PluginReportStateAPI(topic)
        expected_agent_state = {'agent': 'test'}
        with nested(mock.patch.object(reportStateAPI.client, 'call'),
                    mock.patch(self.strtime)) as (call, time):
            time.return_value = 'TESTTIME'
            ctxt = context.RequestContext('fake_user', 'fake_project')
            reportStateAPI.report_state(ctxt, expected_agent_state,
                                        use_call=True)
            expected_args = mock.call(
                ctxt, 'report_state',
                agent_state={'agent_state': expected_agent_state},
                time='TESTTIME')
            self.assertEqual(call.call_args, expected_args)

    def test_plugin_report_state_cast(self):
        topic = 'test'
        reportStateAPI = rpc.PluginReportStateAPI(topic)
        expected_agent_state = {'agent': 'test'}
        with nested(mock.patch.object(reportStateAPI.client, 'cast'),
                    mock.patch(self.strtime)) as (cast, time):
            time.return_value = 'TESTTIME'
            ctxt = context.RequestContext('fake_user', 'fake_project')
            reportStateAPI.report_state(ctxt, expected_agent_state)
            expected_args = mock.call(
                ctxt, 'report_state',
                agent_state={'agent_state': expected_agent_state},
                time='TESTTIME')
            self.assertEqual(cast.call_args, expected_args)


class AgentRPCMethods(base.BaseTestCase):
    def test_create_consumers(self):
        endpoint = mock.Mock()

        expected_get_server = [
            mock.call(mock.ANY, endpoints=[endpoint]),
            mock.call().start(),
        ]
        expected_target = [
            mock.call(topic='foo-topic-op', server=cfg.CONF.host),
        ]

        get_server_call = 'neutron.common.rpc.get_server'
        target_call = 'oslo.messaging.Target'
        with nested(mock.patch(get_server_call),
                    mock.patch(target_call)) as (get_server, target):
            rpc.create_servers([endpoint], 'foo', [('topic', 'op')])
            target.assert_has_calls(expected_target)
            get_server.assert_has_calls(expected_get_server)

    def test_create_consumers_with_node_name(self):
        endpoint = mock.Mock()

        expected_get_server = [
            mock.call(mock.ANY, endpoints=[endpoint]),
            mock.call().start(),
        ]
        expected_target = [
            mock.call(topic='foo-topic-op', server='node1'),
        ]

        get_server_call = 'neutron.common.rpc.get_server'
        target_call = 'oslo.messaging.Target'
        with nested(mock.patch(get_server_call),
                    mock.patch(target_call)) as (get_server, target):
            rpc.create_servers([endpoint], 'foo', [('topic', 'op', 'node1')])
            target.assert_has_calls(expected_target)
            get_server.assert_has_calls(expected_get_server)
