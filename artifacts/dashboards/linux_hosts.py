"""Linux Hosts (agente OpenTelemetry: host_metrics system.*, journald, OBI)."""
import sys
from lib import Dash
from hosts import host_var, host_tabs, logs_tab, app_row

OUT = sys.argv[1]
d = Dash("linux-hosts", "Linux Hosts", ["linux", "host", "opentelemetry"])
P = d.prom
host_var(d, "linux", exclude_dedicated=True)
d.text_var("trace_id")
tabs = host_tabs(d, "linux")

d.row("Linux", tabs + [logs_tab(d, "linux")])
app_row(d, "linux-hosts")
d.save(OUT)
