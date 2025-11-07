#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal tree callback plugin for Ansible
Shows clean tree output with single checkmark per task
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = """
    callback: tree_minimal
    type: stdout
    short_description: Minimal tree output
    description:
        - Clean tree view with single checkmark per task
        - No duplicate output for multiple hosts
        - Proper handling of loops and includes
"""


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "tree_minimal"

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.play_name = None
        self.task_status = {}  # Track task completion status
        self.current_task = None
        self.task_start_time = {}  # Track task start times
        self.play_start_time = None
        self.play_task_times = []  # Track all task times in current play
        self.task_roles = {}  # Map task -> role name
        self.shown_roles = set()  # Track which roles we've shown headers for
        self.shown_tasks = set()  # Track which tasks we've shown (dedupe across hosts)

    def v2_playbook_on_play_start(self, play):
        """Called when a play starts"""
        import time

        name = play.get_name().strip()
        if name and name != "Gathering Facts":
            self.play_name = name
            self.play_start_time = time.time()
            self.play_task_times = []
            self.shown_roles = set()  # Reset role tracking for new play
            self.shown_tasks = set()  # Reset task tracking for new play
            # Orange arrow for play
            self._display.display(f"└── \033[38;5;214m▶\033[0m {name}")

    def v2_playbook_on_task_start(self, task, is_conditional):
        """Called when a task starts"""
        import time

        task_name = task.get_name().strip()

        # Extract role name if this is a role task
        role_name = None
        if " : " in task_name:
            role_name, task_name = task_name.split(" : ", 1)

            # Don't show role headers - play names are descriptive enough
            # Role paths like "system/base" add noise without value
            # We track roles internally for indentation but don't display them

        self.current_task = task_name

        # Store role mapping for this task (for indentation purposes)
        if role_name:
            self.task_roles[self.current_task] = role_name
            self.shown_roles.add(role_name)  # Track to maintain state

        # Skip noise/verbose tasks
        skip_tasks = [
            "gathering facts",
            "setup",
            "deploy each addon",
            "set addon paths",
            "display addon deployment info",
            "check if addon exists",
            "fail if addon does not exist",
            "load addon metadata",
            "fail if addon.yml is missing",
            "validate addon metadata",
            "check addon dependencies",
        ]
        if any(x in self.current_task.lower() for x in skip_tasks):
            self.current_task = None
            return

        # Show phase headers [X/Y] immediately (only from CLI, not Ansible tasks)
        # These are injected by up.py/down.py/orchestrator.py as debug tasks
        import re

        phase_pattern = r"^\[(\d+)/(\d+)\]\s+(.+)$"
        phase_match = re.match(phase_pattern, self.current_task)
        if phase_match:
            # Display as orange arrow + normal text (main phase header)
            self._display.display(f"\033[38;5;214m▶\033[0m {self.current_task}")
            self.current_task = None  # Skip normal processing
            return

        # Show addon deployment header immediately (don't wait for ok)
        if "▶ Deploy" in self.current_task and "addon" in self.current_task:
            # Extract addon name: "▶ Deploy rabbitmq addon" -> "rabbitmq"
            addon_name = (
                self.current_task.replace("▶ Deploy", "").replace("addon", "").strip()
            )
            # Display as: ▶ Addon: caddy (▶ orange, Addon: normal, caddy orange bold)
            self._display.display(
                f"├── \033[38;5;214m▶\033[0m Addon: \033[1m\033[38;5;214m{addon_name}\033[0m"
            )
            self.current_task = None  # Skip normal processing
            return

        # Track start time
        if self.current_task not in self.task_status:
            self.task_status[self.current_task] = "running"
            self.task_start_time[self.current_task] = time.time()

    def v2_runner_on_ok(self, result):
        """Called when a task succeeds"""
        import time

        if not self.current_task or self.current_task not in self.task_status:
            return

        # Dedupe: only show each task once (called once per host)
        if self.current_task in self.shown_tasks:
            return
        self.shown_tasks.add(self.current_task)

        # Only update if not already completed
        if self.task_status[self.current_task] == "running":
            self.task_status[self.current_task] = "ok"

            # Calculate elapsed time
            elapsed = time.time() - self.task_start_time.get(
                self.current_task, time.time()
            )
            self.play_task_times.append(elapsed)
            duration_str = self._format_duration(elapsed)

            # Show checkmark (green) with time (cyan) in parentheses
            # Use │   for nested items (role tasks), ├── for top-level
            is_role_task = self.current_task in self.task_roles
            prefix = "│   " if is_role_task else "├── "
            self._display.display(
                f"{prefix}\033[32m✓\033[0m \033[2m{self.current_task}\033[0m \033[2m\033[36m({duration_str})\033[0m"
            )

    def v2_runner_on_failed(self, result, ignore_errors=False):
        """Called when a task fails"""
        import time

        if not self.current_task or self.current_task not in self.task_status:
            return

        # Dedupe: only show each task once
        if self.current_task in self.shown_tasks:
            return
        self.shown_tasks.add(self.current_task)

        if self.task_status[self.current_task] == "running":
            self.task_status[self.current_task] = "failed"

            # Calculate elapsed time
            elapsed = time.time() - self.task_start_time.get(
                self.current_task, time.time()
            )
            duration_str = self._format_duration(elapsed)

            # Show X (red) with time in parentheses
            # Use │   for nested items (role tasks), ├── for top-level
            is_role_task = self.current_task in self.task_roles
            prefix = "│   " if is_role_task else "├── "
            self._display.display(
                f"{prefix}\033[31m✗\033[0m \033[2m{self.current_task}\033[0m \033[2m\033[36m({duration_str})\033[0m"
            )

            # Show error message
            if "msg" in result._result:
                self._display.display(
                    f"│   \033[31mError: {result._result['msg']}\033[0m"
                )

    def v2_runner_on_skipped(self, result):
        """Called when a task is skipped"""
        if not self.current_task or self.current_task not in self.task_status:
            return

        # Dedupe: only show each task once
        if self.current_task in self.shown_tasks:
            return
        self.shown_tasks.add(self.current_task)

        if self.task_status[self.current_task] == "running":
            self.task_status[self.current_task] = "skipped"
            # Show skip (dark orange) - no time for skipped tasks
            # Use │   for nested items (role tasks), ├── for top-level
            is_role_task = self.current_task in self.task_roles
            prefix = "│   " if is_role_task else "├── "
            self._display.display(
                f"{prefix}\033[38;5;208m⊘\033[0m \033[2m{self.current_task}\033[0m"
            )

    def v2_runner_retry(self, result):
        """Called when a task is retrying"""
        if not self.current_task:
            return

        # Get host name
        hostname = result._host.get_name()

        # Get retry info
        retries = result._result.get("retries", 0)
        attempts = result._result.get("attempts", 1)

        # Calculate remaining attempts
        retries_left = retries - attempts + 1 if retries and attempts else "?"

        # Show retry as dim indented sub-item (no checkmark, just arrow) with hostname
        self._display.display(
            f"│   \033[2m\033[38;5;214m↻\033[0m \033[2m{hostname}: Retrying (attempt {attempts}/{retries})...\033[0m"
        )

    def v2_playbook_on_stats(self, stats):
        """Called at the end"""
        self._display.display("\n└── Summary:")

        hosts = sorted(stats.processed.keys())
        for host in hosts:
            s = stats.summarize(host)
            color = "\033[32m" if s["failures"] == 0 else "\033[31m"
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
