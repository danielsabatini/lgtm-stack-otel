"""Windows + SQL Server (agente OpenTelemetry: host_metrics, Event Log, receiver sqlserver).

Linha Windows = mesma de Windows Hosts; linha SQL Server = receiver sqlserver em
modo de contadores de desempenho (uma identidade por instância:
service.instance.id = <host>\\<instância>; banco em db.namespace).
"""
import sys
from lib import Dash
from hosts import H, host_tabs, logs_tab

OUT = sys.argv[1]
d = Dash("windows-hosts-mssql", "Windows + SQL Server Hosts", ["windows", "mssql", "database", "opentelemetry"])
P = d.prom
I = '"sqlserver.instance.name"'
DB = I + ', "db.namespace"'
INST = "{{sqlserver.instance.name}}"
INST_DB = "{{sqlserver.instance.name}} / {{db.namespace}}"
SEL = H + ', "sqlserver.instance.name"=~"$instance"'


def s(name, by=I):
    """Métrica do SQL Server no host e nas instâncias selecionadas, deduplicada por instância (+ dimensões)."""
    return 'max by (%s) ({"%s", %s})' % (by, name, SEL)


d.query_var("host", "Host", 'query_result(count by ("host.name") ({"sqlserver.user.connection.count"}))',
            '/host\\.name="([^"]+)"/')
d.query_var("instance", "Instância",
            'query_result(count by ("sqlserver.instance.name") ({"sqlserver.user.connection.count", "host.name"="$host"}))',
            '/sqlserver\\.instance\\.name="([^"]+)"/', multi=True)

health = [
    d.stat("Transaction Log Usage (máx %)",
           "Ocupação do log de transações do banco mais cheio de cada instância. Log cheio interrompe as escritas do banco.\n"
           "• O que observar: abaixo de 70%; acima de 80% (laranja) e 90% (vermelho) o log está perto de crescer ou de travar as transações (em modelo FULL, só é liberado após backup de log).\n"
           "• Ação em caso de problema: ver em Diagnostics qual banco está cheio e conferir 'log_reuse_wait_desc' em 'sys.databases'.",
           P(f'max by ({I}) ({s("sqlserver.transaction_log.usage", DB)})', INST), unit="percent", decimals=1,
           names=True, thresholds=[(0, "green"), (70, "yellow"), (80, "orange"), (90, "red")]),
]

capacity = [
    d.ts("User Connections",
         "Conexões de usuário por instância ao longo do tempo.\n"
         "• O que observar: picos coincidentes com lentidão ou crescimento contínuo (vazamento de conexões).\n"
         "• Ação em caso de problema: conferir o tamanho do pool de conexões da aplicação e as sessões com 'sys.dm_exec_sessions'.",
         [P(s("sqlserver.user.connection.count"), INST)], decimals=0),
]

activity = [
    d.ts("Batch Requests/s",
         "Lotes de comandos SQL recebidos por segundo em cada instância.\n"
         "• O que observar: padrão diário de carga e picos fora do normal.\n"
         "• Ação em caso de problema: identificar as consultas mais executadas com 'sys.dm_exec_query_stats' (execution_count).",
         [P(s("sqlserver.batch.request.rate"), INST)], unit="reqps"),
    d.ts("Transactions/s by Database",
         "Transações iniciadas por segundo em cada banco.\n"
         "• O que observar: qual banco concentra a carga de escrita e mudanças bruscas de volume.\n"
         "• Ação em caso de problema: correlacionar com o uso do log de transações em Capacity e com a latência de disco da linha Windows.",
         [P(s("sqlserver.transaction.rate", DB), INST_DB)], unit="ops"),
    d.ts("Page Reads and Writes/s",
         "Leituras e gravações físicas de páginas (8 KB) por segundo em cada instância.\n"
         "• O que observar: leituras físicas altas e sustentadas indicam dados que não cabem no buffer pool.\n"
         "• Ação em caso de problema: conferir Buffer Cache Hit Ratio e Page Life Expectancy e revisar índices das consultas com mais leituras.",
         [P(s("sqlserver.page.operation.rate", f"{I}, type"), "{{sqlserver.instance.name}} {{type}}")], unit="ops"),
]

