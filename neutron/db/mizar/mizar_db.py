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

import functools
import random

import netaddr
from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from neutron_lib import constants
from neutron_lib.db import api as db_api
from neutron_lib.db import model_query
from neutron_lib.db import resource_extend
from neutron_lib.db import utils as lib_db_utils
from neutron_lib.exceptions import mizar as mizar_exc
from neutron_lib.plugins import constants as plugin_constants
from neutron_lib.plugins import directory
from neutron_lib.services import base as base_services
from oslo_log import log as logging
from sqlalchemy import exc

from neutron.api.rpc.agentnotifiers import l3_rpc_agent_api
from neutron.common import utils
from neutron.db.models import l3 as l3_models, mizar as mizar_db
from neutron.db import models_v2
from neutron.objects import router as l3_obj

LOG = logging.getLogger(__name__)


@registry.has_registry_receivers
class Mizar_dbonly_mixin(base_services.WorkerBase):

    @property
    def _l3_plugin(self):
        return directory.get_plugin(plugin_constants.L3)

    def __new__(cls, *args, **kwargs):
        inst = super(Mizar_dbonly_mixin, cls).__new__(cls, *args, **kwargs)
        return inst

    def _make_vpc_dict(self, vpc_db, fields=None):
        res = {
            'id': vpc_db['id'],
            'cidr': vpc_db['cidr'],
            'transit_routers': [r for r in vpc_db.get('transit_routers', [])]
        }

        return lib_db_utils.resource_fields(res, fields)

    def _get_vpc(self, context, vpc_id):
        try:
            vpc = model_query.get_by_id(
                context, mizar_db.Vpc, vpc_id)
        except exc.NoResultFound:
            raise mizar_exc.VpcNotFound(vpc_id=vpc_id)
        return vpc

    @db_api.retry_if_session_inactive()
    def create_vpc(self, context, vpc):
        vpc_info = vpc['vpc']
        router = {
            'router': {
                'tenant_id': vpc_info['tenant_id']
            }
        }
        new_router = self._l3_plugin.create_router(context, router)
        with context.session.begin(subtransactions=True):
            vpc_db = mizar_db.Vpc(
                id=new_router['id'],
                tenant_id=vpc_info['tenant_id'],
                cidr=vpc_info['cidr'])
            context.session.add(vpc_db)

        return self._make_vpc_dict(vpc_db)

    @db_api.retry_if_session_inactive()
    def update_vpc(self, context, id, vpc):
        new = vpc['vpc']

        if 'cidr' in new:
            with db_api.CONTEXT_WRITER.using(context):
                original = self._get_vpc(context, id)
                original['cidr'] = new['cidr']

        router_db = self._update_router_db(context, id, r)
        updated = self._make_router_dict(router_db)

        return updated

    @db_api.retry_if_session_inactive()
    def get_vpc(self, context, id, fields=None):
        vpc_db = self._get_vpc(context, id)
        return self._make_vpc_dict(vpc_db, fields=fields)


@registry.has_registry_receivers
class MizarRpcNotifierMixin(object):
    """Mixin class to add rpc notifier attribute to db_base_plugin_v2."""

    @staticmethod
    @registry.receives(resources.PORT, [events.AFTER_DELETE])
    def _notify_routers_callback(resource, event, trigger, **kwargs):
        context = kwargs['context']
        router_ids = kwargs['router_ids']
        l3plugin = directory.get_plugin(plugin_constants.L3)
        if l3plugin:
            l3plugin.notify_routers_updated(context, router_ids)
        else:
            LOG.debug('%s not configured', plugin_constants.L3)

    @staticmethod
    @registry.receives(resources.SUBNET, [events.AFTER_UPDATE])
    def _notify_subnet_gateway_ip_update(resource, event, trigger, **kwargs):
        l3plugin = directory.get_plugin(plugin_constants.L3)
        if not l3plugin:
            return
        context = kwargs['context']
        orig = kwargs['original_subnet']
        updated = kwargs['subnet']
        if orig['gateway_ip'] == updated['gateway_ip']:
            return
        network_id = updated['network_id']
        subnet_id = updated['id']
        query = context.session.query(models_v2.Port.device_id).filter_by(
                    network_id=network_id,
                    device_owner=DEVICE_OWNER_ROUTER_GW)
        query = query.join(models_v2.Port.fixed_ips).filter(
                    models_v2.IPAllocation.subnet_id == subnet_id)
        router_ids = set(port.device_id for port in query)
        for router_id in router_ids:
            l3plugin.notify_router_updated(context, router_id)

    @staticmethod
    @registry.receives(resources.PORT, [events.AFTER_UPDATE])
    def _notify_gateway_port_ip_changed(resource, event, trigger, **kwargs):
        l3plugin = directory.get_plugin(plugin_constants.L3)
        if not l3plugin:
            return
        new_port = kwargs.get('port')
        original_port = kwargs.get('original_port')

        if original_port['device_owner'] != constants.DEVICE_OWNER_ROUTER_GW:
            return

        if utils.port_ip_changed(new_port, original_port):
            l3plugin.notify_router_updated(kwargs['context'],
                                           new_port['device_id'])

    @staticmethod
    @registry.receives(resources.SUBNETPOOL_ADDRESS_SCOPE,
                       [events.AFTER_UPDATE])
    def _notify_subnetpool_address_scope_update(resource, event,
                                                trigger, payload=None):
        context = payload.context
        subnetpool_id = payload.resource_id

        router_ids = l3_obj.RouterPort.get_router_ids_by_subnetpool(
            context, subnetpool_id)

        l3plugin = directory.get_plugin(plugin_constants.L3)
        if l3plugin:
            l3plugin.notify_routers_updated(context, router_ids)
        else:
            LOG.debug('%s not configured', plugin_constants.L3)

    @property
    def l3_rpc_notifier(self):
        if not hasattr(self, '_l3_rpc_notifier'):
            self._l3_rpc_notifier = l3_rpc_agent_api.L3AgentNotifyAPI()
        return self._l3_rpc_notifier

    @l3_rpc_notifier.setter
    def l3_rpc_notifier(self, value):
        self._l3_rpc_notifier = value

    def notify_router_updated(self, context, router_id,
                              operation=None):
        if router_id:
            self.l3_rpc_notifier.routers_updated(
                context, [router_id], operation)

    def notify_routers_updated(self, context, router_ids,
                               operation=None, data=None):
        if router_ids:
            self.l3_rpc_notifier.routers_updated(
                context, router_ids, operation, data)

    def notify_router_deleted(self, context, router_id):
        self.l3_rpc_notifier.router_deleted(context, router_id)


class Mizar_db_mixin(MizarRpcNotifierMixin):
    """Mixin class to add rpc notifier methods to db_base_plugin_v2."""

    def create_router(self, context, router):
        router_dict = super(Mizar_db_mixin, self).create_router(context,
                                                                 router)
        if router_dict.get('external_gateway_info'):
            self.notify_router_updated(context, router_dict['id'], None)
        return router_dict

    def update_router(self, context, id, router):
        router_dict = super(Mizar_db_mixin, self).update_router(context,
                                                                 id, router)
        self.notify_router_updated(context, router_dict['id'], None)
        return router_dict

    def delete_router(self, context, id):
        super(Mizar_db_mixin, self).delete_router(context, id)
        self.notify_router_deleted(context, id)

    def notify_routers_updated(self, context, router_ids):
        super(Mizar_db_mixin, self).notify_routers_updated(
            context, list(router_ids), 'disassociate_floatingips', {})
