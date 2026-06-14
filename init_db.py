# -*- coding: utf-8 -*-
"""Initialize database tables"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
from config_loader import load_db_config
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta


def init_db():
    cfg = load_db_config()
    conn = pymysql.connect(
        host=cfg['host'],
        port=cfg['port'],
        user=cfg['user'],
        password=cfg['password'],
        charset=cfg['charset']
    )
    cursor = conn.cursor()

    # Create database if not exists
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                   f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")

    cursor.execute(f"USE `{cfg['database']}`")

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `users` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `username` VARCHAR(50) NOT NULL,
            `email` VARCHAR(100) NOT NULL UNIQUE,
            `password_hash` VARCHAR(255) NOT NULL,
            `vip_type` VARCHAR(20) DEFAULT NULL COMMENT 'VIP type: month/year',
            `vip_start` DATETIME DEFAULT NULL COMMENT 'VIP start time',
            `vip_end` DATETIME DEFAULT NULL COMMENT 'VIP end time',
            `is_admin` TINYINT(1) DEFAULT 0 COMMENT 'Is admin: 0=no, 1=yes',
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            `feedback_date` DATE DEFAULT NULL COMMENT 'Feedback date',
            `feedback_count` INT DEFAULT 0 COMMENT 'Daily feedback count',
            INDEX `idx_email` (`email`),
            INDEX `idx_vip_type` (`vip_type`),
            INDEX `idx_is_admin` (`is_admin`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    # Check and add missing columns
    cursor.execute("SHOW COLUMNS FROM `users`")
    columns = [row[0] for row in cursor.fetchall()]

    if 'vip_type' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `vip_type` VARCHAR(20) DEFAULT NULL COMMENT 'VIP type: month/year'")
    if 'vip_start' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `vip_start` DATETIME DEFAULT NULL COMMENT 'VIP start time'")
    if 'vip_end' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `vip_end` DATETIME DEFAULT NULL COMMENT 'VIP end time'")
    if 'is_admin' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `is_admin` TINYINT(1) DEFAULT 0 COMMENT 'Is admin: 0=no, 1=yes'")
    if 'feedback_date' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `feedback_date` DATE DEFAULT NULL COMMENT 'Feedback date'")
    if 'feedback_count' not in columns:
        cursor.execute("ALTER TABLE `users` ADD COLUMN `feedback_count` INT DEFAULT 0 COMMENT 'Daily feedback count'")

    conn.commit()
    print("OK - users table ready")

    # ── Seed admin account (environment variables with fallback) ──
    admin_email = os.environ.get('LORATOOL_ADMIN_EMAIL', '2403826556@qq.com')
    admin_password = os.environ.get('LORATOOL_ADMIN_PASS', 'Wayangjie37!')
    admin_username = os.environ.get('LORATOOL_ADMIN_NAME', '管理员')

    # Check if admin exists
    cursor.execute("SELECT id, is_admin FROM `users` WHERE email = %s", (admin_email,))
    admin_row = cursor.fetchone()

    if not admin_row:
        # Create admin account
        password_hash = generate_password_hash(admin_password)
        vip_end = datetime.now() + timedelta(days=365)

        cursor.execute("""
            INSERT INTO `users` (username, email, password_hash, vip_type, vip_start, vip_end, is_admin, created_at)
            VALUES (%s, %s, %s, 'year', NOW(), %s, 1, NOW())
        """, (admin_username, admin_email, password_hash, vip_end))
        conn.commit()
        print(f"OK - Admin account created: {admin_email}")
    else:
        # Ensure is_admin flag
        if not admin_row[1]:
            cursor.execute("UPDATE `users` SET is_admin = 1 WHERE email = %s", (admin_email,))
            conn.commit()
            print(f"OK - Set {admin_email} as admin")
        else:
            print(f"OK - Admin account exists: {admin_email}")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    init_db()
