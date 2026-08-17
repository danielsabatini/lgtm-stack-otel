# Scripts de Teste de Carga — PostgreSQL & MySQL

Guia para gerar carga realista em PostgreSQL ou MySQL e visualizar as métricas capturadas pelo framework dos 6+2 Pilares.

---

## 📋 Visão Geral

**Versão 2 - Otimizada para 20GB de disco**

Ambos os scripts executam **~30 milhões de operações** em 3 fases:

### Fases do Teste

| Fase | Descrição | Objetivo |
|------|-----------|----------|
| **0: INSERT INICIAL** | 20M registros (uma única vez) | Ativar índices, buffer pool, dados persistentes |
| **1: CARGA ACUMULATIVA** | 5 ciclos × 2M inserts + updates/deletes | Operações I/O reais, row operations, cache activity |
| **2: STRESS EM LEITURA** | 1000s SELECTs por 15 segundos | Cache hit rate, índice usage, query latency |

### Tempo Estimado
- **PostgreSQL:** 8-12 minutos
- **MySQL:** 8-12 minutos

### Disco Utilizado
- **Antes:** 0 GB
- **Durante Teste:** ~5-7 GB (pico, seguro nos 20GB)
- **Após Teste:** ~6-8 GB (dados persistem)

### Métricas Observáveis

| Pilar | PostgreSQL | MySQL | Status |
|-------|-----------|-------|--------|
| **HEALTH** | `pg_up`, `pg_stat_activity_count` | `mysql_up`, `threads_connected` | ✅ Visível |
| **CAPACITY** | `pg_database_size_bytes`, `pg_wal_size_bytes` | `innodb_buffer_pool_bytes_data` | ✅ Persistente |
| **ACTIVITY** | `pg_stat_database_xact_commit` | `mysql_global_status_questions` | ✅ Pico claro |
| **DIAGNOSTICS** | `pg_stat_database_deadlocks` | `innodb_row_lock_waits` | ✅ Observável |
| **I/O** | WAL write rate | `innodb_data_reads/writes` | ✅ Ativo |
| **Cache Hit Rate** | `blks_hit / (blks_hit + blks_read) * 100` | Similar | ✅ 95%+ |

---

## 🚀 Como Usar

### Pré-requisitos

1. **Alloy Gateway em execução** com coleta ativa (Pull Scrape)
2. **Grafana com dashboards MySQL/PostgreSQL provisionados**
3. **Acesso SSH ou direto** ao servidor remoto

### PostgreSQL

#### Passo 1: Conectar ao servidor PostgreSQL

```bash
# Via SSH + psql
ssh -i chave.pem usuario@172.18.1.157

# Ou via psql remoto
psql -h 172.18.1.157 -U postgres -d postgres
```

#### Passo 2: Baixar o script

```bash
# Opção A: Copiar do repositório
curl -o postgres-load-test.sql \
  https://raw.githubusercontent.com/seu-repo/lgtm-stack/main/load-test/postgres-load-test.sql

# Opção B: Local (se já clonado)
cat /path/to/lgtm-stack/load-test/postgres-load-test.sql
```

#### Passo 3: Executar o teste

```bash
# Opção A: Via psql
psql -h 172.18.1.157 -U postgres -d postgres -f postgres-load-test.sql

# Opção B: Interactive (mais lento, melhor visualização)
psql -h 172.18.1.157 -U postgres -d postgres
postgres=# \i postgres-load-test.sql

# Opção C: Em background (recomendado para conexões instáveis)
nohup psql -h 172.18.1.157 -U postgres -d postgres -f postgres-load-test.sql > pg-test.log 2>&1 &
tail -f pg-test.log
```

#### Passo 4: Acompanhar progresso

```bash
# Terminal 2: Monitorar métricas em tempo real
watch -n 5 'psql -h 172.18.1.157 -U postgres -d lgtm -c \
  "SELECT datname, xact_commit, tup_inserted, tup_updated, tup_deleted 
   FROM pg_stat_database WHERE datname = \"lgtm\";"'
```

