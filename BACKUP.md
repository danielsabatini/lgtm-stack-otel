# Backup e Disaster Recovery (Proteção de Dados)

Nossa arquitetura prioriza resiliência física por meio da fragmentação de LVMs. Por se tratar de um ambiente que hospeda bases de dados de alta intensidade transacional em disco e retenções in-memory (RAM WAL), o backup comum baseado na "cópia de arquivos por script `.tar`" **é fortemente contraindicado**, gerando corrupção de TSDB quase imediata.

Para infraestruturas alocadas em nuvem (AWS, GCP, Azure) ou virtualizadores on-premise (VMware, Proxmox), a nossa política Oficial de Restauração orbita sobre o **Snapshot Integral da Camada de Blocos**. 

---

## 📸 Estratégia Principal: Cloud Block Snapshots (EBS/VMDK)

Como dividimos os dados em 5 discos independentes vinculados estruturalmente ao LVM, você deve programar sua Cloud para tirar fotografias (*Snapshots*) sistêmicos dessas unidades.

### 1. Parada Estrita (Quiescence) - *Opcional, mas Altamente Recomendável*
O Mimir e o Loki guardam blocos quentes na RAM e no _Write-Ahead-Log_ (`vdc`) antes de flertarem com o disco longo (`vde`). Para um Snapshot perfeito 100% consistente ("App-Consistent"):

```bash
cd /opt/lgtm-stack
# 1. Congela o recebimento, desce as instâncias e força a escrita.
docker compose down

# 2. Confirmação do kernel no Linux para salvar blocos não-concluídos:
sync
```
*Se você necessita apenas de "Crash-Consistent Snapshots" (como pulling automático da AWS durante a madrugada com o sistema vivo sem poder cair), o LVM e o motor do TSDB Grafana suportarão a recuperação na maioria massiva das vezes, graças aos mecanismos de `WAL recovery` no startup.*

### 2. Captação de Discos (O Backup)
Através do painel do seu provedor, solicite o Backup/Snapshot atrelado simultâneo dos 5 volumes atrelados ao host ou grupo de instâncias. Isso salvará a matriz do sistema LVM.
*   **Vol 1:** Storage raiz da Engine do Docker (`vdb`)
*   **Vol 2:** O Buffer/WAL do Alloy e SQLite do Grafana (`vdc`)
*   **Vol 3, 4 e 5:** Loki, Mimir e Tempo isolados (`vdd`, `vde`, `vdf`)

*(Nunca se esqueça de efetuar o backup e incluir nos repositórios o arquivo **`.env`** que carrega senhas criptografadas fixas. Sem ele, a restauração da chave Grafana falhará).*

---

## ♻️ Restauração em Ambiente Cópia (Disaster Recovery)

Houve colapso do Servidor Primário ou você quer invocar um ambiente Idêntico (Homologação) noutra nuvem.

### Passo 1: Provisionamento
1. Levante uma nova Máquina (Node / VM) limpa no ambiente alvo, dotada apenas do seu "Disco C (OS)" padrão.
2. Na nuvem, restaure os seus 5 Snapshots brutos criando Volumes Frescos e anexe/agregue (Attach) os 5 discos físicos à nova VM em ordem idêntica (mapeando de `/dev/vdb` à `/dev/vdf`).

### Passo 2: O Despertar do LVM
Sendo discos LVM legítimos preexistentes, a nova máquina Linux não precisará de scripts longos de formatação! O sistema buscará instantaneamente as partições contidas ali:

```bash
# 1. Varre e recupera os grupos nativos na nova VM
sudo vgscan
sudo vgchange -ay

# 2. Recrie as pastas alvo exatamente iguais
sudo mkdir -p /docker /lgtm/apps/grafana /lgtm/apps/alloy-gateway /lgtm/apps/alloy-agent /lgtm/loki /lgtm/mimir /lgtm/tempo

# 3. Adicione nossas diretrizes no FSTAB e monte novamente
cat <<EOF | sudo tee -a /etc/fstab
/dev/mapper/vg_docker-lv_docker  /docker     ext4  defaults  0 2
/dev/mapper/vg_apps-lv_apps      /lgtm/apps  ext4  defaults  0 2
/dev/mapper/vg_loki-lv_loki      /lgtm/loki  ext4  defaults  0 2
/dev/mapper/vg_mimir-lv_mimir    /lgtm/mimir ext4  defaults  0 2
/dev/mapper/vg_tempo-lv_tempo    /lgtm/tempo ext4  defaults  0 2
EOF

sudo mount -a
```

### Passo 3: Inicialização da Stack Transplantada
Instale o Docker do zero (já que o Motor Docker está no `/docker` mapeado em disco, e não se reinstala os plugins sem o binário base). Configure o caminho do `/etc/docker/daemon.json` apontando para a raiz "data-root" contida no `INFRASTRUCTURE.md` se precisar.

No final, crie os links fantasmas e bata a chave de partida na DMZ nova com todos os anos de registros intactos e blindados:
```bash
git clone <seu-repo> /opt/lgtm-stack
cd /opt/lgtm-stack
# Cole o seu .env com as credenciais

# Cria apontamentos cegos idênticos (Eles herdarão tudo do Bind mapeado no Fstab anterior):
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/grafana --opt o=bind grafana-data
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/alloy-gateway --opt o=bind alloy-gateway-data
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/alloy-agent   --opt o=bind alloy-agent-data
docker volume create --driver local --opt type=none --opt device=/lgtm/loki         --opt o=bind loki-data
docker volume create --driver local --opt type=none --opt device=/lgtm/mimir        --opt o=bind mimir-data
docker volume create --driver local --opt type=none --opt device=/lgtm/tempo        --opt o=bind tempo-data

docker compose up -d
```
Toda a plataforma LGTM voltará à vida do milissegundo exato pausado no Disaster Recovery ou Snapshot Noturno.
