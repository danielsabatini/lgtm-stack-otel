#!/bin/bash
FILE="grafana/provisioning/dashboards/Host/node-exporter-self.json"
TMP="node.tmp.json"

PANEL='{
  "type": "logs",
  "title": "Systemd Journal (Host Logs)",
  "gridPos": { "x": 0, "y": 100, "w": 24, "h": 10 },
  "datasource": { "uid": "loki", "type": "loki" },
  "targets": [
    {
      "expr": "{job=\"system/journal\", instance=\"$instance\"}",
      "refId": "A"
    }
  ],
  "options": {
    "showTime": true,
    "showLabels": false,
    "showCommonLabels": false,
    "wrapLogMessage": true,
    "sortOrder": "Descending"
  }
}'

jq --argjson panel "$PANEL" '.panels += [$panel]' $FILE > $TMP && mv $TMP $FILE
