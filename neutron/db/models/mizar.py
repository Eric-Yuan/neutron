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

from neutron_lib.api.definitions import l3 as l3_apidef
from neutron_lib.db import constants as db_const
from neutron_lib.db import model_base
import sqlalchemy as sa
from sqlalchemy import orm

from neutron.db.models import l3agent as rb_model
from neutron.db import models_v2
from neutron.db import standard_attr
from neutron.db.models.l3 import Router


class VpcBinding(model_base.BASEV2):
    vpc_id = sa.Column(sa.String(36),
                       sa.ForeignKey('vpcs.id', ondelete="CASCADE"),
                       primary_key=True)
    droplet_id = sa.Column(sa.String(36),
                           sa.ForeignKey('droplet.id', ondelete="CASCADE"),
                           primary_key=True)


class VpcnetBinding(model_base.BASEV2):
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('vpcnet.id', ondelete="CASCADE"),
                           primary_key=True)
    droplet_id = sa.Column(sa.String(36),
                           sa.ForeignKey('droplet.id', ondelete="CASCADE"),
                           primary_key=True)


class EndpointBinding(model_base.BASEV2):
    endpoint_id = sa.Column(sa.String(36),
                            sa.ForeignKey('endpoint.id', ondelete="CASCADE"),
                            primary_key=True)
    droplet_id = sa.Column(sa.String(36),
                           sa.ForeignKey('droplet.id', ondelete="CASCADE"),
                           primary_key=True)


class Droplet(model_base.BASEV2, model_base.HasId):
    vtep_ip = sa.Column(sa.String(64), nullable=False)


class Vpc(model_base.BASEV2):
    router_id = sa.Column(sa.String(36),
                          sa.ForeignKey('routers.id',
                                        ondelete="CASCADE"),
                          primary_key=True,
                          index=True)
    cidr = sa.Column(sa.String(64), nullable=False)
    transit_routers = orm.relationship(
        VpcBinding,
        backref=orm.backref('transit_router', load_on_pending=True),
        lazy='subquery')
    

class Vpcnet(model_base.BASEV2):
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id',
                                         ondelete="CASCADE"),
                           primary_key=True,
                           index=True)
    vpc_id = sa.Column(sa.String(36),
                       sa.ForeignKey('vpcs.id'),
                       index=True)
    cidr = sa.Column(sa.String(64), nullable=False)
    transit_switches = orm.relationship(
        VpcnetBinding,
        backref=orm.backref('transit_switch', load_on_pending=True),
        lazy='subquery')


class Endpoint(model_base.BASEV2):
    port_id = sa.Column(sa.String(36),
                        sa.ForeignKey('ports.id',
                                      ondelete="CASCADE"),
                        primary_key=True,
                        index=True)

    locations = orm.relationship(
        EndpointBinding,
        backref=orm.backref('endpoint', load_on_pending=True),
        lazy='subquery')
