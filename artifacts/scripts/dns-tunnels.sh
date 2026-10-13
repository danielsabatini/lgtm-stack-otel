#!/bin/bash
# =============================================================================
# LGTM Stack - Túneis SSH para os hosts de DNS interno (br-ne1)
#
# Os três hosts de DNS ficam em rede privada, alcançáveis só pelo bastion.
# O otel-agent (rede do host) coleta via "host.docker.internal:<porta>", então
# cada endpoint remoto precisa de um forward local com porta única.
#
# O mapa de portas abaixo é a contraparte dos alvos de otel-agent/pull.d/dns-hosts.yaml:
# mudar uma porta aqui exige mudar o alvo correspondente lá, senão o scrape
# falha silenciosamente (up=0) e o dashboard fica cego sem erro visível.
# Alternativa sem túnel por porta: proxy SOCKS (ver examples/pull/dns/INSTALL.md).
#
# Convenção: <n><porta-original>, onde <n> é o número do nó.
# A porta 2380 é deliberadamente evitada — é a porta de peer do etcd, e reusá-la
# localmente confundiria quem fosse depurar o cluster depois.
#
# Uso:
#   ./dns-tunnels.sh up       sobe os túneis que estiverem faltando
#   ./dns-tunnels.sh down     derruba todos
#   ./dns-tunnels.sh status   mostra o estado de cada porta (padrão)
#   ./dns-tunnels.sh restart  down + up
# =============================================================================

set -uo pipefail

SSH_USER="ubuntu"

# nome:ip:porta_local_node:porta_local_coredns:porta_local_etcd
HOSTS=(
  "dns-ne1-1:172.18.0.50:19100:19153:12379"
  "dns-ne1-2:172.18.16.50:29100:29153:22379"
  "dns-ne1-3:172.18.16.51:39100:39153:32379"
)

# Portas de origem no host remoto. Todas escutam em 127.0.0.1 lá.
R_NODE=9100
R_COREDNS=9153
R_ETCD=2379

# -----------------------------------------------------------------------------

# Casa o processo pelo IP de destino em vez de por PID: sobrevive a reboot do
# terminal e não depende de arquivo de estado que possa ficar órfão.
tunnel_pid() {
  pgrep -f "ssh -f -N .*${1}\$" 2>/dev/null | head -1
}

port_open() {
  nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}

do_up() {
  local rc=0
  for entry in "${HOSTS[@]}"; do
    IFS=':' read -r name ip p_node p_coredns p_etcd <<<"$entry"

    if [ -n "$(tunnel_pid "$ip")" ]; then
      echo "  $name  já ativo"
      continue
    fi

    # ExitOnForwardFailure impede o caso mais traiçoeiro: o ssh conectar mas
    # falhar o bind de uma das portas, deixando um túnel parcial de pé — o
    # scrape daquele serviço falharia enquanto os outros dois funcionariam.
    if ssh -f -N \
      -o ExitOnForwardFailure=yes \
      -o BatchMode=yes \
      -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=3 \
      -L "${p_node}:127.0.0.1:${R_NODE}" \
      -L "${p_coredns}:127.0.0.1:${R_COREDNS}" \
      -L "${p_etcd}:127.0.0.1:${R_ETCD}" \
      "${SSH_USER}@${ip}" </dev/null >/dev/null 2>&1
    then
      echo "  $name  OK    ${p_node} / ${p_coredns} / ${p_etcd}"
    else
      echo "  $name  FALHOU (${ip})"
      rc=1
    fi
  done
  return $rc
}

do_down() {
  for entry in "${HOSTS[@]}"; do
    IFS=':' read -r name ip _ <<<"$entry"
    local pid
    pid="$(tunnel_pid "$ip")"
    if [ -n "$pid" ]; then
      kill "$pid" && echo "  $name  encerrado (pid $pid)"
    else
      echo "  $name  já parado"
    fi
  done
}

do_status() {
  local rc=0
  for entry in "${HOSTS[@]}"; do
    IFS=':' read -r name ip p_node p_coredns p_etcd <<<"$entry"
    printf '  %-10s %-14s' "$name" "$ip"
    for pair in "node:${p_node}" "coredns:${p_coredns}" "etcd:${p_etcd}"; do
      svc="${pair%%:*}"; port="${pair##*:}"
      if port_open "$port"; then
        printf ' %s:%s=on' "$svc" "$port"
      else
        printf ' %s:%s=OFF' "$svc" "$port"
        rc=1
      fi
    done
    printf '\n'
  done
  return $rc
}

case "${1:-status}" in
  up)      echo "--- subindo túneis DNS ---";    do_up ;;
  down)    echo "--- derrubando túneis DNS ---"; do_down ;;
  restart) echo "--- reiniciando túneis DNS ---"; do_down; sleep 1; do_up ;;
  status)  echo "--- estado dos túneis DNS ---"; do_status ;;
  *)       echo "uso: $0 {up|down|restart|status}" >&2; exit 2 ;;
esac
