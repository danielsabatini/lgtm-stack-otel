#!/bin/sh
# =============================================================================
# otel-agent — monta a lista de configs do Collector
# =============================================================================
# config.yaml (coleta local do servidor da stack) + pull-semconv.yaml
# (processors que convertem as coletas pull para a OTel Semantic Conventions)
# + cada pull.d/*.yaml (coletas pull de servidores legados, ex.: node_exporter).
# O Collector mescla os arquivos: cada pull define seus receivers e pipelines e
# reutiliza o exportador otlp_grpc/gateway e os processors de conversão.
# =============================================================================
set -e

set -- --config=/etc/otelcol-contrib/config.yaml --config=/etc/otelcol-contrib/pull-semconv.yaml "$@"
for f in /etc/otelcol-contrib/pull.d/*.yaml; do
  [ -e "$f" ] || continue
  echo "otel-agent: carregando coleta pull $f" >&2
  set -- "$@" --config="$f"
done

exec /otelcol-contrib "$@"
