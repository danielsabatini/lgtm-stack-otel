"""OPNsense Firewall (Telegraf -> OTel Gateway: system.*, zfs.*, opnsense.pf.*, ipsec.*, unbound.*, ntp.*, network.*)."""
import sys
from lib import Dash
from hosts import H, g, r

OUT = sys.argv[1]
d = Dash("opnsense-firewall", "OPNsense Firewall", ["opnsense", "freebsd", "firewall", "opentelemetry"])
P = d.prom

FSD = "device, mountpoint, state"
USED = 'state="used"'
IDLE = 'state="idle"'
WIRED = 'state="wired"'
INACTIVE = 'state="inactive"'
MEM_CACHE = 'state=~"inactive|cached|buffered"'
RW = 'mode="rw"'
NOT_IDLE = 'state!="idle"'
FS_UF = 'state=~"used|free", mode="rw"'
ALLOC = 'state="allocated"'
HIT = 'result="hit"'
HIT_MISS = 'result=~"hit|miss"'
MATCH = 'reason="match"'
NOT_MATCH = 'reason!="match"'
STATE_ALL = 'state="all"'
STATE_CFG = 'state="configured"'
TYPE_MAX = 'type="max"'
TYPE_MIN = 'type="min"'
TYPE_TGT = 'type="target"'
ERR_TYPE = '"error.type"'
POOL = '"zfs.pool.name"'
PEER = '"server.address"'
TUN = '"ipsec.tunnel.name", "network.peer.address"'

CPU_IDLE = f'sum({r("system.cpu.time", IDLE, "state")})'
CPU_ALL = f'sum({r("system.cpu.time", "", "state")})'
FS_USED = f'sum by (mountpoint) ({g("system.filesystem.usage", USED + ", " + RW, FSD)})'
FS_SIZE = f'sum by (mountpoint) ({g("system.filesystem.usage", FS_UF, FSD)})'
IN_USED = f'sum by (mountpoint) ({g("system.filesystem.inodes.usage", USED + ", " + RW, FSD)})'
IN_SIZE = f'sum by (mountpoint) ({g("system.filesystem.inodes.usage", RW, FSD)})'

def gl(name, extra="", by=""):
    """Última amostra em janela de 10 min para coletores periódicos (ex.: Speedtest a cada 6 min)."""
    sel = f'last_over_time({{"{name}", {H}{(", " + extra) if extra else ""}}}[10m])'
    return f"max by ({by}) ({sel})" if by else f"max({sel})"


d.query_var("host", "Host", 'query_result(count by ("host.name") ({"opnsense.pf.states.count"}))',
            '/host\\.name="([^"]+)"/')

# =============================================================================
# 1. Linha FreeBSD & ZFS
# =============================================================================
bsd_health = [
    d.gauge("CPU Utilization (%)",
            "Percentual de uso de CPU do appliance OPNsense (100% menos o tempo ocioso de todos os núcleos).\n"
            "• O que observar: abaixo de 70% (verde). Valores sustentados acima de 80% (laranja) e 90% (vermelho) aumentam a latência de encaminhamento de pacotes.\n"
            "• Ação em caso de problema: ver em Diagnostics 'CPU - Usage by State (%)' se o consumo é de interrupções de rede (interrupt), kernel (system) ou processos (user) e inspecionar com 'top -aSH'.",
            P(f"1 - {CPU_IDLE} / {CPU_ALL}")),
    d.gauge("Memory Utilization (%)",
            "Memória em uso (active + wired) sobre a memória RAM total do firewall (exclui páginas inactive/cache recuperáveis).\n"
            "• O que observar: abaixo de 80%. Em FreeBSD com ZFS, o ARC usa memória wired e libera páginas automaticamente sob pressão.\n"
            "• Ação em caso de problema: ver em Capacity e Diagnostics a divisão entre Wired (ZFS ARC/kernel) e Active (processos) e conferir com 'top -o res' ou 'vmstat -m'.",
            P(f'{g("system.memory.usage", USED)} / {g("system.memory.limit")}')),
    d.stat("ZFS Pool Health",
           "Estado operacional de cada pool ZFS do firewall (UP = ONLINE; DOWN = DEGRADED, FAULTED ou UNAVAIL).\n"
           "• O que observar: deve estar sempre UP (ONLINE).\n"
           "• Ação em caso de problema: executar 'zpool status -xv' no OPNsense para identificar o disco com falha e iniciar o resilver/substituição.",
           P(f'(count by ({POOL}) ({{"zfs.pool.limit", {H}, "zfs.pool.health"="ONLINE"}}) >= bool 1) '
             f'or on ({POOL}) ({g("zfs.pool.limit", "", POOL)} * 0)', "{{zfs.pool.name}}"),
           thresholds=[(0, "red"), (1, "green")], names=True, updown=True),
    d.gauge("ZFS Pool Utilization (max %)",
            "Ocupação do pool ZFS mais cheio do appliance.\n"
            "• O que observar: abaixo de 70%. Acima de 80% o ZFS troca o alocador de blocos por best-fit, aumentando a fragmentação e a latência de escrita.\n"
            "• Ação em caso de problema: listar snapshots e datasets com 'zfs list -o space' e 'zpool list' e remover snapshots/logs antigos.",
            P(f'max({g("zfs.pool.utilization", "", POOL)})')),
    d.gauge("Filesystem Utilization (max %)",
            "Ocupação do ponto de montagem gravável mais cheio do sistema (datasets ZFS e partição de boot EFI).\n"
            "• O que observar: abaixo de 70%. Acima de 90% há risco de falha na gravação de logs (/var/log) e configurações.\n"
            "• Ação em caso de problema: ver em Capacity qual mountpoint está cheio e localizar os maiores diretórios com 'du -xhd 1 <mountpoint> | sort -h'.",
            P(f"max({FS_USED} / {FS_SIZE})")),
    d.stat("Network Throughput (bits/s)",
           "Tráfego total somado de todas as interfaces do firewall (entrada + saída) em bits por segundo. Sem limiar fixo de alarme pois a capacidade do link varia por ambiente.\n"
           "• O que observar: comparar com a velocidade contratada da WAN e das portas LAN/VLAN.\n"
           "• Ação em caso de problema: ver em Activity qual interface concentra o tráfego e inspecionar com 'pfTop' ou 'iftop -i <interface>'.",
           P(f'sum({r("system.network.io", "", "device, direction")}) * 8'), unit="bps", decimals=1),
]

