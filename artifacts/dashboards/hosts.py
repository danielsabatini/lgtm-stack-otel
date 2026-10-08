"""Linha de host (agente OpenTelemetry, host_metrics system.*) comum a Linux e Windows.

Usada por Hosts/* e Hosts + Database/*. Consultas deduplicadas com max by (...)
(ver docs/DASHBOARDS.md §9.6).
"""

class Q:
    """Consultas de host. single: um host ("host.name"="$host"); multi: vários hosts
    ("host.name"=~"$host"), agrupando por host.name e com o host nas legendas."""

    def __init__(self, multi=False):
        self.multi = multi
        self.H = '"host.name"=~"$host"' if multi else '"host.name"="$host"'

    def by(self, b=""):
        return ", ".join(x for x in ('"host.name"' if self.multi else "", b) if x)

    def m(self, name, extra=""):
        return '{"%s", %s%s}' % (name, self.H, (", " + extra) if extra else "")

    def g(self, name, extra="", by=""):
        """Série deduplicada: max by (dimensões reais) descarta cópias geradas por
        troca de labels de recurso/escopo (ex.: upgrade do Collector muda
        otel_scope_version e, por ~5 min, as duas versões coexistem)."""
        b = self.by(by)
        return "max by (%s) (%s)" % (b, self.m(name, extra)) if b else "max(%s)" % self.m(name, extra)

    def r(self, name, extra="", by=""):
        """Taxa por segundo deduplicada (mesma regra de g)."""
        sel = "rate(%s[$__rate_interval])" % self.m(name, extra)
        b = self.by(by)
        return "max by (%s) (%s)" % (b, sel) if b else "max(%s)" % sel

    def agg(self, fn, expr, by=""):
        b = self.by(by)
        return "%s by (%s) (%s)" % (fn, b, expr) if b else "%s(%s)" % (fn, expr)

    def L(self, legend=""):
        """Legenda com o host no modo multi."""
        return ("{{host.name}} " + legend).strip() if self.multi else legend


_single = Q()
H, m, g, r = _single.H, _single.m, _single.g, _single.r

FSD = "device, mountpoint, state"
USED = 'state="used"'
RW = 'mode="rw"'
NOT_IDLE = 'state!="idle"'
CACHE = 'state=~"cached|buffered|slab_reclaimable"'

