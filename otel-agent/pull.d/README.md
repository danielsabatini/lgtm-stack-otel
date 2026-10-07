# otel-agent/pull.d — coletas pull de servidores legados

Cada arquivo `*.yaml` deste diretório é carregado pelo `otel-agent` como
configuração adicional do OpenTelemetry Collector (mesclada ao `config.yaml`).
Use para servidores onde não é possível instalar o agente (ex.: só há
`node_exporter`): o `otel-agent` faz o scrape, converte para OTLP com a
identidade OpenTelemetry do servidor remoto e envia ao `otel-gateway`.

Os templates ficam em `examples/pull/<tipo>/` — copie para cá, ajuste os
alvos e reinicie: `docker compose restart otel-agent`.

Os arquivos `*.yaml` daqui contêm IPs/nomes do ambiente e não são versionados
(ver `.gitignore`).
