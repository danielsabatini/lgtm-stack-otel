# Manual de Upgrades e Lifecycle (Update SRE)

> **Referência Técnica:** Este documento estabelece as regras mandatórias, os passos de validação a seco e os procedimentos de rollback para atualizações de versão seguras na LGTM Stack.

---

## 1. Introdução

A atualização de versões em Bancos de Dados Time-Series (*TSDBs*) como Loki, Mimir e Tempo **não deve ser tratada como a simples atualização de uma aplicação web comum**. A mudança de versões principais (*major releases*) frequentemente altera a estrutura de compactação, esquemas de blocos e índices em disco. Um avanço cego de versão sem validação prévia pode corromper dados históricos de forma irreversível.

---

## 2. Objetivo

1. **Prevenir Corrupção de Dados:** Garantir que atualizações de TSDBs passem por validações sequenciais sem pular versões principais.
2. **Fornecer Checklist Seguro de Atualização:** Descrever o processo passo a passo desde o backup prévio até o teste pós-subida.
3. **Documentar Procedimento de Rollback:** Fornecer os passos imediatos de reversão caso uma nova imagem apresente falha de inicialização.

---

## 3. Regras Críticas de Upgrade

### 🛑 Regra 1: Nunca Pule Major Releases em TSDBs (Loki, Mimir, Tempo)
Se o seu ambiente estiver rodando Loki `2.9.x` e a versão atual for `3.7.x`, **não avance diretamente para a 3.7**. Atualize primeiro sequencialmente para a `3.0`, suba o container para que ele execute as rotinas internas de migração de blocos e esquemas no disco, e só então avance para as versões seguintes.

> **Exceção (Grafana):** O Grafana (`grafana/grafana`) pode saltar major versions com segurança, pois seu banco relacional SQLite possui rotinas automáticas de migração de esquema na inicialização.

### 🛑 Regra 2: Validação Prévia de Esquema (Schema Validation)
Antes de alterar as versões no arquivo `.env`:
1. Consulte as *Release Notes* oficiais do componente procurando por `Breaking Changes`, `schema_config` e `migration`.
2. Se a nova versão exigir alterações no arquivo de configuração (`loki.yaml`, `mimir.yaml`, `tempo.yaml`), edite os arquivos **antes** de atualizar a imagem.

### 🛑 Regra 3: Instalação Sempre Monolítica e Single-Tenant
Loki, Mimir e Tempo rodam **sempre** como monolito (`target: all`, um único processo por backend) e **sem multi-tenancy** (`auth_enabled: false` no Loki, `multitenancy_enabled: false` no Mimir e no Tempo). Essas chaves ficam explícitas no topo de `loki/loki.yaml`, `mimir/mimir.yaml` e `tempo/tempo.yaml` — não remova nem altere ao fazer upgrade, mesmo que o default da nova versão mude. Nenhum cliente precisa enviar o header `X-Scope-OrgID`.

### 3.1 Breaking Changes Conhecidos (bump de 2026-10)

| Componente | De → Para | O que muda | Impacto nesta stack |
|---|---|---|---|
| Mimir | `3.1.4` → `3.2.1` | Query sharding e *remote execution* passam a vir ligados por padrão; flags experimentais de query removidos; UI web do Alertmanager removida (só API v2). | Nenhum: nenhum flag removido é usado. |
| Tempo | `3.0.2` → `3.1.0` | Blocos novos gravados em **vParquet5**; escrita em vParquet3 proibida; mudanças em cache Redis e query-frontend. | Nenhum: blocos vParquet4 existentes continuam legíveis e são compactados normalmente; Redis não é usado. |
| Alloy | `v1.18.0` → `v1.20.1` | v1.19 renomeou as métricas internas do `memory_limiter` e removeu `prometheus.write.queue`; v1.20 alterou componentes de kafka/hetzner/k8sattributes. | Nenhum: nenhum dashboard consulta essas métricas e nenhum desses componentes é usado. |
| Loki / Grafana | `3.7.4` → `3.7.8` / `13.1.2` → `13.2.3` | Apenas correções de segurança. | Nenhum. |

---

## 4. Procedimento de Upgrade Passo a Passo

### 4.1 Parada Estratégica e Backup
```bash
cd /caminho/para/lgtm-stack

# Parar a stack e descarregar a memória para o disco antes do snapshot:
docker compose stop
sync
```

### 4.2 Alteração Paramétrica no `.env`
Edite apenas as variáveis das imagens que deseja atualizar:
```bash
# Exemplo no arquivo .env:
# GRAFANA_LOKI_VERSION=3.7.8
# GRAFANA_MIMIR_VERSION=3.2.1
```

### 4.3 Validação do Compose e Download Seguro
```bash
# 1. Validar a sintaxe do compose.yaml e variáveis do .env:
docker compose config --quiet && echo "✓ compose.yaml válido"

# 2. Baixar as novas imagens antes de subir:
docker compose pull
```

### 4.4 Validação a Seco da Configuração (Dry-Run)
Valide se os arquivos de configuração são aceitos pelas novas imagens antes de colocar o ambiente em produção:

```bash
# Validar Loki:
docker run --rm \
  -e LOKI_RETENTION=${LOKI_RETENTION:-30d} \
  -v $(pwd)/loki/loki.yaml:/etc/loki/local-config.yaml \
  grafana/loki:${GRAFANA_LOKI_VERSION:-3.7.8} \
  -config.file=/etc/loki/local-config.yaml -config.expand-env=true -verify-config \
  && echo "✓ loki.yaml válido"

# Validar Mimir:
docker run --rm \
  -e MIMIR_RETENTION=${MIMIR_RETENTION:-30d} \
  -v $(pwd)/mimir/mimir.yaml:/etc/mimir.yaml \
  grafana/mimir:${GRAFANA_MIMIR_VERSION:-3.2.1} \
  -config.file=/etc/mimir.yaml -config.expand-env=true -modules \
  && echo "✓ mimir.yaml válido"

# Validar Tempo (o binário não tem flag de verify: sobe um container
# descartável e confere se ele chega em "Tempo started"):
docker run -d --name tempo-verify \
  -e TEMPO_RETENTION=${TEMPO_RETENTION:-336h} \
  -v $(pwd)/tempo/tempo.yaml:/etc/tempo.yaml \
  grafana/tempo:${GRAFANA_TEMPO_VERSION:-3.1.0} \
  -config.file=/etc/tempo.yaml -config.expand-env=true
sleep 10
docker logs tempo-verify 2>&1 | grep -q "Tempo started" \
  && echo "✓ tempo.yaml válido" \
  || docker logs tempo-verify 2>&1 | tail -20
docker rm -f tempo-verify

# Validar o OTel Gateway e as configs de agente em examples/:
docker run --rm -e ENVIRONMENT=prd \
  -v $(pwd)/otel-gateway/config.yaml:/etc/otelcol-contrib/config.yaml:ro \
  otel/opentelemetry-collector-contrib:${OTELCOL_CONTRIB_VERSION:-0.162.0} \
  validate --config=/etc/otelcol-contrib/config.yaml && echo "✓ otel-gateway válido"
python3 artifacts/scripts/check-examples-consistency.py
```

### 4.5 Inicialização e Acompanhamento de Logs
```bash
# Subir a stack com as novas imagens:
docker compose up -d

# Acompanhar os logs de inicialização de todos os serviços:
docker compose logs -f loki mimir tempo grafana
```

---

## 5. Matriz de Compatibilidade (Versões Estáveis Homologadas)

As versões abaixo foram testadas e validadas neste repositório:

| Componente | Versão Estável | Papel na Stack | Observações de Compatibilidade |
|---|:---:|---|---|
| **Grafana** | `13.2.3` | Visualização | UI, Provisioning e migrações SQLite 100% validadas. |
| **OpenTelemetry Collector Contrib** | `0.162.0` | Gateway & Agent | Gateway OTLP (tail sampling) e agent Linux (`host_metrics`, `journald`) validados em Debian 13. |
| **OBI** | `v0.14.0` | Agent (eBPF) | Traces + métricas HTTP com propagação de contexto validados (kernel 6.12). |
| **Alloy** (legado) | `v1.20.1` | Agent local da stack e templates não migrados | Em migração para OpenTelemetry Collector. |
| **Loki** | `3.7.8` | Logs TSDB | Suporte a chunks TSDB v13 e retenção via compactor. |
| **Mimir** | `3.2.1` | Métricas TSDB | Suporte a blocos de índice v2 e compactor integrado. |
| **Tempo** | `3.1.0` | Traces TSDB | Modo monolítico; blocos novos em vParquet5 (vParquet4 antigos seguem legíveis, sem migração). |

---

## 6. Procedimento de Emergência e Rollback

Caso o novo serviço entre em falha contínua após o upgrade:

1. **Parar os containers:** `docker compose down`
2. **Reverter a versão no `.env`:** Altere a variável de versão para o valor estável anterior.
3. **Subir novamente:** `docker compose up -d`
4. **Restaurar Snapshot (se necessário):** Se a falha tiver alterado a estrutura de dados em disco, restaure o snapshot do disco `/docker` criado antes do upgrade (conforme [BACKUP.md](BACKUP.md)).

---

## 7. Checklist de Validação Pós-Upgrade (Teste de 5 Minutos)

- [ ] **Métricas:** No Grafana, execute no Explore a query `up` apontando para o Mimir (todos os serviços devem retornar `1`).
- [ ] **Logs:** No Explore, busque logs recentes no Loki (`{service_name="ssh"}`) e confirme que novas entradas estão chegando.
- [ ] **Traces:** Confirme que spans recentes aparecem no datasource do Tempo.
- [ ] **Health do Gateway:** `curl -s http://localhost:13133/` deve retornar `"status":"Server available"`.

---

## 8. Governança e Referências

* Para a metodologia de observabilidade e painéis, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).
* Para procedimentos de backup preventivo, consulte [BACKUP.md](BACKUP.md).
* Para a arquitetura de rede e portas, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

---
🔙 Voltar: [README Principal](../README.md)