# Comandos de diagnóstico por sistema operacional (bloco "Ação em caso de problema")
CMD = {
    "linux": {
        "cpu": "identificar o processo com 'top' ou 'htop'",
        "cpu_state": "ver em Diagnostics 'CPU - Usage by State' se o consumo é de processos (user), kernel (system) ou espera de disco (wait) e identificar o processo com 'top' ou 'htop'.",
        "mem": "identificar os maiores consumidores com 'ps aux --sort=-%mem | head' e conferir eventos do OOM killer com 'journalctl -k | grep -i oom'.",
        "mem_cmp": "conferir com 'free -h' e identificar o processo com 'ps aux --sort=-%mem | head'.",
        "fs": "localizar os maiores diretórios com 'sudo du -xh --max-depth=1 <mountpoint> | sort -h' e revisar rotação de logs.",
        "net": "identificar as conexões com 'ss -tunap' ou 'sudo iftop -i <interface>'.",
        "disk_proc": "identificar o processo com 'sudo iotop -o' e conferir latência e ocupação em Diagnostics.",
        "iops": "conferir com 'iostat -x 1' e, em nuvem, o limite de IOPS contratado do volume.",
        "busy": "conferir com 'iostat -x 1' (coluna %util) e identificar o processo com 'sudo iotop -o'.",
        "lat": "conferir com 'iostat -x 1' (colunas r_await/w_await) e verificar se o volume atingiu o limite de IOPS.",
        "neterr": "conferir contadores com 'ip -s link show <interface>' e 'ethtool -S <interface>'.",
        "load": "inspecionar com 'vmstat 1' (coluna 'r' = fila de CPU, coluna 'b' = processos bloqueados em disco).",
        "swap": "ver a atividade de swap com 'vmstat 1' (colunas si/so) e avaliar aumento de RAM ou redução de consumo.",
        "reboot": "se não foi reboot programado, consultar o boot anterior com 'sudo journalctl -b -1 -e'.",
        "fs_total": "conferir com 'df -hT -x tmpfs -x overlay'.",
        "swap_total": "conferir com 'swapon --show'.",
    },
    "windows": {
        "cpu": "identificar o processo no Gerenciador de Tarefas ou com 'Get-Process | Sort-Object CPU -Descending | Select -First 10'",
        "cpu_state": "ver em Diagnostics 'CPU - Usage by State' se o consumo é de processos (user), kernel (system) ou interrupções de hardware (interrupt) e identificar o processo com 'Get-Process | Sort-Object CPU -Descending | Select -First 10'.",
        "mem": "identificar os maiores consumidores com 'Get-Process | Sort-Object WS -Descending | Select -First 10' e conferir o Monitor de Recursos (resmon).",
        "mem_cmp": "conferir no Monitor de Recursos (resmon, aba Memória) e com 'Get-Process | Sort-Object WS -Descending | Select -First 10'.",
        "fs": "localizar os maiores diretórios com o WinDirStat/TreeSize ou 'Get-ChildItem <unidade> -Directory | ForEach { ... }' e limpar com 'cleanmgr'.",
        "net": "identificar as conexões com 'Get-NetTCPConnection' ou o Monitor de Recursos (aba Rede).",
        "disk_proc": "identificar o processo no Monitor de Recursos (resmon, aba Disco) e conferir latência e ocupação em Diagnostics.",
        "iops": "conferir com 'Get-Counter \"\\PhysicalDisk(*)\\Disk Transfers/sec\"' e, em nuvem, o limite de IOPS contratado do volume.",
        "busy": "conferir com 'Get-Counter \"\\PhysicalDisk(*)\\% Idle Time\"' e identificar o processo no Monitor de Recursos (aba Disco).",
        "lat": "conferir com 'Get-Counter \"\\PhysicalDisk(*)\\Avg. Disk sec/Transfer\"' e verificar se o volume atingiu o limite de IOPS.",
        "neterr": "conferir com 'Get-NetAdapterStatistics' e o driver da placa de rede.",
        "load": "a carga no Windows é estimada pelo Collector a partir da fila do processador; conferir com 'Get-Counter \"\\System\\Processor Queue Length\"'.",
        "swap": "conferir o arquivo de paginação com 'Get-CimInstance Win32_PageFileUsage' e avaliar aumento de RAM.",
        "reboot": "se não foi reboot programado, consultar o motivo com 'Get-WinEvent -FilterHashtable @{LogName=\"System\"; Id=1074,6008}'.",
        "fs_total": "conferir com 'Get-Volume'.",
        "swap_total": "conferir com 'Get-CimInstance Win32_PageFileUsage'.",
    },
}

