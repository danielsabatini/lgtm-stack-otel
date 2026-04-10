# Backup e Disaster Recovery (Proteção de Dados)

Nossa arquitetura prioriza resiliência física por meio da fragmentação de LVMs. Por se tratar de um ambiente que hospeda bases de dados de alta intensidade transacional em disco e retenções in-memory (RAM WAL), o backup comum baseado na "cópia de arquivos por script `.tar`" **é fortemente contraindicado**, gerando corrupção de TSDB quase imediata.

Para infraestruturas alocadas em nuvem (AWS, GCP, Azure) ou virtualizadores on-premise (VMware, Proxmox), a nossa política Oficial de Restauração orbita sobre o **Snapshot Integral da Camada de Blocos**.

---

## 📸 Estratégia Principal: Cloud Block Snapshots (EBS/VMDK)

Como todos os dados residem no disco `/docker` (data-root do Docker), você deve programar sua Cloud para tirar fotografias (*Snapshots*) desse único volume.

### 1. Parada Estrita (Quiescence) — *Recomendada para App-Consistent*

O Mimir e o Loki guardam blocos quentes na RAM e no _Write-Ahead-Log_ (`vdc`) antes de persistirem no disco longo (`vde`/`vdd`). Para um Snapshot 100% consistente:

```bash
cd /caminho/para/lgtm-stack

# Desce os containers e força a escrita dos WALs para disco
docker compose down
sync
```

> **Crash-Consistent Snapshots (sistema vivo):** O LVM e os mecanismos de WAL recovery do Loki, Mimir e Tempo suportam recuperação na esmagadora maioria dos casos em snapshots automáticos noturnos sem parada. Use com consciência do risco residual de perda das últimas escritas in-flight.

### 2. Captação do Disco (O Backup)

Pelo painel do seu provedor, solicite Snapshot do volume físico `/docker` atrelado ao host. Todo o estado da stack (volumes Docker, imagens e dados dos backends) reside nesse único disco.

> **Atenção WAL:** Os diretórios de WAL do Loki e do Tempo estão dentro dos volumes Docker nomeados, que residem em `/docker/volumes/` — são capturados automaticamente no snapshot do disco. Não exclua esses diretórios de backups pontuais.

### 3. Proteção do Arquivo de Configuração

O arquivo `.env` contém credenciais de acesso ao Grafana e parâmetros críticos de retenção. **Nunca comite o `.env` em repositórios Git.** Armazene-o em um gerenciador de segredos:

- **AWS:** AWS Secrets Manager ou Systems Manager Parameter Store
- **GCP:** Secret Manager
- **Azure:** Key Vault
- **On-premise:** HashiCorp Vault, Bitwarden Secrets, ou criptografia simétrica com `gpg`

```bash
# Exemplo: backup criptografado do .env com GPG
gpg --symmetric --cipher-algo AES256 .env
# Armazene o .env.gpg no vault da equipe
```

---

## 🗄️ Backup Pontual do Grafana (SQLite)

O banco relacional do Grafana (`grafana.db`) armazena dashboards customizados, usuários, alertas e datasources que **não estão no código do repositório** (criados via UI). A cópia desse arquivo enquanto o container está rodando **não é segura** — a documentação oficial exige parada prévia.

```bash
# 1. Para apenas o Grafana (backends continuam recebendo dados via Alloy)
docker compose stop grafana

# 2. Copia o grafana.db para fora do volume
docker run --rm \
  -v lgtm-stack_grafana-data:/source:ro \
  -v $(pwd)/backup:/backup \
  busybox cp /source/grafana.db /backup/grafana-$(date +%Y%m%d).db

# 3. Sobe o Grafana novamente
docker compose start grafana
```

> **Nota:** Dashboards e datasources gerenciados por arquivos em `grafana/provisioning/` são recriados automaticamente na subida — não precisam de backup separado.

---

## 💻 Backup em Desenvolvimento Local (Sem LVM)

Para ambientes de desenvolvimento com volumes Docker virtuais (não LVM), o snapshot de bloco não é aplicável. Use este procedimento simples:

```bash
cd /caminho/para/lgtm-stack

# Para toda a stack
docker compose down
sync

# Exporta cada volume para um arquivo tar
for vol in \
  lgtm-stack_grafana-data \
  lgtm-stack_loki-data \
  lgtm-stack_mimir-data \
  lgtm-stack_tempo-data \
  lgtm-stack_alloy-gateway-data \
  lgtm-stack_alloy-agent-data; do
  docker run --rm \
    -v ${vol}:/data:ro \
    -v $(pwd)/backup:/backup \
    busybox tar czf /backup/${vol}-$(date +%Y%m%d).tar.gz -C /data .
  echo "✓ $vol exportado"
done

# Sobe novamente
docker compose up -d
```

Restauração:
```bash
docker compose down

for vol in \
  lgtm-stack_grafana-data \
  lgtm-stack_loki-data \
  lgtm-stack_mimir-data \
  lgtm-stack_tempo-data \
  lgtm-stack_alloy-gateway-data \
  lgtm-stack_alloy-agent-data; do
  docker volume create ${vol} 2>/dev/null || true
  docker run --rm \
    -v ${vol}:/data \
    -v $(pwd)/backup:/backup \
    busybox tar xzf /backup/${vol}-YYYYMMDD.tar.gz -C /data
done

docker compose up -d
```

---

## ♻️ Restauração em Ambiente Cópia (Disaster Recovery)

Houve colapso do Servidor Primário ou você quer invocar um ambiente idêntico (Homologação) noutra nuvem.

### Passo 1: Provisionamento

1. Levante uma nova VM limpa no ambiente alvo (apenas o disco OS padrão).
2. Restaure os 5 Snapshots criando Volumes Frescos e anexe os 5 discos à nova VM em ordem idêntica (`/dev/vdb` → `/dev/vdf`).

### Passo 2: Reconectar o disco restaurado

Restaure o snapshot do disco `/docker` na nova VM e monte-o:

```bash
sudo vgscan
sudo vgchange -ay
sudo mount -a
```

Confirme que o Docker enxerga o data-root correto:

```bash
docker info | grep "Docker Root Dir"  # → /docker
```

### Passo 3: Inicialização da Stack Transplantada

Como os volumes nomeados residem dentro de `/docker/volumes/`, eles são restaurados automaticamente com o disco — não é necessário recriar volumes manualmente.

```bash
git clone <seu-repo> /caminho/para/lgtm-stack
cd /caminho/para/lgtm-stack

# Recupere o .env do seu vault de segredos
# vault kv get -field=value secret/lgtm/.env > .env

docker compose up -d
```

Toda a plataforma LGTM voltará à vida do milissegundo exato pausado no Disaster Recovery ou Snapshot Noturno.

---
🔙 Voltar: [README Principal](README.md)
