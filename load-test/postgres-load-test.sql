-- ============================================================================
-- SCRIPT DE TESTE DE CARGA - POSTGRESQL
--
-- Objetivo: Gerar carga realista em PostgreSQL (1 Bilhão de operações)
-- para visualizar métricas no dashboard "Linux + PostgreSQL"
--
-- Uso:
--   psql -h 172.18.1.157 -U postgres -d postgres -f postgres-load-test.sql
--
-- Características:
--   • 100 ciclos (lotes)
--   • 10 milhões de inserts por ciclo
--   • Updates em todos os registros por ciclo
--   • Truncate para limpeza e medição de I/O
--   • Métricas coletadas: QPS, Throughput, Cache Hit Rate, WAL Growth
-- ============================================================================

\set QUIET on

-- ============================================================================
-- 1. CONFIGURAÇÃO DA SESSÃO
-- ============================================================================

SET work_mem = '256MB';                      -- Aumentar memória para operações
SET maintenance_work_mem = '512MB';          -- Memória para TRUNCATE/VACUUM
SET max_parallel_workers_per_gather = 4;     -- Paralelizar quando possível
SET random_page_cost = 1.1;                  -- Preferir index scans
SET synchronous_commit = 'off';              -- Balance entre performance e durabilidade

-- Habilitar timing
\timing on

\set QUIET off

\echo '╔════════════════════════════════════════════╗'
\echo '║  TESTE DE CARGA - PostgreSQL                ║'
\echo '║  Total: 1 Bilhão de operações              ║'
\echo '║  Lotes: 100 x 10.000.000 registros         ║'
\echo '╚════════════════════════════════════════════╝'

-- ============================================================================
-- 2. CRIAR BANCO DE DADOS
-- ============================================================================

\echo ''
\echo '[1/4] Criando banco de dados LGTM...'

DROP DATABASE IF EXISTS lgtm;
CREATE DATABASE lgtm WITH
    ENCODING='UTF8'
    LC_COLLATE='C.UTF-8'
    LC_CTYPE='C.UTF-8'
    TEMPLATE=template0;

\c lgtm

-- ============================================================================
-- 3. CRIAR TABELA E ÍNDICES
-- ============================================================================

\echo '[2/4] Criando tabela cadastro...'

DROP TABLE IF EXISTS cadastro;

-- Usar UNLOGGED para evitar WAL overhead (as em teste de carga, durabilidade não é crítica)
CREATE UNLOGGED TABLE cadastro (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    endereco VARCHAR(100) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    data_criacao TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'ativo',
    CHECK (status IN ('ativo', 'inativo', 'processado'))
);

-- Índices para simular queries de busca realistas
CREATE INDEX idx_cadastro_status ON cadastro(status);
CREATE INDEX idx_cadastro_data_criacao ON cadastro(data_criacao DESC);
CREATE INDEX idx_cadastro_telefone ON cadastro(telefone);

\echo 'Tabela cadastro criada com sucesso!'

-- ============================================================================
-- 4. PROCEDURE/FUNCTION PARA TESTE DE CARGA
-- ============================================================================

\echo '[3/4] Criando função de teste de carga...'

CREATE OR REPLACE FUNCTION gerar_carga_teste()
RETURNS TABLE (
    mensagem TEXT
) AS $$
DECLARE
    total_lotes CONSTANT INT := 100;
    tamanho_lote CONSTANT INT := 10000000;
    i INT;
    inicio_lote TIMESTAMP;
    fim_lote TIMESTAMP;
    duracao_ms NUMERIC;
    registros_inseridos INT;
    registros_atualizados INT;
    tempo_inicio_global TIMESTAMP;
    tempo_fim_global TIMESTAMP;
    duracao_total_ms NUMERIC;
