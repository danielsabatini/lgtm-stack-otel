#!/bin/bash
# =============================================================================
# LGTM Stack - Teste de carga para a solução de DNS interno (CoreDNS + etcd)
#
# Gera carga realista nos três pilares que o dashboard MGC Internal DNS Solution
# observa: consultas DNS, escrita/remoção de registros no etcd e resolução
# externa via forward.
#
# DECISÃO DE DESENHO — cada nó consulta os TRÊS servidores pela rede, nunca
# só 127.0.0.1. O teste anterior usava exclusivamente loopback, e isso criava
# um ponto cego: um bloqueio de firewall na porta 53 deixaria o painel Query
# Rate verde, porque tráfego de loopback não atravessa firewall. Consultando os
# vizinhos pela rede, o painel passa a refletir alcançabilidade real.
#
# Tipos de registro exercitados: A, AAAA, CNAME, TXT, MX, SRV.
# NS fica de fora de propósito: foi verificado empiricamente que o plugin etcd
# nesta configuração responde NXDOMAIN para NS no apex — incluí-lo geraria
# "erro" permanente no dashboard sem nenhum defeito real por trás.
#
# Uso:
#   ./dns-load-test.sh                 roda até Ctrl-C com os padrões
#   QPS=50 ./dns-load-test.sh          50 consultas/segundo
#   DURATION=600 ./dns-load-test.sh    para sozinho após 10 min
#
# Variáveis: QPS, DURATION (0 = infinito), POOL_MAX, CREATE_PER_CYCLE,
#            DELETE_PER_CYCLE, SERVERS, ETCD_ENDPOINT
# =============================================================================

set -uo pipefail

QPS="${QPS:-20}"
DURATION="${DURATION:-0}"
POOL_MAX="${POOL_MAX:-400}"
CREATE_PER_CYCLE="${CREATE_PER_CYCLE:-6}"
DELETE_PER_CYCLE="${DELETE_PER_CYCLE:-3}"
CYCLE_SECONDS=5

SERVERS="${SERVERS:-172.18.0.50 172.18.16.50 172.18.16.51}"
ETCD_ENDPOINT="${ETCD_ENDPOINT:-http://127.0.0.1:2379}"
ETCD_PATH="/dns"

STATE_DIR="${STATE_DIR:-/var/lib/dns-loadtest}"
POOL="${STATE_DIR}/pool"       # registros vivos:    nome<TAB>tipo
GRAVE="${STATE_DIR}/graveyard" # apagados recentes:  nome<TAB>tipo
SEQ_FILE="${STATE_DIR}/seq"

# Sufixo por nó para que os três não disputem as mesmas chaves no etcd, que é
# compartilhado. Sem isso um nó apagaria registros que outro acabou de criar e
# o teste geraria NXDOMAIN espúrio, indistinguível de defeito real.
NODE_ID="$(hostname | grep -oE '[0-9]+$' || echo 0)"

# zona -> caminho da chave no etcd (labels DNS invertidos sob ETCD_PATH)
ZONES=("ne1.cloud.internal" "a.ne1.cloud.internal" "b.ne1.cloud.internal")
zone_path() {
  case "$1" in
    ne1.cloud.internal)   echo "${ETCD_PATH}/internal/cloud/ne1" ;;
    a.ne1.cloud.internal) echo "${ETCD_PATH}/internal/cloud/ne1/a" ;;
    b.ne1.cloud.internal) echo "${ETCD_PATH}/internal/cloud/ne1/b" ;;
  esac
}

TYPES=(A AAAA CNAME TXT MX SRV)

# Alvos do bloco "." (forward para os resolvers recursivos da nuvem MGC / upstream)
EXT_DOMAINS=(google.com cloudflare.com github.com magalu.com debian.org
             wikipedia.org amazon.com microsoft.com ubuntu.com grafana.com
             magalucloud.com.br pypi.org docker.io npmjs.org)
EXT_SUBS=(www.google.com api.github.com raw.githubusercontent.com
          registry.npmjs.org deb.debian.org docs.grafana.com
          registry-1.docker.io pypi.org archive.ubuntu.com api.magalucloud.com.br)
EXT_TYPES=(A A A AAAA MX)

mkdir -p "$STATE_DIR"
: >>"$POOL"; : >>"$GRAVE"
[ -s "$SEQ_FILE" ] || echo 0 >"$SEQ_FILE"

etcd() { etcdctl --endpoints="$ETCD_ENDPOINT" "$@" >/dev/null 2>&1; }

