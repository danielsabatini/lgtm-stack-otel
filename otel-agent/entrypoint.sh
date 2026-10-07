#!/bin/sh
# =============================================================================
# otel-agent — monta a lista de configs do Collector
# =============================================================================
# config.yaml (coleta local do servidor da stack) + cada pull.d/*.yaml (coletas
# pull de servidores legados, ex.: node_exporter). O Collector mescla os
# arquivos: cada pull define seus próprios receivers/processors/pipelines e
# reutiliza o exportador otlp_grpc/gateway do config.yaml.
# =============================================================================
set -e

set -- --config=/etc/otelcol-contrib/config.yaml "$@"
for f in /etc/otelcol-contrib/pull.d/*.yaml; do
  [ -e "$f" ] || continue
  echo "otel-agent: carregando coleta pull $f" >&2
  set -- "$@" --config="$f"
done

exec /otelcol-contrib "$@"