---

### MySQL

#### Passo 1: Conectar ao servidor MySQL

```bash
# Via SSH
ssh -i chave.pem usuario@192.168.1.13

# Ou via mysql remoto
mysql -h 192.168.1.13 -u root -p
```

#### Passo 2: Baixar o script

```bash
# Opção A: Via curl
curl -o mysql-load-test.sql \
  https://raw.githubusercontent.com/seu-repo/lgtm-stack/main/load-test/mysql-load-test.sql

# Opção B: Local
cat /path/to/lgtm-stack/load-test/mysql-load-test.sql
```

#### Passo 3: Executar o teste

```bash
# Opção A: Via mysql CLI (recomendado)
mysql -h 192.168.1.13 -u root -p < mysql-load-test.sql

# Opção B: Interactive
mysql -h 192.168.1.13 -u root -p
mysql> SOURCE /tmp/mysql-load-test.sql;

# Opção C: Em background
nohup mysql -h 192.168.1.13 -u root -p < mysql-load-test.sql > mysql-test.log 2>&1 &
tail -f mysql-test.log
```

#### Passo 4: Acompanhar progresso

```bash
# Terminal 2: Monitorar tabela em tempo real
watch -n 5 'mysql -h 192.168.1.13 -u root -p -e \
  "SELECT 
    TABLE_NAME, 
    TABLE_ROWS, 
    DATA_LENGTH, 
    INDEX_LENGTH 
   FROM information_schema.TABLES 
   WHERE TABLE_SCHEMA = \"lgtm\" AND TABLE_NAME = \"cadastro\";"'
```

---

## 📊 Visualizar Métricas no Grafana

### PostgreSQL

1. **Acesse o Dashboard:**
   ```
   http://localhost:3000/d/linux-pgsql-hosts
   ```

2. **Configure Variáveis:**
   - `instance = srv-pgsql-01` (ou seu hostname)

3. **Monitore os Pilares:**
   - **HEALTH:** `pg_up = 1` (deve estar estável)
   - **ACTIVITY:** `pg_stat_database_xact_commit` (deve estar em **pico**)
   - **CAPACITY:** `pg_wal_size_bytes` (crescimento visível)
   - **DIAGNOSTICS:** `pg_stat_database_deadlocks` (deve ser **0**)
   - **I/O:** WAL write rate no pico

### MySQL

1. **Acesse o Dashboard:**
   ```
   http://localhost:3000/d/linux-mysql-hosts
   ```

2. **Configure Variáveis:**
   - `instance = srv-mysql-01` (ou seu hostname)

3. **Monitore os Pilares:**
   - **HEALTH:** `mysql_up = 1` (deve estar estável)
   - **ACTIVITY:** `mysql_global_status_questions` (deve estar em **pico**)
   - **CAPACITY:** `mysql_global_status_innodb_buffer_pool_bytes_data` (pico de utilização)
   - **DIAGNOSTICS:** `mysql_global_status_innodb_row_lock_waits` (deve ser baixo)
   - **I/O:** `mysql_global_status_innodb_data_reads` (pico)

---

## 🔍 Troubleshooting

### Problema: "Access Denied" ao conectar

**PostgreSQL:**
```bash
# Verificar se postgres está rodando
systemctl status postgresql

# Conectar via socket local
sudo -u postgres psql

# Ou configurar .pgpass
echo "172.18.1.157:5432:postgres:postgres:senha" > ~/.pgpass
chmod 600 ~/.pgpass
```

**MySQL:**
```bash
# Verificar se mysql está rodando
systemctl status mysql

# Conectar localmente
mysql -u root -p

# Ou criar usuário sem senha para teste
mysql -u root -p -e "CREATE USER 'loadtest'@'%' IDENTIFIED BY 'teste123';"
mysql -u root -p -e "GRANT ALL ON lgtm.* TO 'loadtest'@'%';"
```