LOGS = {
    "linux": {
        "security": ("Security", "Logs de segurança do host (autenticações SSH, acessos negados).\n"
                     "• O que observar: falhas de login consecutivas da mesma origem ou acessos fora do horário esperado.\n"
                     "• Ação em caso de problema: bloquear a origem no firewall ('sudo ufw deny from <ip>') ou configurar fail2ban."),
        "system": ("System", "Logs do sistema operacional a partir de WARN: kernel (hardware, disco, rede, OOM killer), systemd (serviços falhando ao iniciar ou em loop), cron e, no servidor da stack, os daemons dockerd/containerd (campo service_name).\n"
                   "• O que observar: I/O error, OOM, falhas de driver, serviços reiniciando em loop e tarefas agendadas com erro.\n"
                   "• Ação em caso de problema: kernel com 'sudo journalctl -k -p warning -e'; serviços com 'systemctl --failed' e 'sudo journalctl -u <serviço> -e'."),
        "application": ("Application", "Logs de aplicações a partir de WARN: bancos de dados, containers e serviços de aplicação.\n"
                        "• O que observar: erros recorrentes de um mesmo serviço (campo service_name).\n"
                        "• Ação em caso de problema: abrir o serviço com 'sudo journalctl -u <serviço> -e' e correlacionar com o trace pelo campo trace_id."),
    },
    "windows": {
        "security": ("Security", "Eventos de segurança do Windows: logon/logoff (4624, 4634, 4647), falhas de logon (4625), privilégios especiais (4672) e gestão de contas (criação, desativação, bloqueio).\n"
                     "• O que observar: falhas de logon em sequência (4625, elevadas a WARN) e bloqueios de conta (4740).\n"
                     "• Ação em caso de problema: identificar a origem pelos campos source.address e user.name e bloquear no firewall ou revisar a política de bloqueio de contas."),
        "system": ("System", "Eventos Critical/Error/Warning do sistema: log System (drivers, disco, rede, hardware), Service Control Manager (serviços falhando ou em loop) e Agendador de Tarefas (campo service_name).\n"
                   "• O que observar: erros de disco (provider disk/Ntfs), desligamentos inesperados (6008), o mesmo serviço falhando repetidamente (7031, 7034, 7000) e tarefas com erro.\n"
                   "• Ação em caso de problema: abrir o evento pelo ID (campo windows_eventlog_event_id); serviços com 'Get-Service <nome>'; tarefas com 'Get-ScheduledTaskInfo'."),
        "application": ("Application", "Eventos Critical/Error/Warning de aplicações (no template de banco, SQL Server).\n"
                        "• O que observar: erros de aplicação recorrentes.\n"
                        "• Ação em caso de problema: abrir o evento no Visualizador de Eventos e o log da própria aplicação."),
    },
}