bsd_capacity = [
    d.ts("CPU - Load",
         "Médias de carga (load average) de 1, 5 e 15 minutos comparadas com o número de CPUs lógicas (linha tracejada).\n"
         "• O que observar: a carga deve permanecer abaixo do número de CPUs lógicas.\n"
         "• Ação em caso de problema: inspecionar a fila de execução com 'vmstat 1' e os threads do kernel com 'top -SH'.",
         [P(g("system.cpu.load_average.1m"), "Load (1m)"),
          P(g("system.cpu.load_average.5m"), "Load (5m)"),
          P(g("system.cpu.load_average.15m"), "Load (15m)"),
          P(g("system.cpu.logical.count"), "CPUs (Limite)")]),
    d.ts("Memory - Usage (bytes)",
         "Memória em uso (Active + Wired), páginas recuperáveis (Inactive / Cache / Buffers) e memória RAM total instalada (linha tracejada); a distância até o limite é a memória livre (Free).\n"
         "• O que observar: crescimento contínuo de Used acompanhado de queda de Free sem estabilização.\n"
         "• Ação em caso de problema: ver o detalhamento Wired vs Active em Diagnostics e conferir processos com 'ps auxww -m | head -n 20'.",
         [P(g("system.memory.usage", USED), "Used (Active + Wired)"),
          P(f'sum({g("system.memory.usage", MEM_CACHE, "state")})', "Inactive / Cache"),
          P(g("system.memory.limit"), "Total (Limite)")], unit="bytes", stack=True),
    d.ts("ZFS Pool - Usage (bytes)",
         "Espaço físico alocado em cada pool ZFS comparado com a capacidade total do pool (linha tracejada); a diferença é o espaço livre no pool.\n"
         "• O que observar: manter pelo menos 20% de folga livre para preservar o desempenho de escrita Copy-on-Write do ZFS.\n"
         "• Ação em caso de problema: conferir com 'zpool list -v' e 'zfs list -t snapshot'.",
         [P(g("zfs.pool.usage", ALLOC, POOL), "{{zfs.pool.name}} alocado"),
          P(g("zfs.pool.limit", "", POOL), "{{zfs.pool.name}} (Limite)")], unit="bytes"),
    d.ts("ZFS ARC - Size vs Limit (bytes)",
         "Tamanho atual do Adaptive Replacement Cache (ARC) do ZFS comparado com o tamanho-alvo (target), mínimo (c_min) e máximo permitido (c_max, linha tracejada).\n"
         "• O que observar: o ARC cresce até o Target/Limite em operação normal e encolhe automaticamente quando processos pedem RAM.\n"
         "• Ação em caso de problema: caso o ARC consuma RAM excessiva em appliance com muitos serviços, ajustar 'vfs.zfs.arc_max' em System > Settings > Tunables.",
         [P(g("zfs.arc.size"), "ARC Size"),
          P(g("zfs.arc.limit", TYPE_TGT), "ARC Target"),
          P(g("zfs.arc.limit", TYPE_MIN), "ARC Min"),
          P(g("zfs.arc.limit", TYPE_MAX), "ARC Max (Limite)")], unit="bytes"),
    d.ts("Filesystem - Usage by Mountpoint (bytes)",
         "Espaço utilizado em cada ponto de montagem gravável comparado com o tamanho disponível ao dataset/partição (linha tracejada).\n"
         "• O que observar: crescimento anormal em /var/log (logs de filtro/proxy) ou /tmp.\n"
         "• Ação em caso de problema: revisar a retenção de logs em System > Settings > Logging e inspecionar '/var/log' com 'du -sh /var/log/*'.",
         [P(FS_USED, "{{mountpoint}} usado"), P(FS_SIZE, "{{mountpoint}} (Limite)")], unit="bytes"),
    d.ts("Filesystem - Inodes by Mountpoint",
         "Inodes utilizados em cada ponto de montagem gravável comparados com o total disponível (linha tracejada).\n"
         "• O que observar: esgotamento de inodes (especialmente em partições não-ZFS como /boot/efi ou diretórios de spool/cache).\n"
         "• Ação em caso de problema: verificar com 'df -ih' no shell do OPNsense.",
         [P(IN_USED, "{{mountpoint}} usados"), P(IN_SIZE, "{{mountpoint}} (Limite)")], decimals=0),
]

