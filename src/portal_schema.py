"""Create only the application-owned Durafit portal database and tables."""

from __future__ import annotations

import mysql.connector

from src.portal_db import mysql_options


SCHEMA = """
CREATE DATABASE IF NOT EXISTS `durafit_portal` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_submissions` (
  `submission_id` BINARY(16) NOT NULL PRIMARY KEY,
  `idempotency_key` CHAR(36) NOT NULL UNIQUE,
  `crm_order_id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL,
  `crm_product_name` TEXT NULL, `crm_purchased_product` TEXT NULL, `crm_sku_new` TEXT NULL,
  `crm_customer_name` TEXT NULL, `crm_mobile_number` VARCHAR(64) NULL, `crm_customer_email` VARCHAR(320) NULL,
  `crm_sales_order_owner` VARCHAR(255) NULL,
  `full_name` VARCHAR(255) NOT NULL, `email_address` VARCHAR(320) NULL, `phone_number` VARCHAR(32) NOT NULL,
  `alternate_number` VARCHAR(32) NULL, `order_id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `customer_address` TEXT NOT NULL, `state` VARCHAR(128) NULL, `pincode` VARCHAR(32) NOT NULL,
  `issue_category` VARCHAR(128) NOT NULL, `subject` VARCHAR(255) NULL, `detailed_description` TEXT NOT NULL,
  `submission_status` VARCHAR(32) NOT NULL, `created_at` DATETIME(6) NOT NULL, `updated_at` DATETIME(6) NOT NULL,
  INDEX `ix_portal_submissions_crm_order_created` (`crm_order_id`, `created_at`),
  INDEX `ix_portal_submissions_status_created` (`submission_status`, `created_at`),
  INDEX `ix_portal_submissions_order_created` (`order_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_cases` (
  `case_id` VARCHAR(40) NOT NULL PRIMARY KEY, `submission_id` BINARY(16) NOT NULL UNIQUE,
  `crm_order_id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL, `case_status` VARCHAR(32) NOT NULL,
  `created_at` DATETIME(6) NOT NULL, `updated_at` DATETIME(6) NOT NULL, `closed_at` DATETIME(6) NULL,
  `assigned_to` VARCHAR(255) NULL, `priority` VARCHAR(32) NULL, `internal_notes` TEXT NULL,
  INDEX `ix_portal_cases_crm_order_created` (`crm_order_id`, `created_at`), INDEX `ix_portal_cases_status_created` (`case_status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_submission_attachments` (
  `attachment_id` BINARY(16) NOT NULL PRIMARY KEY, `submission_id` BINARY(16) NOT NULL, `attachment_kind` VARCHAR(32) NOT NULL,
  `display_order` SMALLINT UNSIGNED NOT NULL, `storage_key` VARCHAR(512) NOT NULL UNIQUE, `original_filename` VARCHAR(255) NOT NULL,
  `content_type` VARCHAR(127) NOT NULL, `byte_size` BIGINT UNSIGNED NOT NULL, `sha256` BINARY(32) NOT NULL,
  `upload_status` VARCHAR(32) NOT NULL, `created_at` DATETIME(6) NOT NULL,
  INDEX `ix_portal_attachments_submission_kind_order` (`submission_id`, `attachment_kind`, `display_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_submission_events` (
  `event_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, `submission_id` BINARY(16) NOT NULL, `case_id` VARCHAR(40) NULL,
  `event_type` VARCHAR(64) NOT NULL, `event_payload` JSON NULL, `created_at` DATETIME(6) NOT NULL,
  INDEX `ix_portal_events_submission_created` (`submission_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_email_outbox` (
  `outbox_id` BINARY(16) NOT NULL PRIMARY KEY, `submission_id` BINARY(16) NOT NULL, `message_type` VARCHAR(64) NOT NULL,
  `delivery_status` VARCHAR(32) NOT NULL, `attempt_count` INT UNSIGNED NOT NULL DEFAULT 0, `next_attempt_at` DATETIME(6) NULL,
  `sent_at` DATETIME(6) NULL, `provider_message_id` VARCHAR(255) NULL, `last_error` TEXT NULL,
  UNIQUE KEY `ux_portal_outbox_submission_message` (`submission_id`, `message_type`),
  INDEX `ix_portal_outbox_status_next_attempt` (`delivery_status`, `next_attempt_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS `durafit_portal`.`portal_import_history` (
  `import_id` BINARY(16) NOT NULL PRIMARY KEY, `import_type` VARCHAR(16) NOT NULL,
  `original_filename` VARCHAR(255) NOT NULL, `started_at` DATETIME(6) NOT NULL, `completed_at` DATETIME(6) NULL,
  `total_rows` INT UNSIGNED NOT NULL DEFAULT 0, `inserted_rows` INT UNSIGNED NOT NULL DEFAULT 0,
  `skipped_rows` INT UNSIGNED NOT NULL DEFAULT 0, `failed_rows` INT UNSIGNED NOT NULL DEFAULT 0,
  `status` VARCHAR(32) NOT NULL, `error_summary` TEXT NULL, `created_at` DATETIME(6) NOT NULL,
  INDEX `ix_portal_import_history_type_created` (`import_type`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def create_schema() -> None:
    options = mysql_options()
    options.pop("database", None)
    options.pop("pool_name", None)
    options.pop("pool_size", None)
    options.pop("pool_reset_session", None)
    conn = mysql.connector.connect(**options)
    try:
        cursor = conn.cursor()
        for statement in (part.strip() for part in SCHEMA.split(";") if part.strip()):
            cursor.execute(statement)
        cursor.execute("ALTER TABLE `durafit_portal`.`portal_submissions` MODIFY COLUMN `state` VARCHAR(128) NULL")
        cursor.execute("ALTER TABLE `durafit_portal`.`portal_submissions` MODIFY COLUMN `subject` VARCHAR(255) NULL")
        cursor.execute("ALTER TABLE `durafit_portal`.`portal_submissions` MODIFY COLUMN `crm_order_id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL")
        cursor.execute("ALTER TABLE `durafit_portal`.`portal_cases` MODIFY COLUMN `crm_order_id` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    create_schema()
