#!/bin/bash
# =============================================================================
# LGTM Stack - Script de Backup com Rotação
# Mantém os últimos 7 backups locais.
# =============================================================================

set -e

# Configurações
STACK_DIR="/home/debian/code/lgtm-stack" # AJUSTE ESTE CAMINHO
BACKUP_DIR="${STACK_DIR}/backup"
DATE=$(date +%Y%m%d_%H%M)
RETENTION_DAYS=7

# Lista de volumes para backup
VOLUMES=(
  "lgtm-stack-otel_grafana-data"
  "lgtm-stack-otel_loki-data"
  "lgtm-stack-otel_mimir-data"
  "lgtm-stack-otel_tempo-data"
)

echo "--- Iniciando Backup LGTM Stack: ${DATE} ---"

# Criar pasta de backup se não existir
mkdir -p "${BACKUP_DIR}"

cd "${STACK_DIR}"

# 1. Parada segura da stack
echo "1. Parando containers para garantir consistência..."
docker compose down
sync

# 2. Executar backup de cada volume
echo "2. Comprimindo volumes..."
for vol in "${VOLUMES[@]}"; do
  FILENAME="${BACKUP_DIR}/${vol}-${DATE}.tar.gz"
  echo "   - Backup de ${vol}..."
  docker run --rm \
    -v "${vol}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    busybox tar czf "/backup/$(basename "${FILENAME}")" -C /data .
done

# Coletas pull (otel-agent/pull.d/*.yaml): não versionadas, contêm os alvos do ambiente
if compgen -G "otel-agent/pull.d/*.yaml" > /dev/null; then
  echo "   - Backup de otel-agent/pull.d..."
  tar czf "${BACKUP_DIR}/otel-agent-pull.d-${DATE}.tar.gz" otel-agent/pull.d/*.yaml
fi

# 3. Subir a stack novamente
echo "3. Reiniciando stack..."
docker compose up -d

# 4. Rotação (Limpeza de arquivos antigos)
echo "4. Limpando backups com mais de ${RETENTION_DAYS} dias..."
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +${RETENTION_DAYS} -exec rm -f {} \;

echo "--- Backup concluído com sucesso! ---"
