# Scripts de Teste de Carga

Scripts SQL para gerar carga realista em PostgreSQL e MySQL, permitindo validar a coleta de métricas nos dashboards do framework dos 6+2 Pilares.

---

## 📂 Conteúdo

| Arquivo | Descrição | Tempo |
|---------|-----------|-------|
| [LOAD-TEST.md](./LOAD-TEST.md) | Guia completo com instruções passo a passo, troubleshooting e interpretação de resultados | — |
| [postgres-load-test.sql](./postgres-load-test.sql) | Script de teste para PostgreSQL: 1 bilhão de operações em 100 lotes | 10-15 min |
| [mysql-load-test.sql](./mysql-load-test.sql) | Script de teste para MySQL: 1 bilhão de operações em 100 lotes | 15-25 min |

---

## 🚀 Uso Rápido

### PostgreSQL

```bash
psql -h 172.18.1.157 -U postgres -f postgres-load-test.sql
```

### MySQL

```bash
mysql -h 192.168.1.13 -u root -p < mysql-load-test.sql
```

---

## 📊 O que é testado

- ✅ **HEALTH** — Status up/down, conexões ativas
- ✅ **CAPACITY** — CPU, Memória, Disco, Buffer Pool
- ✅ **ACTIVITY** — Throughput de queries (QPS), rows processadas
- ✅ **DIAGNOSTICS** — Locks, contentions, deadlocks
- ✅ **INVENTORY** — Informações do OS
- ✅ **I/O** — Operações de disco, latência

---

## 📖 Próximas Etapas

1. **Executar o script** de teste (PostgreSQL ou MySQL)
2. **Acompanhar progresso** em tempo real (ver [LOAD-TEST.md](./LOAD-TEST.md))
3. **Visualizar métricas** no Grafana:
   - PostgreSQL: `http://localhost:3000/d/linux-pgsql-hosts`
   - MySQL: `http://localhost:3000/d/linux-mysql-hosts`
4. **Interpretar resultados** usando o guia de troubleshooting

---

Para instruções detalhadas: 👉 **[LOAD-TEST.md](./LOAD-TEST.md)**
