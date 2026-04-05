# Setup Físico e Dimensionamentos (Infrastructure)

A Stack LGTM foi rigorosamente testada e dimensionada para servidores que abraçam Linux LVM, dividindo cada serviço pesado de IOPS (Escrita) para discos físicos exclusivos. Abaixo reside o roteiro Devops para Subir e Operar essa orquestração.

## Limites Físicos Sugeridos (Hardware Limiters)

*   **Padrão Gold:** Em Produção (Alta Carga de APM), exija um Host/VM com `8 Cores` e `32GB RAM`.
*   A distribuição de uso de núcleo via Kernel (CGroups Docker) que parametrizamos segue estencialmente a alocação do arquivo `.env.example`:
  *   Loki e Mimir: ~2vCPU / 6GB a 8GB de RAM fixos.
  *   Tempo: ~2vCPU / 6GB RAM fixos.
  *   Alloy Gateway e Grafana: ~1vCPU / 2GB a 4GB fixos.
  *   Alloy Agent (Monitor Interno): Sub-Kernel, ~0.5 CPU / 1GB.
*   Note que a soma do _Worst-Case-Scenario_ em todos os contêineres retém até `4 GB de RAM` salvos para que o OS respire sem o risco estourar processos vitais do bash ou sshd.

## Roteiro de Implantação (com LVM Volumes)

*(Pule esta fase se estiver brincando localmente via "Desenvolvimento Rápido" simulado)*

Para garantir isolamento, conectaremos partições LVM baseadas nos `vd*` mapeados no Host para pontes de containers.
Tenha em mãos 5 discos montados em sua máquina:
| Disco | Ponto de Montagem Real | Destino LVM no Sistema |
|---|---|---|
| `vdb` | `/docker` | Engine Docker |
| `vdc` | `/lgtm/apps` | Grafana · Alloy (Buffers Fixos WAL) |
| `vdd` | `/lgtm/loki` | Logs (Loki Storage) |
| `vde` | `/lgtm/mimir` | Metrics (Mimir TSDB Storage) |
| `vdf` | `/lgtm/tempo` | Traces (Tempo Storage) |

### 0. Apontar o Docker Engine para o disco dedicado

Antes de instalar ou iniciar o Docker, configure o `daemon.json` para usar o LVM de Docker como raiz de dados. Isso garante que imagens, containers e overlays não consumam o disco OS:

```bash
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "data-root": "/docker"
}
EOF
# Reinicie o daemon após montar o LV de Docker (passo 3 abaixo)
sudo systemctl restart docker
```

### Script Bash (Execução como Root)

```bash
# 1. Preparo das instâncias Volume (VG/LV)
sudo pvcreate /dev/vdb /dev/vdc /dev/vdd /dev/vde /dev/vdf

# Docker Core
sudo vgcreate vg_docker /dev/vdb
sudo lvcreate -l 100%FREE -n lv_docker vg_docker

# Apps (Alloy & Grafana) 
sudo vgcreate vg_apps /dev/vdc
sudo lvcreate -l 100%FREE -n lv_apps vg_apps

# Backends Individuais
sudo vgcreate vg_loki /dev/vdd
sudo lvcreate -l 100%FREE -n lv_loki vg_loki
sudo vgcreate vg_mimir /dev/vde
sudo lvcreate -l 100%FREE -n lv_mimir vg_mimir
sudo vgcreate vg_tempo /dev/vdf
sudo lvcreate -l 100%FREE -n lv_tempo vg_tempo

# 2. Formatar partição para EXT4 Linux padrão:
sudo mkfs.ext4 /dev/vg_docker/lv_docker
sudo mkfs.ext4 /dev/vg_apps/lv_apps
sudo mkfs.ext4 /dev/vg_loki/lv_loki
sudo mkfs.ext4 /dev/vg_mimir/lv_mimir
sudo mkfs.ext4 /dev/vg_tempo/lv_tempo

# 3. Mount-Pointers Físicos
sudo mkdir -p /docker /lgtm/apps/grafana /lgtm/apps/alloy-gateway /lgtm/apps/alloy-agent /lgtm/loki /lgtm/mimir /lgtm/tempo

cat <<EOF | sudo tee -a /etc/fstab
/dev/mapper/vg_docker-lv_docker  /docker     ext4  defaults  0 2
/dev/mapper/vg_apps-lv_apps      /lgtm/apps  ext4  defaults  0 2
/dev/mapper/vg_loki-lv_loki      /lgtm/loki  ext4  defaults  0 2
/dev/mapper/vg_mimir-lv_mimir    /lgtm/mimir ext4  defaults  0 2
/dev/mapper/vg_tempo-lv_tempo    /lgtm/tempo ext4  defaults  0 2
EOF

sudo mount -a

# Assegurar subpastas (Evitar corrupção de bind-mount)
sudo mkdir -p /lgtm/apps/grafana /lgtm/apps/alloy-gateway /lgtm/apps/alloy-agent
```

### 4. UIDs e Permissões de Diretório (Dockerfiles Oficiais)

Para evitar erros crônicos de "Permission Denied", os UIDs dos containers devem ser alinhados aos diretórios em disco antes de criar os volumes bind:

```bash
# Grafana — UID 472, GID 0 (root group, conforme Dockerfile oficial grafana/grafana)
sudo chown -R 472:0 /lgtm/apps/grafana

# Backends — UID/GID 10001 (conforme Dockerfiles grafana/loki, grafana/mimir, grafana/tempo)
sudo chown -R 10001:10001 /lgtm/loki /lgtm/mimir /lgtm/tempo

# Alloy Gateway e Alloy Agent — sem chown necessário (rodam como root)
# Os diretórios /lgtm/apps/alloy-gateway e /lgtm/apps/alloy-agent já foram criados acima.
```

### 5. Ativar as Gavetas Locais via Docker CLI

Essa arquitetura dispensa "Volumes virtuais Mágicos". Criamos `docker volumes` que mapeiam _device drivers hard-binded_:

```bash
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/grafana --opt o=bind grafana-data
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/alloy-gateway --opt o=bind alloy-gateway-data
docker volume create --driver local --opt type=none --opt device=/lgtm/apps/alloy-agent   --opt o=bind alloy-agent-data
docker volume create --driver local --opt type=none --opt device=/lgtm/loki         --opt o=bind loki-data
docker volume create --driver local --opt type=none --opt device=/lgtm/mimir        --opt o=bind mimir-data
docker volume create --driver local --opt type=none --opt device=/lgtm/tempo        --opt o=bind tempo-data
```

Você estará pronto agora para preencher o seu arquivo `[.]env` e compilar usando `docker compose up -d` na raiz do diretório GitHub.

---
🔙 Voltar: [README Principal](README.md)