bsd_activity = [
    d.ts("Network - Throughput by Interface (bytes/s)",
         "Volume de tráfego recebido (receive) e transmitido (transmit) por interface física, virtual e de túnel (vtnet, igb, enc0, ipsec).\n"
         "• O que observar: distribuição de banda entre WAN, LAN e interfaces IPsec.\n"
         "• Ação em caso de problema: inspecionar os fluxos por IP e porta com 'pfTop' ou 'iftop -ni <interface>'.",
         [P(r("system.network.io", "", "device, direction"), "{{device}} {{direction}}")], unit="Bps"),
    d.ts("Network - Packets by Interface (pkt/s)",
         "Taxa de pacotes recebidos e transmitidos por segundo em cada interface de rede.\n"
         "• O que observar: picos de pacotes por segundo (pps) com throughput baixo indicam pacotes pequenos (flood SYN/UDP ou problemas de MTU/fragmentação).\n"
         "• Ação em caso de problema: capturar amostra com 'tcpdump -ni <interface> -c 100' e conferir a aba Diagnostics da linha Firewall (PF).",
         [P(r("system.network.packets", "", "device, direction"), "{{device}} {{direction}}")], unit="pps"),
    d.ts("Disk - Throughput (bytes/s)",
         "Volume de dados lidos e gravados por segundo no dispositivo de bloco do firewall.\n"
         "• O que observar: escrita constante elevada costuma vir de logs excessivos de firewall/DNS ou RRD/NetFlow.\n"
         "• Ação em caso de problema: conferir 'gstat -b' ou 'iostat -x 1' e identificar processos com 'top -m io'.",
         [P(r("system.disk.io", "", "device, direction"), "{{device}} {{direction}}")], unit="Bps"),
    d.ts("Disk - IOPS",
         "Operações de leitura e escrita por segundo em cada disco.\n"
         "• O que observar: valores próximos ao limite do volume causam aumento de latência e fila pendente em Diagnostics.\n"
         "• Ação em caso de problema: conferir 'iostat -x 1' e avaliar logs em RAM (/var MFS) caso o disco seja lento.",
         [P(r("system.disk.operations", "", "device, direction"), "{{device}} {{direction}}")], unit="iops"),
    d.ts("ZFS ARC & ZFetch - Requests (ops/s)",
         "Requisições de leitura ao cache ARC (hit/miss) e de pré-busca sequencial ZFetch (hit/miss) por segundo.\n"
         "• O que observar: predominância de hits no ARC sobre misses.\n"
         "• Ação em caso de problema: conferir o Hit Ratio (%) na aba Diagnostics.",
         [P(r("zfs.arc.requests", "", "result"), "ARC {{result}}"),
          P(r("zfs.zfetch.requests", "", "result"), "ZFetch {{result}}")], unit="ops"),
]

bsd_diagnostics = [
    d.ts("CPU - Usage by State (%)",
         "Decomposição do uso de CPU por estado: interrupt (interrupções de placas de rede/criptografia), system (kernel/pf), user (daemons como Unbound/charon) e nice.\n"
         "• O que observar: 'interrupt' ou 'system' elevados indicam gargalo no processamento de pacotes ou criptografia IPsec.\n"
         "• Ação em caso de problema: verificar 'vmstat -i' (interrupções por IRQ), habilitar AES-NI / QAT em System > Settings > Miscellaneous e revisar RSS/multiqueue da NIC.",
         [P(f'{r("system.cpu.time", NOT_IDLE, "state")} / scalar({CPU_ALL})', "{{state}}")],
         unit="percentunit", stack=True),
    d.ts("Memory - Wired vs Active vs Inactive (bytes)",
         "Decomposição da memória do FreeBSD: Wired (páginas fixadas pelo kernel e ZFS ARC), Active (páginas em uso ativo por processos) e Inactive (cache candidato a reuso).\n"
         "• O que observar: se Wired crescer sozinho, é kernel/ARC; se Active crescer sem parar, é vazamento em processo de usuário.\n"
         "• Ação em caso de problema: para Wired, inspecionar 'sysctl kstat.zfs.misc.arcstats' e 'vmstat -z'; para Active, usar 'ps auxww -m'.",
         [P(g("system.memory.usage", WIRED), "Wired (Kernel / ZFS ARC)"),
          P(f'{g("system.memory.usage", USED)} - {g("system.memory.usage", WIRED)}', "Active (Userland)"),
          P(g("system.memory.usage", INACTIVE), "Inactive (Cache)")], unit="bytes"),
    d.ts("ZFS ARC - Hit Ratio (%)",
         "Percentual de leituras ZFS atendidas diretamente pela memória RAM (ARC hit / total de requisições ARC).\n"
         "• O que observar: acima de 95% em operação normal; quedas indicam leitura de dados frios ou ARC muito pequeno.\n"
         "• Ação em caso de problema: conferir 'sysctl kstat.zfs.misc.arcstats.hits kstat.zfs.misc.arcstats.misses' e o tamanho do ARC em Capacity.",
         [P(f'{r("zfs.arc.requests", HIT)} / clamp_min(sum({r("zfs.arc.requests", "", "result")}), 1e-9)',
            "ARC hit ratio")], unit="percentunit", mx=1),
    d.ts("ZFS Pool - Fragmentation (%)",
         "Percentual de fragmentação do espaço livre de cada pool ZFS.\n"
         "• O que observar: abaixo de 50%. Fragmentação alta combinada com ocupação acima de 80% degrada a escrita.\n"
         "• Ação em caso de problema: manter o pool abaixo de 80% de ocupação (ver 'zpool list').",
         [P(g("zfs.pool.fragmentation", "", POOL), "{{zfs.pool.name}}")], unit="percentunit", mx=1),
    d.ts("Disk - Busy Time (%)",
         "Fração do tempo em que o disco esteve ocupado atendendo operações de E/S.\n"
         "• O que observar: valores sustentados próximos de 100% indicam saturação do disco.\n"
         "• Ação em caso de problema: executar 'gstat -b' para ver a fila e a ocupação (%busy) por partição/geom.",
         [P(r("system.disk.io_time", "", "device"), "{{device}}")], unit="percentunit", mx=1),
    d.ts("Disk - Latency (s)",
         "Tempo médio por operação de leitura e escrita no disco.\n"
         "• O que observar: abaixo de 10 ms em SSD/NVMe; valores acima de 50 ms travam commits de logs e sincronização de estado.\n"
         "• Ação em caso de problema: verificar a saúde do volume no hipervisor/cloud e com 'iostat -x 1'.",
         [P(f'{r("system.disk.operation_time", "", "device, direction")} / '
            f'clamp_min({r("system.disk.operations", "", "device, direction")}, 1e-9)',
            "{{device}} {{direction}}")], unit="s", decimals=4),
    d.ts("Disk - Pending & Merged Operations",
         "Operações de disco aguardando na fila (pending) e operações mescladas pelo escalonador por segundo (merged).\n"
         "• O que observar: 'pending' deve permanecer em zero ou próximo de zero.\n"
         "• Ação em caso de problema: correlacionar com Disk - Latency (s) e 'gstat -b'.",
         [P(g("system.disk.pending_operations", "", "device"), "pending {{device}}"),
          P(r("system.disk.merged", "", "device, direction"), "merged/s {{device}} {{direction}}")]),
    d.ts("Network - Errors and Drops (pkt/s)",
         "Pacotes com erro e pacotes descartados por interface e direção.\n"
         "• O que observar: zero em interfaces físicas (vtnet/igb). Em interfaces virtuais IPsec (ipsec*), erros de transmit ocorrem quando o túnel está desconectado (sem SA ativa para encaminhar o pacote).\n"
         "• Ação em caso de problema: conferir 'netstat -i -n' e, se for em interface ipsec*, verificar o status do túnel na linha Firewall (PF) & IPsec VPN.",
         [P(r("system.network.errors", "", "device, direction"), "errors {{device}} {{direction}}"),
          P(r("system.network.dropped", "", "device, direction"), "dropped {{device}} {{direction}}")], unit="pps"),
    d.ts("Processes by Status",
         "Quantidade de processos do sistema por estado (running, sleeping, idle, wait, blocked, stopped, defunct).\n"
         "• O que observar: 'blocked' ou 'wait' subindo rapidamente indicam contenção de disco ou lock de kernel; 'defunct' indica processos zumbis.\n"
         "• Ação em caso de problema: listar processos com 'ps auxww' e 'top -S'.",
         [P(g("system.processes.count", "", "status"), "{{status}}")], decimals=0, stack=True),
]

