#!/usr/bin/env bash
# =============================================================================
# volumes-reset.sh — Apaga todos os dados da LGTM Stack
#
# Uso:
#   docker compose down -v
#   sudo bash scripts/volumes-reset.sh
#
# ATENÇÃO: operação irreversível. Apaga todos os dados de métricas, logs,
# traces, dashboards e configurações do Grafana armazenados em /lgtm/*.
#
# Em prod com LVM, os discos físicos são preservados — apenas o conteúdo
# dos diretórios é removido. Os pontos de montagem continuam intactos.
# =============================================================================

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Execute com sudo: sudo bash scripts/volumes-reset.sh"
  exit 1
fi

echo "ATENÇÃO: este script apaga todos os dados em /lgtm/*"
read -r -p "Confirmar? (yes/N): " confirm
if [[ "$confirm" != "yes" ]]; then
  echo "Cancelado."
  exit 0
fi

echo ""
echo "==> Limpando dados..."

# Apaga conteúdo mantendo os pontos de montagem intactos
for dir in \
  /lgtm/apps/grafana \
  /lgtm/apps/alloy-gateway \
  /lgtm/apps/alloy-agent \
  /lgtm/loki \
  /lgtm/mimir \
  /lgtm/tempo; do
  if [[ -d "$dir" ]]; then
    rm -rf "${dir:?}/"*
    echo "    [ok] $dir limpo"
  else
    echo "    [skip] $dir não existe"
  fi
done

echo ""
echo "==> Reinicializando permissões e subdiretórios..."
bash "$(dirname "$0")/volumes-init.sh"
