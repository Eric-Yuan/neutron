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

# NOTE(haleyb): remove once the default backend is ``BackendType.THREADING``
import oslo_service.backend as service
service.init_backend(service.BackendType.THREADING)

# pylint: disable=wrong-import-position
import setproctitle  # noqa: E402

from neutron.agent import metadata_agent  # noqa: E402
from neutron_lib import constants  # noqa: E402


def main():
    proctitle = "{} ({})".format(
        constants.AGENT_PROCESS_METADATA, setproctitle.getproctitle())
    setproctitle.setproctitle(proctitle)

    metadata_agent.main()
