#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal tree callback plugin for Ansible
Shows clean tree output with single checkmark per task
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.callback import CallbackBase
from ansible import constants as C

DOCUMENTATION = '''
    callback: tree_minimal
    type: stdout
    short_description: Minimal tree output
    description:
        - Clean tree view with single checkmark per task
        - No duplicate output for multiple hosts
        - Proper handling of loops and includes
'''


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'tree_minimal'

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.play_name = None
        self.task_status = {}  # Track task completion status
        self.current_task = None
        self.task_start_time = {}  # Track task start times
        self.play_start_time = None
        self.play_task_times = []  # Track all task times in current play

    def v2_playbook_on_play_start(self, play):
        """Called when a play starts"""
        import time
        
        name = play.get_name().strip()
        if name and name != "Gathering Facts":
            self.play_name = name
            self.play_start_time = time.time()
            self.play_task_times = []
            # Yellow arrow for play (no time shown for plays, only tasks)
            self._display.display(f"└── \033[33m▶\033[0m {name}")

    def v2_playbook_on_task_start(self, task, is_conditional):
        """Called when a task starts"""
        import time
        
        self.current_task = task.get_name().strip()
        
        # Skip noise
        if any(x in self.current_task.lower() for x in ['gathering facts', 'setup']):
            self.current_task = None
            return
        
        # Clean task name (remove role prefix)
        if ' : ' in self.current_task:
            _, self.current_task = self.current_task.split(' : ', 1)
        
        # Track start time
        if self.current_task not in self.task_status:
            self.task_status[self.current_task] = 'running'
            self.task_start_time[self.current_task] = time.time()

    def v2_runner_on_ok(self, result):
        """Called when a task succeeds"""
        import time
        
        if not self.current_task or self.current_task not in self.task_status:
            return
        
        # Only update if not already completed
        if self.task_status[self.current_task] == 'running':
            self.task_status[self.current_task] = 'ok'
            
            # Calculate elapsed time
            elapsed = time.time() - self.task_start_time.get(self.current_task, time.time())
            self.play_task_times.append(elapsed)
            duration_str = self._format_duration(elapsed)
            
            # Show checkmark (green) with time (cyan) in parentheses
            self._display.display(f"├── \033[32m✓\033[0m \033[2m{self.current_task}\033[0m \033[2m\033[36m({duration_str})\033[0m")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        """Called when a task fails"""
        import time
        
        if not self.current_task or self.current_task not in self.task_status:
            return
        
        if self.task_status[self.current_task] == 'running':
            self.task_status[self.current_task] = 'failed'
            
            # Calculate elapsed time
            elapsed = time.time() - self.task_start_time.get(self.current_task, time.time())
            duration_str = self._format_duration(elapsed)
            
            # Show X (red) with time in parentheses
            self._display.display(f"├── \033[31m✗\033[0m \033[2m{self.current_task}\033[0m \033[2m\033[36m({duration_str})\033[0m")
            
            # Show error message
            if 'msg' in result._result:
                self._display.display(f"│   \033[31mError: {result._result['msg']}\033[0m")

    def v2_runner_on_skipped(self, result):
        """Called when a task is skipped"""
        if not self.current_task or self.current_task not in self.task_status:
            return
        
        if self.task_status[self.current_task] == 'running':
            self.task_status[self.current_task] = 'skipped'
            # Show skip (magenta) - no time for skipped tasks
            self._display.display(f"├── \033[35m⊘\033[0m \033[2m{self.current_task}\033[0m")

    def v2_playbook_on_stats(self, stats):
        """Called at the end"""
        self._display.display("\n└── Summary:")
        
        hosts = sorted(stats.processed.keys())
        for host in hosts:
            s = stats.summarize(host)
            color = "\033[32m" if s['failures'] == 0 else "\033[31m"
            self._display.display(
                f"    {color}{host}\033[0m: ok={s['ok']} changed={s['changed']} "
                f"failed={s['failures']} skipped={s['skipped']}"
            )
    
    def _format_duration(self, seconds):
        """Format duration as 1m 23s or 5s"""
        if seconds < 1:
            return "1s"
        elif seconds < 60:
            return f"{int(seconds)}s"
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs:02d}s"
