#!/bin/bash
FILE="grafana/provisioning/dashboards/Host/docker-container-self.json"
TMP="docker.tmp.json"

PANEL='{
  "type": "logs",
  "title": "Container Logs (stdout/stderr)",
  "gridPos": { "x": 0, "y": 100, "w": 24, "h": 10 },
  "datasource": { "uid": "loki", "type": "loki" },
  "targets": [
    {
      "expr": "{job=\"docker/containers\", instance=\"$instance\", name=~\"$container\"}",
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
