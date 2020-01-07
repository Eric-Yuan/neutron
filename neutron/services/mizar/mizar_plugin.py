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
from neutron_lib.api.definitions.mizar import droplet, endpoint, vpc, vpcnet
from neutron_lib.db import resource_extend
from neutron_lib.services import base as service_base
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils

from neutron.db.models import l3 as l3_models
from neutron.quota import resource_registry

LOG = logging.getLogger(__name__)


@resource_extend.has_resource_extenders
class MizarPlugin(service_base.ServicePluginBase):

    """Implementation of the Mizar Service Plugin.
    """
    _supported_extension_aliases = [vpc.VPC,
                                    vpcnet.NETWORK,
                                    endpoint.ENDPOINT,
                                    droplet.DROPLET]

    __native_pagination_support = True
    __native_sorting_support = True
    __filter_validation_support = True

    @resource_registry.tracked_resources(router=l3_models.Router)
    def __init__(self):
        self.router_scheduler = importutils.import_object(
            cfg.CONF.router_scheduler_driver)
        self.add_periodic_l3_agent_status_check()
        super(L3RouterPlugin, self).__init__()
        if 'dvr' in self.supported_extension_aliases:
            l3_dvrscheduler_db.subscribe()
        if 'l3-ha' in self.supported_extension_aliases:
            l3_hascheduler_db.subscribe()
        self.agent_notifiers.update(
            {n_const.AGENT_TYPE_L3: l3_rpc_agent_api.L3AgentNotifyAPI()})

        rpc_worker = service.RpcWorker([self], worker_process_count=0)

        self.add_worker(rpc_worker)
        self.l3_driver_controller = driver_controller.DriverController(self)

    @property
    def supported_extension_aliases(self):
        if not hasattr(self, '_aliases'):
            aliases = self._supported_extension_aliases[:]
            disable_dvr_extension_by_config(aliases)
            disable_l3_qos_extension_by_plugins('qos-fip', aliases)
            disable_l3_qos_extension_by_plugins('qos-gateway-ip', aliases)
            self._aliases = aliases
        return self._aliases

    @log_helpers.log_method_call
    def start_rpc_listeners(self):
        # RPC support
        self.topic = topics.L3PLUGIN
        self.conn = n_rpc.Connection()
        self.endpoints = [l3_rpc.L3RpcCallback()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        return self.conn.consume_in_threads()

    @classmethod
    def get_plugin_type(cls):
        return plugin_constants.L3

    def get_plugin_description(self):
        """returns string description of the plugin."""
        return ("L3 Router Service Plugin for basic L3 forwarding"
                " between (L2) Neutron networks and access to external"
                " networks via a NAT gateway.")

    def router_supports_scheduling(self, context, router_id):
        return self.l3_driver_controller.uses_scheduler(context, router_id)

    def create_floatingip(self, context, floatingip):
        """Create floating IP.

        :param context: Neutron request context
        :param floatingip: data for the floating IP being created
        :returns: A floating IP object on success

        As the l3 router plugin asynchronously creates floating IPs
        leveraging the l3 agent, the initial status for the floating
        IP object will be DOWN.
        """
        return super(L3RouterPlugin, self).create_floatingip(
            context, floatingip,
            initial_status=n_const.FLOATINGIP_STATUS_DOWN)
