"""Construtores de dashboards Grafana 13 (dashboard.grafana.app/v2) no padrão do repositório."""
import json

GV = "13.2.3"


class Dash:
    def __init__(self, uid, title, tags):
        self.uid, self.title, self.tags = uid, title, tags
        self.elements, self.n = {}, 0
        self.variables, self.rows = [], []

    # ----------------------------------------------------------------- queries
    @staticmethod
    def prom(expr, legend="", exemplar=False, instant=False):
        s = {"editorMode": "code", "expr": expr, "legendFormat": legend, "range": not instant}
        if instant:
            s["instant"] = True
        if exemplar:
            s["exemplar"] = True
        return ("prometheus", "mimir", s)

    @staticmethod
    def loki(expr):
        return ("loki", "loki", {"direction": "backward", "editorMode": "code", "expr": expr, "queryType": "range"})

    @staticmethod
    def tempo(query, limit=20):
        return ("tempo", "tempo", {"limit": limit, "query": query, "queryType": "traceql", "tableType": "traces"})

    # ------------------------------------------------------------------ panels
    def _panel(self, title, desc, queries, group, options, defaults, overrides=None, interval="30s"):
        self.n += 1
        qs = []
        for i, (g, ds, spec) in enumerate(queries):
            qs.append({"kind": "PanelQuery", "spec": {
                "query": {"kind": "DataQuery", "group": g, "version": "v0", "datasource": {"name": ds}, "spec": spec},
                "refId": chr(65 + i), "hidden": False}})
        name = f"panel-{self.n}"
        self.elements[name] = {"kind": "Panel", "spec": {
            "id": self.n, "title": title, "description": desc, "links": [],
            "data": {"kind": "QueryGroup", "spec": {"queries": qs, "transformations": [],
                                                      "queryOptions": {"interval": interval} if interval else {}}},
            "vizConfig": {"kind": "VizConfig", "group": group, "version": GV, "spec": {
                "options": options, "fieldConfig": {"defaults": defaults, "overrides": overrides or []}}}}}
        return name

    def gauge(self, title, desc, q, unit="percentunit", steps=(70, 80, 90), mx=1, thresholds=None):
        """thresholds: lista explícita [(valor, cor), ...] (ex.: invertidos, baixo = ruim)."""
        return self._panel(title, desc, [q], "gauge", {
            "minVizHeight": 75, "minVizWidth": 75, "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showThresholdLabels": False, "showThresholdMarkers": True, "sizing": "auto",
            "sparkline": True, "textMode": "auto"},
            {"unit": unit, "decimals": 1, "min": 0, **({"max": mx} if mx is not None else {}),
             "thresholds": {"mode": "absolute" if thresholds or mx is None else "percentage", "steps":
                            [{"value": v, "color": c} for v, c in thresholds] if thresholds else
                            [{"value": 0, "color": "green"}] + [{"value": v, "color": c} for v, c in
                                                                 zip(steps, ("yellow", "orange", "red"))]},
             "color": {"mode": "thresholds"}})

    def stat(self, title, desc, q, unit=None, text=False, decimals=None, thresholds=None, names=False,
             updown=False):
        """names: mostra valor e nome da série (vários valores, ex.: uma por instância)."""
        opts = {"colorMode": "value", "graphMode": "none", "justifyMode": "center", "orientation": "auto",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showPercentChange": False, "textMode": "name" if text else "value_and_name" if names else "value",
                "wideLayout": True}
        if names:
            opts["text"] = {"titleSize": 12, "valueSize": 28}
        if text:
            opts["text"] = {"valueSize": 16}
        d = {"thresholds": {"mode": "absolute", "steps": [{"value": v, "color": c} for v, c in
                                                          (thresholds or [(0, "text")])]},
             "color": {"mode": "thresholds"}}
        if unit:
            d["unit"] = unit
        if decimals is not None:
            d["decimals"] = decimals
        if updown:
            d["mappings"] = [{"type": "value", "options": {
                "0": {"text": "DOWN", "color": "red", "index": 0},
                "1": {"text": "UP", "color": "green", "index": 1}}}]
        return self._panel(title, desc, [q], "stat", opts, d)

    def ts(self, title, desc, queries, unit=None, stack=False, mx=None, decimals=2, limit_regex=".*Limite.*",
           draw="line", threshold_line=None):
        """threshold_line: (valor, cor) desenhado como linha tracejada de referência."""
        d = {"decimals": decimals, "min": 0,
             "thresholds": {"mode": "absolute", "steps": [{"value": 0, "color": "green"}]},
             "color": {"mode": "palette-classic"},
             "custom": {"drawStyle": draw, "fillOpacity": 25 if stack else 10, "lineInterpolation": "smooth",
                        "lineWidth": 2, "showPoints": "never", "spanNulls": False,
                        "stacking": {"group": "A", "mode": "normal" if stack else "none"},
                        "axisPlacement": "auto", "gradientMode": "none", "thresholdsStyle": {"mode": "off"}}}
        if unit:
            d["unit"] = unit
        if mx is not None:
            d["max"] = mx
        if threshold_line:
            d["thresholds"] = {"mode": "absolute", "steps": [{"value": 0, "color": "transparent"},
                                                             {"value": threshold_line[0], "color": threshold_line[1]}]}
            d["custom"]["thresholdsStyle"] = {"mode": "dashed"}
        ov = [{"matcher": {"id": "byRegexp", "options": limit_regex}, "properties": [
            {"id": "custom.lineStyle", "value": {"dash": [10, 10], "fill": "dash"}},
            {"id": "custom.fillOpacity", "value": 0},
            {"id": "custom.stacking", "value": {"group": "A", "mode": "none"}},
            {"id": "color", "value": {"fixedColor": "dark-red", "mode": "fixed"}}]}]
        return self._panel(title, desc, queries, "timeseries", {
            "legend": {"calcs": ["lastNotNull", "max"], "displayMode": "table", "placement": "bottom",
                       "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"}}, d, ov)

    def logs(self, title, desc, expr):
        return self._panel(title, desc, [self.loki(expr)], "logs", {
            "dedupStrategy": "none", "enableLogDetails": True, "prettifyLogMessage": True,
            "showCommonLabels": False, "showLabels": False, "showTime": True, "sortOrder": "Descending",
            "wrapLogMessage": True, "enableInfiniteScrolling": False}, {})

    def trace_table(self, title, desc, query, link):
        ov = [{"matcher": {"id": "byName", "options": "Trace ID"}, "properties": [
            {"id": "links", "value": [{"title": "Ver waterfall neste dashboard", "url": link}]}]}]
        return self._panel(title, desc, [self.tempo(query)], "table", {
            "cellHeight": "sm", "enablePagination": True, "showHeader": True},
            {"custom": {"align": "auto", "filterable": True}}, ov)

    def trace_view(self, title, desc):
        return self._panel(title, desc, [self.tempo("$trace_id")], "traces", {}, {}, interval=None)

    # ------------------------------------------------------------------ layout
    def row(self, title, tabs, show_if=None):
        """tabs: lista de (título, [panels], maxColumnCount).
        show_if: nome de uma variável de modelo (model_var); a linha só aparece quando
        o host selecionado tem dados daquele modelo (ex.: agente x pull)."""
        self.rows.append((title, tabs, show_if))

    def model_var(self, name, metric_selector):
        """Variável oculta: número de séries do seletor com dados em QUALQUER ponto do
        período selecionado (last_over_time em $__range; vazia se não há). Usada por
        row(show_if=...) para exibir uma linha só quando o host tem aqueles dados."""
        q = "query_result(count(last_over_time(%s[$__range])))" % metric_selector
        self.variables.append({"kind": "QueryVariable", "spec": {
            "name": name, "hide": "hideVariable", "refresh": "onTimeRangeChanged", "skipUrlSync": True,
            "current": {"text": "", "value": ""},
            "query": {"kind": "DataQuery", "group": "prometheus", "version": "v0", "datasource": {"name": "mimir"},
                      "spec": {"qryType": 3, "query": q, "refId": "PrometheusVariableQueryEditor-VariableQuery"}},
            "definition": q, "regex": "/^\\{\\}\\s+([0-9]+)/", "regexApplyTo": "value", "sort": "disabled",
            "options": [], "multi": False, "includeAll": False, "allowCustomValue": False}})

    def query_var(self, name, label, query, regex, multi=False):
        """multi: seleção múltipla com opção All (padrão All)."""
        self.variables.append({"kind": "QueryVariable", "spec": {
            "name": name, "label": label, "hide": "dontHide", "skipUrlSync": False,
            "current": {"text": ["All"], "value": ["$__all"]} if multi else {"text": "", "value": ""},
            "query": {"kind": "DataQuery", "group": "prometheus", "version": "v0", "datasource": {"name": "mimir"},
                      "spec": {"qryType": 3, "query": query, "refId": "PrometheusVariableQueryEditor-VariableQuery"}},
            "definition": query, "regex": regex, "regexApplyTo": "value", "sort": "alphabeticalAsc",
            "refresh": "onTimeRangeChanged" if multi else "onDashboardLoad",
            "options": [], "multi": multi, "includeAll": multi, "allowCustomValue": False}})

    def text_var(self, name):
        self.variables.append({"kind": "TextVariable", "spec": {
            "name": name, "current": {"text": "", "value": ""}, "query": "", "hide": "hideVariable",
            "skipUrlSync": False}})

    def build(self):
        def grid(panels, cols):
            narrow = cols > 1
            return {"kind": "AutoGridLayout", "spec": {
                "maxColumnCount": cols, "columnWidthMode": "narrow" if narrow else "standard",
                "rowHeightMode": "short" if narrow else "standard",
                "items": [{"kind": "AutoGridLayoutItem", "spec": {"element": {"kind": "ElementReference", "name": p}}}
                          for p in panels]}}

        def cond(var):
            return {"kind": "ConditionalRenderingGroup", "spec": {
                "visibility": "show", "condition": "and",
                "items": [{"kind": "ConditionalRenderingVariable",
                           "spec": {"variable": var, "operator": "matches", "value": "^[0-9]+$"}}]}}

        rows = []
        for t, tabs, show_if in self.rows:
            spec = {"title": t, "collapse": False, "layout": {"kind": "TabsLayout", "spec": {"tabs": [
                {"kind": "TabsLayoutTab", "spec": {"title": tt, "layout": grid(ps, c)}} for tt, ps, c in tabs]}}}
            if show_if:
                spec["conditionalRendering"] = cond(show_if)
            rows.append({"kind": "RowsLayoutRow", "spec": spec})
        return {"apiVersion": "dashboard.grafana.app/v2", "kind": "Dashboard", "metadata": {"name": self.uid},
                "spec": {
                    "annotations": [{"kind": "AnnotationQuery", "spec": {
                        "query": {"kind": "DataQuery", "group": "grafana", "version": "v0",
                                  "datasource": {"name": "-- Grafana --"}, "spec": {}},
                        "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts", "builtIn": True}}],
                    "cursorSync": "Crosshair", "editable": True, "elements": self.elements,
                    "layout": {"kind": "RowsLayout", "spec": {"rows": rows}},
                    "links": [], "liveNow": False, "preload": False, "tags": self.tags,
                    "timeSettings": {"timezone": "browser", "from": "now-6h", "to": "now", "autoRefresh": "1m",
                                     "autoRefreshIntervals": ["30s", "1m", "5m", "15m", "30m", "1h"],
                                     "hideTimepicker": False, "fiscalYearStartMonth": 0},
                    "title": self.title, "variables": self.variables, "uid": self.uid}}

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.build(), f, indent=2, ensure_ascii=False)
            f.write("\n")
