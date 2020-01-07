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

from neutron_lib.api.definitions.mizar import endpoint as apidef
from neutron_lib.api import extensions as api_extensions
import six

from neutron.api.v2 import resource_helper


class Endpoint(api_extensions.APIExtensionDescriptor):
    """Extension class supporting Address Scopes."""
    api_definition = apidef

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        plural_mappings = resource_helper.build_plural_mappings(
            {}, apidef.RESOURCE_ATTRIBUTE_MAP)
        return resource_helper.build_resource_info(
            plural_mappings, apidef.RESOURCE_ATTRIBUTE_MAP,
            apidef.ENDPOINT, action_map=apidef.ACTION_MAP)


@six.add_metaclass(abc.ABCMeta)
class EndpointPluginBase(object):

    @abc.abstractmethod
    def create_enpoint(self, context, endpoint):
        pass

    @abc.abstractmethod
    def update_enpoint(self, context, id, endpoint):
        pass

    @abc.abstractmethod
    def get_enpoint(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def get_enpoints(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None,
                     page_reverse=False):
        pass

    @abc.abstractmethod
    def delete_enpoint(self, context, id):
        pass