def host_tabs(d, os, multi=False):
    """Abas Health, Capacity, Activity, Diagnostics e Inventory do host.
    multi: vários hosts ao mesmo tempo (ex.: cluster DNS), um valor/linha por host."""
    q = Q(multi)
    g, r, H, L, A = q.g, q.r, q.H, q.L, q.agg
    P = d.prom
    c = CMD[os]
    linux = os == "linux"
    CPU_IDLE = A("sum", r("system.cpu.time", 'state="idle"', "state"))
    CPU_ALL = A("sum", r("system.cpu.time", "", "state"))
    FS_USED = A("sum", g("system.filesystem.usage", USED + ", " + RW, FSD), "mountpoint")
    FS_SIZE = A("sum", g("system.filesystem.usage", 'state=~"used|free", mode="rw"', FSD), "mountpoint")
    IN_USED = A("sum", g("system.filesystem.inodes.usage", USED + ", " + RW, FSD), "mountpoint")
    IN_SIZE = A("sum", g("system.filesystem.inodes.usage", 'mode="rw"', FSD), "mountpoint")

    health = [
        d.gauge("CPU Utilization (%)",
                "Percentual de uso de CPU do host (100% menos o tempo ocioso de todos os núcleos).\n"
                "• O que observar: abaixo de 70% (verde). Valores sustentados acima de 80% (laranja) e 90% (vermelho) indicam sobrecarga.\n"
                f"• Ação em caso de problema: {c['cpu_state']}",
                P(f"1 - {CPU_IDLE} / {CPU_ALL}", L())),
        d.gauge("Memory Utilization (%)",
                ("Memória em uso pelos processos (exclui cache e buffers recuperáveis) sobre a memória total.\n"
                 "• O que observar: abaixo de 70%. Acima de 90% o kernel começa a usar swap e pode acionar o OOM killer.\n"
                 if linux else
                 "Memória em uso sobre a memória total do servidor.\n"
                 "• O que observar: abaixo de 70%. Acima de 90% o Windows passa a paginar intensamente no arquivo de paginação.\n")
                + f"• Ação em caso de problema: {c['mem']}",
                P(f'{g("system.memory.usage", USED)} / {g("system.memory.limit")}', L())),
        d.gauge("Filesystem Utilization (max %)",
                ("Ocupação do filesystem mais cheio do host (somente montagens graváveis).\n" if linux else
                 "Ocupação da unidade de disco mais cheia do servidor.\n")
                + "• O que observar: abaixo de 70%. Acima de 90% há risco de falha de escrita de aplicações e logs.\n"
                  f"• Ação em caso de problema: ver em Capacity qual {'ponto de montagem' if linux else 'unidade'} está cheio e {c['fs']}",
                P(A("max", f"{FS_USED} / {FS_SIZE}"), L())),
        d.stat("Network Throughput (bits/s)",
               "Tráfego total de rede do host (entrada + saída) em bits por segundo, somando as interfaces físicas. Sem limiar de alarme: a capacidade do link varia por servidor e não é coletada (um limiar fixo não seria portável).\n"
               "• O que observar: o valor deve ficar bem abaixo da capacidade do link (ex.: 1 Gbps). Picos podem indicar backups, réplicas ou tráfego anômalo.\n"
               f"• Ação em caso de problema: {c['net']}",
               P(f'{A("sum", r("system.network.io", "", "device, direction"))} * 8', L()), unit="bps", decimals=1,
               names=multi),
    ]

    mem_q = [P(g("system.memory.usage", USED), L("Used"))]
    if linux:
        mem_q.append(P(A("sum", g("system.memory.usage", CACHE, "state")),
                       L("Cache / Buffers")))
    mem_q.append(P(g("system.memory.limit"), L("Total (Limite)")))
    capacity = [
        d.ts("CPU - Load",
             "Médias de carga (load average) de 1, 5 e 15 minutos comparadas com o número de CPUs lógicas (linha tracejada).\n"
             "• O que observar: a carga deve ficar abaixo do número de CPUs. Load de 15m acima da linha indica processos enfileirados aguardando CPU"
             + (" ou disco.\n" if linux else ".\n") + f"• Ação em caso de problema: {c['load']}",
             [P(g("system.cpu.load_average.1m"), L("Load (1m)")), P(g("system.cpu.load_average.5m"), L("Load (5m)")),
              P(g("system.cpu.load_average.15m"), L("Load (15m)")), P(g("system.cpu.logical.count"), L("CPUs (Limite)"))]),
        d.ts("Memory - Usage (bytes)",
             ("Memória usada por processos, memória de cache/buffers (recuperável pelo kernel) e memória total (linha tracejada).\n"
              "• O que observar: 'Used' crescendo sem parar indica vazamento de memória; cache alto é normal e é liberado sob demanda.\n"
              if linux else
              "Memória em uso comparada com a memória total (linha tracejada).\n"
              "• O que observar: 'Used' crescendo sem parar indica vazamento de memória em algum processo ou serviço.\n")
             + f"• Ação em caso de problema: {c['mem_cmp']}",
             mem_q, unit="bytes", stack=True),
        d.ts("Swap - Usage (bytes)" if linux else "Page File - Usage (bytes)",
             ("Swap em uso comparado com o total configurado (linha tracejada).\n"
              "• O que observar: uso de swap crescente indica falta de memória RAM; o ideal é ficar próximo de zero.\n"
              if linux else
              "Arquivo de paginação em uso comparado com o tamanho total (linha tracejada).\n"
              "• O que observar: uso crescente indica falta de memória RAM.\n")
             + f"• Ação em caso de problema: {c['swap']}",
             [P(A("sum", g("system.paging.usage", USED, "device")), L("Used")),
              P(A("sum", g("system.paging.usage", "", "device, state")), L("Total (Limite)"))], unit="bytes"),
        d.ts("Filesystem - Usage by Mountpoint (bytes)" if linux else "Disk - Usage by Drive (bytes)",
             ("Espaço usado em cada filesystem gravável do host comparado com o tamanho total (linha tracejada); a distância entre as linhas é a folga livre.\n" if linux else
              "Espaço usado em cada unidade de disco comparado com o tamanho total (linha tracejada); a distância entre as linhas é a folga livre.\n")
             + "• O que observar: crescimento linear constante permite prever quando o espaço vai acabar.\n"
               f"• Ação em caso de problema: {c['fs']}",
             [P(FS_USED, L("{{mountpoint}} usado")), P(FS_SIZE, L("{{mountpoint}} (Limite)"))], unit="bytes"),
    ]
    if linux:
        capacity.append(d.ts(
            "Filesystem - Inodes by Mountpoint",
            "Inodes (entradas de arquivos) usados em cada filesystem gravável comparados com o total (linha tracejada).\n"
            "• O que observar: a folga até o total. Inodes esgotados impedem a criação de arquivos mesmo com espaço livre.\n"
            "• Ação em caso de problema: localizar diretórios com muitos arquivos pequenos com 'sudo find <mountpoint> -xdev -type f | cut -d/ -f2-3 | sort | uniq -c | sort -n | tail'.",
            [P(IN_USED, L("{{mountpoint}} usados")), P(IN_SIZE, L("{{mountpoint}} (Limite)"))], decimals=0))

    activity = [
        d.ts("Disk - Throughput (bytes/s)",
             "Volume de dados lidos e gravados por disco.\n"
             "• O que observar: picos coincidentes com lentidão das aplicações; o limite depende do tipo de disco (SSD/NVMe ou volume de bloco).\n"
             f"• Ação em caso de problema: {c['disk_proc']}",
             [P(r("system.disk.io", "", "device, direction"), L("{{device}} {{direction}}"))], unit="Bps"),
        d.ts("Disk - IOPS",
             "Operações de leitura e escrita por segundo em cada disco.\n"
             "• O que observar: valores próximos do limite de IOPS do volume causam fila e aumento de latência.\n"
             f"• Ação em caso de problema: {c['iops']}",
             [P(r("system.disk.operations", "", "device, direction"), L("{{device}} {{direction}}"))], unit="iops"),
        d.ts("Network - Throughput (bytes/s)",
             "Tráfego de entrada (receive) e saída (transmit) por interface de rede.\n"
             "• O que observar: assimetrias inesperadas ou picos fora do padrão diário.\n"
             f"• Ação em caso de problema: {c['net']}",
             [P(r("system.network.io", "", "device, direction"), L("{{device}} {{direction}}"))], unit="Bps"),
    ]

    diagnostics = [
        d.ts("CPU - Usage by State (%)",
             ("Distribuição do tempo de CPU por estado: user (aplicações), system (kernel), wait (espera de disco), steal (CPU tomada pelo hipervisor), entre outros.\n"
              "• O que observar: 'wait' alto indica gargalo de disco; 'steal' alto indica host de virtualização sobrecarregado.\n"
              "• Ação em caso de problema: para 'wait', conferir latência de disco abaixo; para 'steal', acionar o provedor ou redimensionar a VM."
              if linux else
              "Distribuição do tempo de CPU por estado: user (aplicações), system (kernel) e interrupt (interrupções de hardware).\n"
              "• O que observar: 'system' ou 'interrupt' altos indicam problema de driver ou de hardware (rede, disco).\n"
              f"• Ação em caso de problema: {c['cpu']} e atualizar drivers se 'interrupt' estiver alto."),
             [P(f'{r("system.cpu.time", NOT_IDLE, "state")} / on ("host.name") group_left {CPU_ALL}' if multi else
                f'{r("system.cpu.time", NOT_IDLE, "state")} / scalar({CPU_ALL})',
                L("{{state}}"))], unit="percentunit", stack=not multi),
        d.ts("Disk - Busy Time (%)",
             "Fração do tempo em que cada disco esteve ocupado atendendo requisições.\n"
             "• O que observar: valores próximos de 100% indicam disco saturado (em SSD/NVMe, confirmar pela latência).\n"
             f"• Ação em caso de problema: {c['busy']}",
             [P(r("system.disk.io_time", "", "device"), L("{{device}}"))], unit="percentunit", mx=1),
        d.ts("Disk - Latency (s)",
             "Tempo médio de cada operação de leitura e escrita por disco.\n"
             "• O que observar: em SSD/NVMe, abaixo de 10 ms; latências sustentadas acima de 50 ms afetam bancos de dados e aplicações.\n"
             f"• Ação em caso de problema: {c['lat']}",
             [P(f'{r("system.disk.operation_time", "", "device, direction")} / '
                f'clamp_min({r("system.disk.operations", "", "device, direction")}, 1e-9)',
                L("{{device}} {{direction}}"))], unit="s", decimals=4),
        d.ts("Network - Errors and Drops (pkt/s)",
             "Pacotes com erro e pacotes descartados por interface e direção.\n"
             "• O que observar: deve ser zero ou próximo de zero. Erros indicam problema físico/driver; descartes indicam buffers cheios.\n"
             f"• Ação em caso de problema: {c['neterr']}",
             [P(r("system.network.errors", "", "device, direction"), L("errors {{device}} {{direction}}")),
              P(r("system.network.dropped", "", "device, direction"), L("dropped {{device}} {{direction}}"))],
             unit="pps"),
    ]

    OSB = q.by('"os.description"')
    os_expr = (f'label_replace(max by ({OSB}) ({{"target_info", {H}, "os.description"!=""}}), '
               f'"os", "$1", "os.description", "^(.*?) \\\\(Linux.*")' if linux else
               f'max by ({OSB}) ({{"target_info", {H}, "os.description"!=""}})')
    inventory = [
        d.stat("Uptime",
               "Tempo desde a última inicialização do sistema operacional.\n"
               "• O que observar: crescimento contínuo. Queda repentina indica reinício da máquina.\n"
               f"• Ação em caso de problema: {c['reboot']}",
               P(g("system.uptime"), L()), unit="s", names=multi),
        d.stat("CPUs",
               "Número de CPUs lógicas (núcleos x threads) do host.\n"
               "• O que observar: referência para a carga (Load) em Capacity.\n"
               "• Ação em caso de problema: divergência do tamanho contratado indica VM provisionada incorretamente.",
               P(g("system.cpu.logical.count"), L()), decimals=0, names=multi),
        d.stat("Memory Total",
               "Memória RAM total do host.\n"
               "• O que observar: referência para o uso de memória.\n"
               "• Ação em caso de problema: divergência do tamanho contratado indica VM provisionada incorretamente.",
               P(g("system.memory.limit"), L()), unit="bytes", names=multi),
        d.stat("Swap Total" if linux else "Page File Total",
               ("Tamanho total da área de swap.\n• O que observar: hosts de banco de dados costumam operar com swap pequeno ou desabilitado.\n"
                if linux else
                "Tamanho total do arquivo de paginação.\n• O que observar: referência para o uso de paginação em Capacity.\n")
               + f"• Ação em caso de problema: {c['swap_total']}",
               P(A("sum", g("system.paging.usage", "", "device, state")), L()), unit="bytes", names=multi),
        d.stat("Filesystem Total" if linux else "Disk Total",
               ("Capacidade somada dos filesystems graváveis do host (cada dispositivo contado uma vez).\n" if linux else
                "Capacidade somada das unidades de disco do servidor.\n")
               + "• O que observar: referência para o planejamento de capacidade.\n"
                 f"• Ação em caso de problema: {c['fs_total']}",
               P(A("sum", A("max", A("sum", g("system.filesystem.usage", RW, FSD), "device, mountpoint"), "device")), L()),
               unit="bytes", names=multi),
        d.stat("OS",
               "Sistema operacional e versão (atributo os.description do agente).\n"
               "• O que observar: todos os servidores de um mesmo papel devem rodar a mesma versão homologada.\n"
               "• Ação em caso de problema: hosts despadronizados devem ser atualizados via automação.",
               P(os_expr, (L("· {{os}}") if multi else "{{os}}") if linux else L("{{os.description}}")), text=True),
    ]

    return [("Health", health, 4), ("Capacity", capacity, 1), ("Activity", activity, 1),
            ("Diagnostics", diagnostics, 1), ("Inventory", inventory, 3)]


