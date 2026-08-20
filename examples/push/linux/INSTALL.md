# Grafana Alloy — Instalação em Servidor Linux (Modo Agent)

Guia para instalar o Grafana Alloy em um servidor Linux remoto e configurá-lo
para enviar métricas, logs e, opcionalmente, traces (via Beyla eBPF) para o
`alloy-gateway` da stack LGTM.

---

## Pré-requisitos

- Sistema operacional: Debian / Ubuntu (ou derivado)
- Acesso root ou sudo
- Servidor LGTM com `alloy-gateway` acessível na rede
- `git` instalado (`sudo apt-get install -y git`)
- `systemd` em execução (obrigatório para coleta de journal logs)

---

## 1. Clonar o repositório

No servidor remoto, clone o repositório da stack para obter os arquivos
de configuração e este guia:

```bash
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack/examples/push/linux
```

> Para atualizar os arquivos no futuro, basta executar `git pull` dentro
> do diretório `lgtm-stack/`.

---

## 2. Configurar resolução de nome

O Alloy usará o hostname `lgtm-stack` para se conectar ao `alloy-gateway`.
Defina o IP do servidor LGTM e adicione a entrada no `/etc/hosts`:

```bash
LGTM_IP="<IP_DO_SERVIDOR_LGTM>"
echo "$LGTM_IP  lgtm-stack" | sudo tee -a /etc/hosts
```

> Se estiver acessando este servidor via SSH a partir da máquina LGTM,
> o IP pode ser obtido automaticamente:
> ```bash
> LGTM_IP=$(echo $SSH_CLIENT | awk '{print $1}')
> echo "$LGTM_IP  lgtm-stack" | sudo tee -a /etc/hosts
> ```

Teste a resolução:

```bash
ping -c 1 lgtm-stack
```

---

## 3. Instalar o Grafana Alloy

