#!/usr/bin/env bash
# =============================================================================
# volumes-init.sh — Prepara os diretórios de dados da LGTM Stack
#
# Uso:
#   sudo bash scripts/volumes-init.sh
#
# Cria a estrutura de diretórios abaixo no disco local (dev) ou nos pontos
# de montagem LVM já existentes (prod) — a estrutura é idêntica em ambos:
#
#   /lgtm/apps/grafana       → Grafana
#   /lgtm/apps/alloy-gateway → Alloy Gateway (WAL)
#   /lgtm/apps/alloy-agent   → Alloy Agent (WAL)
#   /lgtm/loki               → Loki (logs)
#   /lgtm/mimir              → Mimir (métricas)
#   /lgtm/tempo              → Tempo (traces)
#
# Em dev: diretórios criados no disco root.
# Em prod: execute após montar os LVM em /lgtm/* (ver INFRASTRUCTURE.md).
#          O script apenas corrige permissões — não apaga dados existentes.
#
# Após este script: docker compose up -d
# Para reset completo: docker compose down -v && sudo bash scripts/volumes-reset.sh
# =============================================================================

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Execute com sudo: sudo bash scripts/volumes-init.sh"
  exit 1
fi

echo "==> Criando estrutura de diretórios..."

# Apps (Grafana + Alloy)
mkdir -p \
  /lgtm/apps/grafana \
  /lgtm/apps/alloy-gateway \
  /lgtm/apps/alloy-agent

# Backends
mkdir -p /lgtm/loki
mkdir -p /lgtm/tempo

# Mimir — subdiretórios obrigatórios (imagem distroless não tem mkdir)
mkdir -p \
  /lgtm/mimir/storage \
  /lgtm/mimir/tsdb \
  /lgtm/mimir/tsdb-sync \
  /lgtm/mimir/compactor \
  /lgtm/mimir/ruler \
  /lgtm/mimir/ruler-temp

echo "    [ok] /lgtm/apps/grafana, alloy-gateway, alloy-agent"
echo "    [ok] /lgtm/loki, /lgtm/mimir, /lgtm/tempo"

echo ""
echo "==> Corrigindo permissões..."

# Grafana — UID 472, GID 0 (Dockerfile oficial grafana/grafana)
chown -R 472:0 /lgtm/apps/grafana
echo "    [ok] /lgtm/apps/grafana → 472:0"

# Mimir, Loki, Tempo — UID 10001:10001 (imagens distroless grafana/*)
chown -R 10001:10001 /lgtm/mimir /lgtm/loki /lgtm/tempo
echo "    [ok] /lgtm/mimir, /lgtm/loki, /lgtm/tempo → 10001:10001"

# Alloy — roda como root, sem chown necessário
echo "    [ok] /lgtm/apps/alloy-* → root (sem alteração)"

echo ""
echo "==> Pronto. Execute: docker compose up -d"
