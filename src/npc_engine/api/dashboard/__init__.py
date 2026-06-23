"""
Package: dashboard
Layer: api
Purpose: Designer dashboard models and static asset registration.
Public surface: DashboardConfigView, register_dashboard, DASHBOARD_MOUNT_PATH.
Does NOT: define routes or middleware.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .dashboard_models import DashboardConfigView
from .dashboard_static import DASHBOARD_MOUNT_PATH, register_dashboard

__all__ = [
    "DashboardConfigView",
    "register_dashboard",
    "DASHBOARD_MOUNT_PATH",
]
