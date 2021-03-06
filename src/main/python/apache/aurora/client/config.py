#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

'''Library of utilities called by the aurora client binary
'''

from __future__ import print_function

import functools
import math
import re
import sys

from pystachio import Empty

from apache.aurora.client import binding_helper
from apache.aurora.client.base import deprecation_warning, die
from apache.aurora.config import AuroraConfig

from gen.apache.aurora.api.constants import DEFAULT_ENVIRONMENT


CRON_DEPRECATION_WARNING = """
The "cron_policy" parameter to Jobs has been renamed to "cron_collision_policy".
Please update your Jobs accordingly.
"""


def _warn_on_deprecated_cron_policy(config):
  if config.raw().cron_policy() is not Empty:
    deprecation_warning(CRON_DEPRECATION_WARNING)


DAEMON_DEPRECATION_WARNING = """
The "daemon" parameter to Jobs is deprecated in favor of the "service" parameter.
Please update your Job to set "service = True" instead of "daemon = True", or use
the top-level Service() instead of Job().
"""


def _warn_on_deprecated_daemon_job(config):
  if config.raw().daemon() is not Empty:
    deprecation_warning(DAEMON_DEPRECATION_WARNING)


HEALTH_CHECK_INTERVAL_SECS_DEPRECATION_WARNING = """
The "health_check_interval_secs" parameter to Jobs is deprecated in favor of the
"health_check_config" parameter. Please update your Job to set the parameter by creating a new
HealthCheckConfig.

See the HealthCheckConfig section of the Configuration Reference page for more information:
http://go/auroraconfig/#Aurora%2BThermosConfigurationReference-HealthCheckConfig
"""


def _warn_on_deprecated_health_check_interval_secs(config):
  if config.raw().health_check_interval_secs() is not Empty:
    deprecation_warning(HEALTH_CHECK_INTERVAL_SECS_DEPRECATION_WARNING)


ANNOUNCE_WARNING = """
Announcer specified primary port as '%(primary_port)s' but no processes have bound that port.
If you would like to utilize this port, you should listen on {{thermos.ports[%(primary_port)s]}}
from some Process bound to your task.
"""


def _validate_announce_configuration(config):
  if not config.raw().has_announce():
    return

  primary_port = config.raw().announce().primary_port().get()
  if primary_port not in config.ports():
    print(ANNOUNCE_WARNING % {'primary_port': primary_port}, file=sys.stderr)

  if config.raw().has_announce() and not config.raw().has_constraints() or (
      'dedicated' not in config.raw().constraints()):
    for port in config.raw().announce().portmap().get().values():
      try:
        port = int(port)
      except ValueError:
        continue
      raise ValueError('Job must be dedicated in order to specify static ports!')


STAGING_RE = re.compile(r'^staging\d*$')


def _validate_environment_name(config):
  env_name = str(config.raw().environment())
  if STAGING_RE.match(env_name):
    return
  if env_name not in ('prod', 'devel', 'test'):
    raise ValueError('Environment name should be one of "prod", "devel", "test" or '
                     'staging<number>!  Got %s' % env_name)


UPDATE_CONFIG_MAX_FAILURES_ERROR = '''
max_total_failures in update_config must be lesser than the job size.
Based on your job size (%s) you should use max_total_failures <= %s.

See http://go/auroraconfig for details.
'''


UPDATE_CONFIG_DEDICATED_THRESHOLD_ERROR = '''
Since this is a dedicated job, you must set your max_total_failures in
your update configuration to no less than 2%% of your job size.
Based on your job size (%s) you should use max_total_failures >= %s.

See http://go/auroraconfig for details.
'''


WATCH_SECS_INSUFFICIENT_ERROR_FORMAT = '''
You have specified an insufficiently short watch period (%d seconds) in your update configuration.
Your update will always succeed. In order for the updater to detect health check failures,
UpdateConfig.watch_secs must be greater than %d seconds to account for an initial
health check interval (%d seconds) plus %d consecutive failures at a check interval of %d seconds.
'''