Procedimento baseado na [documentação oficial](https://grafana.com/docs/alloy/latest/set-up/install/linux/).

### Debian / Ubuntu

#### Adicionar o repositório Grafana

```bash
sudo apt-get install -y gpg

sudo mkdir -p /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/grafana.asc https://apt.grafana.com/gpg-full.key
sudo chmod 644 /etc/apt/keyrings/grafana.asc

echo "deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main" \
  | sudo tee /etc/apt/sources.list.d/grafana.list
```

#### Instalar a versão compatível com a stack

```bash
sudo apt-get update

# Consulte a versão homologada (variável GRAFANA_ALLOY_VERSION) no arquivo .env.example do repositório
sudo apt-get install -y alloy=<VERSAO>-1
```

> Para consultar as versões disponíveis: `apt-cache madison alloy`

---

### Red Hat / CentOS / Fedora

#### Adicionar o repositório Grafana

```bash
wget -q -O gpg.key https://rpm.grafana.com/gpg.key
sudo rpm --import gpg.key

sudo tee /etc/yum.repos.d/grafana.repo << 'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF
```

#### Instalar a versão compatível com a stack

```bash
# Consulte a versão homologada (variável GRAFANA_ALLOY_VERSION) no arquivo .env.example do repositório
sudo dnf install -y alloy-<VERSAO>-1
```

> Para consultar as versões disponíveis: `dnf list --showduplicates alloy`

---

> **Versão de referência:** A versão exata instalada neste servidor será sempre sincronizada com a variável `GRAFANA_ALLOY_VERSION` do arquivo `.env.example` clonado na sua máquina.

---

## 4. Verificar o arquivo de ambiente do serviço

O arquivo `/etc/default/alloy` criado pelo pacote define variáveis lidas pelo
serviço. O Alloy já aponta para `/etc/alloy/config.alloy` por padrão — confirme
que o arquivo não foi alterado e que `HOSTNAME` está disponível:

```bash
cat /etc/default/alloy
```

O `HOSTNAME` é lido automaticamente do ambiente do sistema pelo `config.alloy`
via `sys.env("HOSTNAME")`. Se o valor retornado for vazio ou incorreto, defina-o
explicitamente no `/etc/default/alloy`:

```bash
# Adicionar apenas se sys.env("HOSTNAME") não retornar o nome correto
echo "HOSTNAME=$(hostname)" | sudo tee -a /etc/default/alloy
```

---

## 5. Copiar o arquivo de configuração

O arquivo já está disponível no repositório clonado no passo 1.
Copie-o para o diretório do Alloy:

```bash
sudo cp ~/lgtm-stack/examples/push/linux/config.alloy /etc/alloy/config.alloy
```

> **O que é coletado e quais são os Labels?**
> Para detalhes arquiteturais sobre quais métricas/logs são coletados pelo Alloy neste host e como configurá-los via labels (como `environment` ou `cloud_provider`), consulte a documentação oficial da stack em **[METRICS.md](../../METRICS.md)** e **[LOGS.md](../../LOGS.md)**.

---

## 5.1. Traces (Beyla eBPF) — Opcional

> Pule esta seção se você não for coletar traces distribuídos (`beyla.ebpf`)
> deste host. Métricas e logs funcionam normalmente sem este passo.

O Alloy `v1.18.0` já inclui nativamente o componente `beyla.ebpf` — não é
necessário instalar um binário Beyla separado. Porém, auto-instrumentação
eBPF exige requisitos de kernel e capabilities que o pacote systemd padrão
do Alloy **não** concede por padrão (o serviço roda como usuário dedicado,
não root).

### Pré-requisitos

- Kernel Linux `>= 5.8` com suporte a BTF (`CONFIG_DEBUG_INFO_BTF=y`)
- Acesso root/sudo para conceder capabilities ao serviço `alloy`
- Serviço HTTP/gRPC rodando neste host, cuja porta você conhece
  (usada em `open_ports` no `config.alloy`)

### Validar o kernel antes de prosseguir

```bash
# Versão do kernel (precisa ser >= 5.8)
uname -r

# BTF habilitado — qualquer um dos dois deve confirmar
ls /sys/kernel/btf/vmlinux 2>/dev/null && echo "BTF OK via sysfs"
zcat /proc/config.gz 2>/dev/null | grep CONFIG_DEBUG_INFO_BTF
```

Se `/sys/kernel/btf/vmlinux` não existir e `CONFIG_DEBUG_INFO_BTF` não
aparecer como `y`, o `beyla.ebpf` falhará ao iniciar. Não prossiga sem
resolver isso (geralmente exige kernel mais recente da distribuição).

### Conceder capabilities ao serviço Alloy

O Beyla precisa de capabilities eBPF específicas — não é necessário rodar
o Alloy inteiro como root. Crie um drop-in systemd:

```bash
sudo systemctl edit alloy
```

Cole o seguinte conteúdo no editor (entre os marcadores que o systemd
já insere):

```ini
[Service]
AmbientCapabilities=CAP_BPF CAP_SYS_PTRACE CAP_NET_RAW CAP_CHECKPOINT_RESTORE CAP_DAC_READ_SEARCH CAP_PERFMON CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_BPF CAP_SYS_PTRACE CAP_NET_RAW CAP_CHECKPOINT_RESTORE CAP_DAC_READ_SEARCH CAP_PERFMON CAP_SYS_ADMIN
```

Salve e feche o editor. O systemd grava o arquivo em
`/etc/systemd/system/alloy.service.d/override.conf`.

> **Nota:** `CAP_SYS_ADMIN` não está na lista de capabilities documentada
> oficialmente pelo Beyla, mas foi necessária em teste real (Debian 13,
> kernel 6.12) para o `discover.ProcessWatcher` funcionar — sem ela, o
> Beyla loga `Unable to load eBPF watcher for process events... permission
> denied` e só descobre processos que já estavam rodando antes do Alloy
> iniciar (não detecta novos processos abrindo a porta depois).

Aplique:

```bash
sudo systemctl daemon-reload
sudo systemctl restart alloy
```

### Liberar o diretório do Beyla no bpffs

O Alloy roda como usuário `alloy`, mas `/sys/fs/bpf` é montado com modo
`700` e dono `root`. O Beyla tenta criar ali seu diretório de trabalho e
falha, logando a cada início:

```
WARN creating OTEL namespace in bpffs failed (is bpffs mounted?)
     err="creating bpffs otel path: mkdir /sys/fs/bpf/otel: permission denied"
```

O aviso é benigno — o Beyla continua instrumentando —, mas polui os logs.
Crie o diretório uma vez e entregue-o ao usuário `alloy`:

```bash
sudo mkdir -p /sys/fs/bpf/otel
sudo chown alloy:alloy /sys/fs/bpf/otel
sudo systemctl restart alloy
```

> **Nota:** `CAP_DAC_READ_SEARCH` concede leitura e travessia, não escrita —
> por isso a capability sozinha não resolve. Prefira este `chown` pontual a
> afrouxar o modo do `/sys/fs/bpf` inteiro. Como `bpffs` não sobrevive ao
> reboot, reaplique via unit `tmpfiles.d` ou `ExecStartPre` se precisar de
> persistência.

### Configurar os serviços a instrumentar

No arquivo `/etc/alloy/config.alloy` já copiado (passo 5), edite a seção
`TRACES: Beyla eBPF (Opcional)`:

```hcl
open_ports = "8080"  // troque pela porta real do seu serviço
name       = "app"   // troque pelo nome lógico do serviço
```

Se o host roda mais de um serviço, replique o bloco `instrument` — um por
serviço, cada um escopado por porta e com seu próprio `name`:

```hcl
discovery {
  instrument {
    open_ports = "8080"
    name       = "frontend"
    sampler { name = "always_on" }
  }

  instrument {
    open_ports = "8081"
    name       = "middleware"
    sampler { name = "always_on" }
  }
}
```

> **Sempre escope por porta.** Instrumentar o host inteiro sem filtro torna
> o volume de spans e a cardinalidade impossíveis de prever.

### Propagação de contexto entre serviços

Se os serviços deste host chamam uns aos outros por HTTP, o bloco `ebpf`
é o que costura essas chamadas sob um **único `traceID`**:

```hcl
ebpf {
  context_propagation = "headers"
}
```

Sem ele, cada serviço gera um trace isolado — você vê os spans, mas não vê
a cadeia, e perde exatamente a informação que motiva tracing distribuído.
O kernel injeta o cabeçalho W3C `traceparent` via eBPF, **sem nenhuma linha
de instrumentação no código da aplicação**.

> **Por que `headers` e não `tcp`/`all`?** `headers` injeta apenas o
> cabeçalho HTTP, o que basta para HTTP em texto claro. Os modos `tcp` e
> `all` são necessários apenas para HTTPS e exigem programas de Linux
> Traffic Control (TC), que podem conflitar com outros programas TC do host
> (ex: Cilium).

Reaplique:

```bash
sudo cp ~/lgtm-stack/examples/push/linux/config.alloy /etc/alloy/config.alloy
sudo systemctl restart alloy
```

### Testar

```bash
# Gere tráfego real no serviço instrumentado (ajuste porta/rota)
curl -s http://localhost:8080/ > /dev/null

# Acompanhe o Alloy processando os spans
sudo journalctl -u alloy -f | grep -i beyla
```

No Grafana:

1. Acesse **Explore** → datasource **Tempo**.
2. Busque por `{ resource.service.name = "app" }` (ajuste ao `name`
   configurado) ou filtre pelo label `instance` do host.
3. Confirme que o trace aparece com os atributos
   `instance`/`environment`/`cloud_provider`/`cloud_region`/`cloud_availability_zone`.
4. Se você configurou propagação de contexto, abra um trace que atravesse
   dois serviços e confirme na árvore o encadeamento `CLIENT → SERVER`
   cruzando a fronteira de processo, com um único `traceID`. Se aparecerem
   traces separados por serviço, a propagação não está ativa.
5. Opcional: no datasource **Mimir**, busque
   `traces_spanmetrics_calls_total{service="app"}` — deve popular
   automaticamente a partir do primeiro trace recebido pelo Tempo (gerado
   pelo `metrics_generator` do Tempo, sem configuração adicional).

---

## 6. Permissão para leitura do journal

O usuário do serviço Alloy precisa de acesso aos logs do systemd:

```bash
sudo usermod -aG systemd-journal alloy
```

---

## 7. Iniciar e habilitar o serviço

```bash
sudo systemctl enable alloy
sudo systemctl start alloy
```

Verificar status:

```bash
sudo systemctl status alloy
```

---

## 8. Verificar o envio de dados

### Logs do Alloy em tempo real

```bash
sudo journalctl -u alloy -f
```

**Importante:** quando o envio dá certo, o Alloy fica em silêncio — ele não
loga nada a cada batch enviado com sucesso. Um envio malsucedido, por outro
lado, aparece explicitamente como `WARN`:

```
level=warn msg="Failed to send batch, retrying" component_id=prometheus.remote_write.gateway err="dial tcp ...: connect: connection refused"
```

Ou seja: **ausência de erro/warn no log não confirma envio, só a ausência de
falha.** Para confirmar positivamente que os dados chegaram, consulte a API
do Mimir/Loki diretamente (rode a partir do servidor LGTM, dentro do
container `grafana`, que tem acesso à rede interna):

```bash
docker exec grafana curl -sG "http://mimir:9009/prometheus/api/v1/query" \
  --data-urlencode 'query=up{instance="<INSTANCE_NAME_OU_HOSTNAME>"}'

docker exec grafana curl -sG "http://loki:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={instance="<INSTANCE_NAME_OU_HOSTNAME>"}' \
  --data-urlencode 'limit=5'
```

> A imagem do Grafana não tem `jq`/`python3` instalado — o comando acima
> retorna o JSON bruto. Procure por `"result":[...]` **não vazio**: se
> aparecer pelo menos um item, os dados chegaram. `"result":[]` significa
> que nada foi recebido ainda para esse `instance`.

### Confirmar no Grafana

1. Acesse o Grafana da stack (`http://<IP_DO_SERVIDOR_LGTM>:3000`)
2. Abra o dashboard **Linux Hosts**
3. Selecione o `instance` correspondente ao novo servidor
4. Verifique se métricas e logs estão chegando

---

## Atualizar configurações

Quando houver atualizações nos arquivos de configuração do repositório:

```bash
cd ~/lgtm-stack
git pull
sudo cp examples/push/linux/config.alloy /etc/alloy/config.alloy
sudo systemctl restart alloy
```

---
 
## 9. Dimensionamento e Estudo de Capacidade (Sizing)
 
 Para cálculos de projeção de disco, cardinalidade real por host e cenários de exemplo, consulte o documento central de capacidade da stack:
 
 👉 **[SIZING.md](../../SIZING.md)**
 
 ---

## Solução de problemas

**Verificar conectividade com o gateway antes de iniciar o Alloy**
```bash
# Métricas (deve retornar HTTP 204 ou 400 — qualquer resposta confirma conectividade)
curl -s -o /dev/null -w "%{http_code}" -X POST http://lgtm-stack:9999/api/v1/metrics/write

# Logs (deve retornar HTTP 204 ou 400)
curl -s -o /dev/null -w "%{http_code}" -X POST http://lgtm-stack:9998/loki/api/v1/push
```

**Alloy não conecta em `lgtm-stack`**
```bash
# Verifique se a entrada existe em /etc/hosts
grep lgtm-stack /etc/hosts

# Teste a porta diretamente
curl -v http://lgtm-stack:9999/api/v1/metrics/write
# Verifique /etc/hosts e se a porta está acessível (firewall)
```

**Logs do journal não aparecem**
```bash
# Confirme que o usuário alloy está no grupo systemd-journal
groups alloy

# Reinicie o serviço após adicionar ao grupo
sudo systemctl restart alloy
```

**Verificar configuração sem reiniciar**
```bash
alloy fmt /etc/alloy/config.alloy
```

**`beyla.ebpf` falha ao iniciar / erros de permissão nos logs**
```bash
sudo journalctl -u alloy -n 100 | grep -i -E "beyla|bpf|permission|capabilit"
```
Causas comuns:
- Kernel sem BTF → revalidar `/sys/kernel/btf/vmlinux` (seção 5.1).
- Capability faltando → confirme o drop-in com `systemctl cat alloy` e
  verifique se as 7 capabilities aparecem em `AmbientCapabilities` e
  `CapabilityBoundingSet`.
- Kernel `< 5.8` → não há workaround; Beyla eBPF não é suportado neste host.

**Nenhum span de trace aparece no Tempo**
- Confirme que `open_ports` corresponde à porta real do processo:
  `sudo ss -tlnp | grep <porta>`.
- Confirme que o processo gerou tráfego HTTP/gRPC real durante a janela
  de observação (Beyla só instrumenta requisições que efetivamente
  trafegam pela porta monitorada).
- Confirme conectividade com o gateway na porta gRPC do Alloy Gateway:
  `curl -v http://lgtm-stack:4317`.

**Volume de spans excessivo no Tempo**
- Não reduza o `sampler` do Beyla para um valor por ratio (`traceidratio`)
  — isso quebra a garantia de retenção de 100% de erros/traces lentos do
  tail sampling do Alloy Gateway. O ajuste de volume é feito
  exclusivamente nas políticas de `otelcol.processor.tail_sampling` do
  Gateway central (fora do escopo deste guia — consulte `TRACES.md`).
