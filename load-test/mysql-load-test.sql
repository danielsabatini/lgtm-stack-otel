-- ============================================================================
-- SCRIPT DE TESTE DE CARGA - MYSQL
--
-- Objetivo: Gerar carga realista em MySQL (1 Bilhão de operações)
-- para visualizar métricas no dashboard "Linux + MySQL"
--
-- Uso:
--   mysql -h 192.168.1.13 -u root -p < mysql-load-test.sql
--
-- Características:
--   • 100 ciclos (lotes)
--   • 10 milhões de inserts por ciclo
--   • Updates em todos os registros por ciclo
--   • Truncate para limpeza e medição de I/O
--   • Métricas coletadas: QPS, Throughput, Buffer Pool, Redo Logs
-- ============================================================================

SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
SET SESSION max_allowed_packet = 67108864;           -- 64MB para bulk inserts
SET SESSION innodb_autoinc_lock_mode = 2;            -- Lightweight locks para auto-increment
SET SESSION innodb_flush_log_at_trx_commit = 2;      -- Balance entre performance e durabilidade

-- ============================================================================
-- 1. CRIAR BANCO DE DADOS E PREPARAÇÃO
-- ============================================================================

DROP DATABASE IF EXISTS lgtm;
CREATE DATABASE lgtm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lgtm;

SELECT 'Banco de dados LGTM criado' AS status;

-- ============================================================================
-- 2. CRIAR TABELA DE TESTE
-- ============================================================================

DROP TABLE IF EXISTS cadastro;

CREATE TABLE cadastro (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    nome VARCHAR(50) NOT NULL,
    endereco VARCHAR(100) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('ativo', 'inativo', 'processado') DEFAULT 'ativo',
    KEY idx_status (status),
    KEY idx_data_criacao (data_criacao)
) ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    ROW_FORMAT=DYNAMIC;

SELECT 'Tabela cadastro criada com sucesso' AS status;
SELECT TABLE_NAME, ENGINE, TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'lgtm' AND TABLE_NAME = 'cadastro';

-- ============================================================================
-- 3. PROCEDURE PARA TESTE DE CARGA
-- ============================================================================

DELIMITER //

DROP PROCEDURE IF EXISTS gerar_carga_teste //

CREATE PROCEDURE gerar_carga_teste()
READS SQL DATA
SQL SECURITY INVOKER
BEGIN
    DECLARE total_lotes INT DEFAULT 100;
    DECLARE tamanho_lote INT DEFAULT 10000000;     -- 10 milhões por lote
    DECLARE i INT DEFAULT 1;
    DECLARE inicio_lote TIMESTAMP;
    DECLARE fim_lote TIMESTAMP;
    DECLARE duracao_ms INT;
    DECLARE registros_inscritos INT;
    DECLARE registros_atualizados INT;

    -- Variáveis para estatísticas globais
    DECLARE tempo_inicio_global TIMESTAMP;
    DECLARE tempo_fim_global TIMESTAMP;
    DECLARE duracao_total_ms INT;

    -- Capturar tempo global de início
    SET tempo_inicio_global = NOW(6);

    SELECT CONCAT(
        '╔════════════════════════════════════════════╗\n',
        '║  TESTE DE CARGA - MySQL                     ║\n',
        '║  Total: 1 Bilhão de operações              ║\n',
        '║  Lotes: ', total_lotes, ' x ', tamanho_lote, ' registros      ║\n',
        '╚════════════════════════════════════════════╝'
    ) AS banner;

    -- ========================================================================
    -- LOOP PRINCIPAL: 100 lotes de 10 milhões
    -- ========================================================================
    lote_loop: LOOP
        IF i > total_lotes THEN
            LEAVE lote_loop;
        END IF;

        SET inicio_lote = NOW(6);

        -- Mensagem de progresso
        SELECT CONCAT(
            '[LOTE ', LPAD(i, 3, '0'), '/', total_lotes, '] ',
            'Inserindo ', FORMAT(tamanho_lote, 0), ' registros...'
        ) AS progresso;

        -- ====================================================================
        -- FASE 1: INSERT MASSIVO
        -- ====================================================================
        -- Usando INSERT...SELECT para máxima performance
        -- Esta operação gera carga em:
        -- - Threads connected (1)
        -- - Questions/Queries (X por INSERT)
        -- - InnoDB buffer pool (read requests)
        -- - Redo log (log bytes written)

        INSERT INTO cadastro (nome, endereco, telefone, email, status)
        SELECT
            CONCAT('Usuario_', s, '_L', i),
            CONCAT('Endereco de Teste - Lote ', i, ' - Numero ', s),
            CONCAT('(11) 9', LPAD(MOD(s, 99999999), 8, '0')),
            CONCAT('user', s, '_lote', i, '@lgtm.local'),
            CASE
                WHEN s % 3 = 0 THEN 'ativo'
                WHEN s % 3 = 1 THEN 'inativo'
                ELSE 'processado'
            END
        FROM
            (SELECT @row:=@row+1 as s FROM
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t1,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t2,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t3,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t4,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t5,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t6,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t7,
                (SELECT 0 UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4
                 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) t8,
                (SELECT @row:=-1) init
             LIMIT tamanho_lote) x;

        SELECT ROW_COUNT() INTO registros_inscritos;

        -- ====================================================================
        -- FASE 2: UPDATE EM MASSA
        -- ====================================================================
        -- Esta operação gera carga em:
        -- - InnoDB row lock waits (se houver contenção)
        -- - InnoDB data writes
        -- - Buffer pool write requests

        UPDATE cadastro
        SET status = CASE
                WHEN status = 'ativo' THEN 'processado'
                WHEN status = 'inativo' THEN 'ativo'
                ELSE 'inativo'
            END,
            nome = CONCAT(nome, '_UPD')
        WHERE status IN ('ativo', 'inativo', 'processado');

        SELECT ROW_COUNT() INTO registros_atualizados;

        -- ====================================================================
        -- FASE 3: DELETE SELETIVO (alternativa ao TRUNCATE)
        -- ====================================================================
        -- Simula carga mais realista que DELETE parcial (mantém alguns dados)
        -- Gera: innodb_system_rows_deleted, table_locks, row lock time

        DELETE FROM cadastro
        WHERE MOD(id, 3) = 0;  -- Remove 1/3 dos registros

        -- ====================================================================
        -- FASE 4: LIMPEZA E MEDIÇÃO I/O
        -- ====================================================================
        -- TRUNCATE libera espaço em disco e reseta auto-increment
        -- Mensurável como: innodb_data_writes, innodb_pages_written

        TRUNCATE TABLE cadastro;

        -- Registrar tempo do lote
        SET fim_lote = NOW(6);
        SET duracao_ms = TIMESTAMPDIFF(MICROSECOND, inicio_lote, fim_lote) / 1000;

        -- Exibir estatísticas do lote
        SELECT CONCAT(
            '  ├─ INSERT: ', FORMAT(registros_inscritos, 0), ' registros em ', duracao_ms, 'ms\n',
            '  ├─ UPDATE: ', FORMAT(registros_atualizados, 0), ' registros\n',
            '  ├─ DELETE: ~', FORMAT(registros_inscritos / 3, 0), ' registros\n',
            '  └─ TRUNCATE: Disco limpo e compactado'
        ) AS lote_resumo;

        SET i = i + 1;
    END LOOP;

    -- Capturar tempo final
    SET tempo_fim_global = NOW(6);
    SET duracao_total_ms = TIMESTAMPDIFF(MICROSECOND, tempo_inicio_global, tempo_fim_global) / 1000;

    -- ========================================================================
    -- RELATÓRIO FINAL
    -- ========================================================================
    SELECT CONCAT(
        '╔════════════════════════════════════════════╗\n',
        '║         TESTE CONCLUÍDO COM SUCESSO        ║\n',
        '║                                            ║\n',
        '║  Total de Operações: 1 Bilhão              ║\n',
        '║  Tempo Total: ', FORMAT(duracao_total_ms / 1000, 2), ' segundos     ║\n',
        '║  Taxa: ', FORMAT(1000000 / (duracao_total_ms / 1000), 0), ' ops/seg        ║\n',
        '║                                            ║\n',
        '╚════════════════════════════════════════════╝'
    ) AS resumo_final;

    -- Exibir estado final da tabela
    SELECT 'Estado Final da Tabela cadastro:' AS secao;
    SELECT TABLE_NAME, ENGINE, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = 'lgtm' AND TABLE_NAME = 'cadastro';

