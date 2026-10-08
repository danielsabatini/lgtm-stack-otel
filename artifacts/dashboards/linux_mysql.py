"""Linux + MySQL (agente OpenTelemetry: host_metrics, journald, receiver mysql, error log)."""
import sys
from lib import Dash
from hosts import app_row, H, g as gm, r as rm, host_tabs, logs_tab

OUT = sys.argv[1]
d = Dash("linux-mysql-hosts", "Linux + MySQL Hosts", ["linux", "mysql", "database", "opentelemetry"])
P = d.prom


BP_READS = rm("mysql.buffer_pool.operations", 'operation="reads"')
BP_REQS = rm("mysql.buffer_pool.operations", 'operation="read_requests"')
LOCK_TIME = rm("mysql.row_locks", 'kind="time"')
LOCK_WAITS = rm("mysql.row_locks", 'kind="waits"')

d.query_var("host", "Host", 'query_result(count by ("host.name") ({"mysql.uptime"}))',
            '/host\\.name="([^"]+)"/')
d.text_var("trace_id")

health = [
    d.stat("MySQL Status",
           "Indica se o agente consegue conectar e consultar o MySQL (UP/DOWN).\n"
           "• O que observar: deve estar sempre UP. DOWN indica serviço parado, credencial do usuário de monitoramento inválida ou limite de conexões atingido.\n"
           "• Ação em caso de problema: conferir com 'systemctl status mysql' e o error log na aba Logs.",
           P(gm("mysql.server.healthy")), thresholds=[(0, "red"), (1, "green")], updown=True),
    d.stat("Slow Queries (%)",
           "Percentual das consultas que excederam long_query_time (taxa geral de lentidão do banco).\n"
           "• O que observar: próximo de zero; acima de 1% (laranja) e 5% (vermelho) os usuários sentem a lentidão.\n"
           "• Ação em caso de problema: ver Slow Queries/s em Diagnostics e analisar o slow query log com 'mysqldumpslow' ou 'pt-query-digest'.",
           P(f'{rm("mysql.query.slow.count")} / clamp_min({rm("mysql.query.count")}, 1e-9)'), unit="percentunit",
           decimals=2, thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")]),
]

capacity = [
    d.ts("InnoDB Buffer Pool - Usage (bytes)",
         "Páginas do buffer pool ocupadas (clean = iguais ao disco; dirty = alteradas e ainda não gravadas) comparadas com o tamanho configurado (linha tracejada).\n"
         "• O que observar: buffer pool cheio é normal em produção; dirty alto e persistente indica escrita mais rápida que o flush para disco.\n"
         "• Ação em caso de problema: avaliar innodb_buffer_pool_size (tipicamente 50–75% da RAM em servidor dedicado) e a latência de disco na linha Linux.",
         [P(gm("mysql.buffer_pool.usage", "", "status"), "{{status}}"),
          P(gm("mysql.buffer_pool.limit"), "Buffer Pool (Limite)")], unit="bytes", stack=True),
    d.ts("Threads",
         "Threads de conexão: connected (abertas), running (executando agora) e cached (prontas para reuso).\n"
         "• O que observar: running alto e sustentado indica consultas acumulando (lentidão ou lock); connected próximo do limite indica falta de conexões.\n"
         "• Ação em caso de problema: conferir 'SHOW PROCESSLIST' (coluna State) e os locks em Diagnostics.",
         [P(gm("mysql.threads", 'kind=~"connected|running|cached"', "kind"), "{{kind}}"),
          P(gm("mysql.max_used_connections"), "Máximo usado desde o start")], decimals=0),
]

activity = [
    d.ts("Queries/s",
         "Comandos executados por segundo (todos os statements, inclusive os de monitoramento).\n"
         "• O que observar: padrão diário de carga; quedas a zero em horário comercial indicam aplicação sem acesso ao banco.\n"
         "• Ação em caso de problema: identificar as consultas mais custosas com 'performance_schema.events_statements_summary_by_digest'.",
         [P(rm("mysql.query.count"), "queries")], unit="qps"),
    d.ts("InnoDB Row Operations/s",
         "Linhas lidas, inseridas, atualizadas e removidas por segundo no InnoDB.\n"
         "• O que observar: leituras muito acima do volume de consultas indicam varreduras completas (falta de índice).\n"
         "• Ação em caso de problema: revisar o plano das consultas com 'EXPLAIN' e os índices das tabelas mais lidas.",
         [P(rm("mysql.row_operations", "", "operation"), "{{operation}}")], unit="ops"),
    d.ts("InnoDB Buffer Pool - Reads/s",
         "Leituras lógicas (atendidas pela memória) e leituras físicas (precisaram ir ao disco) por segundo.\n"
         "• O que observar: leituras físicas altas e sustentadas indicam buffer pool pequeno para o volume de dados ativo.\n"
         "• Ação em caso de problema: conferir o hit ratio em Diagnostics e avaliar aumento de innodb_buffer_pool_size.",
         [P(BP_REQS, "read requests (memória)"), P(BP_READS, "reads (disco)")], unit="ops"),
]

diagnostics = [
    d.ts("Slow Queries/s",
         "Consultas que excederam long_query_time, por segundo.\n"
         "• O que observar: devem ser exceção; picos coincidem com lentidão percebida pelos usuários.\n"
         "• Ação em caso de problema: analisar o slow query log com 'mysqldumpslow' ou 'pt-query-digest' e o plano das consultas com 'EXPLAIN'.",
         [P(rm("mysql.query.slow.count"), "slow queries")], unit="qps"),
    d.ts("InnoDB Buffer Pool - Hit Ratio (%)",
         "Percentual das leituras atendidas pela memória (1 - leituras de disco / leituras lógicas).\n"
         "• O que observar: acima de 99% em OLTP; quedas indicam dados ativos maiores que o buffer pool ou varreduras completas.\n"
         "• Ação em caso de problema: identificar consultas com varredura completa e avaliar o tamanho do buffer pool.",
         [P(f"1 - {BP_READS} / clamp_min({BP_REQS}, 1e-9)", "hit ratio")], unit="percentunit", mx=1),
    d.ts("InnoDB Row Lock - Waits/s",
         "Esperas por lock de linha por segundo.\n"
         "• O que observar: deve ficar próximo de zero; picos indicam transações disputando as mesmas linhas.\n"
         "• Ação em caso de problema: identificar o bloqueio com 'SELECT * FROM sys.innodb_lock_waits' e reduzir a duração das transações.",
         [P(LOCK_WAITS, "waits/s")], unit="ops"),
    d.ts("InnoDB Row Lock - Avg Wait Time",
         "Tempo médio de cada espera por lock de linha no intervalo.\n"
         "• O que observar: esperas longas (centenas de ms) afetam diretamente o tempo de resposta e podem levar a timeouts (innodb_lock_wait_timeout).\n"
         "• Ação em caso de problema: ver 'sys.innodb_lock_waits' e o último deadlock em 'SHOW ENGINE INNODB STATUS'.",
         [P(f"{LOCK_TIME} / clamp_min({LOCK_WAITS}, 1e-9)", "avg wait")], unit="ms"),
    d.ts("Temporary Tables/s",
         "Tabelas temporárias criadas por segundo: em memória (tables), em disco (disk_tables) e arquivos temporários (files).\n"
         "• O que observar: disk_tables alto indica ORDER BY/GROUP BY grandes demais para tmp_table_size.\n"
         "• Ação em caso de problema: revisar as consultas com GROUP BY/ORDER BY e avaliar tmp_table_size/max_heap_table_size.",
         [P(rm("mysql.tmp_resources", "", "resource"), "{{resource}}")], unit="ops"),
    d.ts("Connection Errors/s",
         "Erros de conexão por tipo: aborted (clientes que não fecharam a conexão), max_connections (recusadas por limite), accept, internal etc.\n"
         "• O que observar: max_connections acima de zero significa conexões recusadas; aborted alto indica aplicação encerrando conexões de forma incorreta.\n"
         "• Ação em caso de problema: conferir 'SHOW GLOBAL STATUS LIKE \"Aborted%\"' e o pool de conexões da aplicação.",
         [P(rm("mysql.connection.errors", "", "error"), "{{error}}")], unit="ops"),
    d.ts("InnoDB Redo Log - Checkpoint Age (bytes)",
         "Volume do redo log ainda não consolidado em disco (distância até o último checkpoint).\n"
         "• O que observar: valores próximos da capacidade do redo log forçam flush síncrono e travam as escritas.\n"
         "• Ação em caso de problema: avaliar innodb_redo_log_capacity e a latência de escrita do disco.",
         [P(gm("mysql.innodb.redo_log.checkpoint.age"), "checkpoint age")], unit="bytes"),
]

inventory = [
    d.stat("MySQL Uptime",
           "Tempo desde a última inicialização do MySQL.\n"
           "• O que observar: crescimento contínuo; queda indica reinício do serviço.\n"
           "• Ação em caso de problema: se não foi reinício programado, consultar o error log na aba Logs.",
           P(gm("mysql.uptime")), unit="s"),
    d.stat("Version",
           "Versão do servidor MySQL (atributo db.system.version do receiver).\n"
           "• O que observar: servidores de um mesmo papel devem rodar a mesma versão homologada.\n"
           "• Ação em caso de problema: planejar a atualização seguindo as notas de versão do MySQL.",
           P('max by ("db.system.version") ({"target_info", %s, "service.name"="mysql"})' % H,
             "{{db.system.version}}"), text=True),
    d.stat("Buffer Pool Size",
           "Tamanho configurado do InnoDB buffer pool (innodb_buffer_pool_size).\n"
           "• O que observar: referência para o uso do buffer pool em Capacity.\n"
           "• Ação em caso de problema: ajustar em /etc/mysql/mysql.conf.d/ e reiniciar o serviço.",
           P(gm("mysql.buffer_pool.limit")), unit="bytes"),
]

logs = [d.logs("MySQL Error Log",
               "Error log do MySQL (/var/log/mysql/error.log): erros, avisos e eventos de sistema (start/stop). O código MY-nnnnnn fica em mysql_error_code.\n"
               "• O que observar: [ERROR] recorrentes, falhas de autenticação e avisos de recursos (ex.: arquivos abertos, memória).\n"
               "• Ação em caso de problema: pesquisar o código MY-nnnnnn na referência de erros do MySQL.",
               '{host_name="$host", service_name="mysql"}')]

d.row("Linux", host_tabs(d, "linux") + [logs_tab(d, "linux")])
d.row("MySQL", [("Health", health, 4), ("Capacity", capacity, 1), ("Activity", activity, 1),
                ("Diagnostics", diagnostics, 1), ("Inventory", inventory, 3), ("Logs", logs, 1)])
app_row(d, "linux-mysql-hosts")
d.save(OUT)