next_seq() {
  local n
  n=$(( $(cat "$SEQ_FILE") + 1 ))
  echo "$n" >"$SEQ_FILE"
  echo "$n"
}

# --- criação -----------------------------------------------------------------
create_record() {
  local seq zone base type name key value
  seq="$(next_seq)"
  zone="${ZONES[$((RANDOM % ${#ZONES[@]}))]}"
  base="$(zone_path "$zone")"
  type="${TYPES[$((RANDOM % ${#TYPES[@]}))]}"
  local short="lt${NODE_ID}-${seq}"

  case "$type" in
    A)
      name="${short}.${zone}"; key="${base}/${short}"
      value="{\"host\":\"10.$((RANDOM % 250)).$((RANDOM % 250)).$((RANDOM % 250))\",\"ttl\":30}" ;;
    AAAA)
      name="${short}.${zone}"; key="${base}/${short}"
      value="{\"host\":\"2001:db8::$(printf '%x' $((RANDOM % 65535)))\",\"ttl\":30}" ;;
    CNAME)
      name="${short}.${zone}"; key="${base}/${short}"
      value="{\"host\":\"alvo.${zone}\",\"ttl\":30}" ;;
    TXT)
      name="${short}.${zone}"; key="${base}/${short}"
      value="{\"text\":\"carga-lgtm seq=${seq} node=${NODE_ID}\",\"ttl\":30}" ;;
    MX)
      name="${short}.${zone}"; key="${base}/${short}"
      value="{\"host\":\"mail.${zone}\",\"mail\":true,\"priority\":$((10 + RANDOM % 40)),\"ttl\":30}" ;;
    SRV)
      # SRV inverte os labels de serviço junto com os da zona:
      # _svc-N._tcp.<zona> vira <base>/_tcp/_svc-N
      name="_svc-${short}._tcp.${zone}"; key="${base}/_tcp/_svc-${short}/s1"
      value="{\"host\":\"alvo.${zone}\",\"port\":$((1024 + RANDOM % 60000)),\"priority\":10,\"weight\":20,\"ttl\":30}" ;;
  esac

  if etcd put "$key" "$value"; then
    printf '%s\t%s\t%s\n' "$name" "$type" "$key" >>"$POOL"
  fi
}

# --- remoção -----------------------------------------------------------------
delete_record() {
  local line name type key
  # Apaga o mais antigo: gera um ciclo de vida realista (criado, consultado
  # algumas vezes, depois removido) em vez de churn puramente aleatório.
  line="$(head -1 "$POOL")"
  [ -z "$line" ] && return
  IFS=$'\t' read -r name type key <<<"$line"
  etcd del "$key"
  sed -i '1d' "$POOL"
  printf '%s\t%s\n' "$name" "$type" >>"$GRAVE"
  # cemitério limitado: só interessa consultar remoção recente, para exercitar
  # o cache de negativas enquanto a entrada ainda pode estar lá
  tail -200 "$GRAVE" >"${GRAVE}.tmp" && mv "${GRAVE}.tmp" "$GRAVE"
}

# --- montagem do lote de consultas -------------------------------------------
# Mistura calibrada para refletir o tráfego corporativo real e exercitar os painéis:
#   60% acerto etcd -> Query Rate, latência interna (<15ms), cache hit (>85%)
#   10% inexistente e 5% apagado -> NXDOMAIN interno e cache de negativas
#   20% forward externo legítimo -> resolução recursiva de serviços e APIs da nuvem
#    5% estático -> exercita o plugin file na zona cloud.internal
build_batch() {
  local total="$1" out="$2" i r
  : >"$out"
  local pool_n grave_n
  pool_n=$(wc -l <"$POOL")
  grave_n=$(wc -l <"$GRAVE")

  for ((i = 0; i < total; i++)); do
    r=$((RANDOM % 100))
    if [ "$r" -lt 60 ] && [ "$pool_n" -gt 0 ]; then
      awk -v n=$((RANDOM % pool_n + 1)) 'NR==n{print $1" "$2}' "$POOL" >>"$out"
    elif [ "$r" -lt 70 ]; then
      # Distribui os inexistentes entre as três zonas internas.
      echo "nao-existe-$RANDOM.${ZONES[$((RANDOM % ${#ZONES[@]}))]} A" >>"$out"
    elif [ "$r" -lt 75 ] && [ "$grave_n" -gt 0 ]; then
      awk -v n=$((RANDOM % grave_n + 1)) 'NR==n{print $1" "$2}' "$GRAVE" >>"$out"
    elif [ "$r" -lt 95 ]; then
      # Forward externo: distribuição realista de tráfego de saída
      #   - 70% domínios populares frequentes (exercita cache local + upstream)
      #   - 25% subdomínios e APIs externas legítimas
      #   - 5%  NXDOMAIN externo esporádico (sem bombardear os resolvers)
      local e=$((RANDOM % 100))
      if [ "$e" -lt 70 ]; then
        echo "${EXT_DOMAINS[$((RANDOM % ${#EXT_DOMAINS[@]}))]} ${EXT_TYPES[$((RANDOM % ${#EXT_TYPES[@]}))]}" >>"$out"
      elif [ "$e" -lt 95 ]; then
        echo "${EXT_SUBS[$((RANDOM % ${#EXT_SUBS[@]}))]} A" >>"$out"
      else
        echo "nx-$RANDOM.${EXT_DOMAINS[$((RANDOM % ${#EXT_DOMAINS[@]}))]} A" >>"$out"
      fi
    else
      local st=(ns-ne1-1.cloud.internal ns-ne1-2.cloud.internal ns-ne1-3.cloud.internal cloud.internal)
      echo "${st[$((RANDOM % 4))]} A" >>"$out"
    fi
  done
}