bsd_inventory = [
    d.stat("Uptime",
           "Tempo desde a última inicialização do sistema operacional FreeBSD/OPNsense.\n"
           "• O que observar: crescimento contínuo; queda indica reboot do firewall.\n"
           "• Ação em caso de problema: verificar o histórico de boot com 'last -n 10 boot' e '/var/crash'.",
           P(g("system.uptime")), unit="s"),
    d.stat("CPUs (Logical)",
           "Número de CPUs lógicas visíveis pelo sistema.\n"
           "• O que observar: referência para o gráfico CPU - Load em Capacity.\n"
           "• Ação em caso de problema: conferir com 'sysctl hw.ncpu'.",
           P(g("system.cpu.logical.count")), decimals=0),
    d.stat("CPUs (Physical Cores)",
           "Número de núcleos físicos do processador.\n"
           "• O que observar: comparar com o dimensionamento da VM/appliance.\n"
           "• Ação em caso de problema: conferir a topologia de CPU com 'sysctl kern.sched.topology_spec'.",
           P(g("system.cpu.physical.count")), decimals=0),
    d.stat("Memory Total",
           "Memória RAM física total instalada no firewall.\n"
           "• O que observar: referência para Memory - Usage (bytes) em Capacity.\n"
           "• Ação em caso de problema: conferir com 'sysctl hw.physmem'.",
           P(g("system.memory.limit")), unit="bytes"),
    d.stat("ZFS Pool Total",
           "Capacidade bruta somada dos pools ZFS do appliance.\n"
           "• O que observar: referência para o armazenamento total do firewall.\n"
           "• Ação em caso de problema: conferir com 'zpool list'.",
           P(f'sum({g("zfs.pool.limit", "", POOL)})'), unit="bytes"),
    d.stat("ZFS ARC Max Limit",
           "Teto máximo configurado para o cache ZFS ARC na memória RAM.\n"
           "• O que observar: referência para ZFS ARC - Size vs Limit em Capacity.\n"
           "• Ação em caso de problema: ajustar via 'vfs.zfs.arc_max' caso necessário.",
           P(g("zfs.arc.limit", TYPE_MAX)), unit="bytes"),
    d.stat("ZFS Deduplication Ratio",
           "Taxa de deduplicação de blocos de cada pool ZFS (1.00 = deduplicação desabilitada ou sem blocos duplicados).\n"
           "• O que observar: em firewalls é recomendado manter em 1.00x (dedup desligado) para economizar RAM.\n"
           "• Ação em caso de problema: conferir 'zpool get dedupratio'.",
           P(g("zfs.pool.deduplication.ratio", "", POOL), "{{zfs.pool.name}}"), decimals=2, names=True),
    d.stat("Platform",
           "Identificação do serviço, sistema operacional e zona/região do recurso OpenTelemetry.\n"
           "• O que observar: metadados de inventário padronizados no otel-gateway.\n"
           "• Ação em caso de problema: revisar resource attributes em otel-gateway/opnsense.yaml.",
           P(f'max by ("os.type", "service.name", "cloud.region", "cloud.availability_zone") ({{"target_info", {H}}})',
             "{{service.name}} ({{os.type}} · {{cloud.region}}-{{cloud.availability_zone}})"), text=True),
]

# =============================================================================
# 2. Linha Firewall (PF) & IPsec VPN
# =============================================================================
PF_ANOM = f'sum({r("opnsense.pf.packets", NOT_MATCH, "reason")})'
PF_ALL = f'sum({r("opnsense.pf.packets", "", "reason")})'