### Problema: Script interrompido ou lento

**PostgreSQL:**
```sql
-- Verificar transações ativas
SELECT pid, usename, state, query 
FROM pg_stat_activity 
WHERE state != 'idle';

-- Cancelar se necessário
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE query LIKE '%gerar_carga%' AND state != 'idle';
```

**MySQL:**
```sql
-- Verificar queries longas
SHOW PROCESSLIST;

-- Resetar tabela se travada
TRUNCATE lgtm.cadastro;

-- Restart da procedure se necessário
CALL gerar_carga_teste();
```

### Problema: Métricas não aparecem no Grafana

1. **Verificar se Alloy Gateway está coletando:**
   ```bash
   curl -s http://alloy-gateway:9090/api/v1/query \
     --data-urlencode 'query=mysql_up{instance="srv-mysql-01"}' | jq
   ```

2. **Verificar exporter remoto:**
   ```bash
   curl -s http://192.168.1.13:8080/mysql/metrics | head -20
   ```

3. **Reiniciar coleta no Gateway:**
   ```bash
   docker restart alloy-gateway
   ```

---

## 📈 Interpretação de Resultados

### Indicadores de Sucesso

| Métrica | PostgreSQL | MySQL | Esperado |
|---------|-----------|-------|----------|
| Queries/sec | `pg_stat_database_xact_commit rate` | `mysql_global_status_questions rate` | **Pico > 100k qps** |
| Cache Hit Rate | `blks_hit / (blks_hit + blks_read) * 100` | `read_requests / (read_requests + reads) * 100` | **> 95%** |
| Row Latency | `active_time / xact_commit` | `data_read + data_written / questions` | **< 1ms** |
| Disk I/O | WAL write rate | `innodb_data_reads + writes` | **Variável** |
| Locks | `deadlocks` | `innodb_row_lock_waits` | **Próximo de 0** |

### Sinais de Problemas

- ⚠️ **Throughput cai abruptamente:** Possível lock ou I/O bottleneck
- ⚠️ **Cache hit rate < 80%:** Memória insuficiente para working set
- ⚠️ **Row lock waits > 0:** Contenção entre inserções/updates
- ⚠️ **Queries ficam lentas:** Possível CPU maxed out ou I/O saturation

---

## 🧹 Limpeza Após Testes

### PostgreSQL

```sql
-- Conectar ao banco
psql -h 172.18.1.157 -U postgres -d postgres

-- Remover banco de testes
DROP DATABASE IF EXISTS lgtm;
\q
```

### MySQL

```sql
-- Conectar ao servidor
mysql -h 192.168.1.13 -u root -p

-- Remover banco de testes
DROP DATABASE IF EXISTS lgtm;
EXIT;
```

---

## 💡 Dicas de Otimização

### Para testes mais realistas:

1. **Adicionar índices:** Modifica o plano de execução
2. **Usar diferentes tipos de dados:** BLOB, JSON, etc.
3. **Executar em paralelo:** 2-3 conexões simultâneas
4. **Variar proporção INSERT/UPDATE/DELETE:** Replicar padrões reais

### Para testes de stress máximo:

1. **Aumentar `tamanho_lote`** de 10M para 50M por ciclo
2. **Reduzir `total_lotes`** de 100 para 20 (mantém 1B operações)
3. **Desabilitar índices** durante carga (recriar depois)
4. **Usar memory tables** (MySQL) ou UNLOGGED (PostgreSQL)

---

## 📚 Referências

- [PostgreSQL: System Views](https://www.postgresql.org/docs/current/monitoring-stats.html)
- [MySQL: Performance Schema](https://dev.mysql.com/doc/refman/8.0/en/performance-schema.html)
- [DASHBOARDS.md](../docs/DASHBOARDS.md)
- [INSTALL.md](../../examples/pull/INSTALL.md)

---

🔙 Voltar: [INSTALL.md](../../examples/pull/INSTALL.md)
