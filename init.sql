-- ============================================================
-- PPA-Dun MLB Database Initialization Script
-- 클라우드 배포 시 이 파일을 실행하여 모든 테이블을 생성합니다.
--
-- 사용법:
--   mysql -u <user> -p <database> < init.sql
--
-- 최종 업데이트: 2026-04-08
-- ============================================================

-- ------------------------------------------------------------
-- 1. mlb_injuries — 부상 정보 (ESPN API / HTML 스크래핑)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `mlb_injuries` (
    `id`              INT           NOT NULL AUTO_INCREMENT,
    `player_id`       VARCHAR(20)   DEFAULT NULL,
    `player_name`     VARCHAR(255)  DEFAULT NULL,
    `position`        VARCHAR(10)   DEFAULT NULL,
    `team_name`       VARCHAR(255)  DEFAULT NULL,
    `team_abbr`       VARCHAR(10)   DEFAULT NULL,
    `injury_status`   VARCHAR(50)   DEFAULT NULL,
    `injury_detail`   TEXT          DEFAULT NULL,
    `injury_type`     TEXT          DEFAULT NULL,
    `injury_location` VARCHAR(255)  DEFAULT NULL,
    `injury_date`     VARCHAR(30)   DEFAULT NULL,
    `source`          VARCHAR(20)   DEFAULT NULL,
    `fetched_at`      VARCHAR(30)   DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_player_id` (`player_id`),
    KEY `idx_player_id` (`player_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 2. mlb_depth_charts — 팀별 뎁스차트 (ESPN 스크래핑)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `mlb_depth_charts` (
    `id`              INT           NOT NULL AUTO_INCREMENT,
    `team`            VARCHAR(255)  DEFAULT NULL,
    `position`        VARCHAR(10)   DEFAULT NULL,
    `depth_order`     INT           DEFAULT NULL,
    `player_name`     VARCHAR(255)  DEFAULT NULL,
    `espn_player_id`  INT           DEFAULT NULL,
    `injury_status`   VARCHAR(10)   DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_team_pos_order` (`team`, `position`, `depth_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 3. trans_conts_status — 트랜잭션/계약 정보 (MLB Stats API)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `trans_conts_status` (
    `id`              INT           NOT NULL AUTO_INCREMENT,
    `transaction_id`  INT           DEFAULT NULL,
    `type_code`       VARCHAR(20)   DEFAULT NULL,
    `type_desc`       VARCHAR(255)  DEFAULT NULL,
    `description`     TEXT          DEFAULT NULL,
    `date`            VARCHAR(30)   DEFAULT NULL,
    `effective_date`  VARCHAR(30)   DEFAULT NULL,
    `resolution_date` VARCHAR(30)   DEFAULT NULL,
    `player_id`       INT           DEFAULT NULL,
    `player_name`     VARCHAR(255)  DEFAULT NULL,
    `from_team_id`    INT           DEFAULT NULL,
    `from_team_name`  VARCHAR(255)  DEFAULT NULL,
    `to_team_id`      INT           DEFAULT NULL,
    `to_team_name`    VARCHAR(255)  DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_transaction_id` (`transaction_id`),
    KEY `idx_transaction_id` (`transaction_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 4. mlb_players — 전체 선수 목록 (MLB Stats API)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `mlb_players` (
    `id`              INT           NOT NULL AUTO_INCREMENT,
    `player_id`       INT           DEFAULT NULL,
    `full_name`       VARCHAR(255)  DEFAULT NULL,
    `first_name`      VARCHAR(255)  DEFAULT NULL,
    `last_name`       VARCHAR(255)  DEFAULT NULL,
    `primary_number`  VARCHAR(10)   DEFAULT NULL,
    `birth_date`      VARCHAR(20)   DEFAULT NULL,
    `birth_city`      VARCHAR(255)  DEFAULT NULL,
    `birth_country`   VARCHAR(255)  DEFAULT NULL,
    `height`          VARCHAR(10)   DEFAULT NULL,
    `weight`          INT           DEFAULT NULL,
    `current_age`     INT           DEFAULT NULL,
    `position`        VARCHAR(10)   DEFAULT NULL,
    `position_name`   VARCHAR(50)   DEFAULT NULL,
    `team_id`         INT           DEFAULT NULL,
    `team_name`       VARCHAR(255)  DEFAULT NULL,
    `bat_side`        VARCHAR(5)    DEFAULT NULL,
    `pitch_hand`      VARCHAR(5)    DEFAULT NULL,
    `mlb_debut_date`  VARCHAR(20)   DEFAULT NULL,
    `active`          INT           DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_player_id` (`player_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 5. mlb_team_list — MLB 팀 목록 (MLB Stats API)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `mlb_team_list` (
    `id`                  INT           NOT NULL AUTO_INCREMENT,
    `team_id`             INT           DEFAULT NULL,
    `name`                VARCHAR(255)  DEFAULT NULL,
    `team_name`           VARCHAR(255)  DEFAULT NULL,
    `location_name`       VARCHAR(255)  DEFAULT NULL,
    `abbreviation`        VARCHAR(10)   DEFAULT NULL,
    `short_name`          VARCHAR(255)  DEFAULT NULL,
    `franchise_name`      VARCHAR(255)  DEFAULT NULL,
    `club_name`           VARCHAR(255)  DEFAULT NULL,
    `league_id`           INT           DEFAULT NULL,
    `league_name`         VARCHAR(255)  DEFAULT NULL,
    `division_id`         INT           DEFAULT NULL,
    `division_name`       VARCHAR(255)  DEFAULT NULL,
    `venue_id`            INT           DEFAULT NULL,
    `venue_name`          VARCHAR(255)  DEFAULT NULL,
    `first_year_of_play`  VARCHAR(10)   DEFAULT NULL,
    `active`              INT           DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_team_id` (`team_id`),
    KEY `idx_team_id` (`team_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 6. draft_config — 사용자별 드래프트 설정
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `draft_config` (
    `user_id`         VARCHAR(100)  NOT NULL,
    `league_type`     VARCHAR(20)   DEFAULT NULL,
    `budget`          INT           DEFAULT NULL,
    `roster_players`  INT           DEFAULT NULL,
    `my_team_name`    VARCHAR(100)  DEFAULT NULL,
    `opp_team_names`  JSON          DEFAULT NULL,
    `opponents_count` INT           DEFAULT NULL,
    `created_at`      DATETIME      DEFAULT NULL,
    `updated_at`      DATETIME      DEFAULT NULL,
    PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 7. draft_picks — 드래프트 픽 기록
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `draft_picks` (
    `id`                  INT           NOT NULL AUTO_INCREMENT,
    `user_id`             VARCHAR(100)  DEFAULT NULL,
    `player_id`           VARCHAR(20)   DEFAULT NULL,
    `drafted_by_team_id`  VARCHAR(20)   DEFAULT NULL,
    `slot_index`          INT           DEFAULT NULL,
    `slot_pos`            VARCHAR(10)   DEFAULT NULL,
    `bid`                 INT           DEFAULT NULL,
    `pick_type`           VARCHAR(10)   DEFAULT NULL,
    `created_at`          DATETIME      DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_user_player` (`user_id`, `player_id`),
    KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 8. players_stats_nl_2025 — 2025 시즌 선수 스탯 (타격 통계)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `players_stats_nl_2025` (
    `Player`  VARCHAR(100)  DEFAULT NULL,
    `AB`      INT           DEFAULT NULL,
    `R`       INT           DEFAULT NULL,
    `H`       INT           DEFAULT NULL,
    `1B`      INT           DEFAULT NULL,
    `2B`      INT           DEFAULT NULL,
    `3B`      INT           DEFAULT NULL,
    `HR`      INT           DEFAULT NULL,
    `RBI`     INT           DEFAULT NULL,
    `BB`      INT           DEFAULT NULL,
    `K`       INT           DEFAULT NULL,
    `SB`      INT           DEFAULT NULL,
    `CS`      INT           DEFAULT NULL,
    `AVG`     FLOAT         DEFAULT NULL,
    `OBP`     FLOAT         DEFAULT NULL,
    `SLG`     FLOAT         DEFAULT NULL,
    `FPTS`    INT           DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- 9. player_ppa_scores — PPA 가치 점수 및 추천 입찰가
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `player_ppa_scores` (
    `id`              INT           NOT NULL AUTO_INCREMENT,
    `player_id`       INT           DEFAULT NULL,
    `player_name`     VARCHAR(255)  DEFAULT NULL,
    `team`            VARCHAR(255)  DEFAULT NULL,
    `position`        VARCHAR(10)   DEFAULT NULL,
    `value_score`     FLOAT         DEFAULT NULL,
    `recommended_bid` INT           DEFAULT NULL,
    `updated_at`      DATETIME      DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_player_id` (`player_id`),
    KEY `idx_player_id` (`player_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