# Métricas que identificam servidores com dashboard dedicado (agente e pull
# gravam os mesmos nomes): esses hosts não aparecem em Linux/Windows Hosts.
#   banco (MySQL, PostgreSQL, SQL Server) -> Hosts + Database
#   nó DNS (CoreDNS)                      -> DNS / MGC Internal DNS
#   servidor da stack (docker_stats)      -> LGTM / LGTM Stack Self-Monitoring
DEDICATED_MARKERS = {
    "linux": ("mysql.uptime", "postgresql.connection.max", "coredns_build_info", "container.cpu.usage.total"),
    "windows": ("sqlserver.user.connection.count",),
}


def host_var(d, os, exclude_dedicated=False):
    q = 'count by ("host.name") ({"system.uptime", "os.type"="%s"})' % os
    if exclude_dedicated:
        q += "".join(' unless on ("host.name") count by ("host.name") ({"%s"})' % mk
                     for mk in DEDICATED_MARKERS[os])
    d.query_var("host", "Host", "query_result(%s)" % q, '/host\\.name="([^"]+)"/')


def logs_tab(d, os, categories=("security", "system", "application")):
    """Categorias da metodologia (Segurança, Sistema, Aplicação); Erros de Negócio
    não tem fonte e a aba é omitida (docs/OBSERVABILITY-METHODOLOGY.md §5.1, §9.2)."""
    return ("Logs", [d.logs(LOGS[os][cat][0], LOGS[os][cat][1], f'{{host_name="$host"}} | category="{cat}"')
                     for cat in categories], 1)


