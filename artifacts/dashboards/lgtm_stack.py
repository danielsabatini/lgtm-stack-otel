"""LGTM Stack Self-Monitoring: pipeline OpenTelemetry (Gateway e agentes), containers
da stack (docker_stats) e o servidor da stack (mesmas abas do Linux Hosts)."""
import sys
from lib import Dash
from hosts import host_tabs, logs_tab

OUT = sys.argv[1]
d = Dash("lgtm-stack", "LGTM Stack Self-Monitoring", ["lgtm", "self-monitoring", "opentelemetry", "containers"])
P = d.prom
DEDUP = "max without (otel_scope_name, otel_scope_version)"
COL = '"service.name", "host.name"'
LCOL = "{{service.name}} {{host.name}}"
C = '"host.name"="$host", "container.name"=~"$container"'


def rate(sel, by):
    return "sum by (%s) (%s (rate(%s[$__rate_interval])))" % (by, DEDUP, sel)


def gauge(sel, by):
    return "max by (%s) (%s)" % (by, sel)


def total(regex):
    """Total no período de contadores que só existem quando há eventos (zero se ausentes)."""
    return 'sum(%s (increase({__name__=~"%s"}[$__range]))) or vector(0)' % (DEDUP, regex)


d.query_var("host", "Servidor da stack", 'query_result(count by ("host.name") ({"container.cpu.usage.total"}))',
            '/host\\.name="([^"]+)"/')
d.variables.append({"kind": "QueryVariable", "spec": {
    "name": "container", "label": "Container", "hide": "dontHide", "refresh": "onTimeRangeChanged",
    "skipUrlSync": False, "current": {"text": ["All"], "value": ["$__all"]},
    "query": {"kind": "DataQuery", "group": "prometheus", "version": "v0", "datasource": {"name": "mimir"},
              "spec": {"qryType": 3, "refId": "PrometheusVariableQueryEditor-VariableQuery",
                       "query": 'query_result(count by ("container.name") ({"container.cpu.usage.total", "host.name"="$host"}))'}},
    "definition": 'query_result(count by ("container.name") ({"container.cpu.usage.total", "host.name"="$host"}))',
    "regex": '/container\\.name="([^"]+)"/', "regexApplyTo": "value", "sort": "alphabeticalAsc",
    "options": [], "multi": True, "includeAll": True, "allowCustomValue": False}})

# ------------------------------------------------------- Pipeline OpenTelemetry
def ratio(bad, good):
    """bad / (good + bad) somando todos os coletores (0 quando não há eventos de falha)."""
    b = 'sum(%s (rate({__name__=~"%s"}[$__rate_interval])))' % (DEDUP, bad)
    g = 'sum(%s (rate({__name__=~"%s"}[$__rate_interval])))' % (DEDUP, good)
    return "(%s / clamp_min(%s + %s, 1e-9)) or vector(0)" % (b, g, b)


