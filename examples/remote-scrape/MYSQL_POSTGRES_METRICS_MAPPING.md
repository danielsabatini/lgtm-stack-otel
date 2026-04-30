# Mapeamento de Métricas: PostgreSQL → MySQL

Referência para equivalências de métricas entre PostgreSQL e MySQL exporters para monitoramento com o framework dos 6+2 Pillars.

## Mapeamento por Categoria

### Status & Conexões

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_up` | `mysql_up` | Status do servidor (up/down) |
| `pg_settings_max_connections` | `mysql_global_variables_max_connections` | Máximo de conexões simultâneas |
| `pg_stat_activity_count` | `mysql_global_status_threads_connected` | Conexões ativas no momento |
| `pg_stat_database_numbackends` | `mysql_global_status_threads_connected` | Número de backends conectados |
| N/A | `mysql_global_status_threads_running` | Threads executando queries (MySQL específico) |
| N/A | `mysql_global_status_threads_created` | Total de threads criadas desde boot |

### Armazenamento (WAL/Binlog)

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_wal_size_bytes` | `mysql_global_status_innodb_redo_log_physical_size` | Tamanho do redo log físico |
| `pg_stat_database_temp_bytes` | `mysql_global_status_created_tmp_disk_tables` | Tabelas temporárias no disco |
| N/A | `mysql_binlog_size_bytes` | Tamanho total dos binlogs |
| N/A | `mysql_global_status_innodb_redo_log_logical_size` | Tamanho lógico do redo log |

### Transações & Queries

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_stat_database_xact_commit` | `mysql_global_status_questions` | Transações/Queries executadas |
| `pg_stat_database_xact_rollback` | **N/A** | MySQL não expõe rollbacks nativamente |
| N/A | `mysql_global_status_queries` | Queries (inclui internas) |
| N/A | `mysql_global_status_commands_total` | Total de comandos por tipo |
| N/A | `mysql_global_status_slow_queries` | Queries que excederam threshold |

### Operações de Linhas (DML)

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_stat_database_tup_returned` | `mysql_global_status_innodb_system_rows_read` | Linhas lidas |
| `pg_stat_database_tup_fetched` | `mysql_global_status_innodb_system_rows_read` | Linhas buscadas (igual a read) |
| `pg_stat_database_tup_inserted` | `mysql_global_status_innodb_system_rows_inserted` | Linhas inseridas |
| `pg_stat_database_tup_updated` | `mysql_global_status_innodb_system_rows_updated` | Linhas atualizadas |
| `pg_stat_database_tup_deleted` | `mysql_global_status_innodb_system_rows_deleted` | Linhas deletadas |

### Buffer Pool / Cache

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_stat_database_blks_hit` | `mysql_global_status_innodb_buffer_pool_read_requests` | Acessos ao buffer pool |
| `pg_stat_database_blks_read` | `mysql_global_status_innodb_buffer_pool_reads` | Misses (leitura de disco) |
| N/A | `mysql_global_status_innodb_buffer_pool_bytes_data` | Bytes de dados no buffer |
| N/A | `mysql_global_status_innodb_buffer_pool_bytes_dirty` | Bytes sujos no buffer |
| N/A | `mysql_global_status_innodb_buffer_pool_write_requests` | Solicitações de escrita |
| N/A | `mysql_global_status_innodb_pages_written` | Páginas escritas no disco |

### I/O (Latência)

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_stat_database_blk_read_time` | `mysql_global_status_innodb_data_reads` | Operações de leitura |
| `pg_stat_database_blk_write_time` | `mysql_global_status_innodb_data_writes` | Operações de escrita |
| N/A | `mysql_global_status_innodb_data_read` | Bytes lidos |
| N/A | `mysql_global_status_innodb_data_written` | Bytes escritos |

### Locks & Conflicts

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| `pg_stat_database_deadlocks` | `mysql_global_status_innodb_row_lock_waits` | Deadlocks/Row lock waits |
| N/A | `mysql_global_status_innodb_row_lock_time` | Tempo gasto aguardando locks |
| N/A | `mysql_global_status_table_locks_waited` | Table locks aguardados |
| N/A | `mysql_global_status_table_locks_immediate` | Table locks concedidos imediatamente |

### Network

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| N/A | `mysql_global_status_bytes_received` | Bytes recebidos do cliente |
| N/A | `mysql_global_status_bytes_sent` | Bytes enviados ao cliente |

### Uptime

| PostgreSQL | MySQL | Descrição |
|-----------|-------|-----------|
| N/A | `mysql_global_status_uptime` | Segundos desde boot |

---

## Observações Importantes

### Diferenças Estruturais

1. **PostgreSQL usa `xact_commit` para transações**, MySQL usa `questions` ou `queries` que incluem todas as queries (não apenas transações completas).

2. **MySQL InnoDB é o motor padrão** analisado aqui. Se usar MyISAM, as métricas são diferentes (não há redo log, buffer pool, etc.).

3. **PostgreSQL não expõe `blk_read_time` e `blk_write_time` em millisegundos** como MySQL faz com `innodb_data_reads/writes`. O cálculo de latência é indireto em PostgreSQL.

4. **MySQL não expõe `deadlocks` diretamente**, use `innodb_row_lock_waits` como proxy.

### Cálculos Derivados

#### Query Latency

**PostgreSQL:**
```promql
rate(pg_stat_database_active_time_seconds_total[5m]) 
/ rate(pg_stat_database_xact_commit[5m])
```

**MySQL (aproximado):**
```promql
rate(mysql_global_status_innodb_data_read[5m]) 
+ rate(mysql_global_status_innodb_data_written[5m])
/ rate(mysql_global_status_questions[5m])
```

#### Cache Hit Rate

**PostgreSQL:**
```promql
rate(pg_stat_database_blks_hit[5m]) 
/ (rate(pg_stat_database_blks_hit[5m]) + rate(pg_stat_database_blks_read[5m])) * 100
```

**MySQL:**
```promql
rate(mysql_global_status_innodb_buffer_pool_read_requests[5m]) 
/ (rate(mysql_global_status_innodb_buffer_pool_read_requests[5m]) + rate(mysql_global_status_innodb_buffer_pool_reads[5m])) * 100
```

---

## Arquivo de Configuração Alloy

Veja `pull-linux-dbaas-mysql-hosts.alloy` para exemplo completo de como coletar estas métricas via Grafana Alloy.

**Métrica não mapeada?** Verifique se a métrica MySQL correspondente está habilitada no `mysqld_exporter`. Nem todas as métricas são exportadas por padrão.
