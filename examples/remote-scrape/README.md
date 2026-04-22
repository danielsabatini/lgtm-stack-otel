# Coleta Remota Defensiva (Pull Scrape)

Servidores legados não executam nativamente nosso Agent. Geralmente rodam instâncias do `node_exporter` ou `mysqld_exporter` bruto (que cospem milhares de sub-métricas inúteis quando recebem *request* HTTP na porta `9100` ou `9104`).

Esta pasta documenta como engatilhar o **Alloy Gateway** de forma modularizada puxando dados ativamente (Pull) e cortando o lixo via Regex (`metric_relabel`) durante o trajeto.

## Arquitetura Modularizada (conf.d)

Nossa configuração do *Gateway* no docker compose atua como um leitor de "Folder". Todos os arquivos listados na subpasta lógica `alloy-gateway/conf.d` serão compilados e amarrados pelo Grafana em tempo real como um único serviço gigantesco.

*   `00-core.alloy`: O Arquivo core que o Gateway usa para as pipelines OTLP.
*   `[X]-legacy.alloy` (Opcional): Cópias baseadas nos templates desta pasta (`examples/remote-scrape`). 

Sinta-se livre para clonar qualquer arquivo desta pasta (`pull-legacy-linux.alloy`, `pull-legacy-windows.alloy`, etc.) pra dentro do diretório `/alloy-gateway/conf.d/`.

*   `Não` existe *Network Discovery/Scan* oculto.
*   Você **precisa declarar** manual e explicitamente o range de Targets nos blocos.
*   Todo `prometheus.remote_write` deve apontar para `http://alloy-gateway:9999/api/v1/metrics/write`. **Nunca escreva diretamente em `mimir:9009`** — o gateway é o único ponto de entrada de ingestão.