p_health = [
    d.stat("Dados Recusados (%)",
           "Percentual dos itens (métricas, logs e spans) recusados pelos receivers sobre o total recebido — em geral pelo memory_limiter, quando o coletor está sem memória.\n"
           "• O que observar: deve ser 0%. Recusas significam perda de dados na origem (o cliente pode reenviar).\n"
           "• Ação em caso de problema: ver em Diagnostics qual coletor/receiver recusa e a memória dele em Capacity; avaliar os limites de memória do coletor.",
           P(ratio("otelcol_receiver_refused_.+", "otelcol_receiver_accepted_.+")), unit="percentunit", decimals=2,
           thresholds=[(0, "green"), (0.0001, "orange"), (0.01, "red")]),
    d.stat("Falhas de Envio (%)",
           "Percentual dos itens que os exporters não conseguiram enviar (agentes → Gateway, Gateway → Mimir/Loki/Tempo) após esgotar as tentativas, sobre o total enviado.\n"
           "• O que observar: deve ser 0%. Falhas significam perda definitiva de dados.\n"
           "• Ação em caso de problema: conferir conectividade e o estado do destino (docker compose ps; logs do otel-gateway e do backend).",
           P(ratio("otelcol_exporter_send_failed_.+", "otelcol_exporter_sent_.+")), unit="percentunit", decimals=2,
           thresholds=[(0, "green"), (0.0001, "orange"), (0.01, "red")]),
    d.gauge("Fila de Exportação (pico %)",
            "Ocupação da fila de reenvio mais cheia entre todos os exporters (lotes na fila / capacidade).\n"
            "• O que observar: perto de zero em operação normal. Fila crescendo indica destino lento ou indisponível; cheia, novos dados são descartados.\n"
            "• Ação em caso de problema: ver em Diagnostics qual exporter enche a fila e verificar o destino (Gateway ou backend).",
            P('max(%s ({"otelcol_exporter_queue_size"}) / %s ({"otelcol_exporter_queue_capacity"}))' % (DEDUP, DEDUP)),
            steps=(50, 80, 90)),
]
p_activity = [
    d.ts("Recebido por Coletor (itens/s)",
         "Itens aceitos pelos receivers de cada coletor, por sinal (pontos de métrica, registros de log e spans).\n"
         "• O que observar: estabilidade; quedas a zero indicam fonte parada, e no Gateway, agentes sem conectividade.\n"
         "• Ação em caso de problema: comparar com 'Enviado por Coletor' e conferir os logs do coletor afetado.",
         [P(rate('{"otelcol_receiver_accepted_metric_points"}', COL), "métricas " + LCOL),
          P(rate('{"otelcol_receiver_accepted_log_records"}', COL), "logs " + LCOL),
          P(rate('{"otelcol_receiver_accepted_spans"}', COL), "spans " + LCOL)], unit="ops"),
    d.ts("Enviado por Coletor (itens/s)",
         "Itens enviados com sucesso pelos exporters de cada coletor (agentes → Gateway; Gateway → backends).\n"
         "• O que observar: deve acompanhar o recebido (descontados filtros e o tail sampling de traces no Gateway).\n"
         "• Ação em caso de problema: diferença persistente entre recebido e enviado indica filtro descartando, fila acumulando ou falhas de envio.",
         [P(rate('{"otelcol_exporter_sent_metric_points"}', COL), "métricas " + LCOL),
          P(rate('{"otelcol_exporter_sent_log_records"}', COL), "logs " + LCOL),
          P(rate('{"otelcol_exporter_sent_spans"}', COL), "spans " + LCOL)], unit="ops"),
]
p_diag = [
    d.ts("Recusados e Falhos por Receiver (itens/s)",
         "Itens recusados (refused: memory_limiter) ou com falha (failed: erro no pipeline) por receiver.\n"
         "• O que observar: deve ser zero.\n"
         "• Ação em caso de problema: recusas → memória do coletor; falhas → logs do coletor (erro de processor/exporter).",
         [P(rate('{__name__=~"otelcol_receiver_refused_.+"}', COL + ", receiver"), "refused {{receiver}} " + LCOL),
          P(rate('{__name__=~"otelcol_receiver_failed_.+"}', COL + ", receiver"), "failed {{receiver}} " + LCOL)],
         unit="ops"),
    d.ts("Falhas de Envio por Exporter (itens/s)",
         "Itens descartados por exporter após esgotar as tentativas de reenvio.\n"
         "• O que observar: deve ser zero.\n"
         "• Ação em caso de problema: verificar o destino do exporter (otlp_grpc/gateway → Gateway; otlp_http/mimir, otlp_http/loki, otlp_grpc/tempo → backends).",
         [P(rate('{__name__=~"otelcol_exporter_send_failed_.+"}', COL + ", exporter"), "{{exporter}} " + LCOL)],
         unit="ops"),
    d.ts("Fila de Exportação (lotes)",
         "Lotes aguardando envio na fila de reenvio de cada exporter, comparados com a capacidade (linha tracejada).\n"
         "• O que observar: perto de zero; crescimento indica destino lento ou fora do ar.\n"
         "• Ação em caso de problema: verificar o destino e a rede; a fila absorve indisponibilidades curtas sem perda.",
         [P(gauge('%s ({"otelcol_exporter_queue_size"})' % DEDUP, COL + ", exporter, data_type"),
            "{{exporter}} {{data_type}} " + LCOL),
          P('max(%s ({"otelcol_exporter_queue_capacity"}))' % DEDUP, "Capacidade (Limite)")], decimals=0),
    d.ts("Erros de Coleta por Scraper (pontos/s)",
         "Pontos que os scrapers (host_metrics, docker_stats, receivers de banco) não conseguiram coletar.\n"
         "• O que observar: deve ser zero; erros indicam permissão, alvo fora do ar ou credencial inválida.\n"
         "• Ação em caso de problema: conferir os logs do coletor do host indicado.",
         [P(rate('{"otelcol_scraper_errored_metric_points"}', COL + ", receiver, scraper"),
            "{{receiver}} {{scraper}} " + LCOL)], unit="ops"),
    d.ts("Tail Sampling — Traces em Memória",
         "Traces aguardando a decisão de amostragem no Gateway (decision_wait) e traces descartados antes da decisão por falta de espaço (num_traces).\n"
         "• O que observar: valor estável; descartes antes da decisão significam num_traces pequeno para o volume.\n"
         "• Ação em caso de problema: aumentar num_traces no tail_sampling do otel-gateway/config.yaml ou a memória do Gateway.",
         [P('max(%s ({"otelcol_processor_tail_sampling_sampling_traces_on_memory"}))' % DEDUP, "em memória"),
          P('sum(%s (rate({"otelcol_processor_tail_sampling_sampling_trace_dropped_too_early"}[$__rate_interval])))' % DEDUP,
            "descartados antes da decisão (/s)")], decimals=0),
    d.ts("Tail Sampling — Avaliações por Política (/s)",
         "Execuções de cada política de amostragem do Gateway: keep-errors (erros), keep-slow (> 1 s) e sample-ok (5% dos demais).\n"
         "• O que observar: as três políticas avaliando traces quando há tráfego; erros de avaliação devem ser zero.\n"
         "• Ação em caso de problema: conferir as políticas em otel-gateway/config.yaml e os logs do otel-gateway.",
         [P(rate('{"otelcol_processor_tail_sampling_sampling_policy_execution_count"}', "policy"), "{{policy}}"),
          P(rate('{"otelcol_processor_tail_sampling_sampling_policy_evaluation_error"}', "policy"), "erros {{policy}}")],
         unit="ops"),
]
p_cap = [
    d.ts("Memória por Coletor (RSS)",
         "Memória física usada por cada coletor.\n"
         "• O que observar: estável após o aquecimento; crescimento contínuo indica fila acumulando ou volume acima do dimensionado. O memory_limiter recusa dados ao se aproximar do limite.\n"
         "• Ação em caso de problema: ver a fila de exportação em Diagnostics e o volume recebido em Activity.",
         [P(gauge('%s ({"otelcol_process_memory_rss"})' % DEDUP, COL), LCOL)], unit="bytes"),
    d.ts("CPU por Coletor (cores)",
         "CPU consumida por cada coletor, em núcleos.\n"
         "• O que observar: proporcional ao volume recebido; picos sustentados indicam processamento pesado (transformações, tail sampling).\n"
         "• Ação em caso de problema: comparar com o volume em Activity e com o limite de CPU do container.",
         [P(rate('{"otelcol_process_cpu_seconds"}', COL), LCOL)], decimals=3),
]
p_inv = [
    d.stat("Coletores Ativos",
           "Coletores OpenTelemetry (Gateway e agentes, inclusive dos hosts monitorados) enviando a própria telemetria.\n"
           "• O que observar: deve corresponder ao número de agentes instalados + o Gateway; uma queda indica coletor parado ou sem conectividade com o Gateway.\n"
           "• Ação em caso de problema: no host, 'systemctl status otelcol-contrib' (Linux) ou 'Get-Service otelcol-contrib' (Windows); na stack, 'docker compose ps'.",
           P('count(%s ({"otelcol_process_uptime"}))' % DEDUP), decimals=0),
    d.stat("Coletores",
           "Coletores OpenTelemetry com host e versão (target_info da telemetria interna).\n"
           "• O que observar: todos na mesma versão homologada (OTELCOL_CONTRIB_VERSION).\n"
           "• Ação em caso de problema: atualizar os agentes divergentes seguindo docs/UPGRADE.md.",
           P('max by ("service.name", "host.name", "service.version") ({"target_info", "service.name"=~"otel-.+"})',
             "{{service.name}} {{host.name}} v{{service.version}}"), text=True),
    d.stat("Uptime por Coletor",
           "Tempo desde o último início de cada coletor.\n"
           "• O que observar: reinícios inesperados (uptime baixo) indicam falha ou OOM.\n"
           "• Ação em caso de problema: conferir o journal/Event Log do coletor e a memória em Capacity.",
           P(gauge('%s ({"otelcol_process_uptime"})' % DEDUP, COL), LCOL), unit="s", names=True),
]

