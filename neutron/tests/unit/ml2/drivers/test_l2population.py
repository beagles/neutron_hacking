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
# @author: Sylvain Afchain, eNovance SAS
# @author: Francois Eleouet, Orange
# @author: Mathieu Rohon, Orange

import mock

from neutron.common import constants
from neutron.common import topics
from neutron import context
from neutron.db import agents_db
from neutron.db import api as db_api
from neutron.extensions import portbindings
from neutron.extensions import providernet as pnet
from neutron import manager
from neutron.openstack.common import timeutils
from neutron.plugins.ml2 import config as config
from neutron.plugins.ml2.drivers.l2pop import constants as l2_consts
from neutron.plugins.ml2 import managers
from neutron.plugins.ml2 import rpc
from neutron.tests.unit import test_db_plugin as test_plugin

HOST = 'my_l2_host'
L2_AGENT = {
    'binary': 'neutron-openvswitch-agent',
    'host': HOST,
    'topic': constants.L2_AGENT_TOPIC,
    'configurations': {'tunneling_ip': '20.0.0.1',
                       'tunnel_types': ['vxlan']},
    'agent_type': constants.AGENT_TYPE_OVS,
    'tunnel_type': [],
    'start_flag': True
}

L2_AGENT_2 = {
    'binary': 'neutron-openvswitch-agent',
    'host': HOST + '_2',
    'topic': constants.L2_AGENT_TOPIC,
    'configurations': {'tunneling_ip': '20.0.0.2',
                       'tunnel_types': ['vxlan']},
    'agent_type': constants.AGENT_TYPE_OVS,
    'tunnel_type': [],
    'start_flag': True
}

L2_AGENT_3 = {
    'binary': 'neutron-openvswitch-agent',
    'host': HOST + '_3',
    'topic': constants.L2_AGENT_TOPIC,
    'configurations': {'tunneling_ip': '20.0.0.2',
                       'tunnel_types': []},
    'agent_type': constants.AGENT_TYPE_OVS,
    'tunnel_type': [],
    'start_flag': True
}

PLUGIN_NAME = 'neutron.plugins.ml2.plugin.Ml2Plugin'
NOTIFIER = 'neutron.plugins.ml2.rpc.AgentNotifierApi'
L2POPAGENT = 'neutron.plugins.ml2.drivers.l2pop.rpc.L2populationAgentNotifyAPI'


