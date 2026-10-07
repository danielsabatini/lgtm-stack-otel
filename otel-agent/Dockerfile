# =============================================================================
# otel-agent — OpenTelemetry Collector Contrib + journalctl
# =============================================================================
# A imagem oficial otel/opentelemetry-collector-contrib é "scratch" (sem shell
# nem journalctl), e o receiver journald depende do binário journalctl. Esta
# imagem apenas copia o binário oficial (mesma versão pinada no .env) para um
# Debian slim com journalctl — nenhuma alteração no Collector. O entrypoint
# só monta a lista de arquivos de configuração (config.yaml + pull.d/*.yaml).
# =============================================================================

ARG OTELCOL_CONTRIB_VERSION=0.162.0
ARG DEBIAN_VERSION=trixie-slim

FROM otel/opentelemetry-collector-contrib:${OTELCOL_CONTRIB_VERSION} AS otelcol

FROM debian:${DEBIAN_VERSION}

# journalctl (pacote systemd) para o receiver journald; ca-certificates para TLS.
RUN apt-get update \
 && apt-get install -y --no-install-recommends systemd ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=otelcol /otelcol-contrib /otelcol-contrib

# Carrega config.yaml + pull.d/*.yaml (coletas pull de servidores legados).
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