END //

DELIMITER ;

-- ============================================================================
-- 4. EXECUTAR O TESTE DE CARGA
-- ============================================================================

SELECT 'Iniciando teste de carga (este processo pode demorar 10-30 minutos)...' AS info;

CALL gerar_carga_teste();

-- ============================================================================
-- 5. EXIBIR MÉTRICAS COLETADAS (para validar no dashboard)
-- ============================================================================

SELECT '═══ VALIDAÇÃO DE MÉTRICAS ═══' AS secao;

-- Verificar se as métricas estão sendo coletadas pelo mysqld_exporter
SELECT CONCAT(
    'Para validar as métricas no dashboard MySQL:\n',
    '1. Acesse: http://localhost:3000/d/mysql-metrics\n',
    '2. Filtre por instance="srv-mysql-01"\n',
    '3. Verifique os seguintes painéis:\n',
    '   • ACTIVITY: mysql_global_status_questions (deve estar em pico)\n',
    '   • CAPACITY: mysql_global_status_innodb_buffer_pool_* (utilização aumentada)\n',
    '   • DIAGNOSTICS: mysql_global_status_innodb_data_* (I/O ativo)\n',
    '   • HEALTH: mysql_global_status_threads_connected (1 conexão)\n',
    '   • mysql_global_status_uptime (deve manter estável)'
) AS instrucoes_validacao;

SELECT
    'mysql_up' AS metrica,
    'Status do servidor (deve ser 1)' AS descricao,
    'HEALTH' AS pilar;

SELECT
    'mysql_global_status_questions' AS metrica,
    'Queries executadas (deve aumentar drasticamente durante teste)' AS descricao,
    'ACTIVITY' AS pilar;

SELECT
    'mysql_global_status_innodb_buffer_pool_read_requests' AS metrica,
    'Acessos ao buffer (indica hits, deve ser alto)' AS descricao,
    'CAPACITY' AS pilar;

SELECT
    'mysql_global_status_innodb_row_lock_waits' AS metrica,
    'Contentions de lock (deve ser baixo em carga uniforme)' AS descricao,
    'DIAGNOSTICS' AS pilar;

SELECT
    'mysql_global_status_innodb_data_reads' AS metrica,
    'Operações de leitura do disco (I/O metrics)' AS descricao,
    'DIAGNOSTICS' AS pilar;

-- ============================================================================
-- 6. LIMPEZA (opcional - comentada por padrão)
-- ============================================================================

-- Para resetar tudo (descomente se desejar):
-- DROP DATABASE IF EXISTS lgtm;
-- SELECT 'Banco de dados LGTM removido' AS status;
