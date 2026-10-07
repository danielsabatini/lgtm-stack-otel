# Backup e Disaster Recovery (Proteção de Dados)

> **Referência Técnica:** Este documento estabelece os procedimentos oficiais de backup, rotação, validação de integridade e recuperação de desastres (Disaster Recovery) para a LGTM Stack.

---

## 1. Introdução

A LGTM Stack hospeda bancos de dados de séries temporais de alta intensidade de escrita em disco com partes de dados mantidas em memória RAM (*Write-Ahead Logs - WAL*). 

Por essa razão, backups manuais baseados em cópia direta de arquivos com o banco rodando **são contraindicados**, pois podem gerar corrupção de blocos TSDB. A estratégia recomendada e homologada para ambientes de produção baseia-se em **Snapshots de Volume de Bloco (Block Storage)** ou procedimentos coordenados com parada graciosa.

---

## 2. Objetivo

1. **Garantir Consistência dos Dados:** Assegurar que os dados de métricas (Mimir), logs (Loki) e traces (Tempo) sejam copiados sem corrupção de índices.
2. **Proteger Configurações e Dashboards:** Garantir o backup seguro do banco relacional do Grafana (`grafana.db`) e do arquivo de credenciais `.env`.
3. **Estabelecer RTO e RPO Mínimos:** Fornecer um roteiro rápido de restauração em caso de falha catastrófica da máquina virtual.

---

## 3. Estratégia Principal: Snapshots de Volume de Bloco (Block Storage)

Como todos os volumes da stack residem no disco dedicado montado em `/docker`, a melhor estratégia de proteção é o agendamento de **Snapshots Periódicos** do volume de bloco no painel do seu provedor de nuvem (Magalu Cloud, AWS, etc.).

### 3.1 Procedimento Recomendado para Snapshot 100% Consistente (App-Consistent)
```bash
cd /caminho/para/lgtm-stack

# 1. Parar os containers para descarregar a memória RAM (WAL) para o disco:
docker compose stop
sync

# 2. Executar o Snapshot do volume no painel do provedor de nuvem.

# 3. Subir a stack novamente:
docker compose start
```

---

## 4. Backup Pontual do Grafana (Banco SQLite)

O banco de dados do Grafana (`grafana.db`) armazena dashboards criados pela UI, usuários, senhas e configurações que não estão versionadas no Git.

```bash
# 1. Parar temporariamente apenas o container do Grafana (os backends continuam recebendo dados):
docker compose stop grafana

# 2. Copiar o arquivo grafana.db com segurança para uma pasta externa:
mkdir -p ./backup
docker run --rm \
  -v lgtm-stack-otel_grafana-data:/source:ro \
  -v $(pwd)/backup:/backup \
  busybox cp /source/grafana.db /backup/grafana-$(date +%Y%m%d).db

# 3. Iniciar o Grafana novamente:
docker compose start grafana
```

---

## 5. Automação e Rotação Noturna de Backups

Para ambientes onde não há snapshot automático de bloco, utilize o script de automação fornecido no repositório. Ele realiza a exportação compactada dos volumes e descarta automaticamente backups com mais de 7 dias para evitar o esgotamento do disco:

👉 **[Script de Automação de Backup](../artifacts/scripts/backup-rotation.sh)**

### Como Agendar no Crontab (Execução diária às 03:00 da manhã):
```bash
0 3 * * * /bin/bash /caminho/para/lgtm-stack/artifacts/scripts/backup-rotation.sh >> /var/log/lgtm-backup.log 2>&1
```

---

## 6. Verificação de Integridade dos Arquivos (Sanity Check)

Antes de confiar no seu backup, valide se os arquivos não foram corrompidos:

```bash
# 1. Validar a integridade do banco SQLite do Grafana (deve retornar "ok"):
sqlite3 backup/grafana-YYYYMMDD.db "PRAGMA integrity_check;"

# 2. Validar se o arquivo compactado de logs ou métricas pode ser lido:
tar -tvf backup/lgtm-stack-otel_loki-data-YYYYMMDD.tar.gz | head -n 10
```

---

## 7. Procedimento de Restauração e Disaster Recovery

Caso o servidor primário sofra uma pane irreversível e seja necessário restaurar a stack em uma nova máquina virtual:

### Passo 1: Criar Nova Instância e Anexar o Volume do Snapshot
1. Crie uma nova VM limpa no provedor de nuvem.
2. Crie um novo volume a partir do **Snapshot mais recente** e anexe-o à VM.

### Passo 2: Montar o Disco Restaurado em `/docker`
```bash
sudo vgscan
sudo vgchange -ay
sudo mkdir -p /docker
sudo mount /dev/mapper/vgdocker-lvdocker /docker

# Confirmar que o Docker enxerga o diretório correto:
sudo docker info | grep "Docker Root Dir"
```

### Passo 3: Subir a Stack Restaurada
```bash
git clone <url-do-repositorio> lgtm-stack
cd lgtm-stack

# Restaurar o arquivo .env a partir do seu cofre de senhas seguro
# Iniciar todos os serviços:
docker compose up -d
```

Todos os dados e dashboards voltarão exatamente ao estado do momento do snapshot.

---

## 8. Governança e Referências

* Para os requisitos de infraestrutura e montagem de disco, consulte [INFRASTRUCTURE.md](INFRASTRUCTURE.md).
* Para procedimentos seguros de atualização de versão, consulte [UPGRADE.md](UPGRADE.md).
* Para a metodologia de observabilidade e painéis, consulte [OBSERVABILITY-METHODOLOGY.md](OBSERVABILITY-METHODOLOGY.md).

---
🔙 Voltar: [README Principal](../README.md)
