"""Linux + PostgreSQL (agente OpenTelemetry: host_metrics, journald, receiver postgresql, log)."""
import sys
from lib import Dash
from hosts import app_row, H, g, r, host_tabs, logs_tab

OUT = sys.argv[1]
d = Dash("linux-pgsql-hosts", "Linux + PostgreSQL Hosts", ["linux", "postgresql", "database", "opentelemetry"])
P = d.prom
DB = '"db.namespace"'
DBF = '"db.namespace"=~"$database"'
LDB = "{{db.namespace}}"

HIT = "sum(%s)" % r("postgresql.blks_hit", DBF, DB)
READ = "sum(%s)" % r("postgresql.blks_read", DBF, DB)
COMMITS = "sum(%s)" % r("postgresql.commits", DBF, DB)
ROLLBACKS = "sum(%s)" % r("postgresql.rollbacks", DBF, DB)

d.query_var("host", "Host", 'query_result(count by ("host.name") ({"postgresql.connection.max"}))',
            '/host\\.name="([^"]+)"/')
d.text_var("trace_id")
d.query_var("database", "Banco",
            'query_result(count by ("db.namespace") ({"postgresql.db_size", "host.name"="$host"}))',
            '/db\\.namespace="([^"]+)"/', multi=True)

health = [
    d.gauge("Connection Usage (%)",
            "Conexões abertas (backends de todos os bancos) sobre o limite max_connections.\n"
            "• O que observar: abaixo de 70%. Ao atingir o limite, novas conexões são recusadas com 'too many clients already'.\n"
            "• Ação em caso de problema: conferir as sessões em 'pg_stat_activity' (agrupando por usename/application_name/state) e usar um pool de conexões (ex.: PgBouncer).",
            P(f'sum({g("postgresql.backends", DBF, DB)}) / {g("postgresql.connection.max")}')),
    d.stat("Rollback Ratio (%)",
           "Percentual de transações desfeitas (rollback) sobre o total, somando os bancos selecionados (taxa geral de erros do banco).\n"
           "• O que observar: em geral abaixo de 5% (laranja); acima de 10% (vermelho) indica falhas na aplicação (constraints, timeouts, deadlocks).\n"
           "• Ação em caso de problema: ver em Diagnostics qual banco concentra os rollbacks e os erros no log do PostgreSQL (aba Logs).",
           P(f"{ROLLBACKS} / clamp_min({COMMITS} + {ROLLBACKS}, 1e-9)"), unit="percentunit", decimals=2,
           thresholds=[(0, "green"), (0.05, "orange"), (0.10, "red")]),
]

capacity = [
    d.ts("Database Size (bytes)",
         "Tamanho de cada banco de dados.\n"
         "• O que observar: crescimento linear permite planejar disco; saltos indicam cargas em massa ou inchaço (bloat) por falta de VACUUM.\n"
         "• Ação em caso de problema: conferir as maiores tabelas com 'pg_total_relation_size' e o autovacuum em 'pg_stat_user_tables'.",
         [P(g("postgresql.db_size", DBF, DB), LDB)], unit="bytes"),
    d.ts("Connections by Database",
         "Conexões (backends) abertas em cada banco comparadas com max_connections (linha tracejada).\n"
         "• O que observar: crescimento contínuo sem aumento de carga indica vazamento de conexões na aplicação.\n"
         "• Ação em caso de problema: conferir sessões ociosas em 'pg_stat_activity' (state = 'idle in transaction') e o pool da aplicação.",
         [P(g("postgresql.backends", DBF, DB), LDB), P(g("postgresql.connection.max"), "max_connections (Limite)")],
         decimals=0),
]

activity = [
    d.ts("Transactions/s by Database",
         "Commits e rollbacks por segundo em cada banco.\n"
         "• O que observar: qual banco concentra a carga e rollbacks acima do normal.\n"
         "• Ação em caso de problema: correlacionar rollbacks com erros no log do PostgreSQL.",
         [P(r("postgresql.commits", DBF, DB), "commits {{db.namespace}}"),
          P(r("postgresql.rollbacks", DBF, DB), "rollbacks {{db.namespace}}")], unit="ops"),
    d.ts("Tuples/s",
         "Linhas processadas por segundo em todos os bancos: returned (lidas em varreduras), fetched (lidas por índice), inserted, updated e deleted.\n"
         "• O que observar: 'returned' muito maior que 'fetched' indica varreduras sequenciais (falta de índice).\n"
         "• Ação em caso de problema: conferir 'seq_scan' x 'idx_scan' em 'pg_stat_user_tables' e o plano das consultas com 'EXPLAIN ANALYZE'.",
         [P(f'sum({r("postgresql.tup_" + op, DBF, DB)})', op)
          for op in ("returned", "fetched", "inserted", "updated", "deleted")], unit="ops"),
    d.ts("Block Reads/s",
         "Blocos (8 KB) lidos da memória (hit) e do disco (read) por segundo, todos os bancos.\n"
         "• O que observar: leituras de disco altas e sustentadas indicam dados que não cabem nos shared buffers.\n"
         "• Ação em caso de problema: ver Cache Hit Ratio por banco em Diagnostics e as consultas com mais leituras em 'pg_stat_statements'.",
         [P(HIT, "hit (memória)"), P(READ, "read (disco)")], unit="ops"),
]

