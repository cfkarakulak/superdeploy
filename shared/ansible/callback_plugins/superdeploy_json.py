# -*- coding: utf-8 -*-
# Copyright: (c) 2024, SuperDeploy
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    name: superdeploy_json
    type: stdout
    short_description: SuperDeploy JSON callback for clean parsing
    description:
        - This callback outputs JSON events that can be parsed by SuperDeploy
        - Each line is a JSON object with event type and data
    requirements:
      - Set as stdout callback in ansible.cfg or via environment variable
'''

import json
import datetime
from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """
    SuperDeploy JSON callback - outputs structured JSON for parsing
    """
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'superdeploy_json'

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.start_time = datetime.datetime.now()

    def _emit(self, event_type, data):
        """Emit a JSON event"""
        event = {
            'type': event_type,
            'timestamp': datetime.datetime.now().isoformat(),
            'data': data
        }
        print(json.dumps(event), flush=True)

    def v2_playbook_on_start(self, playbook):
        self._emit('playbook_start', {
            'playbook': playbook._file_name
        })

    def v2_playbook_on_play_start(self, play):
        self._emit('play_start', {
            'name': play.get_name()
        })

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._emit('task_start', {
            'name': task.get_name(),
            'id': str(task._uuid)
        })

    def v2_runner_on_ok(self, result):
        self._emit('task_ok', {
            'task': result._task.get_name(),
            'host': result._host.get_name(),
            'changed': result._result.get('changed', False)
        })

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._emit('task_failed', {
            'task': result._task.get_name(),
            'host': result._host.get_name(),
            'msg': result._result.get('msg', ''),
            'ignore_errors': ignore_errors
        })

    def v2_runner_on_skipped(self, result):
        self._emit('task_skipped', {
            'task': result._task.get_name(),
            'host': result._host.get_name()
        })

    def v2_runner_on_unreachable(self, result):
        self._emit('task_unreachable', {
            'task': result._task.get_name(),
            'host': result._host.get_name(),
            'msg': result._result.get('msg', '')
        })

    def v2_playbook_on_stats(self, stats):
        hosts = sorted(stats.processed.keys())
        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = {
                'ok': s['ok'],
                'changed': s['changed'],
                'unreachable': s['unreachable'],
                'failures': s['failures'],
                'skipped': s['skipped']
            }
        
        self._emit('playbook_stats', {
            'hosts': summary
        })

    def v2_playbook_on_no_hosts_matched(self):
        self._emit('error', {
            'msg': 'No hosts matched'
        })

    def v2_playbook_on_no_hosts_remaining(self):
        self._emit('error', {
            'msg': 'No hosts remaining'
        })