def _validate_update_config(config):
  job_size = config.instances()
  update_config = config.update_config()
  health_check_config = config.health_check_config()

  max_failures = update_config.max_total_failures().get()
  watch_secs = update_config.watch_secs().get()
  initial_interval_secs = health_check_config.initial_interval_secs().get()
  max_consecutive_failures = health_check_config.max_consecutive_failures().get()
  interval_secs = health_check_config.interval_secs().get()

  if max_failures >= job_size:
    die(UPDATE_CONFIG_MAX_FAILURES_ERROR % (job_size, job_size - 1))

  if config.is_dedicated():
    min_failure_threshold = int(math.floor(job_size * 0.02))
    if max_failures < min_failure_threshold:
      die(UPDATE_CONFIG_DEDICATED_THRESHOLD_ERROR % (job_size, min_failure_threshold))

  target_watch = initial_interval_secs + (max_consecutive_failures * interval_secs)
  if watch_secs <= target_watch:
    die(WATCH_SECS_INSUFFICIENT_ERROR_FORMAT %
        (watch_secs, target_watch, initial_interval_secs, max_consecutive_failures, interval_secs))


HEALTH_CHECK_INTERVAL_SECS_ERROR = '''
health_check_interval_secs paramater to Job has been deprecated. Please specify health_check_config
only.

See http://go/auroraconfig/#Aurora%2BThermosConfigurationReference-HealthCheckConfig
'''


def _validate_health_check_config(config):
  # TODO(Sathya): Remove this check after health_check_interval_secs deprecation cycle is complete.
  if config.raw().has_health_check_interval_secs() and config.raw().has_health_check_config():
    die(HEALTH_CHECK_INTERVAL_SECS_ERROR)


DEFAULT_ENVIRONMENT_WARNING = '''
Job did not specify environment, auto-populating to "%s".
'''


def _inject_default_environment(config):
  if not config.raw().has_environment():
    print(DEFAULT_ENVIRONMENT_WARNING % DEFAULT_ENVIRONMENT, file=sys.stderr)
    config.update_job(config.raw()(environment=DEFAULT_ENVIRONMENT))


def validate_config(config, env=None):
  _validate_health_check_config(config)
  _validate_update_config(config)
  _validate_announce_configuration(config)
  _validate_environment_name(config)


def populate_namespaces(config, env=None):
  _inject_default_environment(config)
  _warn_on_deprecated_cron_policy(config)
  _warn_on_deprecated_daemon_job(config)
  _warn_on_deprecated_health_check_interval_secs(config)
  return config


class GlobalHookRegistry(object):
  """To allow enforcable policy, we need a set of mandatory hooks that are
  registered as part of the client executable. Global hooks are registered
  by calling GlobalHookRegistry.register_global_hook.
  """

  HOOKS = []

  DISABLED = False

  @classmethod
  def register_global_hook(cls, hook):
    cls.HOOKS.append(hook)

  @classmethod
  def get_hooks(cls):
    if cls.DISABLED:
      return []
    else:
      return cls.HOOKS[:]

  @classmethod
  def reset(cls):
    cls.HOOKS = []
    cls.DISABLED = False

  @classmethod
  def disable_hooks(cls):
    cls.DISABLED = True

  @classmethod
  def enable_hooks(cls):
    cls.DISABLED = False


def inject_hooks(config, env=None):
  config.hooks = (env or {}).get('hooks', [])


class AnnotatedAuroraConfig(AuroraConfig):
  @classmethod
  def plugins(cls):
    return (inject_hooks,
            functools.partial(binding_helper.apply_all),
            functools.partial(populate_namespaces),
            validate_config)


def get_config(jobname,
               config_file,
               json=False,
               bindings=(),
               select_cluster=None,
               select_role=None,
               select_env=None):
  """Creates and returns a config object contained in the provided file."""
  loader = AnnotatedAuroraConfig.load_json if json else AnnotatedAuroraConfig.load
  return loader(config_file,
                jobname,
                bindings,
                select_cluster=select_cluster,
                select_role=select_role,
                select_env=select_env)