diagnostics = [
    d.ts("Cache Hit Ratio by Database (%)",
         "Percentual de blocos lidos da memória em cada banco.\n"
         "• O que observar: acima de 99% em OLTP; bancos analíticos podem ter valores menores.\n"
         "• Ação em caso de problema: identificar as tabelas com mais leituras de disco em 'pg_statio_user_tables' (heap_blks_read).",
         [P(f'{r("postgresql.blks_hit", DBF, DB)} / clamp_min({r("postgresql.blks_hit", DBF, DB)} + '
            f'{r("postgresql.blks_read", DBF, DB)}, 1e-9)', LDB)], unit="percentunit", mx=1),
    d.ts("Rollback Ratio (%)",
         "Percentual de transações desfeitas (rollback) sobre o total, por banco.\n"
         "• O que observar: em geral abaixo de 5%; aumentos indicam erros na aplicação (violação de constraint, timeouts, deadlocks).\n"
         "• Ação em caso de problema: correlacionar com os erros no log do PostgreSQL (aba Logs).",
         [P(f'{r("postgresql.rollbacks", DBF, DB)} / clamp_min({r("postgresql.commits", DBF, DB)} + '
            f'{r("postgresql.rollbacks", DBF, DB)}, 1e-9)', LDB)], unit="percentunit"),
    d.ts("Deadlocks/s",
         "Deadlocks detectados por segundo em cada banco.\n"
         "• O que observar: deve ser zero.\n"
         "• Ação em caso de problema: o log do PostgreSQL registra as consultas envolvidas ('deadlock detected'); padronizar a ordem de acesso às tabelas na aplicação.",
         [P(r("postgresql.deadlocks", DBF, DB), LDB)], unit="ops"),
    d.ts("Temporary Files (bytes/s)",
         "Volume gravado em arquivos temporários por segundo (ordenações e hashes que não couberam em work_mem).\n"
         "• O que observar: gravação temporária frequente aumenta I/O e latência das consultas.\n"
         "• Ação em caso de problema: identificar as consultas com 'log_temp_files' e avaliar work_mem ou índices para o ORDER BY/GROUP BY.",
         [P(r("postgresql.temp.io", DBF, DB), LDB)], unit="Bps"),
    d.ts("Checkpoints",
         "Checkpoints por intervalo: scheduled (por checkpoint_timeout) e requested (forçados por volume de WAL).\n"
         "• O que observar: 'requested' frequentes indicam max_wal_size pequeno para o volume de escrita, causando picos de I/O.\n"
         "• Ação em caso de problema: aumentar max_wal_size e conferir 'checkpoints_req' em 'pg_stat_checkpointer'.",
         [P('max by (type) (increase({"postgresql.bgwriter.checkpoint.count", %s}[$__rate_interval]))' % H, "{{type}}")],
         decimals=0, draw="bars"),
]

inventory = [
    d.stat("Version",
           "Versão do servidor PostgreSQL (atributo db.system.version do receiver).\n"
           "• O que observar: servidores de um mesmo papel devem rodar a mesma versão homologada.\n"
           "• Ação em caso de problema: planejar a atualização seguindo as notas de versão do PostgreSQL.",
           P('max by ("db.system.version") ({"target_info", %s, "service.name"="postgresql"})' % H,
             "{{db.system.version}}"), text=True),
    d.stat("Databases",
           "Número de bancos monitorados (exceto templates).\n"
           "• O que observar: referência para o inventário de bancos do servidor.\n"
           "• Ação em caso de problema: conferir a lista com '\\l' no psql.",
           P(f'count({g("postgresql.db_size", DBF, DB)})'), decimals=0),
    d.stat("Max Connections",
           "Limite de conexões simultâneas (max_connections).\n"
           "• O que observar: referência para Connection Usage em Health.\n"
           "• Ação em caso de problema: ajustar no postgresql.conf (exige reinício) ou usar um pool de conexões.",
           P(g("postgresql.connection.max")), decimals=0),
    d.stat("Total Size",
           "Tamanho somado de todos os bancos.\n"
           "• O que observar: referência para o planejamento de disco.\n"
           "• Ação em caso de problema: ver Database Size em Capacity.",
           P(f'sum({g("postgresql.db_size", DBF, DB)})'), unit="bytes"),
]

logs = [d.logs("PostgreSQL Log",
               "Log do PostgreSQL a partir de WARNING (com DETAIL/HINT/STATEMENT agrupados no mesmo registro) e consultas lentas ('duration:', se log_min_duration_statement estiver ativo). Usuário em user_name e banco em db_namespace.\n"
               "• O que observar: ERROR/FATAL recorrentes, falhas de autenticação e 'deadlock detected'.\n"
               "• Ação em caso de problema: abrir o registro completo e conferir o STATEMENT envolvido.",
               '{host_name="$host", service_name="postgresql"} | db_namespace=~"${database:regex}" or db_namespace=""')]

d.row("Linux", host_tabs(d, "linux") + [logs_tab(d, "linux")])
d.row("PostgreSQL", [("Health", health, 4), ("Capacity", capacity, 1), ("Activity", activity, 1),
                     ("Diagnostics", diagnostics, 1), ("Inventory", inventory, 4), ("Logs", logs, 1)])
app_row(d, "linux-pgsql-hosts")
d.save(OUT)
