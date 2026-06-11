"""Logging and deduplication utilities.

Every pipeline action is recorded in the DB so we can prevent duplicate sends
and provide a full audit trail.
"""

from db import (
    already_contacted,
    get_action_logs as get_logs,
    print_log_summary as print_summary,
    write_action_log as write_log,
)
