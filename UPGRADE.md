# Manual de Upgrades e Lifecycle (Update SRE)

A substituição de versões em Bancos de Dados Time-Series (TSDBs) como Loki e Mimir **não deve** ser tratada como a simples atualização de um site. Um *"bump"* cego de versão sem leitura prévia de Release Notes pode corromper índices históricos irreversivelmente.

Nosso repositório concentra o controle de múltiplas imagens de forma unificada no arquivo base `.env`. Siga estritamente as regras abaixo antes de aplicar um upgrade em produção.

---

## 🛑 Rule #1: Nunca Pule Major Releases (TSDBs)

Esta regra se aplica ao **Loki, Mimir e Tempo**. Se o seu `.env` constar Loki `2.9.x` e a Grafana Labs estiver na `4.0.0`, **não avance diretamente**. Passe sequencialmente pela `3.0`, inicie o container para que ele execute as rotinas internas de migração/data-translation no LVM, e só então avance para a próxima barreira.

> **Exceção — Grafana Frontend:** O Grafana (`grafana/grafana`) pode saltar major versions com segurança. Seu banco relacional SQLite possui migração automática progressiva e não compartilha o risco de corrupção de chunk-files dos TSDBs.

---

## 🛑 Rule #2: Schema Validation (A Bíblia do Upgrade)

Antes de alterar os números no `.env`:

1. Abra as **[Release Notes do Loki](https://grafana.com/docs/loki/latest/setup/upgrade/)** ou **[do Mimir](https://grafana.com/docs/mimir/latest/operators-guide/upgrading/)** ou **[do Tempo](https://grafana.com/docs/tempo/latest/setup/upgrade/)**.
2. Dê `Ctrl+F` buscando por `schema_config`, `Breaking Changes` e `migration`.
3. Se a documentação exigir novo Storage Index, edite os arquivos YAML (`loki.yaml`, `mimir.yaml`) **antes** de subir o container — sem o arquivo ajustado, o TSDB travará no boot.

> **Consulte o Apêndice** no final deste documento para os breaking changes conhecidos do Loki 3.x.

---

## 🚀 Procedimento Padrão Step-by-Step

### 1. Downtime Estratégico

Banco de dados TSDB não se atualiza "live" sem HA/Kubernetes. Drene o recebimento:

```bash
docker compose stop
sync  # Força o flush dos WALs para disco antes do snapshot pré-upgrade
```

> **Upgrade apenas do Grafana:** o frontend não compartilha WAL/storage com os
> TSDBs (usa SQLite local, volume próprio) — não é necessário parar a stack
> inteira. Pare só o serviço afetado: `docker compose stop grafana`. O
> downtime completo (`docker compose stop` sem argumento) só é obrigatório
> para upgrades de Loki, Mimir ou Tempo.

### 2. Mudança Paramétrica no `.env`

```bash
# Edite apenas as versões que deseja atualizar
nano .env

# Exemplo:
# GRAFANA_LOKI_VERSION=3.8.0
```

### 3. Validação do Compose (Antes de qualquer pull)

Valide que o `compose.yaml` e as variáveis do `.env` estão sintaticamente corretos antes de fazer qualquer download:

```bash
# Valida a sintaxe e resolve as variáveis do .env
docker compose config --quiet && echo "✓ compose.yaml válido"
```

### 4. Download Estrito das Novas Imagens

Baixe as dependências declaradas antes de forçar a subida. Se faltar disco no *pull*, o setup antigo permanece intacto:

```bash
docker compose pull
```

> Se estiver atualizando um único serviço, restrinja o pull para evitar
> baixar imagens que não mudaram: `docker compose pull grafana`.

### 5. Validação a Seco (Verify-Config + Dry-Run)

**5a. Valide a configuração de cada TSDB com a nova imagem:**

```bash
# Loki
docker run --rm \
  -v $(pwd)/loki/loki.yaml:/etc/loki/local-config.yaml \
  grafana/loki:${GRAFANA_LOKI_VERSION:-3.7.1} \
  -config.file=/etc/loki/local-config.yaml -verify-config \
  && echo "✓ loki.yaml válido"

# Mimir
docker run --rm \
  -v $(pwd)/mimir/mimir.yaml:/etc/mimir.yaml \
  grafana/mimir:${GRAFANA_MIMIR_VERSION:-3.0.5} \
  -config.file=/etc/mimir.yaml -modules \
  && echo "✓ mimir.yaml válido"

# Tempo
docker run --rm \
  -v $(pwd)/tempo/tempo.yaml:/etc/tempo.yaml \
  grafana/tempo:${GRAFANA_TEMPO_VERSION:-2.10.3} \
  -config.file=/etc/tempo.yaml -version \
  && echo "✓ tempo.yaml válido"
```

> **Grafana não tem verify-config.** Diferente dos TSDBs, a imagem
> `grafana/grafana` sempre inicia o servidor completo — não existe um modo
> dry-run acessível via `docker run` (qualquer argumento extra é ignorado
> pelo entrypoint). A validação real do Grafana acontece no passo 6
> (subir de fato) — o risco é baixo porque o SQLite local tem migração
> automática progressiva (ver Rule #1).

**5b. Simule a subida do compose sem aplicar mudanças:**

```bash
docker compose --dry-run up
```

### 6. Wake-Up e Verificação de Saúde

Se não houve erros nos passos anteriores, reviva a infra:

```bash
docker compose up -d

# Acompanhe os logs de inicialização (aguarde "ready" de cada serviço)
docker compose logs -f loki mimir tempo grafana
```

Healthchecks esperados:

> **Verificação Avançada Distroless:**
> Para validar os Healthchecks dos backends que não possuem shell interno exposto, siga rigidamente as orientações e instruções em rede interna documentadas na matriz funcional: **[ARCHITECTURE.md (Verificação de Saúde)](ARCHITECTURE.md#backends-distroless)**.

> **Frontend e Coletor (Grafana e Alloy Gateway):** Acessíveis diretamente pelo host:

```bash
curl -s http://localhost:3000/api/health | jq .database   # → "ok"
curl -s http://localhost:12345/-/ready                    # → "Alloy is ready."

# Visão geral de todos os containers
docker compose ps
```

---

## 🛡️ Mecanismo Anti-Falha (Fallback Nativo)

Se o arquivo `.env` não existir (ex: pull limpo do Git em nova máquina), o stack **não cai**. O `compose.yaml` usa *Safe-Fallback* em toda imagem:

```yaml
image: grafana/loki:${GRAFANA_LOKI_VERSION:-3.7.1}
```

Se o Docker detectar ausência da variável, usa automaticamente a versão travada `3.7.1`, evitando o risco do `:latest`.

---

## 📋 Apêndice: Breaking Changes Conhecidos

### Loki 2.x → 3.x (migração obrigatória)

Se você ainda opera Loki 2.x e planeja migrar:

| Breaking Change | Impacto | Ação Necessária |
|---|---|---|
| Schema TSDB + v13 obrigatório | Boot travado sem migração | Adicione nova entrada em `schema_config` com `from:` futuro antes de subir 3.0 |
| `shared_store` removido | Config inválida | Remova as chaves `shared_store` e `shared_store_key_prefix` do `loki.yaml` |
| Max labels por série: **15** (era 30) | Streams com >15 labels rejeitados | Audite a cardinalidade de labels antes da migração |
| Max log line: **256 KB** | Linhas grandes descartadas silenciosamente | Valide apps que loggam objetos JSON grandes |
| Prefixo de métricas: `loki_*` (era `cortex_*`) | Alertas e dashboards quebram | Atualize queries que referenciam `cortex_` para `loki_` |

### Tempo < 2.0 → 2.x

| Breaking Change | Impacto | Ação Necessária |
|---|---|---|
| Formato vParquet obrigatório | Blocos antigos ilegíveis | Aguarde expiração da retenção ou migre manualmente |
| `overrides.metrics_generator_processors` movido | Config inválida | Use `overrides.defaults.metrics_generator.processors` |

---

## 🎖️ Matriz de Compatibilidade (Versões Gold)

As versões abaixo foram testadas exaustivamente neste repositório e são consideradas o "Baseline Estável".

| Componente | Versão (Stable) | Data do Teste | Nota |
|---|---|---|---|
| **Grafana** | `13.1.2` | 04/08/2026 | UI, Provisioning e migração SQLite OK; corrige CVE-2026-13438 |
| **Alloy** | `v1.16.0` | 25/04/2026 | Estabilidade de memory usage OK |
| **Loki** | `3.7.1` | 25/04/2026 | Bloom filters habilitados OK |
| **Mimir** | `3.0.6` | 25/04/2026 | Ingestão Lean OK |
| **Tempo** | `2.10.5` | 25/04/2026 | Tail Sampling OK |

---

## 🆘 Procedimento de Emergência (Rollback)

Se após o upgrade o serviço entrar em `CrashLoopBackOff` ou os logs indicarem corrupção de índice:

1. **Pare tudo imediatamente:** `docker compose down`
2. **Reverta a versão no `.env`:** Altere a variável para a versão estável anterior.
3. **Limpe o cache local do Alloy (se necessário):** `docker volume rm lgtm-stack_alloy-agent-data` (isso força uma nova descoberta sem lixo antigo).
4. **Suba novamente:** `docker compose up -d`
5. **Restaure o Snapshot:** Se o rollback de imagem não resolver (devido a migração de schema agressiva), siga o [BACKUP.md](BACKUP.md) para restaurar o snapshot de disco feito antes do upgrade.

---

## ✅ Checklist de Validação (O Teste de 5 Minutos)

Sempre realize estes testes após um upgrade:

- [ ] **Ingestão de Métricas:** Explore → Mimir → Query: `up` (todos devem estar 1).
- [ ] **Ingestão de Logs:** Explore → Loki → `{service_name="ssh"}` (label real deste projeto; `container` não existe no schema de labels — ver [LOGS.md](LOGS.md)). Veja se novos logs aparecem.
- [ ] **Leitura de Histórico:** Busque uma métrica de 24h atrás. Se o índice quebrou, o histórico estará vazio ou dará erro de query.
- [ ] **Healthcheck da UI:** Acesse `http://localhost:12345` e valide se todos os componentes do Alloy estão "Healthy".

---
🔙 Voltar: [README Principal](README.md)