# ------------------------------------------------------------------- Containers
CPU_HOST = 'scalar(max({"system.cpu.logical.count", "host.name"="$host"}))'
c_health = [
    d.stat("CPU por Container (% do host)",
           "CPU usada por cada container como fração do total de CPUs do servidor da stack.\n"
           "• O que observar: Mimir, Loki e Tempo dominam em carga; picos sustentados indicam compactação ou consultas pesadas.\n"
           "• Ação em caso de problema: 'docker stats' e os logs do container; ver throttling em Diagnostics.",
           P('sum by ("container.name") (%s (rate({"container.cpu.usage.total", %s}[$__rate_interval]))) / 1e9 / %s'
             % (DEDUP, C, CPU_HOST), "{{container.name}}"), unit="percentunit", decimals=1, names=True),
    d.stat("Memória por Container (% do limite)",
           "Memória usada por cada container sobre o limite configurado no compose.yaml (.env).\n"
           "• O que observar: abaixo de 80%. No limite, o kernel encerra o container (OOM).\n"
           "• Ação em caso de problema: ajustar o limite no .env (ver docs/SIZING.md) ou investigar o consumo do serviço.",
           P('max by ("container.name") (%s ({"container.memory.usage.total", %s})) / max by ("container.name") (%s ({"container.memory.usage.limit", %s}))'
             % (DEDUP, C, DEDUP, C), "{{container.name}}"), unit="percentunit", decimals=1, names=True,
           thresholds=[(0, "green"), (0.8, "orange"), (0.9, "red")]),
]
c_cap = [
    d.ts("CPU por Container (cores)",
         "CPU usada por container, em núcleos.\n"
         "• O que observar: comparar com o limite de CPU de cada serviço no .env.\n"
         "• Ação em caso de problema: ver throttling abaixo e avaliar o limite.",
         [P('sum by ("container.name") (%s (rate({"container.cpu.usage.total", %s}[$__rate_interval]))) / 1e9'
            % (DEDUP, C), "{{container.name}}")], decimals=3),
    d.ts("Memória por Container (bytes)",
         "Memória usada por container (sem cache) e o limite de cada um (linhas tracejadas).\n"
         "• O que observar: distância do limite; crescimento contínuo pode indicar retenção ou cardinalidade alta.\n"
         "• Ação em caso de problema: ver docs/SIZING.md e o limite no .env.",
         [P(gauge('%s ({"container.memory.usage.total", %s})' % (DEDUP, C), '"container.name"'), "{{container.name}}"),
          P(gauge('%s ({"container.memory.usage.limit", %s})' % (DEDUP, C), '"container.name"'),
            "{{container.name}} (Limite)")], unit="bytes"),
]
c_act = [
    d.ts("Rede por Container (bytes/s)",
         "Tráfego recebido e enviado por container.\n"
         "• O que observar: o otel-gateway recebe todo o tráfego OTLP; Mimir/Loki/Tempo recebem do Gateway e respondem ao Grafana.\n"
         "• Ação em caso de problema: picos fora do padrão indicam cliente enviando volume anormal ou consultas pesadas.",
         [P(rate('{"container.network.io.usage.rx_bytes", %s}' % C, '"container.name"'), "rx {{container.name}}"),
          P(rate('{"container.network.io.usage.tx_bytes", %s}' % C, '"container.name"'), "tx {{container.name}}")],
         unit="Bps"),
]
c_diag = [
    d.ts("CPU Throttling por Container (%)",
         "Fração dos períodos de agendamento em que o container foi limitado pelo teto de CPU.\n"
         "• O que observar: deve ficar próximo de zero; throttling alto deixa o serviço lento (consultas, ingestão).\n"
         "• Ação em caso de problema: aumentar o limite de CPU do serviço no .env.",
         [P('%s / clamp_min(%s, 1e-9)' % (
             rate('{"container.cpu.throttling_data.throttled_periods", %s}' % C, '"container.name"'),
             rate('{"container.cpu.throttling_data.periods", %s}' % C, '"container.name"')), "{{container.name}}")],
         unit="percentunit", mx=1),
]
c_inv = [
    d.stat("Containers",
           "Containers do servidor da stack e a imagem de cada um.\n"
           "• O que observar: versões iguais às pinadas no .env.\n"
           "• Ação em caso de problema: 'docker compose pull && docker compose up -d' (ver docs/UPGRADE.md).",
           P('max by ("container.name", "container.image.name") ({"container.memory.usage.total", %s})' % C,
             "{{container.name}}: {{container.image.name}}"), text=True),
]
c_logs = [d.logs("Logs dos Containers",
                 "Logs dos containers do compose a partir de WARN (e linhas sem nível reconhecido).\n"
                 "• O que observar: erros recorrentes de um mesmo serviço (container_name).\n"
                 "• Ação em caso de problema: 'docker logs <container>' para o contexto completo.",
                 '{host_name="$host", container_name=~"$container"}')]

d.row("Pipeline OpenTelemetry", [("Health", p_health, 4), ("Capacity", p_cap, 1), ("Activity", p_activity, 1),
                                 ("Diagnostics", p_diag, 1), ("Inventory", p_inv, 1)])
d.row("Containers", [("Health", c_health, 1), ("Capacity", c_cap, 1), ("Activity", c_act, 1),
                     ("Diagnostics", c_diag, 1), ("Inventory", c_inv, 1), ("Logs", c_logs, 1)])
d.row("Servidor da Stack", host_tabs(d, "linux") + [logs_tab(d, "linux")])
d.save(OUT)