# --- loop principal ----------------------------------------------------------
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; echo; echo "encerrado."; }
trap cleanup EXIT INT TERM

read -r -a SRV_ARR <<<"$SERVERS"
PER_CYCLE=$((QPS * CYCLE_SECONDS))
START="$(date +%s)"
CYCLES=0

echo "teste de carga DNS — nó ${NODE_ID}"
echo "  alvos      : ${SERVERS}"
echo "  taxa       : ${QPS} q/s (${PER_CYCLE} por ciclo de ${CYCLE_SECONDS}s)"
echo "  duração    : $([ "$DURATION" -eq 0 ] && echo "indefinida" || echo "${DURATION}s")"
echo "  etcd       : ${ETCD_ENDPOINT}"
echo

while true; do
  cycle_start="$(date +%s)"

  for ((c = 0; c < CREATE_PER_CYCLE; c++)); do create_record; done

  # Apaga o excedente, não uma quantidade fixa. Com DELETE_PER_CYCLE fixo e
  # menor que CREATE_PER_CYCLE, o pool crescia sem teto (saldo positivo todo
  # ciclo) e o POOL_MAX não limitava coisa alguma — o etcd acumularia chaves
  # indefinidamente e a taxa de acerto do cache derivaria sozinha ao longo das
  # horas, fazendo o dashboard mudar sem que nada tivesse mudado no serviço.
  excess=$(( $(wc -l <"$POOL") - POOL_MAX ))
  if [ "$excess" -gt 0 ]; then
    # Teto por ciclo para a convergência não virar uma rajada de remoções
    # quando POOL_MAX é reduzido com o teste já em andamento.
    max_del=$((CREATE_PER_CYCLE + DELETE_PER_CYCLE))
    [ "$excess" -gt "$max_del" ] && excess=$max_del
    for ((c = 0; c < excess; c++)); do delete_record; done
  fi

  # Divide o lote entre os servidores e dispara em paralelo, para que a taxa
  # observada seja a soma dos três e não fique limitada pela latência serial.
  per_srv=$((PER_CYCLE / ${#SRV_ARR[@]}))
  for srv in "${SRV_ARR[@]}"; do
    build_batch "$per_srv" "${TMP}/batch-${srv}"
    dig +noall +timeout=2 +tries=1 -f "${TMP}/batch-${srv}" "@${srv}" >/dev/null 2>&1 &
  done
  wait

  CYCLES=$((CYCLES + 1))
  now="$(date +%s)"
  if [ $((CYCLES % 12)) -eq 0 ]; then
    printf '[%s] ciclos=%d vivos=%s apagados=%s consultas≈%d\n' \
      "$(date +%H:%M:%S)" "$CYCLES" "$(wc -l <"$POOL")" "$(wc -l <"$GRAVE")" \
      "$((CYCLES * PER_CYCLE))"
  fi

  [ "$DURATION" -gt 0 ] && [ $((now - START)) -ge "$DURATION" ] && break

  elapsed=$((now - cycle_start))
  [ "$elapsed" -lt "$CYCLE_SECONDS" ] && sleep $((CYCLE_SECONDS - elapsed))
done
