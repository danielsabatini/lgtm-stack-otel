#!/bin/bash
# =============================================================================
# LGTM Stack - Gerador de carga para a cadeia demo (frontend -> middleware ->
# backend, ver ../app/tier.py) usada para validar traces distribuídos via
# OBI (eBPF).
#
# Sem isto, o painel "Distributed Traces" só mostra dado durante a janela em
# que alguém chamou a cadeia manualmente (curl), e volta a ficar vazio assim
# que esse trace sai da janela de tempo selecionada no Grafana — o que parece
# "trace não chega" sem ser um problema real de pipeline.
#
# Mistura de rotas: majoritariamente "/" (sucesso), com uma fração de "/slow"
# (>1000ms, exercita a política keep-slow do tail sampling do gateway) e
# "/error" (500, exercita keep-errors). Ver otel-gateway/config.yaml (tail_sampling).
#
# Uso:
#   ./demo-load-test.sh                roda até Ctrl-C com os padrões
#   QPS=5 ./demo-load-test.sh          5 requisições/segundo
#   DURATION=600 ./demo-load-test.sh   para sozinho após 10 min
#
# Variáveis: QPS, DURATION (0 = infinito), TARGET
# =============================================================================

set -uo pipefail

QPS="${QPS:-2}"
DURATION="${DURATION:-0}"
TARGET="${TARGET:-http://localhost:8080}"

CYCLE_SECONDS=1
PER_CYCLE="$QPS"

cleanup() { echo; echo "encerrado."; }
trap cleanup EXIT INT TERM

echo "gerador de carga demo — alvo ${TARGET}"
echo "  taxa    : ${QPS} req/s"
echo "  duração : $([ "$DURATION" -eq 0 ] && echo "indefinida" || echo "${DURATION}s")"
echo

START="$(date +%s)"
CYCLES=0

pick_route() {
  local r=$((RANDOM % 100))
  # 80% sucesso, 12% lento (>1000ms), 8% erro
  if [ "$r" -lt 80 ]; then
    echo "/"
  elif [ "$r" -lt 92 ]; then
    echo "/slow"
  else
    echo "/error"
  fi
}

while true; do
  cycle_start="$(date +%s)"

  for ((i = 0; i < PER_CYCLE; i++)); do
    curl -s -o /dev/null -m 5 "${TARGET}$(pick_route)" &
  done
  wait

  CYCLES=$((CYCLES + 1))
  now="$(date +%s)"
  if [ $((CYCLES % 30)) -eq 0 ]; then
    printf '[%s] ciclos=%d requisicoes~=%d\n' "$(date +%H:%M:%S)" "$CYCLES" "$((CYCLES * PER_CYCLE))"
  fi

  [ "$DURATION" -gt 0 ] && [ $((now - START)) -ge "$DURATION" ] && break

  elapsed=$((now - cycle_start))
  [ "$elapsed" -lt "$CYCLE_SECONDS" ] && sleep $((CYCLE_SECONDS - elapsed))
done
