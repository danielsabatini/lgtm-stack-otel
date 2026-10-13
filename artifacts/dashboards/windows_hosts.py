"""Windows Hosts (agente OpenTelemetry: host_metrics system.*, Event Log)."""
import sys
from lib import Dash
from hosts import host_var, host_tabs, logs_tab

OUT = sys.argv[1]
d = Dash("windows-hosts", "Windows Hosts", ["windows", "host", "opentelemetry"])
host_var(d, "windows", exclude_dedicated=True)
d.row("Windows", host_tabs(d, "windows") + [logs_tab(d, "windows")])
d.save(OUT)