fw_health = [
    d.stat("IPsec Tunnel Status",
           "Estado operacional de cada túnel IPsec Site-to-Site configurado no strongSwan (UP = conectado e com Child SA ativa; DOWN = desconectado).\n"
           "• O que observar: todos os túneis de produção devem permanecer UP (verde).\n"
           "• Ação em caso de problema: verificar o daemon charon em VPN > IPsec > Status Overview ou via SSH com 'swanctl --list-sas' e 'clog /var/log/ipsec/latest.log'.",
           P(g("ipsec.tunnel.status", "", TUN), "{{ipsec.tunnel.name}} ({{network.peer.address}})"),
           thresholds=[(0, "red"), (1, "green")], names=True, updown=True),
    d.stat("PF Anomaly Drop Ratio (%)",
           "Percentual de pacotes descartados por anomalias internas do Packet Filter (state_mismatch, fragment, short, memory, state_limit, congestion) sobre o total de pacotes que acionaram contadores do PF.\n"
           "• O que observar: próximo de 0% (verde); acima de 1% (laranja) e 5% (vermelho) indica perda de pacotes por estado inválido, falta de memória ou limite de state table.\n"
           "• Ação em caso de problema: ver em Diagnostics qual motivo (reason) concentra os descartes e conferir 'pfctl -si'.",
           P(f"{PF_ANOM} / clamp_min({PF_ALL}, 1e-9)"), unit="percentunit", decimals=2,
           thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")]),
]

fw_capacity = [
    d.ts("PF - Active State Table Entries",
         "Quantidade de conexões (states) simultâneas mantidas na tabela de estado do Packet Filter.\n"
         "• O que observar: crescimento repentino indica pico de conexões, varredura de portas ou ataque DDoS (SYN flood).\n"
         "• Ação em caso de problema: inspecionar os estados por IP de origem/destino com 'pfTop' ou 'pfctl -ss | wc -l' e verificar o limite em Firewall > Settings > Advanced (Firewall Maximum States).",
         [P(g("opnsense.pf.states.count"), "active states")], decimals=0),
    d.ts("IPsec - Active & Configured SAs",
         "Quantidade de Security Associations IKE (Fase 1) ativas e Child SAs (Fase 2, ativas e configuradas) por túnel IPsec.\n"
         "• O que observar: para cada túnel ativo, 'IKE SAs' e 'Child SAs (active)' devem ser >= 1 e acompanhar o número configurado.\n"
         "• Ação em caso de problema: listar as SAs com 'swanctl --list-sas' e 'swanctl --list-conns' e reiniciar a conexão com 'swanctl --initiate --child <nome>'.",
         [P(g("ipsec.tunnel.ike_sa.count", "", TUN), "IKE SAs {{ipsec.tunnel.name}} ({{network.peer.address}})"),
          P(g("ipsec.tunnel.child_sa.count", "", TUN + ", state"),
            "Child SAs ({{state}}) {{ipsec.tunnel.name}} ({{network.peer.address}})")], decimals=0),
]

fw_activity = [
    d.ts("PF - State Table Operations (ops/s)",
         "Operações realizadas por segundo na tabela de estados do Packet Filter: search (busca de pacotes em conexões existentes), insert (novas conexões) e removal (conexões encerradas/expiradas).\n"
         "• O que observar: 'search' acompanha a taxa de pacotes das interfaces; 'insert' e 'removal' andam juntos em regime estável.\n"
         "• Ação em caso de problema: se 'insert' superar muito 'removal', a tabela de estados cresce (ver Capacity) — identificar a origem com 'pfTop'.",
         [P(r("opnsense.pf.state.operations", "", "operation"), "{{operation}}")], unit="ops"),
    d.ts("PF - Rule Matches (pkt/s)",
         "Taxa de pacotes por segundo que casaram com regras de filtragem/NAT (match) na criação de novos estados do Packet Filter.\n"
         "• O que observar: reflete a taxa de abertura de novas sessões avaliadas pelo conjunto de regras.\n"
         "• Ação em caso de problema: inspecionar as regras mais acionadas com 'pfctl -vvsr'.",
         [P(r("opnsense.pf.packets", MATCH, "reason"), "rule matches/s")], unit="pps"),
]

fw_diagnostics = [
    d.ts("PF - Packets Dropped by Anomaly Reason (pkt/s)",
         "Taxa de pacotes descartados pelo Packet Filter por motivo técnico: state_mismatch (pacote TCP fora da janela/sequência da conexão), state_limit (tabela cheia), memory (falta de pool memory), fragment, short, bad_offset, congestion, proto_cksum, synproxy, src_limit.\n"
         "• O que observar: deve permanecer próximo de zero. 'state_mismatch' indica roteamento assimétrico ou expiração prematura de estado; 'state_limit' ou 'memory' indicam exaustão da state table.\n"
         "• Ação em caso de problema: conferir 'pfctl -si' e, para state_mismatch, revisar timeouts de estado ou roteamento assimétrico entre interfaces/túneis.",
         [P(r("opnsense.pf.packets", NOT_MATCH, "reason"), "{{reason}}")], unit="pps"),
]

fw_inventory = [
    d.stat("IPsec Tunnels Configured",
           "Total de túneis IPsec monitorados no appliance.\n"
           "• O que observar: deve corresponder à quantidade de conexões Fase 1 habilitadas no OPNsense.\n"
           "• Ação em caso de problema: conferir em VPN > IPsec > Connections.",
           P(f'count({g("ipsec.tunnel.status", "", TUN)})'), decimals=0),
    d.stat("IPsec Peer & Protocol",
           "Quantidade de Child SAs configuradas por túnel, exibindo o nome do túnel, IP do peer remoto e versão do protocolo IKE.\n"
           "• O que observar: padronização em IKEv2 para todos os túneis Site-to-Site.\n"
           "• Ação em caso de problema: revisar a configuração do túnel em VPN > IPsec > Connections.",
           P(g("ipsec.tunnel.child_sa.count", STATE_CFG,
               '"ipsec.tunnel.name", "network.peer.address", "network.protocol.version"'),
             "{{ipsec.tunnel.name}} · {{network.peer.address}} ({{network.protocol.version}})"),
           decimals=0, names=True),
]

# =============================================================================
# 3. Linha DNS (Unbound)
# =============================================================================
UB_HIT = r("unbound.cache.operations", HIT)
UB_TOT = f'sum({r("unbound.cache.operations", HIT_MISS, "result")})'
UB_ERR = f'sum({r("unbound.queries.errors", "", ERR_TYPE)})'
UB_QRY = r("unbound.queries")

dns_health = [
    d.gauge("DNS Cache Hit Ratio (%)",
            "Percentual de consultas DNS respondidas diretamente pelo cache do Unbound sem precisar de recursão externa.\n"
            "• O que observar: acima de 80% (verde) em operação normal; abaixo de 50% (laranja) ou 30% (vermelho) indica cache frio, TTLs muito curtos ou varredura de domínios aleatórios.\n"
            "• Ação em caso de problema: conferir 'unbound-control stats_noreset' e habilitar Prefetch / Serve Expired em Services > Unbound DNS > Advanced.",
            P(f"{UB_HIT} / clamp_min({UB_TOT}, 1e-9)"),
            thresholds=[(0, "red"), (0.3, "orange"), (0.5, "yellow"), (0.7, "green")]),
    d.stat("DNS Query Error Ratio (%)",
           "Percentual de consultas DNS descartadas ou com erro interno no Unbound (timed_out, wait_limit, ip_ratelimited, replyaddr_limit, cookie_invalid) sobre o total de consultas.\n"
           "• O que observar: 0% (verde); acima de 1% (laranja) e 5% (vermelho) indica falha nos resolvers upstream ou saturação da fila.\n"
           "• Ação em caso de problema: ver em Diagnostics 'DNS Query Errors by Type' qual erro ocorreu e testar os resolvers upstream com 'drill @<upstream> example.com'.",
           P(f"{UB_ERR} / clamp_min({UB_QRY}, 1e-9)"), unit="percentunit", decimals=2,
           thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")]),
    d.gauge("DNS Request List Utilization (%)",
            "Ocupação atual da fila de requisições recursivas simultâneas do Unbound sobre o pico máximo observado (request_list.limit).\n"
            "• O que observar: próximo de zero quando os upstreams respondem rápido; valores altos indicam consultas acumulando à espera de recursão.\n"
            "• Ação em caso de problema: conferir a latência de recursão em Diagnostics e a conectividade WAN.",
            P(f'{g("unbound.request_list.usage", STATE_ALL)} / clamp_min({g("unbound.request_list.limit")}, 1)')),
]

dns_capacity = [
    d.ts("Unbound - Request List Usage vs Max",
         "Requisições recursivas ativas na fila do Unbound (all = todas, user = iniciadas por clientes, replies = aguardando resposta), média histórica (avg) e o pico máximo atingido (Max Limite, linha tracejada).\n"
         "• O que observar: fila baixa e estável; crescimento sustentado indica lentidão ou indisponibilidade dos servidores DNS raiz/upstream.\n"
         "• Ação em caso de problema: ver 'DNS Request List Dropped / Overwritten' em Diagnostics e conferir 'unbound-control dump_requestlist'.",
         [P(g("unbound.request_list.usage", "", "state"), "current ({{state}})"),
          P(g("unbound.request_list.avg"), "average"),
          P(g("unbound.request_list.limit"), "Max Seen (Limite)")], decimals=1),
    d.ts("Unbound - TCP Buffers Usage",
         "Quantidade de buffers de conexão TCP/TLS em uso pelo Unbound.\n"
         "• O que observar: próximo de zero para tráfego UDP padrão; sobe quando há respostas grandes (DNSSEC) ou DNS-over-TLS (DoT).\n"
         "• Ação em caso de problema: se atingir o limite de conexões TCP, aumentar 'Incoming Num TCP' em Services > Unbound DNS > Advanced.",
         [P(g("unbound.tcp.usage"), "tcp buffers")], decimals=0),
]

dns_activity = [
    d.ts("DNS Queries & Recursive Replies (qps)",
         "Total de consultas DNS recebidas por segundo pelo Unbound e quantas precisaram de resolução recursiva externa (recursive replies).\n"
         "• O que observar: 'queries' muito acima de 'recursive replies' demonstra que o cache local está absorvendo a demanda.\n"
         "• Ação em caso de problema: em caso de pico anômalo, ativar query log temporário ou inspecionar com 'tcpdump -ni <lan_if> port 53'.",
         [P(UB_QRY, "total queries"),
          P(r("unbound.queries.recursive_replies"), "recursive replies")], unit="qps"),
    d.ts("DNS Cache Operations (ops/s)",
         "Operações de cache do Unbound por segundo: hit (atendidas pelo cache), miss (foram para recursão), prefetch (renovadas antes de expirar) e expired (servidas expiradas).\n"
         "• O que observar: predominância de 'hit' e 'prefetch'.\n"
         "• Ação em caso de problema: ajustar 'Minimum TTL' e habilitar 'Prefetch Support' no Unbound.",
         [P(r("unbound.cache.operations", "", "result"), "{{result}}")], unit="ops"),
    d.ts("DNS Cookies & DNSCrypt Queries (qps)",
         "Consultas com DNS Cookies (client/valid) e consultas DNSCrypt (crypted, cert, cleartext) por segundo.\n"
         "• O que observar: atividade esperada caso DNS Cookies (RFC 7873) ou DNSCrypt estejam habilitados.\n"
         "• Ação em caso de problema: verificar configurações em Services > Unbound DNS.",
         [P(r("unbound.queries.cookies", "", "state"), "cookie ({{state}})"),
          P(r("unbound.dnscrypt.queries", "", "type"), "dnscrypt ({{type}})")], unit="qps"),
]

dns_diagnostics = [
    d.ts("DNS Recursion & Queue Latency (s)",
         "Tempo médio (avg) e mediano (median) que o Unbound leva para resolver consultas recursivas externas, e o tempo máximo de espera na fila (queue max).\n"
         "• O que observar: mediana abaixo de 100 ms; 'avg' muito acima de 'median' indica que alguns domínios/upstreams estão sofrendo timeout.\n"
         "• Ação em caso de problema: correlacionar com o RTT da WAN na linha Conectividade e testar os forwarders/root servers com 'drill'.",
         [P(g("unbound.recursion.duration.avg"), "recursion avg"),
          P(g("unbound.recursion.duration.median"), "recursion median"),
          P(g("unbound.query_queue.duration.max"), "queue max")], unit="s", decimals=4),
    d.ts("DNS Query Errors by Type (qps)",
         "Consultas descartadas ou com erro por segundo, separadas por motivo: timed_out, wait_limit, ip_ratelimited, replyaddr_limit, cookie_invalid, discard_timeout, dns_error_reports, dnscrypt_malformed.\n"
         "• O que observar: deve permanecer em zero.\n"
         "• Ação em caso de problema: 'ip_ratelimited' ou 'replyaddr_limit' indicam cliente fazendo flood de DNS; 'timed_out' indica falha de conectividade externa.",
         [P(r("unbound.queries.errors", "", ERR_TYPE), "{{error.type}}")], unit="qps"),
    d.ts("DNS Request List Dropped / Overwritten (ops/s)",
         "Requisições recursivas descartadas (exceeded) ou sobrescritas (overwritten) por segundo porque a fila de recursão do Unbound encheu.\n"
         "• O que observar: deve ser sempre zero. Qualquer valor acima de zero significa clientes recebendo falha/timeout de DNS.\n"
         "• Ação em caso de problema: verificar a conectividade WAN e aumentar 'Number of Hosts to cache' / 'Outgoing Range' no Unbound.",
         [P(r("unbound.request_list.dropped", "", "reason"), "{{reason}}")], unit="ops"),
]

dns_inventory = [
    d.stat("Unbound Uptime",
           "Tempo desde a última inicialização ou reload do daemon Unbound DNS.\n"
           "• O que observar: crescimento contínuo; quedas frequentes indicam que o Unbound está sendo reiniciado (ex.: registro dinâmico de leases DHCP).\n"
           "• Ação em caso de problema: verificar os logs em Services > Unbound DNS > Log File.",
           P(g("unbound.uptime")), unit="s"),
    d.stat("Request List Max Seen",
           "Maior número de requisições recursivas simultâneas já registrado na fila do Unbound desde o início do processo.\n"
           "• O que observar: referência histórica de pico de concorrência DNS.\n"
           "• Ação em caso de problema: conferir 'total.requestlist.max' com 'unbound-control stats_noreset'.",
           P(g("unbound.request_list.limit")), decimals=0),
]

# =============================================================================
# 4. Linha Conectividade WAN, Ping & NTP
# =============================================================================
wan_health = [
    d.stat("Ping Target Status",
           "Disponibilidade de cada destino monitorado via ICMP Ping pelo firewall (UP = respondendo sem erro; DOWN = timeout ou falha de rota/DNS).\n"
           "• O que observar: todos os gateways e alvos externos (ex.: 1.1.1.1, gateway local) devem estar UP (verde).\n"
           "• Ação em caso de problema: testar no shell do OPNsense com 'ping -c 4 <destino>' e 'traceroute -n <destino>' e verificar System > Gateways > Single.",
           P(f'{g("network.ping.status", "", PEER)} == bool 0', "{{server.address}}"),
           thresholds=[(0, "red"), (1, "green")], names=True, updown=True),
    d.stat("Ping Packet Loss (%)",
           "Percentual de pacotes ICMP perdidos para cada destino monitorado.\n"
           "• O que observar: 0% (verde); acima de 1% (laranja) e 5% (vermelho) indica degradação do link WAN ou congestionamento no provedor.\n"
           "• Ação em caso de problema: comparar se a perda ocorre já no gateway local ou apenas nos alvos de internet para isolar LAN/provedor.",
           P(g("network.ping.packet_loss.ratio", "", PEER), "{{server.address}}"), unit="percentunit", decimals=1,
           thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")], names=True),
    d.stat("WAN Speedtest Packet Loss (%)",
           "Perda de pacotes medida durante o último teste de velocidade (Speedtest) da WAN.\n"
           "• O que observar: 0% (verde); acima de 1% (laranja) e 5% (vermelho) indica saturação de buffer (bufferbloat) ou perda sob carga na WAN.\n"
           "• Ação em caso de problema: configurar Traffic Shaper (FQ_CoDel) em Firewall > Shaper para mitigar bufferbloat sob carga.",
           P(gl("network.speedtest.packet_loss.ratio")), unit="percentunit", decimals=1,
           thresholds=[(0, "green"), (0.01, "orange"), (0.05, "red")]),
    d.stat("NTP Peer Reachability",
           "Indica se cada servidor NTP configurado está alcançável pelo daemon NTP do firewall (UP = registrador octal de alcance > 0; DOWN = 0, nenhuma resposta nas últimas 8 consultas).\n"
           "• O que observar: todos os peers devem estar UP (verde).\n"
           "• Ação em caso de problema: conferir 'ntpq -pn' no OPNsense e liberar UDP/123 de saída na WAN.",
           P(f'{g("ntp.reachability", "", PEER)} > bool 0', "{{server.address}}"),
           thresholds=[(0, "red"), (1, "green")], names=True, updown=True),
]

wan_capacity = [
    d.ts("WAN Speedtest - Bandwidth (bits/s)",
         "Largura de banda efetiva de download (receive) e upload (transmit) medida periodicamente pelo Speedtest no link WAN.\n"
         "• O que observar: estabilidade próxima à velocidade contratada com a operadora.\n"
         "• Ação em caso de problema: se houver queda sustentada sem tráfego concorrente em Network - Throughput, acionar a operadora.",
         [P(gl("network.speedtest.bandwidth", "", "direction"), "{{direction}}")], unit="bps"),
]

wan_activity = [
    d.ts("Ping - Packets Transmitted & Received (pkt/s)",
         "Taxa de pacotes de sondagem ICMP enviados (transmit) e recebidos (receive) por segundo para cada destino monitorado.\n"
         "• O que observar: 'transmit' e 'receive' sobrepostos para cada destino; divergência indica perda de pacotes.\n"
         "• Ação em caso de problema: correlacionar com Ping Packet Loss (%) no Health e Ping - RTT em Diagnostics.",
         [P(r("network.ping.packets", "", '"server.address", direction'),
            "{{server.address}} {{direction}}")], unit="pps"),
]

wan_diagnostics = [
    d.ts("Ping - RTT by Target (s)",
         "Latência de ida e volta (Round-Trip Time: min, avg, max, stddev) para cada destino monitorado via ICMP.\n"
         "• O que observar: gateway local abaixo de 2 ms; alvos de internet estáveis sem picos de desvio padrão (stddev).\n"
         "• Ação em caso de problema: executar 'mtr -rwc 20 <destino>' a partir do OPNsense para identificar em qual salto a latência aumenta.",
         [P(g("network.ping.rtt", "", '"server.address", stat'), "{{server.address}} {{stat}}")],
         unit="s", decimals=4),
    d.ts("WAN Speedtest - RTT & Jitter (s)",
         "Latência (RTT) e variação de latência (Jitter) até o servidor de Speedtest da WAN.\n"
         "• O que observar: jitter baixo (< 5 ms) e RTT consistente.\n"
         "• Ação em caso de problema: comparar com o Ping - RTT by Target no mesmo horário.",
         [P(gl("network.speedtest.rtt"), "RTT"),
          P(gl("network.speedtest.jitter"), "Jitter")], unit="s", decimals=4),
    d.ts("NTP - Offset, Delay & Jitter (s)",
         "Desvio do relógio local em relação a cada servidor NTP (offset), atraso de rede (delay) e variação (jitter), em segundos.\n"
         "• O que observar: offset próximo de zero (< 10 ms); offset elevado afeta validação de certificados TLS, logs e túnel IPsec/Kerberos.\n"
         "• Ação em caso de problema: verificar o peer ativo (*) com 'ntpq -pn' e reiniciar o serviço em Services > Network Time > General.",
         [P(g("ntp.offset", "", PEER), "offset {{server.address}}"),
          P(g("ntp.delay", "", PEER), "delay {{server.address}}"),
          P(g("ntp.jitter", "", PEER), "jitter {{server.address}}")], unit="s", decimals=4),
    d.ts("NTP - Last Sync Age & Reachability",
         "Tempo decorrido desde a última resposta recebida de cada servidor NTP (when/last_sync.age, em segundos) e registrador octal de alcance (377 = 8 de 8 respostas bem-sucedidas).\n"
         "• O que observar: 'last sync age' deve oscilar abaixo do intervalo de poll (ex.: 512 s) e 'reachability' deve permanecer em 377.\n"
         "• Ação em caso de problema: se 'last sync age' crescer indefinidamente e 'reachability' cair, substituir o servidor NTP inacessível.",
         [P(g("ntp.last_sync.age", "", PEER), "last sync age (s) {{server.address}}"),
          P(g("ntp.reachability", "", PEER), "reachability (octal) {{server.address}}")], decimals=0),
]

wan_inventory = [
    d.stat("Ping TTL by Target",
           "Time-To-Live (TTL) dos pacotes ICMP recebidos de cada destino monitorado.\n"
           "• O que observar: valor constante por destino; mudança abrupta de TTL indica alteração na rota BGP/OSPF até o destino.\n"
           "• Ação em caso de problema: conferir a rota atual com 'traceroute -n <destino>'.",
           P(g("network.ping.ttl", "", PEER), "{{server.address}}"), decimals=0, names=True),
    d.stat("NTP Poll Interval & Stratum",
           "Intervalo atual de consulta (poll, em segundos) para cada servidor NTP, exibindo no rótulo o stratum e a fonte de referência (ex.: .GPS., .ONBR.).\n"
           "• O que observar: servidores stratum 1 ou 2 com poll estabilizado (tipicamente 64 s a 1024 s).\n"
           "• Ação em caso de problema: conferir 'ntpq -pn' no OPNsense.",
           P(g("ntp.poll.interval", "", '"server.address", "ntp.stratum", "ntp.reference_id"'),
             "{{server.address}} (stratum {{ntp.stratum}} · {{ntp.reference_id}})"),
           unit="s", decimals=0, names=True),
    d.stat("Speedtest Server",
           "Servidor de referência utilizado pelo Speedtest da WAN (endereço, ID e modo do teste).\n"
           "• O que observar: servidor geograficamente próximo ao pop da operadora.\n"
           "• Ação em caso de problema: ajustar o Server ID na configuração do plugin Speedtest do OPNsense.",
           P('topk(1, %s)' % gl("network.speedtest.rtt", "", '"server.address", "speedtest.server.id", "speedtest.mode"'),
             "{{server.address}} (ID {{speedtest.server.id}} · {{speedtest.mode}})"), text=True),
]

d.row("FreeBSD & ZFS", [("Health", bsd_health, 3), ("Capacity", bsd_capacity, 1),
                        ("Activity", bsd_activity, 1), ("Diagnostics", bsd_diagnostics, 1),
                        ("Inventory", bsd_inventory, 4)])
d.row("Firewall (PF) & IPsec VPN", [("Health", fw_health, 2), ("Capacity", fw_capacity, 1),
                                    ("Activity", fw_activity, 1), ("Diagnostics", fw_diagnostics, 1),
                                    ("Inventory", fw_inventory, 2)])
d.row("DNS (Unbound)", [("Health", dns_health, 3), ("Capacity", dns_capacity, 1),
                        ("Activity", dns_activity, 1), ("Diagnostics", dns_diagnostics, 1),
                        ("Inventory", dns_inventory, 2)])
d.row("Conectividade WAN, Ping & NTP", [("Health", wan_health, 4), ("Capacity", wan_capacity, 1),
                                        ("Activity", wan_activity, 1), ("Diagnostics", wan_diagnostics, 1),
                                        ("Inventory", wan_inventory, 3)])
d.save(OUT)
