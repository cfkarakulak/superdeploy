"""
Ansible Tree Output Renderer

Parses Ansible output and renders clean tree view with:
- ASCII box drawing tree structure (└──, ├──, │)
- Task filtering
- ANSI color codes
- Real-time streaming
"""

import re
from typing import List, Optional


class AnsibleTreeRenderer:
    """Parse Ansible output and render as ASCII tree with colors."""

    def __init__(self, console=None):
        self.current_play: Optional[str] = None
        self.current_sub_play: Optional[str] = None  # For ▶ prefixed tasks
        self.current_tasks: List[str] = []
        self.indent_level = 0
        self.last_task_time = ""
        self.play_count = 0
        self.task_printed = set()  # Track printed tasks by name
        self.pending_task = None  # Task waiting to see if it's skipped
        self.pending_task_status = None
        self.pending_task_time = ""
        self.json_buffer = []  # Buffer for multi-line JSON output
        self.task_start_time = None  # Track when current task started (time.time())
        self.last_line_timestamp = None  # Not used for stdout (only for log parsing)

        # Sub-play context tracking for indented subtasks
        self.in_subplay_context = False
        self.subplay_tasks: List[str] = []  # Track subtasks under current sub-play

        # Track task execution counts for deduplication
        self.task_count = {}  # task_name -> count
        self.task_times = {}  # task_name -> list of times
        self.current_task_name = None  # Track current executing task

        # Track play execution counts for deduplication
        self.play_printed = set()  # Track which plays have been printed
        self.play_execution_count = {}  # play_name -> count of executions
        self.last_printed_play = None  # Track last printed play for updates

        # ANSI color codes (matching old style)
        self.COLOR_ORANGE = "\033[38;5;214m"
        self.COLOR_GREEN = "\033[32m"
        self.COLOR_CYAN = "\033[36m"
        self.COLOR_WHITE = "\033[37m"
        self.COLOR_GRAY = "\033[2m"
        self.COLOR_DIM_CYAN = "\033[2;36m"  # Dim cyan for timing
        self.COLOR_SKIPPED = (
            "\033[2;38;5;183m"  # Dim light purple/pink for skipped tasks
        )
        self.COLOR_RESET = "\033[0m"

        # Patterns to hide
        self.hidden_patterns = [
            r"Set instance paths",
            r"Display instance deployment info",
            r"Check if addon type exists",
            r"Fail if addon type does not exist",
            r"Load addon metadata",
            r"Fail if addon\.yml",
            r"Get addon instance credentials",
            r"Validate instance credentials",
            r"Set instance-specific environment",
            r"Add common instance variables",
            r"Get resource limits",
            r"Add resource variables",
            r"Generate \.env file",
            r"Check if addon has templates",
            r"Set addon has templates",
            r"Check if addon has compose",
            r"Set metadata variables",
            r"Flatten environment variables",
            r"Find additional templates",
            r"Check if addon has ansible\.yml",
            r"Deploy addon instance tasks",
            r"Gathering Facts",
            r"Validate required variables",
            r"Set default values",
            r"Parse vm_apps",
            r"Filter apps for this VM",
            r"Set empty apps",
            r"Display project deployment",
            r"Display directory structure",
            r"Copy config\.yml",
            r"Generate docker-compose",
        ]

    def should_show_task(self, task_name: str) -> bool:
        """Check if task should be displayed."""
        if not task_name or not task_name.strip():
            return False

        # Always show ▶ tasks (sub-plays) and info tasks
        if "▶" in task_name:
            return True

        # Hide matching patterns
        for pattern in self.hidden_patterns:
            if re.search(pattern, task_name, re.IGNORECASE):
                return False

        return True

    def _clean_task_name(self, task_name: str) -> str:
        """Clean task name from unwanted prefixes and emojis."""
        # Remove ANY "role/subrole :" or "namespace/role :" prefix
        # Matches: orchestration/xxx :, system/base :, system/docker :, etc.
        task_name = re.sub(r"^[\w-]+/[\w-]+\s*:\s*", "", task_name)

        # Remove non-play emojis from info lines (keep ▶)
        task_name = re.sub(r"[🗄️🐰🌐✅🔥]", "", task_name)

        # Remove ALL checkmarks from text (including start - status icon will be added separately)
        task_name = re.sub(r"✓\s*", "", task_name)

        # Remove skipped emoji from text (status icon will be added separately)
        task_name = re.sub(r"⊘\s*", "", task_name)

        return task_name.strip()

    def _calculate_elapsed_time(self, start_time: float) -> str:
        """Calculate elapsed time from start_time to now and format it."""
        import time

        elapsed = int(time.time() - start_time)

        if elapsed >= 60:
            minutes = elapsed // 60
            seconds = elapsed % 60
            return f"{minutes}m {seconds:02d}s"
        elif elapsed > 0:
            return f"{elapsed}s"
        else:
            return "1s"  # Show minimum 1s for very fast tasks

    def process_line(self, line: str) -> None:
        """Process a single line of Ansible output."""
        import time

        line = line.rstrip()

        if not line:
            return

        # Check for skipped in JSON buffer (multi-line detection)
        if self.pending_task and (
            '"skipped": true' in line or "'skipped': True" in line
        ):
            # This pending task is actually skipped!
            self.pending_task_status = "⊘"

        # Detect PLAY headers
        if line.startswith("PLAY ["):
            # Flush any pending task before new play
            self._flush_pending_task()

            # Exit sub-play context when new play starts
            if self.in_subplay_context:
                self.in_subplay_context = False
                self.subplay_tasks = []

            play_name = re.sub(r"PLAY \[(.*?)\].*", r"\1", line)
            if play_name and play_name.strip():
                # Track play execution count
                if play_name not in self.play_execution_count:
                    self.play_execution_count[play_name] = 0
                self.play_execution_count[play_name] += 1

                # Hide "Deploy Addon Instance" play (addons shown as sub-plays)
                if play_name != "Deploy Addon Instance":
                    # Only print play once (first time)
                    if play_name not in self.play_printed:
                        self._print_play(play_name)
                        self.play_printed.add(play_name)
                self.current_play = play_name
                self.current_tasks = []
                self.indent_level = 0
            return

        # Detect TASK headers
        if line.startswith("TASK ["):
            # Flush any pending task before new task
            self._flush_pending_task()

            task_name = re.sub(r"TASK \[(.*?)\].*", r"\1", line)
            task_name = self._clean_task_name(task_name)

            # Store current task name for count tracking
            self.current_task_name = task_name

            # Save task start time for timing calculation (use time.time())
            self.task_start_time = time.time()

            # Check if this is a sub-play (▶ prefixed task)
            if "▶" in task_name and not task_name.startswith("▶ Deploy"):
                # This is an addon deployment header - treat as sub-play
                self._print_sub_play(task_name)
                self.current_sub_play = task_name
                self.task_printed.add(task_name)
                # Enter sub-play context for indented subtasks
                self.in_subplay_context = True
                self.subplay_tasks = []
            elif self.should_show_task(task_name):
                self.current_tasks.append(task_name)
            return

        # Detect task results with timing
        # Format: "ok: [hostname]", "skipping: [hostname]", "skipped: [hostname]"
        result_match = re.match(r"^(ok|changed|failed|skipping|skipped):\s+\[", line)
        if result_match:
            result_type = result_match.group(1)

            # Check if line contains "skipped": true (for conditional skips)
            # Ansible sometimes reports: ok: [host] => { "skipped": true, "changed": false }
            is_skipped = '"skipped": true' in line or "'skipped': True" in line

            # Calculate timing using internal timer
            if self.task_start_time:
                elapsed_time = self._calculate_elapsed_time(self.task_start_time)
                self.last_task_time = elapsed_time if elapsed_time else ""
            else:
                # Fallback: try to extract timing if present in line
                # Formats: (1s), (10s), (1m 00s), (2m 30s)
                timing_match = re.search(r"\((?:(\d+)m\s+)?(\d+)s\)", line)
                if timing_match:
                    minutes = timing_match.group(1)
                    seconds = timing_match.group(2)
                    if minutes:
                        self.last_task_time = f"{minutes}m {seconds}s"
                    else:
                        self.last_task_time = f"{seconds}s"
                else:
                    self.last_task_time = ""

            # Flush previous pending task (if any) before handling new result
            self._flush_pending_task()

            # Increment task count for this execution
            if self.current_task_name:
                if self.current_task_name not in self.task_count:
                    self.task_count[self.current_task_name] = 0
                    self.task_times[self.current_task_name] = []
                self.task_count[self.current_task_name] += 1
                if self.last_task_time:
                    self.task_times[self.current_task_name].append(self.last_task_time)

            # Handle task result
            # Check both result_type AND is_skipped flag
            if result_type in ["skipping", "skipped"] or is_skipped:
                # This is a skipped task - mark immediately (no need to wait for next lines)
                if self.current_tasks:
                    task = self.current_tasks[0]
                    if task not in self.task_printed:
                        # Skipped tasks rarely have timing, but if they do, show it
                        self._print_task(task, status="⊘", time=self.last_task_time)
                        self.task_printed.add(task)
                        self.current_tasks.pop(0)
                        self.last_task_time = ""
            elif result_type in ["ok", "changed"]:
                # This might be successful OR conditionally skipped
                # Hold it as pending to check next lines for "skipped": true
                if self.current_tasks:
                    task = self.current_tasks[0]
                    if task not in self.task_printed:
                        self.pending_task = task
                        self.pending_task_status = "✓"
                        self.pending_task_time = self.last_task_time
                        self.last_task_time = ""
                        self.current_tasks.pop(0)

    def _flush_pending_task(self) -> None:
        """Flush any pending task (print it now)."""
        if self.pending_task:
            self._print_task(
                self.pending_task,
                status=self.pending_task_status,
                time=self.pending_task_time,
            )
            self.task_printed.add(self.pending_task)
            self.pending_task = None
            self.pending_task_status = None
            self.pending_task_time = ""

    def _print_play(self, play_name: str) -> None:
        """Print play header with tree connector."""
        # Note: Count will be updated in finalize() if needed
        # For now, just print the play name (first occurrence only)

        # Always use └── for plays (root level of tree)
        connector = "└──"
        icon = f"{self.COLOR_ORANGE}▶{self.COLOR_RESET}"
        print(f"{connector} {icon} {play_name}", flush=True)
        self.play_count += 1
        self.current_sub_play = None  # Reset sub-play

    def _print_sub_play(self, sub_play_name: str) -> None:
        """Print sub-play header (addon deployment) at root level."""
        # Format addon name properly
        if "databases.primary" in sub_play_name:
            formatted = "Addon: PostgreSQL (databases.primary)"
        elif "queues.main" in sub_play_name:
            formatted = "Addon: RabbitMQ (queues.main)"
        elif "proxy.main" in sub_play_name:
            formatted = "Addon: Caddy (proxy.main)"
        else:
            # Generic format
            formatted = sub_play_name.replace("▶", "Addon:").strip()

        # Print at root level
        connector = "└──"
        icon = f"{self.COLOR_ORANGE}▶{self.COLOR_RESET}"
        print(f"{connector} {icon} {formatted}", flush=True)

    def _print_task(self, task_name: str, status: str = "✓", time: str = "") -> None:
        """Print task with tree structure and colors."""
        # Skip if already printed as sub-play
        if task_name in self.task_printed and "▶" in task_name:
            return

        # Determine colors based on status
        if status == "✓":
            status_colored = f"{self.COLOR_GREEN}{status}{self.COLOR_RESET}"
        elif status == "⊘":
            status_colored = f"{self.COLOR_SKIPPED}{status}{self.COLOR_RESET}"
        elif status == "▶":
            status_colored = f"{self.COLOR_ORANGE}{status}{self.COLOR_RESET}"
        else:
            status_colored = status

        # Get task execution count and build count string
        count = self.task_count.get(task_name, 1)
        count_str = f" - {count}x" if count > 1 else ""

        # Build timing string (dim cyan color for timing)
        # Use the last recorded time, or average if multiple
        if time:
            timing_str = f" {self.COLOR_DIM_CYAN}({time}){self.COLOR_RESET}"
        elif task_name in self.task_times and self.task_times[task_name]:
            # Use the last time recorded
            last_time = self.task_times[task_name][-1]
            timing_str = f" {self.COLOR_DIM_CYAN}({last_time}){self.COLOR_RESET}"
        else:
            timing_str = ""

        # Build tree structure - no indentation, all tasks at same level
        indent = ""

        # Track subtasks if in subplay context
        if self.in_subplay_context:
            self.subplay_tasks.append(task_name)

        # Always use ├── connector (└── will be used for last subtask on finalize)
        connector = "├──"

        # Print with proper formatting (task name in dim/gray)
        print(
            f"{connector} {status_colored} {self.COLOR_GRAY}{task_name}{count_str}{self.COLOR_RESET}{timing_str}",
            flush=True,
        )

    def add_summary_task(self, message: str, substatus: str = "") -> None:
        """
        Add a final summary task to the tree (after all Ansible tasks complete).

        Args:
            message: Main summary message (e.g., "Services configured")
            substatus: Optional sub-message (e.g., "Services configured successfully")
        """
        # Print main message as a play (with ▶ icon)
        icon = f"{self.COLOR_ORANGE}▶{self.COLOR_RESET}"
        print(
            f"└── {icon} {message}",
            flush=True,
        )

        # If substatus provided, print it as a normal task (no indent)
        if substatus:
            status_colored = f"{self.COLOR_GREEN}✓{self.COLOR_RESET}"
            print(
                f"└── {status_colored} {self.COLOR_GRAY}{substatus}{self.COLOR_RESET}",
                flush=True,
            )

    def finalize(self) -> None:
        """Finalize rendering (flush any remaining tasks)."""
        # Flush any pending task first
        self._flush_pending_task()

        # Print any remaining tasks
        for task in self.current_tasks:
            self._print_task(task, status="✓", time="")
        self.current_tasks = []