class TestL2PopulationRpcTestCase(test_plugin.NeutronDbPluginV2TestCase):

    def setUp(self):
        # Enable the test mechanism driver to ensure that
        # we can successfully call through to all mechanism
        # driver apis.
        config.cfg.CONF.set_override('mechanism_drivers',
                                     ['openvswitch', 'linuxbridge',
                                      'l2population'],
                                     'ml2')
        super(TestL2PopulationRpcTestCase, self).setUp(PLUGIN_NAME)
        self.addCleanup(config.cfg.CONF.reset)

        self.adminContext = context.get_admin_context()

        self.type_manager = managers.TypeManager()
        self.notifier = rpc.AgentNotifierApi(topics.AGENT)
        self.callbacks = rpc.RpcCallbacks(self.notifier, self.type_manager)

        self.orig_supported_agents = l2_consts.SUPPORTED_AGENT_TYPES
        l2_consts.SUPPORTED_AGENT_TYPES = [constants.AGENT_TYPE_OVS]

        net_arg = {pnet.NETWORK_TYPE: 'vxlan',
                   pnet.SEGMENTATION_ID: '1'}
        self._network = self._make_network(self.fmt, 'net1', True,
                                           arg_list=(pnet.NETWORK_TYPE,
                                                     pnet.SEGMENTATION_ID,),
                                           **net_arg)

        notifier_patch = mock.patch(NOTIFIER)
        notifier_patch.start()

        self.fanout_topic = topics.get_topic_name(topics.AGENT,
                                                  topics.L2POPULATION,
                                                  topics.UPDATE)
        prepare = ('oslo.messaging.RPCClient.prepare')
        prepare_patch = mock.patch(prepare)
        self.mock_prepare = prepare_patch.start()

        uptime = ('neutron.plugins.ml2.drivers.l2pop.db.L2populationDbMixin.'
                  'get_agent_uptime')
        uptime_patch = mock.patch(uptime, return_value=190)
        uptime_patch.start()

        l2_notify_patch = mock.patch((L2POPAGENT + '._notification_host'))
        self.mock_notify = l2_notify_patch.start()

        l2_fanout_patch = mock.patch((L2POPAGENT + '._notification_fanout'))
        self.mock_fanout = l2_fanout_patch.start()

        self.addCleanup(mock.patch.stopall)
        self.addCleanup(db_api.clear_db)

    def tearDown(self):
        l2_consts.SUPPORTED_AGENT_TYPES = self.orig_supported_agents
        super(TestL2PopulationRpcTestCase, self).tearDown()

    def _register_ml2_agents(self):
        callback = agents_db.AgentExtRpcCallback()
        callback.report_state(self.adminContext,
                              agent_state={'agent_state': L2_AGENT},
                              time=timeutils.strtime())
        callback.report_state(self.adminContext,
                              agent_state={'agent_state': L2_AGENT_2},
                              time=timeutils.strtime())
        callback.report_state(self.adminContext,
                              agent_state={'agent_state': L2_AGENT_3},
                              time=timeutils.strtime())

    def test_fdb_add_called(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg):
                    p1 = port1['port']

                    device = 'tap' + p1['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device)

                    p1_ips = [p['ip_address'] for p in p1['fixed_ips']]
                    expected = \
                        {p1['network_id']:
                            {'ports': {
                                '20.0.0.1': [constants.FLOODING_ENTRY,
                                             [p1['mac_address'],
                                              p1_ips[0]]]},
                             'network_type': 'vxlan',
                             'segment_id': 1}}

                    self.mock_fanout.assert_called_with(mock.ANY,
                                                        'add_fdb_entries',
                                                        expected)

    def test_fdb_add_not_called_type_local(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST + '_3'}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg):
                    p1 = port1['port']

                    device = 'tap' + p1['id']
                    self.mock_fanout.reset()
                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device)

                    self.assertFalse(self.mock_fanout.called)

    def test_fdb_add_two_agents(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST,
                        'admin_state_up': True}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID, 'admin_state_up',),
                           **host_arg) as port1:
                host_arg = {portbindings.HOST_ID: HOST + '_2',
                            'admin_state_up': True}
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,
                                         'admin_state_up',),
                               **host_arg) as port2:
                    p1 = port1['port']
                    p2 = port2['port']

                    device = 'tap' + p1['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device)

                    p1_ips = [p['ip_address'] for p in p1['fixed_ips']]
                    p2_ips = [p['ip_address'] for p in p2['fixed_ips']]

                    expected1 =\
                        {p1['network_id']:
                            {'ports':
                                {'20.0.0.2': [constants.FLOODING_ENTRY,
                                              [p2['mac_address'],
                                                  p2_ips[0]]]},
                                'network_type': 'vxlan',
                                'segment_id': 1}}

                    self.mock_notify.assert_called_with(mock.ANY,
                                                        'add_fdb_entries',
                                                        expected1, HOST)

                    expected2 =\
                        {p1['network_id']:
                            {'ports':
                                {'20.0.0.1': [constants.FLOODING_ENTRY,
                                              [p1['mac_address'],
                                                  p1_ips[0]]]},
                                'network_type': 'vxlan',
                                'segment_id': 1}}

                    self.mock_fanout.assert_called_with(mock.ANY,
                                                        'add_fdb_entries',
                                                        expected2)

    def test_fdb_add_called_two_networks(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST + '_2'}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                with self.subnet(cidr='10.1.0.0/24') as subnet2:
                    with self.port(subnet=subnet2,
                                   arg_list=(portbindings.HOST_ID,),
                                   **host_arg):
                        host_arg = {portbindings.HOST_ID: HOST}
                        with self.port(subnet=subnet,
                                       arg_list=(portbindings.HOST_ID,),
                                       **host_arg) as port3:
                            p1 = port1['port']
                            p3 = port3['port']

                            device = 'tap' + p3['id']

                            self.callbacks.update_device_up(
                                self.adminContext, agent_id=HOST,
                                device=device)

                            p1_ips = [p['ip_address']
                                      for p in p1['fixed_ips']]
                            expected1 =\
                                {p1['network_id']:
                                    {'ports':
                                        {'20.0.0.2':
                                            [constants.FLOODING_ENTRY,
                                                [p1['mac_address'],
                                                 p1_ips[0]]]},
                                        'network_type': 'vxlan',
                                        'segment_id': 1}}

                            self.mock_notify.assert_called_with(
                                mock.ANY, 'add_fdb_entries', expected1, HOST)

                            p3_ips = [p['ip_address']
                                      for p in p3['fixed_ips']]
                            expected2 =\
                                {p1['network_id']:
                                    {'ports':
                                        {'20.0.0.1':
                                            [constants.FLOODING_ENTRY,
                                             [p3['mac_address'],
                                                 p3_ips[0]]]},
                                     'network_type': 'vxlan',
                                     'segment_id': 1}}

                            self.mock_fanout.assert_called_with(
                                mock.ANY, 'add_fdb_entries', expected2)

    def test_update_port_down(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg) as port2:
                    p2 = port2['port']
                    device2 = 'tap' + p2['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device2)

                    p1 = port1['port']
                    device1 = 'tap' + p1['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device1)
                    self.callbacks.update_device_down(self.adminContext,
                                                      agent_id=HOST,
                                                      device=device2)

                    p2_ips = [p['ip_address'] for p in p2['fixed_ips']]
                    expected =\
                        {p2['network_id']:
                            {'ports':
                                {'20.0.0.1': [[p2['mac_address'],
                                               p2_ips[0]]]},
                                'network_type': 'vxlan',
                                'segment_id': 1}}

                    self.mock_fanout.assert_called_with(
                        mock.ANY, 'remove_fdb_entries', expected)

    def test_update_port_down_last_port_up(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg):
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg) as port2:
                    p2 = port2['port']
                    device2 = 'tap' + p2['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device2)

                    self.callbacks.update_device_down(self.adminContext,
                                                      agent_id=HOST,
                                                      device=device2)

                    p2_ips = [p['ip_address'] for p in p2['fixed_ips']]
                    expected =\
                        {p2['network_id']:
                            {'ports':
                                {'20.0.0.1': [constants.FLOODING_ENTRY,
                                             [p2['mac_address'],
                                                 p2_ips[0]]]},
                                'network_type': 'vxlan',
                                'segment_id': 1}}

                    self.mock_fanout.assert_called_with(
                        mock.ANY, 'remove_fdb_entries', expected)

    def test_delete_port(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port:
                p1 = port['port']
                device = 'tap' + p1['id']

                self.callbacks.update_device_up(self.adminContext,
                                                agent_id=HOST,
                                                device=device)

                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg) as port2:
                    p2 = port2['port']
                    device1 = 'tap' + p2['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device1)

                p2_ips = [p['ip_address'] for p in p2['fixed_ips']]
                expected =\
                    {p2['network_id']:
                        {'ports':
                            {'20.0.0.1': [[p2['mac_address'],
                                           p2_ips[0]]]},
                            'network_type': 'vxlan',
                            'segment_id': 1}}

                self.mock_fanout.assert_called_with(
                    mock.ANY, 'remove_fdb_entries', expected)

    def test_delete_port_last_port_up(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet,
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg):
                with self.port(subnet=subnet,
                               arg_list=(portbindings.HOST_ID,),
                               **host_arg) as port:
                    p1 = port['port']

                    device = 'tap' + p1['id']

                    self.callbacks.update_device_up(self.adminContext,
                                                    agent_id=HOST,
                                                    device=device)

                p1_ips = [p['ip_address'] for p in p1['fixed_ips']]
                expected =\
                    {p1['network_id']:
                        {'ports':
                            {'20.0.0.1': [constants.FLOODING_ENTRY,
                                         [p1['mac_address'],
                                             p1_ips[0]]]},
                            'network_type': 'vxlan',
                            'segment_id': 1}}

                self.mock_fanout.assert_called_with(
                    mock.ANY, 'remove_fdb_entries', expected)

    def test_fixed_ips_changed(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet, cidr='10.0.0.0/24',
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                p1 = port1['port']

                device = 'tap' + p1['id']

                self.callbacks.update_device_up(self.adminContext,
                                                agent_id=HOST,
                                                device=device)

                data = {'port': {'fixed_ips': [{'ip_address': '10.0.0.2'},
                                               {'ip_address': '10.0.0.10'}]}}
                req = self.new_update_request('ports', data, p1['id'])
                res = self.deserialize(self.fmt, req.get_response(self.api))
                ips = res['port']['fixed_ips']
                self.assertEqual(len(ips), 2)

                add_expected =\
                    {'chg_ip':
                        {p1['network_id']:
                            {'20.0.0.1':
                                {'after': [[p1['mac_address'],
                                           '10.0.0.10']]}}}}

                self.mock_fanout.assert_called_with(
                    mock.ANY, 'update_fdb_entries', add_expected)

                data = {'port': {'fixed_ips': [{'ip_address': '10.0.0.2'},
                                               {'ip_address': '10.0.0.16'}]}}
                req = self.new_update_request('ports', data, p1['id'])
                res = self.deserialize(self.fmt, req.get_response(self.api))
                ips = res['port']['fixed_ips']
                self.assertEqual(len(ips), 2)

                upd_expected =\
                    {'chg_ip':
                        {p1['network_id']:
                            {'20.0.0.1':
                                {'before': [[p1['mac_address'],
                                            '10.0.0.10']],
                                 'after': [[p1['mac_address'],
                                           '10.0.0.16']]}}}}

                self.mock_fanout.assert_called_with(
                    mock.ANY, 'update_fdb_entries', upd_expected)

                data = {'port': {'fixed_ips': [{'ip_address': '10.0.0.16'}]}}
                req = self.new_update_request('ports', data, p1['id'])
                res = self.deserialize(self.fmt, req.get_response(self.api))
                ips = res['port']['fixed_ips']
                self.assertEqual(len(ips), 1)

                del_expected =\
                    {'chg_ip':
                        {p1['network_id']:
                            {'20.0.0.1':
                                {'before': [[p1['mac_address'],
                                             '10.0.0.2']]}}}}

                self.mock_fanout.assert_called_with(
                    mock.ANY, 'update_fdb_entries', del_expected)

    def test_no_fdb_updates_without_port_updates(self):
        self._register_ml2_agents()

        with self.subnet(network=self._network) as subnet:
            host_arg = {portbindings.HOST_ID: HOST}
            with self.port(subnet=subnet, cidr='10.0.0.0/24',
                           arg_list=(portbindings.HOST_ID,),
                           **host_arg) as port1:
                p1 = port1['port']

                device = 'tap' + p1['id']

                self.callbacks.update_device_up(self.adminContext,
                                                agent_id=HOST,
                                                device=device)
                p1['status'] = 'ACTIVE'

                fanout = ('neutron.plugins.ml2.drivers.l2pop.rpc.'
                          'L2populationAgentNotifyAPI._notification_fanout')
                fanout_patch = mock.patch(fanout)
                mock_fanout = fanout_patch.start()

                plugin = manager.NeutronManager.get_plugin()
                plugin.update_port(self.adminContext, p1['id'], port1)

                self.assertFalse(mock_fanout.called)
                fanout_patch.stop()