diagnostics = [
    d.ts("Transaction Log - Usage by Database (%)",
         "Percentual do log de transações ocupado em cada banco (detalhe do alarme do Health).\n"
         "• O que observar: valores próximos de 100% forçam crescimento do arquivo (ou falha, se o crescimento estiver limitado). Em modelo FULL, o log só é liberado após backup de log.\n"
         "• Ação em caso de problema: conferir 'log_reuse_wait_desc' em 'sys.databases' (ex.: LOG_BACKUP, ACTIVE_TRANSACTION) e a rotina de backup de log.",
         [P(s("sqlserver.transaction_log.usage", DB), INST_DB)], unit="percent", mx=100),
    d.ts("Transaction Log - Growths",
         "Número de vezes que o arquivo de log de transações cresceu, por banco, no intervalo.\n"
         "• O que observar: crescimentos frequentes indicam log subdimensionado ou incremento de autogrowth pequeno, causando fragmentação (VLFs) e pausas de escrita.\n"
         "• Ação em caso de problema: dimensionar o log para o pico de uso e ajustar o FILEGROWTH para um valor fixo adequado (ex.: 512 MB).",
         [P(f'max by ({DB}) (increase({{"sqlserver.transaction_log.growth.count", {SEL}}}[$__rate_interval]))',
            INST_DB)], decimals=0, draw="bars"),
    d.ts("SQL Compilations and Recompilations/s",
         "Compilações e recompilações de planos de execução por segundo.\n"
         "• O que observar: compilações acima de ~10% dos Batch Requests/s indicam consultas sem reaproveitamento de plano (SQL ad hoc sem parâmetros); recompilações frequentes indicam mudanças de esquema ou estatísticas.\n"
         "• Ação em caso de problema: parametrizar as consultas da aplicação ou avaliar 'optimize for ad hoc workloads'.",
         [P(s("sqlserver.batch.sql_compilation.rate"), "compilations {{sqlserver.instance.name}}"),
          P(s("sqlserver.batch.sql_recompilation.rate"), "recompilations {{sqlserver.instance.name}}")], unit="ops"),
    d.ts("Lock Waits/s",
         "Pedidos de lock que precisaram esperar, por segundo.\n"
         "• O que observar: deve ficar próximo de zero; picos indicam bloqueio entre transações.\n"
         "• Ação em caso de problema: identificar a sessão bloqueadora com 'sys.dm_exec_requests' (coluna blocking_session_id) ou 'sp_who2'.",
         [P(s("sqlserver.lock.wait.rate"), INST)], unit="ops"),
    d.ts("Lock Wait Time (avg)",
         "Tempo médio de espera dos pedidos de lock que precisaram aguardar.\n"
         "• O que observar: esperas acima de centenas de milissegundos afetam diretamente o tempo de resposta da aplicação.\n"
         "• Ação em caso de problema: reduzir a duração das transações e revisar índices das consultas envolvidas no bloqueio.",
         [P(s("sqlserver.lock.wait_time.avg"), INST)], unit="ms"),
    d.ts("Page Life Expectancy",
         "Tempo de vida das páginas no buffer pool ao longo do tempo (referência clássica: acima de 300 s).\n"
         "• O que observar: quedas bruscas coincidem com consultas que varrem grandes volumes de dados.\n"
         "• Ação em caso de problema: correlacionar o horário da queda com as consultas em execução e com as leituras físicas em Activity.",
         [P(s("sqlserver.page.life_expectancy"), INST)], unit="s"),
    d.ts("Buffer Cache Hit Ratio (%)",
         "Percentual de páginas encontradas em memória ao longo do tempo.\n"
         "• O que observar: quedas abaixo de 95% sustentadas.\n"
         "• Ação em caso de problema: ver Page Life Expectancy e leituras físicas; avaliar aumento de memória.",
         [P(s("sqlserver.page.buffer_cache.hit_ratio"), INST)], unit="percent", mx=100),
]

inventory = [
    d.stat("Instances",
           "Número de instâncias do SQL Server monitoradas neste servidor.\n"
           "• O que observar: deve corresponder às instâncias instaladas (serviços MSSQLSERVER e MSSQL$<NOME>).\n"
           "• Ação em caso de problema: instância ausente indica receiver sqlserver não configurado para ela no config.yaml do agente.",
           P(f'count({s("sqlserver.user.connection.count")})'), decimals=0),
    d.stat("Databases",
           "Número de bancos de usuário e de sistema monitorados (exclui os bancos internos ocultos).\n"
           "• O que observar: referência para o inventário de bancos do servidor.\n"
           "• Ação em caso de problema: conferir a lista com 'SELECT name FROM sys.databases'.",
           P(f'count({s("sqlserver.transaction_log.usage", DB)})'),
           decimals=0),
]

logs = [d.logs("SQL Server Errors",
               "Erros e avisos (Critical/Error/Warning) das instâncias do SQL Server no Event Log Application. A mensagem traz 'Error: <n> Severity: <s> State: <e>'; o número do erro fica em db_response_status_code.\n"
               "• O que observar: severidade 17 ou maior (recursos, hardware ou falhas graves), falhas de login (18456) e erros de I/O (823/824/825).\n"
               "• Ação em caso de problema: consultar o número do erro na documentação do SQL Server e o ERRORLOG da instância.",
               f'{{host_name="$host", service_name="mssql"}} | windows_eventlog_provider=~"(MSSQL\\\\$)?(${{instance:regex}})"')]

d.row("Windows", host_tabs(d, "windows") + [logs_tab(d, "windows")])
d.row("SQL Server", [("Health", health, 4), ("Capacity", capacity, 1), ("Activity", activity, 1),
                     ("Diagnostics", diagnostics, 1), ("Inventory", inventory, 2), ("Logs", logs, 1)])
d.save(OUT)