BEGIN
    tempo_inicio_global := CLOCK_TIMESTAMP();

    -- Loop principal: 100 lotes de 10 milhões
    FOR i IN 1..total_lotes LOOP
        inicio_lote := CLOCK_TIMESTAMP();

        RETURN QUERY SELECT format('[LOTE %03s/%s] Inserindo %s registros...',
            i, total_lotes, to_char(tamanho_lote, '999G999G999'));

        -- ====================================================================
        -- FASE 1: INSERT MASSIVO
        -- ====================================================================
        -- Esta operação gera carga em:
        -- - Transações commit (xact_commit)
        -- - Tuplas inseridas (tup_inserted)
        -- - WAL bytes written
        -- - Disk I/O

        WITH dados AS (
            SELECT
                'Usuario_' || s || '_L' || i AS nome,
                'Endereco de Teste - Lote ' || i || ' - Numero ' || s AS endereco,
                '(11) 9' || lpad((s % 99999999)::text, 8, '0') AS telefone,
                'user' || s || '_lote' || i || '@lgtm.local' AS email,
                CASE
                    WHEN s % 3 = 0 THEN 'ativo'
                    WHEN s % 3 = 1 THEN 'inativo'
                    ELSE 'processado'
                END AS status
            FROM generate_series(1, tamanho_lote) AS s
        )
        INSERT INTO cadastro (nome, endereco, telefone, email, status)
        SELECT nome, endereco, telefone, email, status FROM dados;

        GET DIAGNOSTICS registros_inseridos = ROW_COUNT;

        -- ====================================================================
        -- FASE 2: UPDATE EM MASSA
        -- ====================================================================
        -- Esta operação gera carga em:
        -- - Tuplas atualizadas (tup_updated)
        -- - WAL bytes for updates
        -- - Bloat de tabela

        UPDATE cadastro
        SET
            status = CASE
                WHEN status = 'ativo' THEN 'processado'
                WHEN status = 'inativo' THEN 'ativo'
                ELSE 'inativo'
            END,
            nome = nome || '_UPD'
        WHERE status IN ('ativo', 'inativo', 'processado');

        GET DIAGNOSTICS registros_atualizados = ROW_COUNT;

        -- ====================================================================
        -- FASE 3: DELETE SELETIVO
        -- ====================================================================
        -- Simula carga mais realista de DELETE parcial
        -- Gera: tuplas deletadas (tup_deleted), bloat

        DELETE FROM cadastro WHERE id % 3 = 0;

        -- ====================================================================
        -- FASE 4: TRUNCATE PARA LIMPEZA
        -- ====================================================================
        -- TRUNCATE reseta o auto-increment e libera espaço
        -- Mensurável em WAL growth e disk usage

        TRUNCATE TABLE cadastro;

        -- Registrar duração do lote
        fim_lote := CLOCK_TIMESTAMP();
        duracao_ms := EXTRACT(EPOCH FROM (fim_lote - inicio_lote)) * 1000;

        RETURN QUERY SELECT format(
            '  ├─ INSERT: %s registros em %.0fms | UPDATE: %s | DELETE: ~%s | TRUNCATE: OK',
            to_char(registros_inseridos, '999G999G999'),
            duracao_ms,
            to_char(registros_atualizados, '999G999G999'),
            to_char(registros_inseridos / 3, '999G999G999')
        );
    END LOOP;

    tempo_fim_global := CLOCK_TIMESTAMP();
    duracao_total_ms := EXTRACT(EPOCH FROM (tempo_fim_global - tempo_inicio_global)) * 1000;

    -- ========================================================================
    -- RELATÓRIO FINAL
    -- ========================================================================
    RETURN QUERY SELECT '';
    RETURN QUERY SELECT '╔════════════════════════════════════════════╗';
    RETURN QUERY SELECT '║         TESTE CONCLUÍDO COM SUCESSO        ║';
    RETURN QUERY SELECT '║                                            ║';
    RETURN QUERY SELECT '║  Total de Operações: 1 Bilhão              ║';
    RETURN QUERY SELECT format('║  Tempo Total: %.2f segundos         ║', duracao_total_ms / 1000);
    RETURN QUERY SELECT format('║  Taxa: %.0f ops/seg             ║', 1000000 / (duracao_total_ms / 1000));
    RETURN QUERY SELECT '║                                            ║';
    RETURN QUERY SELECT '╚════════════════════════════════════════════╝';
END;
$$ LANGUAGE plpgsql;

\echo 'Função gerar_carga_teste criada com sucesso!'

-- ============================================================================
-- 5. EXECUTAR O TESTE DE CARGA
-- ============================================================================

\echo ''
\echo '[4/4] Iniciando teste de carga (este processo pode demorar 10-30 minutos)...'
\echo ''

SELECT * FROM gerar_carga_teste();

-- ============================================================================
-- 6. VALIDAÇÃO DE MÉTRICAS
-- ============================================================================

\echo ''
\echo '═══ VALIDAÇÃO DE MÉTRICAS ═══'
\echo ''

\echo 'Para validar as métricas no dashboard PostgreSQL:'
\echo '1. Acesse: http://localhost:3000/d/postgres-metrics'
\echo '2. Filtre por instance="srv-pgsql-01"'
\echo '3. Verifique os seguintes painéis:'
\echo '   • ACTIVITY: pg_stat_database_xact_commit (deve estar em pico)'
\echo '   • CAPACITY: pg_database_size_bytes e pg_wal_size_bytes'
\echo '   • DIAGNOSTICS: pg_stat_database_deadlocks (deve ser 0)'
\echo '   • HEALTH: pg_up (deve ser 1) e pg_stat_activity_count'
\echo '   • WAL: pg_wal_size_bytes (crescimento visível durante teste)'
\echo ''

-- Exibir estado final da tabela
\echo 'Estado Final da Tabela cadastro:'
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS tamanho_total,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS tamanho_indices
FROM pg_tables
JOIN pg_stat_user_tables ON tablename = relname
WHERE schemaname = 'public' AND tablename = 'cadastro';

-- ============================================================================
-- 7. LIMPEZA (opcional - comentada por padrão)
-- ============================================================================

-- Para resetar tudo (descomente se desejar):
-- \c postgres
-- DROP DATABASE IF EXISTS lgtm;
-- \echo 'Banco de dados LGTM removido'

\echo ''
\echo 'Teste de carga concluído! Métricas estão sendo coletadas pelo postgres_exporter.'