def app_row(d, uid):
    """Linha "Aplicações (OBI)" (método RED + Traces), exibida só para hosts com
    aplicações instrumentadas pelo OBI (metodologia §9.2). Requer as variáveis
    host e trace_id; uid = dashboard atual (link da tabela de traces)."""
    P = d.prom
    # ------------------------------------------------- Aplicações (OBI, método RED)
    # Metodologia §9.1/§9.3: Rate -> Activity; taxa geral de erros e latência p99 do
    # serviço -> Health; decomposição por rota -> Diagnostics.
    HTTP = '{"http.server.request.duration", %s}' % H
    HTTP_5XX = '{"http.server.request.duration", %s, "http.response.status_code"=~"5.."}' % H
    SVC = '"service.name"'
    ROUTE = '"service.name", "http.route"'
    
    
    def req_rate(sel, by):
        return f'sum by ({by}) (histogram_count(rate({sel}[$__rate_interval])))'
    
    
    def err_ratio(by):
        return f'{req_rate(HTTP_5XX, by)} / {req_rate(HTTP, by)}'
    
    
    def p99(by):
        return f'histogram_quantile(0.99, sum by ({by}) (rate({HTTP}[$__rate_interval])))'
    
    
    app_health = [
        d.stat("HTTP Error Rate (%)",
               "Percentual de respostas HTTP 5xx (erro do servidor) de cada serviço do host, medido pelo OBI (eBPF) sobre 100% do tráfego.\n"
               "• O que observar: próximo de zero. Acima de 1% (laranja) e 5% (vermelho) o serviço está falhando para os usuários.\n"
               "• Ação em caso de problema: ver em Diagnostics qual rota concentra os erros e abrir os traces com erro na aba Traces.",
               P(err_ratio(SVC), "{{service.name}}"), unit="percentunit", decimals=2, names=True,
               thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")]),
        d.stat("HTTP Latency p99",
               "Tempo de resposta do percentil 99 de cada serviço (99% das requisições respondem abaixo deste valor). É a latência que o usuário sente.\n"
               "• O que observar: estável e abaixo do objetivo do serviço; acima de 500 ms (laranja) e 1 s (vermelho) indica degradação (requisições > 1 s são retidas 100% pelo tail sampling).\n"
               "• Ação em caso de problema: ver em Diagnostics a latência por rota e abrir um trace lento na aba Traces.",
               P(p99(SVC), "{{service.name}}"), unit="s", decimals=3, names=True,
               thresholds=[(0, "green"), (0.5, "orange"), (1, "red")]),
    ]
    app_activity = [
        d.ts("HTTP - Request Rate (req/s)",
             "Requisições HTTP recebidas por segundo em cada serviço do host (OBI, 100% do tráfego).\n"
             "• O que observar: padrão de demanda; quedas bruscas indicam serviço fora do ar ou tráfego desviado.\n"
             "• Ação em caso de problema: conferir o serviço com 'systemctl status <serviço>' e os logs da linha Linux.",
             [P(req_rate(HTTP, SVC), "{{service.name}}")], unit="reqps"),
    ]
    app_diag = [
        d.ts("HTTP - Request Rate by Route and Status (req/s)",
             "Requisições por segundo por serviço, rota e código de status.\n"
             "• O que observar: rotas com muitos 4xx/5xx ou com volume fora do padrão.\n"
             "• Ação em caso de problema: filtrar os traces da rota na aba Traces e conferir a aplicação.",
             [P(req_rate(HTTP, '"service.name", "http.route", "http.response.status_code"'),
                "{{service.name}} {{http.route}} {{http.response.status_code}}")], unit="reqps"),
        d.ts("HTTP - Error Rate by Route (%)",
             "Percentual de respostas 5xx por serviço e rota.\n"
             "• O que observar: qual rota concentra os erros do serviço.\n"
             "• Ação em caso de problema: abrir os traces com erro da rota e correlacionar com os logs pelo trace_id.",
             [P(err_ratio(ROUTE), "{{service.name}} {{http.route}}")], unit="percentunit"),
        d.ts("HTTP - Latency p99 by Route (s)",
             "Latência p99 por serviço e rota. Os pontos (exemplars) abrem o trace correspondente no Tempo.\n"
             "• O que observar: qual rota puxa a latência do serviço para cima.\n"
             "• Ação em caso de problema: clicar num exemplar para abrir o trace e identificar a etapa lenta no waterfall.",
             [P(p99(ROUTE), "{{service.name}} {{http.route}}", exemplar=True)], unit="s", decimals=3),
    ]
    
    traces = [
        d.trace_table("Distributed Traces",
                      "Traces dos serviços do host capturados pelo OBI (eBPF). Ficam retidos: todos com erro, todos acima de 1 s e 5% dos demais.\n"
                      "• O que observar: duração elevada (coluna Duration) ou status de erro.\n"
                      "• Ação em caso de problema: clicar no Trace ID para abrir o waterfall abaixo e, dentro dele, saltar para os logs do span.",
                      '{ resource.host.name = "$host" }',
                      "/d/" + uid + "/" + uid + "?${__url_time_range}&var-host=${host}&var-trace_id=${__value.raw}"),
        d.trace_view("Trace Detail",
                     "Waterfall do trace selecionado na tabela acima (variável trace_id)."),
    ]
    d.model_var("apps", '{"http.server.request.duration", "host.name"="$host"}')
    d.row("Aplicações (OBI)", [("Health", app_health, 2), ("Activity", app_activity, 1),
                               ("Diagnostics", app_diag, 1), ("Traces", traces, 1)], show_if="apps")
