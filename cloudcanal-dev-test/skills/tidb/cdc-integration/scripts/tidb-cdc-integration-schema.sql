-- CloudCanal TiDB CDC 18-case integration-test schema.
--
-- Run on the source TiDB before creating or starting the CloudCanal task.
-- This deliberately drops and recreates seven tables. Use only the dedicated
-- cc_tidb_cdc_test database and never run it while a task is consuming the DB.

CREATE DATABASE IF NOT EXISTS `cc_tidb_cdc_test`
  CHARACTER
SET utf8mb4
    COLLATE utf8mb4_bin;

USE
`cc_tidb_cdc_test
`;

DROP TABLE IF EXISTS ` cc_CDC_MixedCase `;
DROP TABLE IF EXISTS ` cc_cdc_partition_main `;
DROP TABLE IF EXISTS ` cc_cdc_txn_conflict `;
DROP TABLE IF EXISTS ` cc_cdc_region_03 `;
DROP TABLE IF EXISTS ` cc_cdc_region_02 `;
DROP TABLE IF EXISTS ` cc_cdc_region_01 `;
DROP TABLE IF EXISTS ` cc_cdc_dml_main `;

-- Cases 7, 9, 12, 14, 15, 17, and 18.
CREATE TABLE ` cc_cdc_dml_main `
(
    `
    id` BIGINT PRIMARY KEY
    AUTO_INCREMENT, `
    username` VARCHAR(64) NOT NULL, `
    email` VARCHAR(128)   NOT NULL, `
    age` INT                   DEFAULT NULL, `
    salary` DECIMAL(12, 2)     DEFAULT NULL, `
    is_active ` TINYINT        DEFAULT 1, `
    created_at` TIMESTAMP      DEFAULT CURRENT_TIMESTAMP, `
    updated_at` TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
    ON UPDATE
    CURRENT_TIMESTAMP, `
    birthday` DATE             DEFAULT NULL, `
    login_time ` DATETIME      DEFAULT NULL, `
    profile` VARCHAR(255)      DEFAULT NULL, `
    score` DOUBLE              DEFAULT NULL, `
    balance` DOUBLE            DEFAULT NULL, `
    data_json ` JSON           DEFAULT NULL, `
    binary_data` VARBINARY(64) DEFAULT NULL,
    UNIQUE KEY ` uk_cc_cdc_dml_username ` (` username `),
    KEY ` idx_cc_cdc_dml_email ` (`email`)
);

-- Cases 1, 2, 3, 4, 8, and 13. Consecutive creation makes the table key
-- ranges adjacent, but the case must still confirm the actual region layout.
CREATE TABLE ` cc_cdc_region_01 ` LIKE ` cc_cdc_dml_main `;
CREATE TABLE ` cc_cdc_region_02 ` LIKE ` cc_cdc_dml_main `;
CREATE TABLE ` cc_cdc_region_03 ` LIKE ` cc_cdc_dml_main `;

-- Cases 5 and 6. Insert conflict rows only after task initialization.
CREATE TABLE ` cc_cdc_txn_conflict `
(
    `
    id` BIGINT PRIMARY KEY, `
    uid` BIGINT           DEFAULT NULL, `
    count_value` INT      DEFAULT 0, `
    remark` VARCHAR(128)  DEFAULT NULL, `
    updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ON UPDATE
    CURRENT_TIMESTAMP
);

-- Cases 10 and 16. Case 10 adds p4 during the run.
CREATE TABLE ` cc_cdc_partition_main `
(
    `
    id` BIGINT            NOT NULL, `
    username` VARCHAR(64) NOT NULL, `
    email` VARCHAR(128)   DEFAULT NULL, `
    created_at ` DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (` id `)
)
    PARTITION BY RANGE COLUMNS
(
    `
    id `
)
(
    PARTITION `
    p0 `
    VALUES
    LESS
    THAN
(
    1000
),
    PARTITION `p1` VALUES LESS THAN (2000),
  PARTITION `p2` VALUES LESS THAN (3000),
  PARTITION `p3` VALUES LESS THAN (4000)
);

-- Case 11.
CREATE TABLE ` cc_CDC_MixedCase `
(
    `
    ID` BIGINT PRIMARY KEY
    AUTO_INCREMENT, `
    UserName` VARCHAR(64) NOT NULL, `
    Email` VARCHAR(128)    DEFAULT NULL, `
    Extra_Col` VARCHAR(64) DEFAULT NULL,
    UNIQUE KEY ` uk_cc_cdc_mixed_username ` (` UserName `)
);

-- Deliberately no seed rows. Start and initialize the task before writing
-- unique case markers so pure incremental semantics remain unambiguous.
