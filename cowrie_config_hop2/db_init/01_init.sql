-- Auto-generated honeypot database init script
ALTER USER postgres WITH PASSWORD 'H0n3yp0t_R00t!';

CREATE ROLE replicator WITH LOGIN PASSWORD 'R3pl1c@t0r_Key';
CREATE ROLE backupuser WITH LOGIN PASSWORD 'B@ckup_Usr_2024!';
CREATE ROLE app_user WITH LOGIN PASSWORD 'Pr0d_App_P@ssw0rd';
CREATE ROLE nagios_check WITH LOGIN PASSWORD 'N@g10s_M0n_2024';

-- Seeding default postgres database
GRANT ALL PRIVILEGES ON DATABASE postgres TO replicator;
GRANT ALL PRIVILEGES ON DATABASE postgres TO backupuser;
GRANT ALL PRIVILEGES ON DATABASE postgres TO app_user;
GRANT ALL PRIVILEGES ON DATABASE postgres TO nagios_check;


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    department VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    description TEXT,
    status VARCHAR(20) DEFAULT 'completed',
    reference_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    ip_address INET,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200) NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (1, 'admin', 'admin@corp.internal', '$2b$12$fakehash0001', 'admin', 'IT', '2024-02-02 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (2, 'jsmith', 'john.smith@corp.internal', '$2b$12$fakehash0002', 'manager', 'Finance', '2024-03-03 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (3, 'alee', 'alice.lee@corp.internal', '$2b$12$fakehash0003', 'analyst', 'Finance', '2024-04-04 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (4, 'bwilson', 'bob.wilson@corp.internal', '$2b$12$fakehash0004', 'developer', 'Engineering', '2024-05-05 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (5, 'cmartinez', 'carol.martinez@corp.internal', '$2b$12$fakehash0005', 'developer', 'Engineering', '2024-06-06 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (6, 'dchen', 'david.chen@corp.internal', '$2b$12$fakehash0006', 'lead', 'Engineering', '2024-07-07 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (7, 'ejohnson', 'emma.johnson@corp.internal', '$2b$12$fakehash0007', 'analyst', 'HR', '2024-08-08 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (8, 'fgarcia', 'frank.garcia@corp.internal', '$2b$12$fakehash0008', 'manager', 'Operations', '2024-09-09 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (9, 'gwhite', 'grace.white@corp.internal', '$2b$12$fakehash0009', 'developer', 'Engineering', '2024-10-10 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (10, 'hbrown', 'henry.brown@corp.internal', '$2b$12$fakehash0010', 'analyst', 'Marketing', '2024-11-11 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (11, 'itaylor', 'iris.taylor@corp.internal', '$2b$12$fakehash0011', 'developer', 'Engineering', '2024-12-12 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (12, 'jdavis', 'jack.davis@corp.internal', '$2b$12$fakehash0012', 'sysadmin', 'IT', '2024-01-13 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (13, 'kmoore', 'karen.moore@corp.internal', '$2b$12$fakehash0013', 'manager', 'Sales', '2024-02-14 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (14, 'lthompson', 'larry.thompson@corp.internal', '$2b$12$fakehash0014', 'analyst', 'Finance', '2024-03-15 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (15, 'manderson', 'maria.anderson@corp.internal', '$2b$12$fakehash0015', 'developer', 'Engineering', '2024-04-16 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (16, 'nclark', 'nick.clark@corp.internal', '$2b$12$fakehash0016', 'intern', 'Engineering', '2024-05-17 09:00:00', false);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (17, 'owright', 'olivia.wright@corp.internal', '$2b$12$fakehash0017', 'analyst', 'Operations', '2024-06-18 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (18, 'pyoung', 'peter.young@corp.internal', '$2b$12$fakehash0018', 'developer', 'Engineering', '2024-07-19 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (19, 'qhall', 'quinn.hall@corp.internal', '$2b$12$fakehash0019', 'manager', 'IT', '2024-08-20 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (20, 'rking', 'rachel.king@corp.internal', '$2b$12$fakehash0020', 'analyst', 'Marketing', '2024-09-21 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (21, 'sgreen', 'scott.green@corp.internal', '$2b$12$fakehash0021', 'developer', 'Engineering', '2024-10-22 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (22, 'tadams', 'tina.adams@corp.internal', '$2b$12$fakehash0022', 'admin', 'IT', '2024-11-23 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (23, 'ubaker', 'ursula.baker@corp.internal', '$2b$12$fakehash0023', 'analyst', 'HR', '2024-12-24 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (24, 'vcarter', 'victor.carter@corp.internal', '$2b$12$fakehash0024', 'developer', 'Engineering', '2024-01-25 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (25, 'service_account', 'svc@corp.internal', '$2b$12$fakehash0025', 'service', 'IT', '2024-02-26 09:00:00', true);
SELECT setval('users_id_seq', 25);
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (1, 2, 57.37, 'USD', 'Transaction TXN-2024-000001', 'completed', 'TXN-2024-000001', '2024-01-02 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (2, 3, 64.74, 'USD', 'Transaction TXN-2024-000002', 'completed', 'TXN-2024-000002', '2024-01-03 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (3, 4, 72.11, 'USD', 'Transaction TXN-2024-000003', 'completed', 'TXN-2024-000003', '2024-01-04 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (4, 5, 79.48, 'USD', 'Transaction TXN-2024-000004', 'completed', 'TXN-2024-000004', '2024-01-05 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (5, 6, 86.85, 'USD', 'Transaction TXN-2024-000005', 'completed', 'TXN-2024-000005', '2024-01-06 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (6, 7, 94.22, 'USD', 'Transaction TXN-2024-000006', 'completed', 'TXN-2024-000006', '2024-01-07 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (7, 8, 101.59, 'USD', 'Transaction TXN-2024-000007', 'completed', 'TXN-2024-000007', '2024-01-08 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (8, 9, 108.96, 'USD', 'Transaction TXN-2024-000008', 'completed', 'TXN-2024-000008', '2024-01-09 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (9, 10, 116.33, 'USD', 'Transaction TXN-2024-000009', 'completed', 'TXN-2024-000009', '2024-01-10 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (10, 11, 123.7, 'USD', 'Transaction TXN-2024-000010', 'pending', 'TXN-2024-000010', '2024-01-11 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (11, 12, 131.07, 'USD', 'Transaction TXN-2024-000011', 'completed', 'TXN-2024-000011', '2024-01-12 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (12, 13, 138.44, 'USD', 'Transaction TXN-2024-000012', 'completed', 'TXN-2024-000012', '2024-01-13 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (13, 14, 145.81, 'USD', 'Transaction TXN-2024-000013', 'completed', 'TXN-2024-000013', '2024-01-14 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (14, 15, 153.18, 'USD', 'Transaction TXN-2024-000014', 'completed', 'TXN-2024-000014', '2024-01-15 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (15, 16, 160.55, 'USD', 'Transaction TXN-2024-000015', 'completed', 'TXN-2024-000015', '2024-01-16 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (16, 17, 167.92, 'USD', 'Transaction TXN-2024-000016', 'completed', 'TXN-2024-000016', '2024-01-17 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (17, 18, 175.29, 'USD', 'Transaction TXN-2024-000017', 'completed', 'TXN-2024-000017', '2024-01-18 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (18, 19, 182.66, 'USD', 'Transaction TXN-2024-000018', 'completed', 'TXN-2024-000018', '2024-01-19 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (19, 20, 190.03, 'USD', 'Transaction TXN-2024-000019', 'completed', 'TXN-2024-000019', '2024-01-20 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (20, 1, 197.4, 'USD', 'Transaction TXN-2024-000020', 'failed', 'TXN-2024-000020', '2024-01-21 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (21, 2, 204.77, 'USD', 'Transaction TXN-2024-000021', 'completed', 'TXN-2024-000021', '2024-02-22 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (22, 3, 212.14, 'USD', 'Transaction TXN-2024-000022', 'completed', 'TXN-2024-000022', '2024-02-23 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (23, 4, 219.51, 'USD', 'Transaction TXN-2024-000023', 'completed', 'TXN-2024-000023', '2024-02-24 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (24, 5, 226.88, 'USD', 'Transaction TXN-2024-000024', 'completed', 'TXN-2024-000024', '2024-02-25 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (25, 6, 234.25, 'USD', 'Transaction TXN-2024-000025', 'completed', 'TXN-2024-000025', '2024-02-26 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (26, 7, 241.62, 'USD', 'Transaction TXN-2024-000026', 'completed', 'TXN-2024-000026', '2024-02-27 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (27, 8, 248.99, 'USD', 'Transaction TXN-2024-000027', 'completed', 'TXN-2024-000027', '2024-02-28 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (28, 9, 256.36, 'USD', 'Transaction TXN-2024-000028', 'completed', 'TXN-2024-000028', '2024-02-01 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (29, 10, 263.73, 'USD', 'Transaction TXN-2024-000029', 'completed', 'TXN-2024-000029', '2024-02-02 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (30, 11, 271.1, 'USD', 'Transaction TXN-2024-000030', 'pending', 'TXN-2024-000030', '2024-02-03 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (31, 12, 278.47, 'USD', 'Transaction TXN-2024-000031', 'completed', 'TXN-2024-000031', '2024-02-04 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (32, 13, 285.84, 'USD', 'Transaction TXN-2024-000032', 'completed', 'TXN-2024-000032', '2024-02-05 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (33, 14, 293.21, 'USD', 'Transaction TXN-2024-000033', 'completed', 'TXN-2024-000033', '2024-02-06 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (34, 15, 300.58, 'USD', 'Transaction TXN-2024-000034', 'completed', 'TXN-2024-000034', '2024-02-07 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (35, 16, 307.95, 'USD', 'Transaction TXN-2024-000035', 'completed', 'TXN-2024-000035', '2024-02-08 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (36, 17, 315.32, 'USD', 'Transaction TXN-2024-000036', 'completed', 'TXN-2024-000036', '2024-02-09 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (37, 18, 322.69, 'USD', 'Transaction TXN-2024-000037', 'completed', 'TXN-2024-000037', '2024-02-10 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (38, 19, 330.06, 'USD', 'Transaction TXN-2024-000038', 'completed', 'TXN-2024-000038', '2024-02-11 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (39, 20, 337.43, 'USD', 'Transaction TXN-2024-000039', 'completed', 'TXN-2024-000039', '2024-02-12 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (40, 1, 344.8, 'USD', 'Transaction TXN-2024-000040', 'failed', 'TXN-2024-000040', '2024-02-13 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (41, 2, 352.17, 'USD', 'Transaction TXN-2024-000041', 'completed', 'TXN-2024-000041', '2024-03-14 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (42, 3, 359.54, 'USD', 'Transaction TXN-2024-000042', 'completed', 'TXN-2024-000042', '2024-03-15 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (43, 4, 366.91, 'USD', 'Transaction TXN-2024-000043', 'completed', 'TXN-2024-000043', '2024-03-16 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (44, 5, 374.28, 'USD', 'Transaction TXN-2024-000044', 'completed', 'TXN-2024-000044', '2024-03-17 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (45, 6, 381.65, 'USD', 'Transaction TXN-2024-000045', 'completed', 'TXN-2024-000045', '2024-03-18 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (46, 7, 389.02, 'USD', 'Transaction TXN-2024-000046', 'completed', 'TXN-2024-000046', '2024-03-19 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (47, 8, 396.39, 'USD', 'Transaction TXN-2024-000047', 'completed', 'TXN-2024-000047', '2024-03-20 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (48, 9, 403.76, 'USD', 'Transaction TXN-2024-000048', 'completed', 'TXN-2024-000048', '2024-03-21 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (49, 10, 411.13, 'USD', 'Transaction TXN-2024-000049', 'completed', 'TXN-2024-000049', '2024-03-22 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (50, 11, 418.5, 'USD', 'Transaction TXN-2024-000050', 'pending', 'TXN-2024-000050', '2024-03-23 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (51, 12, 425.87, 'USD', 'Transaction TXN-2024-000051', 'completed', 'TXN-2024-000051', '2024-03-24 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (52, 13, 433.24, 'USD', 'Transaction TXN-2024-000052', 'completed', 'TXN-2024-000052', '2024-03-25 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (53, 14, 440.61, 'USD', 'Transaction TXN-2024-000053', 'completed', 'TXN-2024-000053', '2024-03-26 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (54, 15, 447.98, 'USD', 'Transaction TXN-2024-000054', 'completed', 'TXN-2024-000054', '2024-03-27 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (55, 16, 455.35, 'USD', 'Transaction TXN-2024-000055', 'completed', 'TXN-2024-000055', '2024-03-28 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (56, 17, 462.72, 'USD', 'Transaction TXN-2024-000056', 'completed', 'TXN-2024-000056', '2024-03-01 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (57, 18, 470.09, 'USD', 'Transaction TXN-2024-000057', 'completed', 'TXN-2024-000057', '2024-03-02 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (58, 19, 477.46, 'USD', 'Transaction TXN-2024-000058', 'completed', 'TXN-2024-000058', '2024-03-03 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (59, 20, 484.83, 'USD', 'Transaction TXN-2024-000059', 'completed', 'TXN-2024-000059', '2024-03-04 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (60, 1, 492.2, 'USD', 'Transaction TXN-2024-000060', 'failed', 'TXN-2024-000060', '2024-03-05 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (61, 2, 499.57, 'USD', 'Transaction TXN-2024-000061', 'completed', 'TXN-2024-000061', '2024-04-06 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (62, 3, 506.94, 'USD', 'Transaction TXN-2024-000062', 'completed', 'TXN-2024-000062', '2024-04-07 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (63, 4, 514.31, 'USD', 'Transaction TXN-2024-000063', 'completed', 'TXN-2024-000063', '2024-04-08 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (64, 5, 521.68, 'USD', 'Transaction TXN-2024-000064', 'completed', 'TXN-2024-000064', '2024-04-09 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (65, 6, 529.05, 'USD', 'Transaction TXN-2024-000065', 'completed', 'TXN-2024-000065', '2024-04-10 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (66, 7, 536.42, 'USD', 'Transaction TXN-2024-000066', 'completed', 'TXN-2024-000066', '2024-04-11 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (67, 8, 543.79, 'USD', 'Transaction TXN-2024-000067', 'completed', 'TXN-2024-000067', '2024-04-12 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (68, 9, 551.16, 'USD', 'Transaction TXN-2024-000068', 'completed', 'TXN-2024-000068', '2024-04-13 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (69, 10, 558.53, 'USD', 'Transaction TXN-2024-000069', 'completed', 'TXN-2024-000069', '2024-04-14 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (70, 11, 565.9, 'USD', 'Transaction TXN-2024-000070', 'pending', 'TXN-2024-000070', '2024-04-15 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (71, 12, 573.27, 'USD', 'Transaction TXN-2024-000071', 'completed', 'TXN-2024-000071', '2024-04-16 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (72, 13, 580.64, 'USD', 'Transaction TXN-2024-000072', 'completed', 'TXN-2024-000072', '2024-04-17 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (73, 14, 588.01, 'USD', 'Transaction TXN-2024-000073', 'completed', 'TXN-2024-000073', '2024-04-18 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (74, 15, 595.38, 'USD', 'Transaction TXN-2024-000074', 'completed', 'TXN-2024-000074', '2024-04-19 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (75, 16, 602.75, 'USD', 'Transaction TXN-2024-000075', 'completed', 'TXN-2024-000075', '2024-04-20 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (76, 17, 610.12, 'USD', 'Transaction TXN-2024-000076', 'completed', 'TXN-2024-000076', '2024-04-21 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (77, 18, 617.49, 'USD', 'Transaction TXN-2024-000077', 'completed', 'TXN-2024-000077', '2024-04-22 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (78, 19, 624.86, 'USD', 'Transaction TXN-2024-000078', 'completed', 'TXN-2024-000078', '2024-04-23 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (79, 20, 632.23, 'USD', 'Transaction TXN-2024-000079', 'completed', 'TXN-2024-000079', '2024-04-24 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (80, 1, 639.6, 'USD', 'Transaction TXN-2024-000080', 'failed', 'TXN-2024-000080', '2024-04-25 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (81, 2, 646.97, 'USD', 'Transaction TXN-2024-000081', 'completed', 'TXN-2024-000081', '2024-05-26 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (82, 3, 654.34, 'USD', 'Transaction TXN-2024-000082', 'completed', 'TXN-2024-000082', '2024-05-27 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (83, 4, 661.71, 'USD', 'Transaction TXN-2024-000083', 'completed', 'TXN-2024-000083', '2024-05-28 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (84, 5, 669.08, 'USD', 'Transaction TXN-2024-000084', 'completed', 'TXN-2024-000084', '2024-05-01 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (85, 6, 676.45, 'USD', 'Transaction TXN-2024-000085', 'completed', 'TXN-2024-000085', '2024-05-02 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (86, 7, 683.82, 'USD', 'Transaction TXN-2024-000086', 'completed', 'TXN-2024-000086', '2024-05-03 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (87, 8, 691.19, 'USD', 'Transaction TXN-2024-000087', 'completed', 'TXN-2024-000087', '2024-05-04 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (88, 9, 698.56, 'USD', 'Transaction TXN-2024-000088', 'completed', 'TXN-2024-000088', '2024-05-05 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (89, 10, 705.93, 'USD', 'Transaction TXN-2024-000089', 'completed', 'TXN-2024-000089', '2024-05-06 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (90, 11, 713.3, 'USD', 'Transaction TXN-2024-000090', 'pending', 'TXN-2024-000090', '2024-05-07 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (91, 12, 720.67, 'USD', 'Transaction TXN-2024-000091', 'completed', 'TXN-2024-000091', '2024-05-08 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (92, 13, 728.04, 'USD', 'Transaction TXN-2024-000092', 'completed', 'TXN-2024-000092', '2024-05-09 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (93, 14, 735.41, 'USD', 'Transaction TXN-2024-000093', 'completed', 'TXN-2024-000093', '2024-05-10 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (94, 15, 742.78, 'USD', 'Transaction TXN-2024-000094', 'completed', 'TXN-2024-000094', '2024-05-11 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (95, 16, 750.15, 'USD', 'Transaction TXN-2024-000095', 'completed', 'TXN-2024-000095', '2024-05-12 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (96, 17, 757.52, 'USD', 'Transaction TXN-2024-000096', 'completed', 'TXN-2024-000096', '2024-05-13 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (97, 18, 764.89, 'USD', 'Transaction TXN-2024-000097', 'completed', 'TXN-2024-000097', '2024-05-14 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (98, 19, 772.26, 'USD', 'Transaction TXN-2024-000098', 'completed', 'TXN-2024-000098', '2024-05-15 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (99, 20, 779.63, 'USD', 'Transaction TXN-2024-000099', 'completed', 'TXN-2024-000099', '2024-05-16 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (100, 1, 787.0, 'USD', 'Transaction TXN-2024-000100', 'failed', 'TXN-2024-000100', '2024-05-17 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (101, 2, 794.37, 'USD', 'Transaction TXN-2024-000101', 'completed', 'TXN-2024-000101', '2024-06-18 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (102, 3, 801.74, 'USD', 'Transaction TXN-2024-000102', 'completed', 'TXN-2024-000102', '2024-06-19 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (103, 4, 809.11, 'USD', 'Transaction TXN-2024-000103', 'completed', 'TXN-2024-000103', '2024-06-20 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (104, 5, 816.48, 'USD', 'Transaction TXN-2024-000104', 'completed', 'TXN-2024-000104', '2024-06-21 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (105, 6, 823.85, 'USD', 'Transaction TXN-2024-000105', 'completed', 'TXN-2024-000105', '2024-06-22 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (106, 7, 831.22, 'USD', 'Transaction TXN-2024-000106', 'completed', 'TXN-2024-000106', '2024-06-23 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (107, 8, 838.59, 'USD', 'Transaction TXN-2024-000107', 'completed', 'TXN-2024-000107', '2024-06-24 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (108, 9, 845.96, 'USD', 'Transaction TXN-2024-000108', 'completed', 'TXN-2024-000108', '2024-06-25 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (109, 10, 853.33, 'USD', 'Transaction TXN-2024-000109', 'completed', 'TXN-2024-000109', '2024-06-26 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (110, 11, 860.7, 'USD', 'Transaction TXN-2024-000110', 'pending', 'TXN-2024-000110', '2024-06-27 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (111, 12, 868.07, 'USD', 'Transaction TXN-2024-000111', 'completed', 'TXN-2024-000111', '2024-06-28 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (112, 13, 875.44, 'USD', 'Transaction TXN-2024-000112', 'completed', 'TXN-2024-000112', '2024-06-01 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (113, 14, 882.81, 'USD', 'Transaction TXN-2024-000113', 'completed', 'TXN-2024-000113', '2024-06-02 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (114, 15, 890.18, 'USD', 'Transaction TXN-2024-000114', 'completed', 'TXN-2024-000114', '2024-06-03 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (115, 16, 897.55, 'USD', 'Transaction TXN-2024-000115', 'completed', 'TXN-2024-000115', '2024-06-04 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (116, 17, 904.92, 'USD', 'Transaction TXN-2024-000116', 'completed', 'TXN-2024-000116', '2024-06-05 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (117, 18, 912.29, 'USD', 'Transaction TXN-2024-000117', 'completed', 'TXN-2024-000117', '2024-06-06 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (118, 19, 919.66, 'USD', 'Transaction TXN-2024-000118', 'completed', 'TXN-2024-000118', '2024-06-07 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (119, 20, 927.03, 'USD', 'Transaction TXN-2024-000119', 'completed', 'TXN-2024-000119', '2024-06-08 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (120, 1, 934.4, 'USD', 'Transaction TXN-2024-000120', 'failed', 'TXN-2024-000120', '2024-06-09 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (121, 2, 941.77, 'USD', 'Transaction TXN-2024-000121', 'completed', 'TXN-2024-000121', '2024-07-10 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (122, 3, 949.14, 'USD', 'Transaction TXN-2024-000122', 'completed', 'TXN-2024-000122', '2024-07-11 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (123, 4, 956.51, 'USD', 'Transaction TXN-2024-000123', 'completed', 'TXN-2024-000123', '2024-07-12 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (124, 5, 963.88, 'USD', 'Transaction TXN-2024-000124', 'completed', 'TXN-2024-000124', '2024-07-13 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (125, 6, 971.25, 'USD', 'Transaction TXN-2024-000125', 'completed', 'TXN-2024-000125', '2024-07-14 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (126, 7, 978.62, 'USD', 'Transaction TXN-2024-000126', 'completed', 'TXN-2024-000126', '2024-07-15 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (127, 8, 985.99, 'USD', 'Transaction TXN-2024-000127', 'completed', 'TXN-2024-000127', '2024-07-16 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (128, 9, 993.36, 'USD', 'Transaction TXN-2024-000128', 'completed', 'TXN-2024-000128', '2024-07-17 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (129, 10, 1000.73, 'USD', 'Transaction TXN-2024-000129', 'completed', 'TXN-2024-000129', '2024-07-18 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (130, 11, 1008.1, 'USD', 'Transaction TXN-2024-000130', 'pending', 'TXN-2024-000130', '2024-07-19 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (131, 12, 1015.47, 'USD', 'Transaction TXN-2024-000131', 'completed', 'TXN-2024-000131', '2024-07-20 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (132, 13, 1022.84, 'USD', 'Transaction TXN-2024-000132', 'completed', 'TXN-2024-000132', '2024-07-21 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (133, 14, 1030.21, 'USD', 'Transaction TXN-2024-000133', 'completed', 'TXN-2024-000133', '2024-07-22 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (134, 15, 1037.58, 'USD', 'Transaction TXN-2024-000134', 'completed', 'TXN-2024-000134', '2024-07-23 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (135, 16, 1044.95, 'USD', 'Transaction TXN-2024-000135', 'completed', 'TXN-2024-000135', '2024-07-24 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (136, 17, 1052.32, 'USD', 'Transaction TXN-2024-000136', 'completed', 'TXN-2024-000136', '2024-07-25 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (137, 18, 1059.69, 'USD', 'Transaction TXN-2024-000137', 'completed', 'TXN-2024-000137', '2024-07-26 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (138, 19, 1067.06, 'USD', 'Transaction TXN-2024-000138', 'completed', 'TXN-2024-000138', '2024-07-27 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (139, 20, 1074.43, 'USD', 'Transaction TXN-2024-000139', 'completed', 'TXN-2024-000139', '2024-07-28 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (140, 1, 1081.8, 'USD', 'Transaction TXN-2024-000140', 'failed', 'TXN-2024-000140', '2024-07-01 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (141, 2, 1089.17, 'USD', 'Transaction TXN-2024-000141', 'completed', 'TXN-2024-000141', '2024-08-02 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (142, 3, 1096.54, 'USD', 'Transaction TXN-2024-000142', 'completed', 'TXN-2024-000142', '2024-08-03 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (143, 4, 1103.91, 'USD', 'Transaction TXN-2024-000143', 'completed', 'TXN-2024-000143', '2024-08-04 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (144, 5, 1111.28, 'USD', 'Transaction TXN-2024-000144', 'completed', 'TXN-2024-000144', '2024-08-05 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (145, 6, 1118.65, 'USD', 'Transaction TXN-2024-000145', 'completed', 'TXN-2024-000145', '2024-08-06 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (146, 7, 1126.02, 'USD', 'Transaction TXN-2024-000146', 'completed', 'TXN-2024-000146', '2024-08-07 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (147, 8, 1133.39, 'USD', 'Transaction TXN-2024-000147', 'completed', 'TXN-2024-000147', '2024-08-08 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (148, 9, 1140.76, 'USD', 'Transaction TXN-2024-000148', 'completed', 'TXN-2024-000148', '2024-08-09 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (149, 10, 1148.13, 'USD', 'Transaction TXN-2024-000149', 'completed', 'TXN-2024-000149', '2024-08-10 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (150, 11, 1155.5, 'USD', 'Transaction TXN-2024-000150', 'pending', 'TXN-2024-000150', '2024-08-11 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (151, 12, 1162.87, 'USD', 'Transaction TXN-2024-000151', 'completed', 'TXN-2024-000151', '2024-08-12 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (152, 13, 1170.24, 'USD', 'Transaction TXN-2024-000152', 'completed', 'TXN-2024-000152', '2024-08-13 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (153, 14, 1177.61, 'USD', 'Transaction TXN-2024-000153', 'completed', 'TXN-2024-000153', '2024-08-14 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (154, 15, 1184.98, 'USD', 'Transaction TXN-2024-000154', 'completed', 'TXN-2024-000154', '2024-08-15 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (155, 16, 1192.35, 'USD', 'Transaction TXN-2024-000155', 'completed', 'TXN-2024-000155', '2024-08-16 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (156, 17, 1199.72, 'USD', 'Transaction TXN-2024-000156', 'completed', 'TXN-2024-000156', '2024-08-17 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (157, 18, 1207.09, 'USD', 'Transaction TXN-2024-000157', 'completed', 'TXN-2024-000157', '2024-08-18 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (158, 19, 1214.46, 'USD', 'Transaction TXN-2024-000158', 'completed', 'TXN-2024-000158', '2024-08-19 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (159, 20, 1221.83, 'USD', 'Transaction TXN-2024-000159', 'completed', 'TXN-2024-000159', '2024-08-20 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (160, 1, 1229.2, 'USD', 'Transaction TXN-2024-000160', 'failed', 'TXN-2024-000160', '2024-08-21 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (161, 2, 1236.57, 'USD', 'Transaction TXN-2024-000161', 'completed', 'TXN-2024-000161', '2024-09-22 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (162, 3, 1243.94, 'USD', 'Transaction TXN-2024-000162', 'completed', 'TXN-2024-000162', '2024-09-23 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (163, 4, 1251.31, 'USD', 'Transaction TXN-2024-000163', 'completed', 'TXN-2024-000163', '2024-09-24 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (164, 5, 1258.68, 'USD', 'Transaction TXN-2024-000164', 'completed', 'TXN-2024-000164', '2024-09-25 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (165, 6, 1266.05, 'USD', 'Transaction TXN-2024-000165', 'completed', 'TXN-2024-000165', '2024-09-26 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (166, 7, 1273.42, 'USD', 'Transaction TXN-2024-000166', 'completed', 'TXN-2024-000166', '2024-09-27 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (167, 8, 1280.79, 'USD', 'Transaction TXN-2024-000167', 'completed', 'TXN-2024-000167', '2024-09-28 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (168, 9, 1288.16, 'USD', 'Transaction TXN-2024-000168', 'completed', 'TXN-2024-000168', '2024-09-01 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (169, 10, 1295.53, 'USD', 'Transaction TXN-2024-000169', 'completed', 'TXN-2024-000169', '2024-09-02 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (170, 11, 1302.9, 'USD', 'Transaction TXN-2024-000170', 'pending', 'TXN-2024-000170', '2024-09-03 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (171, 12, 1310.27, 'USD', 'Transaction TXN-2024-000171', 'completed', 'TXN-2024-000171', '2024-09-04 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (172, 13, 1317.64, 'USD', 'Transaction TXN-2024-000172', 'completed', 'TXN-2024-000172', '2024-09-05 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (173, 14, 1325.01, 'USD', 'Transaction TXN-2024-000173', 'completed', 'TXN-2024-000173', '2024-09-06 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (174, 15, 1332.38, 'USD', 'Transaction TXN-2024-000174', 'completed', 'TXN-2024-000174', '2024-09-07 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (175, 16, 1339.75, 'USD', 'Transaction TXN-2024-000175', 'completed', 'TXN-2024-000175', '2024-09-08 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (176, 17, 1347.12, 'USD', 'Transaction TXN-2024-000176', 'completed', 'TXN-2024-000176', '2024-09-09 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (177, 18, 1354.49, 'USD', 'Transaction TXN-2024-000177', 'completed', 'TXN-2024-000177', '2024-09-10 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (178, 19, 1361.86, 'USD', 'Transaction TXN-2024-000178', 'completed', 'TXN-2024-000178', '2024-09-11 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (179, 20, 1369.23, 'USD', 'Transaction TXN-2024-000179', 'completed', 'TXN-2024-000179', '2024-09-12 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (180, 1, 1376.6, 'USD', 'Transaction TXN-2024-000180', 'failed', 'TXN-2024-000180', '2024-09-13 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (181, 2, 1383.97, 'USD', 'Transaction TXN-2024-000181', 'completed', 'TXN-2024-000181', '2024-10-14 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (182, 3, 1391.34, 'USD', 'Transaction TXN-2024-000182', 'completed', 'TXN-2024-000182', '2024-10-15 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (183, 4, 1398.71, 'USD', 'Transaction TXN-2024-000183', 'completed', 'TXN-2024-000183', '2024-10-16 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (184, 5, 1406.08, 'USD', 'Transaction TXN-2024-000184', 'completed', 'TXN-2024-000184', '2024-10-17 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (185, 6, 1413.45, 'USD', 'Transaction TXN-2024-000185', 'completed', 'TXN-2024-000185', '2024-10-18 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (186, 7, 1420.82, 'USD', 'Transaction TXN-2024-000186', 'completed', 'TXN-2024-000186', '2024-10-19 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (187, 8, 1428.19, 'USD', 'Transaction TXN-2024-000187', 'completed', 'TXN-2024-000187', '2024-10-20 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (188, 9, 1435.56, 'USD', 'Transaction TXN-2024-000188', 'completed', 'TXN-2024-000188', '2024-10-21 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (189, 10, 1442.93, 'USD', 'Transaction TXN-2024-000189', 'completed', 'TXN-2024-000189', '2024-10-22 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (190, 11, 1450.3, 'USD', 'Transaction TXN-2024-000190', 'pending', 'TXN-2024-000190', '2024-10-23 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (191, 12, 1457.67, 'USD', 'Transaction TXN-2024-000191', 'completed', 'TXN-2024-000191', '2024-10-24 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (192, 13, 1465.04, 'USD', 'Transaction TXN-2024-000192', 'completed', 'TXN-2024-000192', '2024-10-25 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (193, 14, 1472.41, 'USD', 'Transaction TXN-2024-000193', 'completed', 'TXN-2024-000193', '2024-10-26 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (194, 15, 1479.78, 'USD', 'Transaction TXN-2024-000194', 'completed', 'TXN-2024-000194', '2024-10-27 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (195, 16, 1487.15, 'USD', 'Transaction TXN-2024-000195', 'completed', 'TXN-2024-000195', '2024-10-28 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (196, 17, 1494.52, 'USD', 'Transaction TXN-2024-000196', 'completed', 'TXN-2024-000196', '2024-10-01 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (197, 18, 1501.89, 'USD', 'Transaction TXN-2024-000197', 'completed', 'TXN-2024-000197', '2024-10-02 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (198, 19, 1509.26, 'USD', 'Transaction TXN-2024-000198', 'completed', 'TXN-2024-000198', '2024-10-03 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (199, 20, 1516.63, 'USD', 'Transaction TXN-2024-000199', 'completed', 'TXN-2024-000199', '2024-10-04 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (200, 1, 1524.0, 'USD', 'Transaction TXN-2024-000200', 'failed', 'TXN-2024-000200', '2024-10-05 08:20:00');
SELECT setval('transactions_id_seq', 200);
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (1, 2, 'logout', '/api/v1/logout', '10.0.11.101', '2024-01-02 09:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (2, 3, 'view_report', '/api/v1/view_report', '10.0.12.102', '2024-01-03 10:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (3, 4, 'export_data', '/api/v1/export_data', '10.0.13.103', '2024-01-04 11:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (4, 5, 'update_record', '/api/v1/update_record', '10.0.14.104', '2024-01-05 12:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (5, 6, 'create_user', '/api/v1/create_user', '10.0.10.105', '2024-01-06 13:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (6, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.106', '2024-01-07 14:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (7, 8, 'change_password', '/api/v1/change_password', '10.0.12.107', '2024-01-08 15:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (8, 9, 'api_call', '/api/v1/api_call', '10.0.13.108', '2024-01-09 16:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (9, 10, 'config_change', '/api/v1/config_change', '10.0.14.109', '2024-01-10 17:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (10, 11, 'login', '/api/v1/login', '10.0.10.110', '2024-01-11 18:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (11, 12, 'logout', '/api/v1/logout', '10.0.11.111', '2024-02-12 19:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (12, 13, 'view_report', '/api/v1/view_report', '10.0.12.112', '2024-02-13 20:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (13, 14, 'export_data', '/api/v1/export_data', '10.0.13.113', '2024-02-14 21:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (14, 15, 'update_record', '/api/v1/update_record', '10.0.14.114', '2024-02-15 08:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (15, 16, 'create_user', '/api/v1/create_user', '10.0.10.115', '2024-02-16 09:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (16, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.116', '2024-02-17 10:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (17, 18, 'change_password', '/api/v1/change_password', '10.0.12.117', '2024-02-18 11:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (18, 19, 'api_call', '/api/v1/api_call', '10.0.13.118', '2024-02-19 12:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (19, 20, 'config_change', '/api/v1/config_change', '10.0.14.119', '2024-02-20 13:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (20, 21, 'login', '/api/v1/login', '10.0.10.120', '2024-02-21 14:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (21, 22, 'logout', '/api/v1/logout', '10.0.11.121', '2024-03-22 15:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (22, 23, 'view_report', '/api/v1/view_report', '10.0.12.122', '2024-03-23 16:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (23, 24, 'export_data', '/api/v1/export_data', '10.0.13.123', '2024-03-24 17:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (24, 25, 'update_record', '/api/v1/update_record', '10.0.14.124', '2024-03-25 18:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (25, 1, 'create_user', '/api/v1/create_user', '10.0.10.125', '2024-03-26 19:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (26, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.126', '2024-03-27 20:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (27, 3, 'change_password', '/api/v1/change_password', '10.0.12.127', '2024-03-28 21:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (28, 4, 'api_call', '/api/v1/api_call', '10.0.13.128', '2024-03-01 08:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (29, 5, 'config_change', '/api/v1/config_change', '10.0.14.129', '2024-03-02 09:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (30, 6, 'login', '/api/v1/login', '10.0.10.130', '2024-03-03 10:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (31, 7, 'logout', '/api/v1/logout', '10.0.11.131', '2024-04-04 11:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (32, 8, 'view_report', '/api/v1/view_report', '10.0.12.132', '2024-04-05 12:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (33, 9, 'export_data', '/api/v1/export_data', '10.0.13.133', '2024-04-06 13:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (34, 10, 'update_record', '/api/v1/update_record', '10.0.14.134', '2024-04-07 14:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (35, 11, 'create_user', '/api/v1/create_user', '10.0.10.135', '2024-04-08 15:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (36, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.136', '2024-04-09 16:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (37, 13, 'change_password', '/api/v1/change_password', '10.0.12.137', '2024-04-10 17:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (38, 14, 'api_call', '/api/v1/api_call', '10.0.13.138', '2024-04-11 18:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (39, 15, 'config_change', '/api/v1/config_change', '10.0.14.139', '2024-04-12 19:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (40, 16, 'login', '/api/v1/login', '10.0.10.140', '2024-04-13 20:40:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (41, 17, 'logout', '/api/v1/logout', '10.0.11.141', '2024-05-14 21:41:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (42, 18, 'view_report', '/api/v1/view_report', '10.0.12.142', '2024-05-15 08:42:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (43, 19, 'export_data', '/api/v1/export_data', '10.0.13.143', '2024-05-16 09:43:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (44, 20, 'update_record', '/api/v1/update_record', '10.0.14.144', '2024-05-17 10:44:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (45, 21, 'create_user', '/api/v1/create_user', '10.0.10.145', '2024-05-18 11:45:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (46, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.146', '2024-05-19 12:46:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (47, 23, 'change_password', '/api/v1/change_password', '10.0.12.147', '2024-05-20 13:47:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (48, 24, 'api_call', '/api/v1/api_call', '10.0.13.148', '2024-05-21 14:48:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (49, 25, 'config_change', '/api/v1/config_change', '10.0.14.149', '2024-05-22 15:49:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (50, 1, 'login', '/api/v1/login', '10.0.10.150', '2024-05-23 16:50:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (51, 2, 'logout', '/api/v1/logout', '10.0.11.151', '2024-06-24 17:51:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (52, 3, 'view_report', '/api/v1/view_report', '10.0.12.152', '2024-06-25 18:52:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (53, 4, 'export_data', '/api/v1/export_data', '10.0.13.153', '2024-06-26 19:53:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (54, 5, 'update_record', '/api/v1/update_record', '10.0.14.154', '2024-06-27 20:54:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (55, 6, 'create_user', '/api/v1/create_user', '10.0.10.155', '2024-06-28 21:55:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (56, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.156', '2024-06-01 08:56:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (57, 8, 'change_password', '/api/v1/change_password', '10.0.12.157', '2024-06-02 09:57:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (58, 9, 'api_call', '/api/v1/api_call', '10.0.13.158', '2024-06-03 10:58:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (59, 10, 'config_change', '/api/v1/config_change', '10.0.14.159', '2024-06-04 11:59:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (60, 11, 'login', '/api/v1/login', '10.0.10.160', '2024-06-05 12:00:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (61, 12, 'logout', '/api/v1/logout', '10.0.11.161', '2024-07-06 13:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (62, 13, 'view_report', '/api/v1/view_report', '10.0.12.162', '2024-07-07 14:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (63, 14, 'export_data', '/api/v1/export_data', '10.0.13.163', '2024-07-08 15:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (64, 15, 'update_record', '/api/v1/update_record', '10.0.14.164', '2024-07-09 16:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (65, 16, 'create_user', '/api/v1/create_user', '10.0.10.165', '2024-07-10 17:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (66, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.166', '2024-07-11 18:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (67, 18, 'change_password', '/api/v1/change_password', '10.0.12.167', '2024-07-12 19:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (68, 19, 'api_call', '/api/v1/api_call', '10.0.13.168', '2024-07-13 20:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (69, 20, 'config_change', '/api/v1/config_change', '10.0.14.169', '2024-07-14 21:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (70, 21, 'login', '/api/v1/login', '10.0.10.170', '2024-07-15 08:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (71, 22, 'logout', '/api/v1/logout', '10.0.11.171', '2024-08-16 09:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (72, 23, 'view_report', '/api/v1/view_report', '10.0.12.172', '2024-08-17 10:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (73, 24, 'export_data', '/api/v1/export_data', '10.0.13.173', '2024-08-18 11:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (74, 25, 'update_record', '/api/v1/update_record', '10.0.14.174', '2024-08-19 12:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (75, 1, 'create_user', '/api/v1/create_user', '10.0.10.175', '2024-08-20 13:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (76, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.176', '2024-08-21 14:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (77, 3, 'change_password', '/api/v1/change_password', '10.0.12.177', '2024-08-22 15:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (78, 4, 'api_call', '/api/v1/api_call', '10.0.13.178', '2024-08-23 16:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (79, 5, 'config_change', '/api/v1/config_change', '10.0.14.179', '2024-08-24 17:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (80, 6, 'login', '/api/v1/login', '10.0.10.180', '2024-08-25 18:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (81, 7, 'logout', '/api/v1/logout', '10.0.11.181', '2024-09-26 19:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (82, 8, 'view_report', '/api/v1/view_report', '10.0.12.182', '2024-09-27 20:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (83, 9, 'export_data', '/api/v1/export_data', '10.0.13.183', '2024-09-28 21:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (84, 10, 'update_record', '/api/v1/update_record', '10.0.14.184', '2024-09-01 08:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (85, 11, 'create_user', '/api/v1/create_user', '10.0.10.185', '2024-09-02 09:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (86, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.186', '2024-09-03 10:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (87, 13, 'change_password', '/api/v1/change_password', '10.0.12.187', '2024-09-04 11:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (88, 14, 'api_call', '/api/v1/api_call', '10.0.13.188', '2024-09-05 12:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (89, 15, 'config_change', '/api/v1/config_change', '10.0.14.189', '2024-09-06 13:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (90, 16, 'login', '/api/v1/login', '10.0.10.190', '2024-09-07 14:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (91, 17, 'logout', '/api/v1/logout', '10.0.11.191', '2024-10-08 15:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (92, 18, 'view_report', '/api/v1/view_report', '10.0.12.192', '2024-10-09 16:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (93, 19, 'export_data', '/api/v1/export_data', '10.0.13.193', '2024-10-10 17:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (94, 20, 'update_record', '/api/v1/update_record', '10.0.14.194', '2024-10-11 18:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (95, 21, 'create_user', '/api/v1/create_user', '10.0.10.195', '2024-10-12 19:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (96, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.196', '2024-10-13 20:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (97, 23, 'change_password', '/api/v1/change_password', '10.0.12.197', '2024-10-14 21:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (98, 24, 'api_call', '/api/v1/api_call', '10.0.13.198', '2024-10-15 08:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (99, 25, 'config_change', '/api/v1/config_change', '10.0.14.199', '2024-10-16 09:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (100, 1, 'login', '/api/v1/login', '10.0.10.200', '2024-10-17 10:40:00');
SELECT setval('audit_log_id_seq', 100);
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (1, 2, 'sess_0001_bcdef123', '10.0.3.101', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (2, 3, 'sess_0002_cdef1234', '10.0.3.102', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (3, 4, 'sess_0003_def12345', '10.0.3.103', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (4, 5, 'sess_0004_ef123456', '10.0.3.104', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (5, 6, 'sess_0005_f1234567', '10.0.3.105', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (6, 7, 'sess_0006_12345678', '10.0.3.106', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (7, 8, 'sess_0007_23456789', '10.0.3.107', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (8, 9, 'sess_0008_34567890', '10.0.3.108', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (9, 10, 'sess_0009_4567890', '10.0.3.109', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (10, 11, 'sess_0010_567890', '10.0.3.110', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (11, 12, 'sess_0011_67890', '10.0.3.111', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (12, 13, 'sess_0012_7890', '10.0.3.112', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (13, 14, 'sess_0013_890', '10.0.3.113', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (14, 15, 'sess_0014_90', '10.0.3.114', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (15, 16, 'sess_0015_0', '10.0.3.115', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (16, 17, 'sess_0016_abcdef12', '10.0.3.116', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (17, 18, 'sess_0017_bcdef123', '10.0.3.117', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (18, 19, 'sess_0018_cdef1234', '10.0.3.118', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (19, 20, 'sess_0019_def12345', '10.0.3.119', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (20, 21, 'sess_0020_ef123456', '10.0.3.120', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (21, 22, 'sess_0021_f1234567', '10.0.3.121', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (22, 23, 'sess_0022_12345678', '10.0.3.122', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (23, 24, 'sess_0023_23456789', '10.0.3.123', '2024-12-24 17:00:00', '2025-01-24 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (24, 25, 'sess_0024_34567890', '10.0.3.124', '2024-12-25 18:00:00', '2025-01-25 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (25, 1, 'sess_0025_4567890', '10.0.3.125', '2024-12-26 19:00:00', '2025-01-26 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (26, 2, 'sess_0026_567890', '10.0.3.126', '2024-12-27 20:00:00', '2025-01-27 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (27, 3, 'sess_0027_67890', '10.0.3.127', '2024-12-28 21:00:00', '2025-01-28 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (28, 4, 'sess_0028_7890', '10.0.3.128', '2024-12-01 08:00:00', '2025-01-01 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (29, 5, 'sess_0029_890', '10.0.3.129', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (30, 6, 'sess_0030_90', '10.0.3.130', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (31, 7, 'sess_0031_0', '10.0.3.131', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (32, 8, 'sess_0032_abcdef12', '10.0.3.132', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (33, 9, 'sess_0033_bcdef123', '10.0.3.133', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (34, 10, 'sess_0034_cdef1234', '10.0.3.134', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (35, 11, 'sess_0035_def12345', '10.0.3.135', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (36, 12, 'sess_0036_ef123456', '10.0.3.136', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (37, 13, 'sess_0037_f1234567', '10.0.3.137', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (38, 14, 'sess_0038_12345678', '10.0.3.138', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (39, 15, 'sess_0039_23456789', '10.0.3.139', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (40, 16, 'sess_0040_34567890', '10.0.3.140', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (41, 17, 'sess_0041_4567890', '10.0.3.141', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (42, 18, 'sess_0042_567890', '10.0.3.142', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (43, 19, 'sess_0043_67890', '10.0.3.143', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (44, 20, 'sess_0044_7890', '10.0.3.144', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (45, 21, 'sess_0045_890', '10.0.3.145', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (46, 22, 'sess_0046_90', '10.0.3.146', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (47, 23, 'sess_0047_0', '10.0.3.147', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (48, 24, 'sess_0048_abcdef12', '10.0.3.148', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (49, 25, 'sess_0049_bcdef123', '10.0.3.149', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (50, 1, 'sess_0050_cdef1234', '10.0.3.150', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
SELECT setval('sessions_id_seq', 50);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (1, 1, '$2b$12$apikeyhash0001', 'Production API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (2, 12, '$2b$12$apikeyhash0002', 'Monitoring', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (3, 19, '$2b$12$apikeyhash0003', 'CI/CD Pipeline', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (4, 22, '$2b$12$apikeyhash0004', 'Admin Tools', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (5, 25, '$2b$12$apikeyhash0005', 'Service Integration', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (6, 6, '$2b$12$apikeyhash0006', 'Engineering API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (7, 4, '$2b$12$apikeyhash0007', 'Dev Testing', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (8, 9, '$2b$12$apikeyhash0008', 'Analytics', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (9, 13, '$2b$12$apikeyhash0009', 'Sales Dashboard', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (10, 8, '$2b$12$apikeyhash0010', 'Marketing API', true);
SELECT setval('api_keys_id_seq', 10);
INSERT INTO config (id, key, value, updated_at) VALUES (1, 'app.name', 'Corp Internal Platform', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (2, 'app.version', '2.4.1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (3, 'app.debug', 'false', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (4, 'app.timezone', 'UTC', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (5, 'auth.session_timeout', '3600', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (6, 'auth.max_attempts', '5', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (7, 'auth.lockout_duration', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (8, 'auth.mfa_required', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (9, 'db.pool_size', '20', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (10, 'db.max_overflow', '10', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (11, 'cache.backend', 'redis', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (12, 'cache.ttl', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (13, 'email.smtp_host', 'smtp.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (14, 'email.smtp_port', '587', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (15, 'email.from_address', 'noreply@corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (16, 'storage.backend', 's3', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (17, 'storage.bucket', 'corp-app-data', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (18, 'storage.region', 'us-east-1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (19, 'logging.level', 'INFO', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (20, 'logging.sentry_dsn', 'https://key@sentry.corp.internal/1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (21, 'api.rate_limit', '1000', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (22, 'api.key_rotation_days', '90', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (23, 'security.cors_origins', 'https://app.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (24, 'security.csp_policy', 'default-src self', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (25, 'backup.schedule', '0 2 * * *', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (26, 'backup.retention_days', '30', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (27, 'monitoring.endpoint', 'https://prometheus.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (28, 'monitoring.interval', '60', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (29, 'feature.new_dashboard', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (30, 'feature.beta_api_v3', 'false', '2024-12-01 00:00:00');
SELECT setval('config_id_seq', 30);

GRANT ALL ON ALL TABLES IN SCHEMA public TO replicator;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO replicator;
GRANT ALL ON ALL TABLES IN SCHEMA public TO backupuser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO backupuser;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO nagios_check;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO nagios_check;

CREATE DATABASE app_production;
\connect app_production
GRANT ALL PRIVILEGES ON DATABASE app_production TO app_user;


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    department VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    description TEXT,
    status VARCHAR(20) DEFAULT 'completed',
    reference_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    ip_address INET,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200) NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (1, 'admin', 'admin@corp.internal', '$2b$12$fakehash0001', 'admin', 'IT', '2024-02-02 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (2, 'jsmith', 'john.smith@corp.internal', '$2b$12$fakehash0002', 'manager', 'Finance', '2024-03-03 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (3, 'alee', 'alice.lee@corp.internal', '$2b$12$fakehash0003', 'analyst', 'Finance', '2024-04-04 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (4, 'bwilson', 'bob.wilson@corp.internal', '$2b$12$fakehash0004', 'developer', 'Engineering', '2024-05-05 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (5, 'cmartinez', 'carol.martinez@corp.internal', '$2b$12$fakehash0005', 'developer', 'Engineering', '2024-06-06 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (6, 'dchen', 'david.chen@corp.internal', '$2b$12$fakehash0006', 'lead', 'Engineering', '2024-07-07 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (7, 'ejohnson', 'emma.johnson@corp.internal', '$2b$12$fakehash0007', 'analyst', 'HR', '2024-08-08 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (8, 'fgarcia', 'frank.garcia@corp.internal', '$2b$12$fakehash0008', 'manager', 'Operations', '2024-09-09 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (9, 'gwhite', 'grace.white@corp.internal', '$2b$12$fakehash0009', 'developer', 'Engineering', '2024-10-10 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (10, 'hbrown', 'henry.brown@corp.internal', '$2b$12$fakehash0010', 'analyst', 'Marketing', '2024-11-11 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (11, 'itaylor', 'iris.taylor@corp.internal', '$2b$12$fakehash0011', 'developer', 'Engineering', '2024-12-12 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (12, 'jdavis', 'jack.davis@corp.internal', '$2b$12$fakehash0012', 'sysadmin', 'IT', '2024-01-13 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (13, 'kmoore', 'karen.moore@corp.internal', '$2b$12$fakehash0013', 'manager', 'Sales', '2024-02-14 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (14, 'lthompson', 'larry.thompson@corp.internal', '$2b$12$fakehash0014', 'analyst', 'Finance', '2024-03-15 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (15, 'manderson', 'maria.anderson@corp.internal', '$2b$12$fakehash0015', 'developer', 'Engineering', '2024-04-16 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (16, 'nclark', 'nick.clark@corp.internal', '$2b$12$fakehash0016', 'intern', 'Engineering', '2024-05-17 09:00:00', false);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (17, 'owright', 'olivia.wright@corp.internal', '$2b$12$fakehash0017', 'analyst', 'Operations', '2024-06-18 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (18, 'pyoung', 'peter.young@corp.internal', '$2b$12$fakehash0018', 'developer', 'Engineering', '2024-07-19 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (19, 'qhall', 'quinn.hall@corp.internal', '$2b$12$fakehash0019', 'manager', 'IT', '2024-08-20 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (20, 'rking', 'rachel.king@corp.internal', '$2b$12$fakehash0020', 'analyst', 'Marketing', '2024-09-21 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (21, 'sgreen', 'scott.green@corp.internal', '$2b$12$fakehash0021', 'developer', 'Engineering', '2024-10-22 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (22, 'tadams', 'tina.adams@corp.internal', '$2b$12$fakehash0022', 'admin', 'IT', '2024-11-23 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (23, 'ubaker', 'ursula.baker@corp.internal', '$2b$12$fakehash0023', 'analyst', 'HR', '2024-12-24 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (24, 'vcarter', 'victor.carter@corp.internal', '$2b$12$fakehash0024', 'developer', 'Engineering', '2024-01-25 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (25, 'service_account', 'svc@corp.internal', '$2b$12$fakehash0025', 'service', 'IT', '2024-02-26 09:00:00', true);
SELECT setval('users_id_seq', 25);
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (1, 2, 57.37, 'USD', 'Transaction TXN-2024-000001', 'completed', 'TXN-2024-000001', '2024-01-02 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (2, 3, 64.74, 'USD', 'Transaction TXN-2024-000002', 'completed', 'TXN-2024-000002', '2024-01-03 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (3, 4, 72.11, 'USD', 'Transaction TXN-2024-000003', 'completed', 'TXN-2024-000003', '2024-01-04 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (4, 5, 79.48, 'USD', 'Transaction TXN-2024-000004', 'completed', 'TXN-2024-000004', '2024-01-05 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (5, 6, 86.85, 'USD', 'Transaction TXN-2024-000005', 'completed', 'TXN-2024-000005', '2024-01-06 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (6, 7, 94.22, 'USD', 'Transaction TXN-2024-000006', 'completed', 'TXN-2024-000006', '2024-01-07 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (7, 8, 101.59, 'USD', 'Transaction TXN-2024-000007', 'completed', 'TXN-2024-000007', '2024-01-08 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (8, 9, 108.96, 'USD', 'Transaction TXN-2024-000008', 'completed', 'TXN-2024-000008', '2024-01-09 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (9, 10, 116.33, 'USD', 'Transaction TXN-2024-000009', 'completed', 'TXN-2024-000009', '2024-01-10 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (10, 11, 123.7, 'USD', 'Transaction TXN-2024-000010', 'pending', 'TXN-2024-000010', '2024-01-11 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (11, 12, 131.07, 'USD', 'Transaction TXN-2024-000011', 'completed', 'TXN-2024-000011', '2024-01-12 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (12, 13, 138.44, 'USD', 'Transaction TXN-2024-000012', 'completed', 'TXN-2024-000012', '2024-01-13 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (13, 14, 145.81, 'USD', 'Transaction TXN-2024-000013', 'completed', 'TXN-2024-000013', '2024-01-14 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (14, 15, 153.18, 'USD', 'Transaction TXN-2024-000014', 'completed', 'TXN-2024-000014', '2024-01-15 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (15, 16, 160.55, 'USD', 'Transaction TXN-2024-000015', 'completed', 'TXN-2024-000015', '2024-01-16 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (16, 17, 167.92, 'USD', 'Transaction TXN-2024-000016', 'completed', 'TXN-2024-000016', '2024-01-17 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (17, 18, 175.29, 'USD', 'Transaction TXN-2024-000017', 'completed', 'TXN-2024-000017', '2024-01-18 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (18, 19, 182.66, 'USD', 'Transaction TXN-2024-000018', 'completed', 'TXN-2024-000018', '2024-01-19 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (19, 20, 190.03, 'USD', 'Transaction TXN-2024-000019', 'completed', 'TXN-2024-000019', '2024-01-20 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (20, 1, 197.4, 'USD', 'Transaction TXN-2024-000020', 'failed', 'TXN-2024-000020', '2024-01-21 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (21, 2, 204.77, 'USD', 'Transaction TXN-2024-000021', 'completed', 'TXN-2024-000021', '2024-02-22 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (22, 3, 212.14, 'USD', 'Transaction TXN-2024-000022', 'completed', 'TXN-2024-000022', '2024-02-23 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (23, 4, 219.51, 'USD', 'Transaction TXN-2024-000023', 'completed', 'TXN-2024-000023', '2024-02-24 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (24, 5, 226.88, 'USD', 'Transaction TXN-2024-000024', 'completed', 'TXN-2024-000024', '2024-02-25 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (25, 6, 234.25, 'USD', 'Transaction TXN-2024-000025', 'completed', 'TXN-2024-000025', '2024-02-26 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (26, 7, 241.62, 'USD', 'Transaction TXN-2024-000026', 'completed', 'TXN-2024-000026', '2024-02-27 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (27, 8, 248.99, 'USD', 'Transaction TXN-2024-000027', 'completed', 'TXN-2024-000027', '2024-02-28 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (28, 9, 256.36, 'USD', 'Transaction TXN-2024-000028', 'completed', 'TXN-2024-000028', '2024-02-01 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (29, 10, 263.73, 'USD', 'Transaction TXN-2024-000029', 'completed', 'TXN-2024-000029', '2024-02-02 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (30, 11, 271.1, 'USD', 'Transaction TXN-2024-000030', 'pending', 'TXN-2024-000030', '2024-02-03 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (31, 12, 278.47, 'USD', 'Transaction TXN-2024-000031', 'completed', 'TXN-2024-000031', '2024-02-04 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (32, 13, 285.84, 'USD', 'Transaction TXN-2024-000032', 'completed', 'TXN-2024-000032', '2024-02-05 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (33, 14, 293.21, 'USD', 'Transaction TXN-2024-000033', 'completed', 'TXN-2024-000033', '2024-02-06 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (34, 15, 300.58, 'USD', 'Transaction TXN-2024-000034', 'completed', 'TXN-2024-000034', '2024-02-07 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (35, 16, 307.95, 'USD', 'Transaction TXN-2024-000035', 'completed', 'TXN-2024-000035', '2024-02-08 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (36, 17, 315.32, 'USD', 'Transaction TXN-2024-000036', 'completed', 'TXN-2024-000036', '2024-02-09 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (37, 18, 322.69, 'USD', 'Transaction TXN-2024-000037', 'completed', 'TXN-2024-000037', '2024-02-10 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (38, 19, 330.06, 'USD', 'Transaction TXN-2024-000038', 'completed', 'TXN-2024-000038', '2024-02-11 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (39, 20, 337.43, 'USD', 'Transaction TXN-2024-000039', 'completed', 'TXN-2024-000039', '2024-02-12 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (40, 1, 344.8, 'USD', 'Transaction TXN-2024-000040', 'failed', 'TXN-2024-000040', '2024-02-13 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (41, 2, 352.17, 'USD', 'Transaction TXN-2024-000041', 'completed', 'TXN-2024-000041', '2024-03-14 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (42, 3, 359.54, 'USD', 'Transaction TXN-2024-000042', 'completed', 'TXN-2024-000042', '2024-03-15 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (43, 4, 366.91, 'USD', 'Transaction TXN-2024-000043', 'completed', 'TXN-2024-000043', '2024-03-16 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (44, 5, 374.28, 'USD', 'Transaction TXN-2024-000044', 'completed', 'TXN-2024-000044', '2024-03-17 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (45, 6, 381.65, 'USD', 'Transaction TXN-2024-000045', 'completed', 'TXN-2024-000045', '2024-03-18 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (46, 7, 389.02, 'USD', 'Transaction TXN-2024-000046', 'completed', 'TXN-2024-000046', '2024-03-19 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (47, 8, 396.39, 'USD', 'Transaction TXN-2024-000047', 'completed', 'TXN-2024-000047', '2024-03-20 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (48, 9, 403.76, 'USD', 'Transaction TXN-2024-000048', 'completed', 'TXN-2024-000048', '2024-03-21 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (49, 10, 411.13, 'USD', 'Transaction TXN-2024-000049', 'completed', 'TXN-2024-000049', '2024-03-22 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (50, 11, 418.5, 'USD', 'Transaction TXN-2024-000050', 'pending', 'TXN-2024-000050', '2024-03-23 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (51, 12, 425.87, 'USD', 'Transaction TXN-2024-000051', 'completed', 'TXN-2024-000051', '2024-03-24 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (52, 13, 433.24, 'USD', 'Transaction TXN-2024-000052', 'completed', 'TXN-2024-000052', '2024-03-25 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (53, 14, 440.61, 'USD', 'Transaction TXN-2024-000053', 'completed', 'TXN-2024-000053', '2024-03-26 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (54, 15, 447.98, 'USD', 'Transaction TXN-2024-000054', 'completed', 'TXN-2024-000054', '2024-03-27 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (55, 16, 455.35, 'USD', 'Transaction TXN-2024-000055', 'completed', 'TXN-2024-000055', '2024-03-28 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (56, 17, 462.72, 'USD', 'Transaction TXN-2024-000056', 'completed', 'TXN-2024-000056', '2024-03-01 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (57, 18, 470.09, 'USD', 'Transaction TXN-2024-000057', 'completed', 'TXN-2024-000057', '2024-03-02 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (58, 19, 477.46, 'USD', 'Transaction TXN-2024-000058', 'completed', 'TXN-2024-000058', '2024-03-03 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (59, 20, 484.83, 'USD', 'Transaction TXN-2024-000059', 'completed', 'TXN-2024-000059', '2024-03-04 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (60, 1, 492.2, 'USD', 'Transaction TXN-2024-000060', 'failed', 'TXN-2024-000060', '2024-03-05 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (61, 2, 499.57, 'USD', 'Transaction TXN-2024-000061', 'completed', 'TXN-2024-000061', '2024-04-06 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (62, 3, 506.94, 'USD', 'Transaction TXN-2024-000062', 'completed', 'TXN-2024-000062', '2024-04-07 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (63, 4, 514.31, 'USD', 'Transaction TXN-2024-000063', 'completed', 'TXN-2024-000063', '2024-04-08 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (64, 5, 521.68, 'USD', 'Transaction TXN-2024-000064', 'completed', 'TXN-2024-000064', '2024-04-09 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (65, 6, 529.05, 'USD', 'Transaction TXN-2024-000065', 'completed', 'TXN-2024-000065', '2024-04-10 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (66, 7, 536.42, 'USD', 'Transaction TXN-2024-000066', 'completed', 'TXN-2024-000066', '2024-04-11 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (67, 8, 543.79, 'USD', 'Transaction TXN-2024-000067', 'completed', 'TXN-2024-000067', '2024-04-12 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (68, 9, 551.16, 'USD', 'Transaction TXN-2024-000068', 'completed', 'TXN-2024-000068', '2024-04-13 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (69, 10, 558.53, 'USD', 'Transaction TXN-2024-000069', 'completed', 'TXN-2024-000069', '2024-04-14 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (70, 11, 565.9, 'USD', 'Transaction TXN-2024-000070', 'pending', 'TXN-2024-000070', '2024-04-15 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (71, 12, 573.27, 'USD', 'Transaction TXN-2024-000071', 'completed', 'TXN-2024-000071', '2024-04-16 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (72, 13, 580.64, 'USD', 'Transaction TXN-2024-000072', 'completed', 'TXN-2024-000072', '2024-04-17 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (73, 14, 588.01, 'USD', 'Transaction TXN-2024-000073', 'completed', 'TXN-2024-000073', '2024-04-18 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (74, 15, 595.38, 'USD', 'Transaction TXN-2024-000074', 'completed', 'TXN-2024-000074', '2024-04-19 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (75, 16, 602.75, 'USD', 'Transaction TXN-2024-000075', 'completed', 'TXN-2024-000075', '2024-04-20 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (76, 17, 610.12, 'USD', 'Transaction TXN-2024-000076', 'completed', 'TXN-2024-000076', '2024-04-21 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (77, 18, 617.49, 'USD', 'Transaction TXN-2024-000077', 'completed', 'TXN-2024-000077', '2024-04-22 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (78, 19, 624.86, 'USD', 'Transaction TXN-2024-000078', 'completed', 'TXN-2024-000078', '2024-04-23 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (79, 20, 632.23, 'USD', 'Transaction TXN-2024-000079', 'completed', 'TXN-2024-000079', '2024-04-24 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (80, 1, 639.6, 'USD', 'Transaction TXN-2024-000080', 'failed', 'TXN-2024-000080', '2024-04-25 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (81, 2, 646.97, 'USD', 'Transaction TXN-2024-000081', 'completed', 'TXN-2024-000081', '2024-05-26 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (82, 3, 654.34, 'USD', 'Transaction TXN-2024-000082', 'completed', 'TXN-2024-000082', '2024-05-27 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (83, 4, 661.71, 'USD', 'Transaction TXN-2024-000083', 'completed', 'TXN-2024-000083', '2024-05-28 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (84, 5, 669.08, 'USD', 'Transaction TXN-2024-000084', 'completed', 'TXN-2024-000084', '2024-05-01 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (85, 6, 676.45, 'USD', 'Transaction TXN-2024-000085', 'completed', 'TXN-2024-000085', '2024-05-02 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (86, 7, 683.82, 'USD', 'Transaction TXN-2024-000086', 'completed', 'TXN-2024-000086', '2024-05-03 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (87, 8, 691.19, 'USD', 'Transaction TXN-2024-000087', 'completed', 'TXN-2024-000087', '2024-05-04 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (88, 9, 698.56, 'USD', 'Transaction TXN-2024-000088', 'completed', 'TXN-2024-000088', '2024-05-05 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (89, 10, 705.93, 'USD', 'Transaction TXN-2024-000089', 'completed', 'TXN-2024-000089', '2024-05-06 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (90, 11, 713.3, 'USD', 'Transaction TXN-2024-000090', 'pending', 'TXN-2024-000090', '2024-05-07 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (91, 12, 720.67, 'USD', 'Transaction TXN-2024-000091', 'completed', 'TXN-2024-000091', '2024-05-08 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (92, 13, 728.04, 'USD', 'Transaction TXN-2024-000092', 'completed', 'TXN-2024-000092', '2024-05-09 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (93, 14, 735.41, 'USD', 'Transaction TXN-2024-000093', 'completed', 'TXN-2024-000093', '2024-05-10 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (94, 15, 742.78, 'USD', 'Transaction TXN-2024-000094', 'completed', 'TXN-2024-000094', '2024-05-11 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (95, 16, 750.15, 'USD', 'Transaction TXN-2024-000095', 'completed', 'TXN-2024-000095', '2024-05-12 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (96, 17, 757.52, 'USD', 'Transaction TXN-2024-000096', 'completed', 'TXN-2024-000096', '2024-05-13 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (97, 18, 764.89, 'USD', 'Transaction TXN-2024-000097', 'completed', 'TXN-2024-000097', '2024-05-14 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (98, 19, 772.26, 'USD', 'Transaction TXN-2024-000098', 'completed', 'TXN-2024-000098', '2024-05-15 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (99, 20, 779.63, 'USD', 'Transaction TXN-2024-000099', 'completed', 'TXN-2024-000099', '2024-05-16 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (100, 1, 787.0, 'USD', 'Transaction TXN-2024-000100', 'failed', 'TXN-2024-000100', '2024-05-17 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (101, 2, 794.37, 'USD', 'Transaction TXN-2024-000101', 'completed', 'TXN-2024-000101', '2024-06-18 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (102, 3, 801.74, 'USD', 'Transaction TXN-2024-000102', 'completed', 'TXN-2024-000102', '2024-06-19 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (103, 4, 809.11, 'USD', 'Transaction TXN-2024-000103', 'completed', 'TXN-2024-000103', '2024-06-20 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (104, 5, 816.48, 'USD', 'Transaction TXN-2024-000104', 'completed', 'TXN-2024-000104', '2024-06-21 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (105, 6, 823.85, 'USD', 'Transaction TXN-2024-000105', 'completed', 'TXN-2024-000105', '2024-06-22 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (106, 7, 831.22, 'USD', 'Transaction TXN-2024-000106', 'completed', 'TXN-2024-000106', '2024-06-23 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (107, 8, 838.59, 'USD', 'Transaction TXN-2024-000107', 'completed', 'TXN-2024-000107', '2024-06-24 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (108, 9, 845.96, 'USD', 'Transaction TXN-2024-000108', 'completed', 'TXN-2024-000108', '2024-06-25 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (109, 10, 853.33, 'USD', 'Transaction TXN-2024-000109', 'completed', 'TXN-2024-000109', '2024-06-26 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (110, 11, 860.7, 'USD', 'Transaction TXN-2024-000110', 'pending', 'TXN-2024-000110', '2024-06-27 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (111, 12, 868.07, 'USD', 'Transaction TXN-2024-000111', 'completed', 'TXN-2024-000111', '2024-06-28 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (112, 13, 875.44, 'USD', 'Transaction TXN-2024-000112', 'completed', 'TXN-2024-000112', '2024-06-01 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (113, 14, 882.81, 'USD', 'Transaction TXN-2024-000113', 'completed', 'TXN-2024-000113', '2024-06-02 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (114, 15, 890.18, 'USD', 'Transaction TXN-2024-000114', 'completed', 'TXN-2024-000114', '2024-06-03 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (115, 16, 897.55, 'USD', 'Transaction TXN-2024-000115', 'completed', 'TXN-2024-000115', '2024-06-04 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (116, 17, 904.92, 'USD', 'Transaction TXN-2024-000116', 'completed', 'TXN-2024-000116', '2024-06-05 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (117, 18, 912.29, 'USD', 'Transaction TXN-2024-000117', 'completed', 'TXN-2024-000117', '2024-06-06 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (118, 19, 919.66, 'USD', 'Transaction TXN-2024-000118', 'completed', 'TXN-2024-000118', '2024-06-07 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (119, 20, 927.03, 'USD', 'Transaction TXN-2024-000119', 'completed', 'TXN-2024-000119', '2024-06-08 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (120, 1, 934.4, 'USD', 'Transaction TXN-2024-000120', 'failed', 'TXN-2024-000120', '2024-06-09 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (121, 2, 941.77, 'USD', 'Transaction TXN-2024-000121', 'completed', 'TXN-2024-000121', '2024-07-10 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (122, 3, 949.14, 'USD', 'Transaction TXN-2024-000122', 'completed', 'TXN-2024-000122', '2024-07-11 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (123, 4, 956.51, 'USD', 'Transaction TXN-2024-000123', 'completed', 'TXN-2024-000123', '2024-07-12 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (124, 5, 963.88, 'USD', 'Transaction TXN-2024-000124', 'completed', 'TXN-2024-000124', '2024-07-13 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (125, 6, 971.25, 'USD', 'Transaction TXN-2024-000125', 'completed', 'TXN-2024-000125', '2024-07-14 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (126, 7, 978.62, 'USD', 'Transaction TXN-2024-000126', 'completed', 'TXN-2024-000126', '2024-07-15 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (127, 8, 985.99, 'USD', 'Transaction TXN-2024-000127', 'completed', 'TXN-2024-000127', '2024-07-16 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (128, 9, 993.36, 'USD', 'Transaction TXN-2024-000128', 'completed', 'TXN-2024-000128', '2024-07-17 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (129, 10, 1000.73, 'USD', 'Transaction TXN-2024-000129', 'completed', 'TXN-2024-000129', '2024-07-18 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (130, 11, 1008.1, 'USD', 'Transaction TXN-2024-000130', 'pending', 'TXN-2024-000130', '2024-07-19 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (131, 12, 1015.47, 'USD', 'Transaction TXN-2024-000131', 'completed', 'TXN-2024-000131', '2024-07-20 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (132, 13, 1022.84, 'USD', 'Transaction TXN-2024-000132', 'completed', 'TXN-2024-000132', '2024-07-21 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (133, 14, 1030.21, 'USD', 'Transaction TXN-2024-000133', 'completed', 'TXN-2024-000133', '2024-07-22 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (134, 15, 1037.58, 'USD', 'Transaction TXN-2024-000134', 'completed', 'TXN-2024-000134', '2024-07-23 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (135, 16, 1044.95, 'USD', 'Transaction TXN-2024-000135', 'completed', 'TXN-2024-000135', '2024-07-24 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (136, 17, 1052.32, 'USD', 'Transaction TXN-2024-000136', 'completed', 'TXN-2024-000136', '2024-07-25 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (137, 18, 1059.69, 'USD', 'Transaction TXN-2024-000137', 'completed', 'TXN-2024-000137', '2024-07-26 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (138, 19, 1067.06, 'USD', 'Transaction TXN-2024-000138', 'completed', 'TXN-2024-000138', '2024-07-27 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (139, 20, 1074.43, 'USD', 'Transaction TXN-2024-000139', 'completed', 'TXN-2024-000139', '2024-07-28 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (140, 1, 1081.8, 'USD', 'Transaction TXN-2024-000140', 'failed', 'TXN-2024-000140', '2024-07-01 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (141, 2, 1089.17, 'USD', 'Transaction TXN-2024-000141', 'completed', 'TXN-2024-000141', '2024-08-02 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (142, 3, 1096.54, 'USD', 'Transaction TXN-2024-000142', 'completed', 'TXN-2024-000142', '2024-08-03 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (143, 4, 1103.91, 'USD', 'Transaction TXN-2024-000143', 'completed', 'TXN-2024-000143', '2024-08-04 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (144, 5, 1111.28, 'USD', 'Transaction TXN-2024-000144', 'completed', 'TXN-2024-000144', '2024-08-05 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (145, 6, 1118.65, 'USD', 'Transaction TXN-2024-000145', 'completed', 'TXN-2024-000145', '2024-08-06 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (146, 7, 1126.02, 'USD', 'Transaction TXN-2024-000146', 'completed', 'TXN-2024-000146', '2024-08-07 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (147, 8, 1133.39, 'USD', 'Transaction TXN-2024-000147', 'completed', 'TXN-2024-000147', '2024-08-08 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (148, 9, 1140.76, 'USD', 'Transaction TXN-2024-000148', 'completed', 'TXN-2024-000148', '2024-08-09 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (149, 10, 1148.13, 'USD', 'Transaction TXN-2024-000149', 'completed', 'TXN-2024-000149', '2024-08-10 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (150, 11, 1155.5, 'USD', 'Transaction TXN-2024-000150', 'pending', 'TXN-2024-000150', '2024-08-11 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (151, 12, 1162.87, 'USD', 'Transaction TXN-2024-000151', 'completed', 'TXN-2024-000151', '2024-08-12 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (152, 13, 1170.24, 'USD', 'Transaction TXN-2024-000152', 'completed', 'TXN-2024-000152', '2024-08-13 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (153, 14, 1177.61, 'USD', 'Transaction TXN-2024-000153', 'completed', 'TXN-2024-000153', '2024-08-14 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (154, 15, 1184.98, 'USD', 'Transaction TXN-2024-000154', 'completed', 'TXN-2024-000154', '2024-08-15 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (155, 16, 1192.35, 'USD', 'Transaction TXN-2024-000155', 'completed', 'TXN-2024-000155', '2024-08-16 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (156, 17, 1199.72, 'USD', 'Transaction TXN-2024-000156', 'completed', 'TXN-2024-000156', '2024-08-17 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (157, 18, 1207.09, 'USD', 'Transaction TXN-2024-000157', 'completed', 'TXN-2024-000157', '2024-08-18 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (158, 19, 1214.46, 'USD', 'Transaction TXN-2024-000158', 'completed', 'TXN-2024-000158', '2024-08-19 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (159, 20, 1221.83, 'USD', 'Transaction TXN-2024-000159', 'completed', 'TXN-2024-000159', '2024-08-20 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (160, 1, 1229.2, 'USD', 'Transaction TXN-2024-000160', 'failed', 'TXN-2024-000160', '2024-08-21 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (161, 2, 1236.57, 'USD', 'Transaction TXN-2024-000161', 'completed', 'TXN-2024-000161', '2024-09-22 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (162, 3, 1243.94, 'USD', 'Transaction TXN-2024-000162', 'completed', 'TXN-2024-000162', '2024-09-23 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (163, 4, 1251.31, 'USD', 'Transaction TXN-2024-000163', 'completed', 'TXN-2024-000163', '2024-09-24 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (164, 5, 1258.68, 'USD', 'Transaction TXN-2024-000164', 'completed', 'TXN-2024-000164', '2024-09-25 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (165, 6, 1266.05, 'USD', 'Transaction TXN-2024-000165', 'completed', 'TXN-2024-000165', '2024-09-26 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (166, 7, 1273.42, 'USD', 'Transaction TXN-2024-000166', 'completed', 'TXN-2024-000166', '2024-09-27 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (167, 8, 1280.79, 'USD', 'Transaction TXN-2024-000167', 'completed', 'TXN-2024-000167', '2024-09-28 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (168, 9, 1288.16, 'USD', 'Transaction TXN-2024-000168', 'completed', 'TXN-2024-000168', '2024-09-01 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (169, 10, 1295.53, 'USD', 'Transaction TXN-2024-000169', 'completed', 'TXN-2024-000169', '2024-09-02 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (170, 11, 1302.9, 'USD', 'Transaction TXN-2024-000170', 'pending', 'TXN-2024-000170', '2024-09-03 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (171, 12, 1310.27, 'USD', 'Transaction TXN-2024-000171', 'completed', 'TXN-2024-000171', '2024-09-04 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (172, 13, 1317.64, 'USD', 'Transaction TXN-2024-000172', 'completed', 'TXN-2024-000172', '2024-09-05 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (173, 14, 1325.01, 'USD', 'Transaction TXN-2024-000173', 'completed', 'TXN-2024-000173', '2024-09-06 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (174, 15, 1332.38, 'USD', 'Transaction TXN-2024-000174', 'completed', 'TXN-2024-000174', '2024-09-07 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (175, 16, 1339.75, 'USD', 'Transaction TXN-2024-000175', 'completed', 'TXN-2024-000175', '2024-09-08 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (176, 17, 1347.12, 'USD', 'Transaction TXN-2024-000176', 'completed', 'TXN-2024-000176', '2024-09-09 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (177, 18, 1354.49, 'USD', 'Transaction TXN-2024-000177', 'completed', 'TXN-2024-000177', '2024-09-10 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (178, 19, 1361.86, 'USD', 'Transaction TXN-2024-000178', 'completed', 'TXN-2024-000178', '2024-09-11 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (179, 20, 1369.23, 'USD', 'Transaction TXN-2024-000179', 'completed', 'TXN-2024-000179', '2024-09-12 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (180, 1, 1376.6, 'USD', 'Transaction TXN-2024-000180', 'failed', 'TXN-2024-000180', '2024-09-13 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (181, 2, 1383.97, 'USD', 'Transaction TXN-2024-000181', 'completed', 'TXN-2024-000181', '2024-10-14 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (182, 3, 1391.34, 'USD', 'Transaction TXN-2024-000182', 'completed', 'TXN-2024-000182', '2024-10-15 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (183, 4, 1398.71, 'USD', 'Transaction TXN-2024-000183', 'completed', 'TXN-2024-000183', '2024-10-16 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (184, 5, 1406.08, 'USD', 'Transaction TXN-2024-000184', 'completed', 'TXN-2024-000184', '2024-10-17 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (185, 6, 1413.45, 'USD', 'Transaction TXN-2024-000185', 'completed', 'TXN-2024-000185', '2024-10-18 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (186, 7, 1420.82, 'USD', 'Transaction TXN-2024-000186', 'completed', 'TXN-2024-000186', '2024-10-19 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (187, 8, 1428.19, 'USD', 'Transaction TXN-2024-000187', 'completed', 'TXN-2024-000187', '2024-10-20 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (188, 9, 1435.56, 'USD', 'Transaction TXN-2024-000188', 'completed', 'TXN-2024-000188', '2024-10-21 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (189, 10, 1442.93, 'USD', 'Transaction TXN-2024-000189', 'completed', 'TXN-2024-000189', '2024-10-22 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (190, 11, 1450.3, 'USD', 'Transaction TXN-2024-000190', 'pending', 'TXN-2024-000190', '2024-10-23 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (191, 12, 1457.67, 'USD', 'Transaction TXN-2024-000191', 'completed', 'TXN-2024-000191', '2024-10-24 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (192, 13, 1465.04, 'USD', 'Transaction TXN-2024-000192', 'completed', 'TXN-2024-000192', '2024-10-25 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (193, 14, 1472.41, 'USD', 'Transaction TXN-2024-000193', 'completed', 'TXN-2024-000193', '2024-10-26 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (194, 15, 1479.78, 'USD', 'Transaction TXN-2024-000194', 'completed', 'TXN-2024-000194', '2024-10-27 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (195, 16, 1487.15, 'USD', 'Transaction TXN-2024-000195', 'completed', 'TXN-2024-000195', '2024-10-28 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (196, 17, 1494.52, 'USD', 'Transaction TXN-2024-000196', 'completed', 'TXN-2024-000196', '2024-10-01 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (197, 18, 1501.89, 'USD', 'Transaction TXN-2024-000197', 'completed', 'TXN-2024-000197', '2024-10-02 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (198, 19, 1509.26, 'USD', 'Transaction TXN-2024-000198', 'completed', 'TXN-2024-000198', '2024-10-03 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (199, 20, 1516.63, 'USD', 'Transaction TXN-2024-000199', 'completed', 'TXN-2024-000199', '2024-10-04 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (200, 1, 1524.0, 'USD', 'Transaction TXN-2024-000200', 'failed', 'TXN-2024-000200', '2024-10-05 08:20:00');
SELECT setval('transactions_id_seq', 200);
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (1, 2, 'logout', '/api/v1/logout', '10.0.11.101', '2024-01-02 09:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (2, 3, 'view_report', '/api/v1/view_report', '10.0.12.102', '2024-01-03 10:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (3, 4, 'export_data', '/api/v1/export_data', '10.0.13.103', '2024-01-04 11:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (4, 5, 'update_record', '/api/v1/update_record', '10.0.14.104', '2024-01-05 12:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (5, 6, 'create_user', '/api/v1/create_user', '10.0.10.105', '2024-01-06 13:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (6, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.106', '2024-01-07 14:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (7, 8, 'change_password', '/api/v1/change_password', '10.0.12.107', '2024-01-08 15:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (8, 9, 'api_call', '/api/v1/api_call', '10.0.13.108', '2024-01-09 16:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (9, 10, 'config_change', '/api/v1/config_change', '10.0.14.109', '2024-01-10 17:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (10, 11, 'login', '/api/v1/login', '10.0.10.110', '2024-01-11 18:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (11, 12, 'logout', '/api/v1/logout', '10.0.11.111', '2024-02-12 19:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (12, 13, 'view_report', '/api/v1/view_report', '10.0.12.112', '2024-02-13 20:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (13, 14, 'export_data', '/api/v1/export_data', '10.0.13.113', '2024-02-14 21:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (14, 15, 'update_record', '/api/v1/update_record', '10.0.14.114', '2024-02-15 08:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (15, 16, 'create_user', '/api/v1/create_user', '10.0.10.115', '2024-02-16 09:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (16, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.116', '2024-02-17 10:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (17, 18, 'change_password', '/api/v1/change_password', '10.0.12.117', '2024-02-18 11:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (18, 19, 'api_call', '/api/v1/api_call', '10.0.13.118', '2024-02-19 12:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (19, 20, 'config_change', '/api/v1/config_change', '10.0.14.119', '2024-02-20 13:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (20, 21, 'login', '/api/v1/login', '10.0.10.120', '2024-02-21 14:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (21, 22, 'logout', '/api/v1/logout', '10.0.11.121', '2024-03-22 15:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (22, 23, 'view_report', '/api/v1/view_report', '10.0.12.122', '2024-03-23 16:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (23, 24, 'export_data', '/api/v1/export_data', '10.0.13.123', '2024-03-24 17:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (24, 25, 'update_record', '/api/v1/update_record', '10.0.14.124', '2024-03-25 18:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (25, 1, 'create_user', '/api/v1/create_user', '10.0.10.125', '2024-03-26 19:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (26, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.126', '2024-03-27 20:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (27, 3, 'change_password', '/api/v1/change_password', '10.0.12.127', '2024-03-28 21:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (28, 4, 'api_call', '/api/v1/api_call', '10.0.13.128', '2024-03-01 08:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (29, 5, 'config_change', '/api/v1/config_change', '10.0.14.129', '2024-03-02 09:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (30, 6, 'login', '/api/v1/login', '10.0.10.130', '2024-03-03 10:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (31, 7, 'logout', '/api/v1/logout', '10.0.11.131', '2024-04-04 11:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (32, 8, 'view_report', '/api/v1/view_report', '10.0.12.132', '2024-04-05 12:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (33, 9, 'export_data', '/api/v1/export_data', '10.0.13.133', '2024-04-06 13:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (34, 10, 'update_record', '/api/v1/update_record', '10.0.14.134', '2024-04-07 14:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (35, 11, 'create_user', '/api/v1/create_user', '10.0.10.135', '2024-04-08 15:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (36, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.136', '2024-04-09 16:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (37, 13, 'change_password', '/api/v1/change_password', '10.0.12.137', '2024-04-10 17:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (38, 14, 'api_call', '/api/v1/api_call', '10.0.13.138', '2024-04-11 18:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (39, 15, 'config_change', '/api/v1/config_change', '10.0.14.139', '2024-04-12 19:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (40, 16, 'login', '/api/v1/login', '10.0.10.140', '2024-04-13 20:40:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (41, 17, 'logout', '/api/v1/logout', '10.0.11.141', '2024-05-14 21:41:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (42, 18, 'view_report', '/api/v1/view_report', '10.0.12.142', '2024-05-15 08:42:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (43, 19, 'export_data', '/api/v1/export_data', '10.0.13.143', '2024-05-16 09:43:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (44, 20, 'update_record', '/api/v1/update_record', '10.0.14.144', '2024-05-17 10:44:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (45, 21, 'create_user', '/api/v1/create_user', '10.0.10.145', '2024-05-18 11:45:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (46, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.146', '2024-05-19 12:46:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (47, 23, 'change_password', '/api/v1/change_password', '10.0.12.147', '2024-05-20 13:47:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (48, 24, 'api_call', '/api/v1/api_call', '10.0.13.148', '2024-05-21 14:48:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (49, 25, 'config_change', '/api/v1/config_change', '10.0.14.149', '2024-05-22 15:49:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (50, 1, 'login', '/api/v1/login', '10.0.10.150', '2024-05-23 16:50:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (51, 2, 'logout', '/api/v1/logout', '10.0.11.151', '2024-06-24 17:51:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (52, 3, 'view_report', '/api/v1/view_report', '10.0.12.152', '2024-06-25 18:52:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (53, 4, 'export_data', '/api/v1/export_data', '10.0.13.153', '2024-06-26 19:53:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (54, 5, 'update_record', '/api/v1/update_record', '10.0.14.154', '2024-06-27 20:54:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (55, 6, 'create_user', '/api/v1/create_user', '10.0.10.155', '2024-06-28 21:55:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (56, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.156', '2024-06-01 08:56:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (57, 8, 'change_password', '/api/v1/change_password', '10.0.12.157', '2024-06-02 09:57:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (58, 9, 'api_call', '/api/v1/api_call', '10.0.13.158', '2024-06-03 10:58:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (59, 10, 'config_change', '/api/v1/config_change', '10.0.14.159', '2024-06-04 11:59:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (60, 11, 'login', '/api/v1/login', '10.0.10.160', '2024-06-05 12:00:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (61, 12, 'logout', '/api/v1/logout', '10.0.11.161', '2024-07-06 13:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (62, 13, 'view_report', '/api/v1/view_report', '10.0.12.162', '2024-07-07 14:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (63, 14, 'export_data', '/api/v1/export_data', '10.0.13.163', '2024-07-08 15:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (64, 15, 'update_record', '/api/v1/update_record', '10.0.14.164', '2024-07-09 16:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (65, 16, 'create_user', '/api/v1/create_user', '10.0.10.165', '2024-07-10 17:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (66, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.166', '2024-07-11 18:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (67, 18, 'change_password', '/api/v1/change_password', '10.0.12.167', '2024-07-12 19:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (68, 19, 'api_call', '/api/v1/api_call', '10.0.13.168', '2024-07-13 20:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (69, 20, 'config_change', '/api/v1/config_change', '10.0.14.169', '2024-07-14 21:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (70, 21, 'login', '/api/v1/login', '10.0.10.170', '2024-07-15 08:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (71, 22, 'logout', '/api/v1/logout', '10.0.11.171', '2024-08-16 09:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (72, 23, 'view_report', '/api/v1/view_report', '10.0.12.172', '2024-08-17 10:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (73, 24, 'export_data', '/api/v1/export_data', '10.0.13.173', '2024-08-18 11:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (74, 25, 'update_record', '/api/v1/update_record', '10.0.14.174', '2024-08-19 12:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (75, 1, 'create_user', '/api/v1/create_user', '10.0.10.175', '2024-08-20 13:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (76, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.176', '2024-08-21 14:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (77, 3, 'change_password', '/api/v1/change_password', '10.0.12.177', '2024-08-22 15:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (78, 4, 'api_call', '/api/v1/api_call', '10.0.13.178', '2024-08-23 16:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (79, 5, 'config_change', '/api/v1/config_change', '10.0.14.179', '2024-08-24 17:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (80, 6, 'login', '/api/v1/login', '10.0.10.180', '2024-08-25 18:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (81, 7, 'logout', '/api/v1/logout', '10.0.11.181', '2024-09-26 19:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (82, 8, 'view_report', '/api/v1/view_report', '10.0.12.182', '2024-09-27 20:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (83, 9, 'export_data', '/api/v1/export_data', '10.0.13.183', '2024-09-28 21:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (84, 10, 'update_record', '/api/v1/update_record', '10.0.14.184', '2024-09-01 08:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (85, 11, 'create_user', '/api/v1/create_user', '10.0.10.185', '2024-09-02 09:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (86, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.186', '2024-09-03 10:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (87, 13, 'change_password', '/api/v1/change_password', '10.0.12.187', '2024-09-04 11:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (88, 14, 'api_call', '/api/v1/api_call', '10.0.13.188', '2024-09-05 12:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (89, 15, 'config_change', '/api/v1/config_change', '10.0.14.189', '2024-09-06 13:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (90, 16, 'login', '/api/v1/login', '10.0.10.190', '2024-09-07 14:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (91, 17, 'logout', '/api/v1/logout', '10.0.11.191', '2024-10-08 15:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (92, 18, 'view_report', '/api/v1/view_report', '10.0.12.192', '2024-10-09 16:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (93, 19, 'export_data', '/api/v1/export_data', '10.0.13.193', '2024-10-10 17:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (94, 20, 'update_record', '/api/v1/update_record', '10.0.14.194', '2024-10-11 18:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (95, 21, 'create_user', '/api/v1/create_user', '10.0.10.195', '2024-10-12 19:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (96, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.196', '2024-10-13 20:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (97, 23, 'change_password', '/api/v1/change_password', '10.0.12.197', '2024-10-14 21:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (98, 24, 'api_call', '/api/v1/api_call', '10.0.13.198', '2024-10-15 08:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (99, 25, 'config_change', '/api/v1/config_change', '10.0.14.199', '2024-10-16 09:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (100, 1, 'login', '/api/v1/login', '10.0.10.200', '2024-10-17 10:40:00');
SELECT setval('audit_log_id_seq', 100);
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (1, 2, 'sess_0001_bcdef123', '10.0.3.101', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (2, 3, 'sess_0002_cdef1234', '10.0.3.102', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (3, 4, 'sess_0003_def12345', '10.0.3.103', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (4, 5, 'sess_0004_ef123456', '10.0.3.104', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (5, 6, 'sess_0005_f1234567', '10.0.3.105', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (6, 7, 'sess_0006_12345678', '10.0.3.106', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (7, 8, 'sess_0007_23456789', '10.0.3.107', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (8, 9, 'sess_0008_34567890', '10.0.3.108', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (9, 10, 'sess_0009_4567890', '10.0.3.109', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (10, 11, 'sess_0010_567890', '10.0.3.110', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (11, 12, 'sess_0011_67890', '10.0.3.111', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (12, 13, 'sess_0012_7890', '10.0.3.112', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (13, 14, 'sess_0013_890', '10.0.3.113', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (14, 15, 'sess_0014_90', '10.0.3.114', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (15, 16, 'sess_0015_0', '10.0.3.115', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (16, 17, 'sess_0016_abcdef12', '10.0.3.116', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (17, 18, 'sess_0017_bcdef123', '10.0.3.117', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (18, 19, 'sess_0018_cdef1234', '10.0.3.118', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (19, 20, 'sess_0019_def12345', '10.0.3.119', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (20, 21, 'sess_0020_ef123456', '10.0.3.120', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (21, 22, 'sess_0021_f1234567', '10.0.3.121', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (22, 23, 'sess_0022_12345678', '10.0.3.122', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (23, 24, 'sess_0023_23456789', '10.0.3.123', '2024-12-24 17:00:00', '2025-01-24 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (24, 25, 'sess_0024_34567890', '10.0.3.124', '2024-12-25 18:00:00', '2025-01-25 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (25, 1, 'sess_0025_4567890', '10.0.3.125', '2024-12-26 19:00:00', '2025-01-26 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (26, 2, 'sess_0026_567890', '10.0.3.126', '2024-12-27 20:00:00', '2025-01-27 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (27, 3, 'sess_0027_67890', '10.0.3.127', '2024-12-28 21:00:00', '2025-01-28 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (28, 4, 'sess_0028_7890', '10.0.3.128', '2024-12-01 08:00:00', '2025-01-01 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (29, 5, 'sess_0029_890', '10.0.3.129', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (30, 6, 'sess_0030_90', '10.0.3.130', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (31, 7, 'sess_0031_0', '10.0.3.131', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (32, 8, 'sess_0032_abcdef12', '10.0.3.132', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (33, 9, 'sess_0033_bcdef123', '10.0.3.133', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (34, 10, 'sess_0034_cdef1234', '10.0.3.134', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (35, 11, 'sess_0035_def12345', '10.0.3.135', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (36, 12, 'sess_0036_ef123456', '10.0.3.136', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (37, 13, 'sess_0037_f1234567', '10.0.3.137', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (38, 14, 'sess_0038_12345678', '10.0.3.138', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (39, 15, 'sess_0039_23456789', '10.0.3.139', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (40, 16, 'sess_0040_34567890', '10.0.3.140', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (41, 17, 'sess_0041_4567890', '10.0.3.141', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (42, 18, 'sess_0042_567890', '10.0.3.142', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (43, 19, 'sess_0043_67890', '10.0.3.143', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (44, 20, 'sess_0044_7890', '10.0.3.144', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (45, 21, 'sess_0045_890', '10.0.3.145', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (46, 22, 'sess_0046_90', '10.0.3.146', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (47, 23, 'sess_0047_0', '10.0.3.147', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (48, 24, 'sess_0048_abcdef12', '10.0.3.148', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (49, 25, 'sess_0049_bcdef123', '10.0.3.149', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (50, 1, 'sess_0050_cdef1234', '10.0.3.150', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
SELECT setval('sessions_id_seq', 50);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (1, 1, '$2b$12$apikeyhash0001', 'Production API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (2, 12, '$2b$12$apikeyhash0002', 'Monitoring', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (3, 19, '$2b$12$apikeyhash0003', 'CI/CD Pipeline', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (4, 22, '$2b$12$apikeyhash0004', 'Admin Tools', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (5, 25, '$2b$12$apikeyhash0005', 'Service Integration', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (6, 6, '$2b$12$apikeyhash0006', 'Engineering API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (7, 4, '$2b$12$apikeyhash0007', 'Dev Testing', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (8, 9, '$2b$12$apikeyhash0008', 'Analytics', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (9, 13, '$2b$12$apikeyhash0009', 'Sales Dashboard', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (10, 8, '$2b$12$apikeyhash0010', 'Marketing API', true);
SELECT setval('api_keys_id_seq', 10);
INSERT INTO config (id, key, value, updated_at) VALUES (1, 'app.name', 'Corp Internal Platform', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (2, 'app.version', '2.4.1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (3, 'app.debug', 'false', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (4, 'app.timezone', 'UTC', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (5, 'auth.session_timeout', '3600', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (6, 'auth.max_attempts', '5', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (7, 'auth.lockout_duration', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (8, 'auth.mfa_required', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (9, 'db.pool_size', '20', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (10, 'db.max_overflow', '10', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (11, 'cache.backend', 'redis', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (12, 'cache.ttl', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (13, 'email.smtp_host', 'smtp.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (14, 'email.smtp_port', '587', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (15, 'email.from_address', 'noreply@corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (16, 'storage.backend', 's3', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (17, 'storage.bucket', 'corp-app-data', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (18, 'storage.region', 'us-east-1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (19, 'logging.level', 'INFO', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (20, 'logging.sentry_dsn', 'https://key@sentry.corp.internal/1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (21, 'api.rate_limit', '1000', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (22, 'api.key_rotation_days', '90', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (23, 'security.cors_origins', 'https://app.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (24, 'security.csp_policy', 'default-src self', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (25, 'backup.schedule', '0 2 * * *', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (26, 'backup.retention_days', '30', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (27, 'monitoring.endpoint', 'https://prometheus.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (28, 'monitoring.interval', '60', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (29, 'feature.new_dashboard', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (30, 'feature.beta_api_v3', 'false', '2024-12-01 00:00:00');
SELECT setval('config_id_seq', 30);

GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user;

CREATE DATABASE monitoring;
\connect monitoring
GRANT ALL PRIVILEGES ON DATABASE monitoring TO nagios_check;


CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    department VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    description TEXT,
    status VARCHAR(20) DEFAULT 'completed',
    reference_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    ip_address INET,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    token VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    key_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    permissions JSONB DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200) NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (1, 'admin', 'admin@corp.internal', '$2b$12$fakehash0001', 'admin', 'IT', '2024-02-02 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (2, 'jsmith', 'john.smith@corp.internal', '$2b$12$fakehash0002', 'manager', 'Finance', '2024-03-03 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (3, 'alee', 'alice.lee@corp.internal', '$2b$12$fakehash0003', 'analyst', 'Finance', '2024-04-04 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (4, 'bwilson', 'bob.wilson@corp.internal', '$2b$12$fakehash0004', 'developer', 'Engineering', '2024-05-05 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (5, 'cmartinez', 'carol.martinez@corp.internal', '$2b$12$fakehash0005', 'developer', 'Engineering', '2024-06-06 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (6, 'dchen', 'david.chen@corp.internal', '$2b$12$fakehash0006', 'lead', 'Engineering', '2024-07-07 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (7, 'ejohnson', 'emma.johnson@corp.internal', '$2b$12$fakehash0007', 'analyst', 'HR', '2024-08-08 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (8, 'fgarcia', 'frank.garcia@corp.internal', '$2b$12$fakehash0008', 'manager', 'Operations', '2024-09-09 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (9, 'gwhite', 'grace.white@corp.internal', '$2b$12$fakehash0009', 'developer', 'Engineering', '2024-10-10 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (10, 'hbrown', 'henry.brown@corp.internal', '$2b$12$fakehash0010', 'analyst', 'Marketing', '2024-11-11 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (11, 'itaylor', 'iris.taylor@corp.internal', '$2b$12$fakehash0011', 'developer', 'Engineering', '2024-12-12 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (12, 'jdavis', 'jack.davis@corp.internal', '$2b$12$fakehash0012', 'sysadmin', 'IT', '2024-01-13 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (13, 'kmoore', 'karen.moore@corp.internal', '$2b$12$fakehash0013', 'manager', 'Sales', '2024-02-14 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (14, 'lthompson', 'larry.thompson@corp.internal', '$2b$12$fakehash0014', 'analyst', 'Finance', '2024-03-15 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (15, 'manderson', 'maria.anderson@corp.internal', '$2b$12$fakehash0015', 'developer', 'Engineering', '2024-04-16 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (16, 'nclark', 'nick.clark@corp.internal', '$2b$12$fakehash0016', 'intern', 'Engineering', '2024-05-17 09:00:00', false);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (17, 'owright', 'olivia.wright@corp.internal', '$2b$12$fakehash0017', 'analyst', 'Operations', '2024-06-18 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (18, 'pyoung', 'peter.young@corp.internal', '$2b$12$fakehash0018', 'developer', 'Engineering', '2024-07-19 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (19, 'qhall', 'quinn.hall@corp.internal', '$2b$12$fakehash0019', 'manager', 'IT', '2024-08-20 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (20, 'rking', 'rachel.king@corp.internal', '$2b$12$fakehash0020', 'analyst', 'Marketing', '2024-09-21 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (21, 'sgreen', 'scott.green@corp.internal', '$2b$12$fakehash0021', 'developer', 'Engineering', '2024-10-22 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (22, 'tadams', 'tina.adams@corp.internal', '$2b$12$fakehash0022', 'admin', 'IT', '2024-11-23 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (23, 'ubaker', 'ursula.baker@corp.internal', '$2b$12$fakehash0023', 'analyst', 'HR', '2024-12-24 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (24, 'vcarter', 'victor.carter@corp.internal', '$2b$12$fakehash0024', 'developer', 'Engineering', '2024-01-25 09:00:00', true);
INSERT INTO users (id, username, email, password_hash, role, department, created_at, is_active) VALUES (25, 'service_account', 'svc@corp.internal', '$2b$12$fakehash0025', 'service', 'IT', '2024-02-26 09:00:00', true);
SELECT setval('users_id_seq', 25);
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (1, 2, 57.37, 'USD', 'Transaction TXN-2024-000001', 'completed', 'TXN-2024-000001', '2024-01-02 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (2, 3, 64.74, 'USD', 'Transaction TXN-2024-000002', 'completed', 'TXN-2024-000002', '2024-01-03 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (3, 4, 72.11, 'USD', 'Transaction TXN-2024-000003', 'completed', 'TXN-2024-000003', '2024-01-04 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (4, 5, 79.48, 'USD', 'Transaction TXN-2024-000004', 'completed', 'TXN-2024-000004', '2024-01-05 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (5, 6, 86.85, 'USD', 'Transaction TXN-2024-000005', 'completed', 'TXN-2024-000005', '2024-01-06 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (6, 7, 94.22, 'USD', 'Transaction TXN-2024-000006', 'completed', 'TXN-2024-000006', '2024-01-07 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (7, 8, 101.59, 'USD', 'Transaction TXN-2024-000007', 'completed', 'TXN-2024-000007', '2024-01-08 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (8, 9, 108.96, 'USD', 'Transaction TXN-2024-000008', 'completed', 'TXN-2024-000008', '2024-01-09 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (9, 10, 116.33, 'USD', 'Transaction TXN-2024-000009', 'completed', 'TXN-2024-000009', '2024-01-10 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (10, 11, 123.7, 'USD', 'Transaction TXN-2024-000010', 'pending', 'TXN-2024-000010', '2024-01-11 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (11, 12, 131.07, 'USD', 'Transaction TXN-2024-000011', 'completed', 'TXN-2024-000011', '2024-01-12 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (12, 13, 138.44, 'USD', 'Transaction TXN-2024-000012', 'completed', 'TXN-2024-000012', '2024-01-13 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (13, 14, 145.81, 'USD', 'Transaction TXN-2024-000013', 'completed', 'TXN-2024-000013', '2024-01-14 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (14, 15, 153.18, 'USD', 'Transaction TXN-2024-000014', 'completed', 'TXN-2024-000014', '2024-01-15 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (15, 16, 160.55, 'USD', 'Transaction TXN-2024-000015', 'completed', 'TXN-2024-000015', '2024-01-16 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (16, 17, 167.92, 'USD', 'Transaction TXN-2024-000016', 'completed', 'TXN-2024-000016', '2024-01-17 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (17, 18, 175.29, 'USD', 'Transaction TXN-2024-000017', 'completed', 'TXN-2024-000017', '2024-01-18 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (18, 19, 182.66, 'USD', 'Transaction TXN-2024-000018', 'completed', 'TXN-2024-000018', '2024-01-19 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (19, 20, 190.03, 'USD', 'Transaction TXN-2024-000019', 'completed', 'TXN-2024-000019', '2024-01-20 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (20, 1, 197.4, 'USD', 'Transaction TXN-2024-000020', 'failed', 'TXN-2024-000020', '2024-01-21 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (21, 2, 204.77, 'USD', 'Transaction TXN-2024-000021', 'completed', 'TXN-2024-000021', '2024-02-22 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (22, 3, 212.14, 'USD', 'Transaction TXN-2024-000022', 'completed', 'TXN-2024-000022', '2024-02-23 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (23, 4, 219.51, 'USD', 'Transaction TXN-2024-000023', 'completed', 'TXN-2024-000023', '2024-02-24 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (24, 5, 226.88, 'USD', 'Transaction TXN-2024-000024', 'completed', 'TXN-2024-000024', '2024-02-25 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (25, 6, 234.25, 'USD', 'Transaction TXN-2024-000025', 'completed', 'TXN-2024-000025', '2024-02-26 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (26, 7, 241.62, 'USD', 'Transaction TXN-2024-000026', 'completed', 'TXN-2024-000026', '2024-02-27 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (27, 8, 248.99, 'USD', 'Transaction TXN-2024-000027', 'completed', 'TXN-2024-000027', '2024-02-28 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (28, 9, 256.36, 'USD', 'Transaction TXN-2024-000028', 'completed', 'TXN-2024-000028', '2024-02-01 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (29, 10, 263.73, 'USD', 'Transaction TXN-2024-000029', 'completed', 'TXN-2024-000029', '2024-02-02 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (30, 11, 271.1, 'USD', 'Transaction TXN-2024-000030', 'pending', 'TXN-2024-000030', '2024-02-03 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (31, 12, 278.47, 'USD', 'Transaction TXN-2024-000031', 'completed', 'TXN-2024-000031', '2024-02-04 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (32, 13, 285.84, 'USD', 'Transaction TXN-2024-000032', 'completed', 'TXN-2024-000032', '2024-02-05 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (33, 14, 293.21, 'USD', 'Transaction TXN-2024-000033', 'completed', 'TXN-2024-000033', '2024-02-06 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (34, 15, 300.58, 'USD', 'Transaction TXN-2024-000034', 'completed', 'TXN-2024-000034', '2024-02-07 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (35, 16, 307.95, 'USD', 'Transaction TXN-2024-000035', 'completed', 'TXN-2024-000035', '2024-02-08 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (36, 17, 315.32, 'USD', 'Transaction TXN-2024-000036', 'completed', 'TXN-2024-000036', '2024-02-09 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (37, 18, 322.69, 'USD', 'Transaction TXN-2024-000037', 'completed', 'TXN-2024-000037', '2024-02-10 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (38, 19, 330.06, 'USD', 'Transaction TXN-2024-000038', 'completed', 'TXN-2024-000038', '2024-02-11 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (39, 20, 337.43, 'USD', 'Transaction TXN-2024-000039', 'completed', 'TXN-2024-000039', '2024-02-12 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (40, 1, 344.8, 'USD', 'Transaction TXN-2024-000040', 'failed', 'TXN-2024-000040', '2024-02-13 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (41, 2, 352.17, 'USD', 'Transaction TXN-2024-000041', 'completed', 'TXN-2024-000041', '2024-03-14 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (42, 3, 359.54, 'USD', 'Transaction TXN-2024-000042', 'completed', 'TXN-2024-000042', '2024-03-15 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (43, 4, 366.91, 'USD', 'Transaction TXN-2024-000043', 'completed', 'TXN-2024-000043', '2024-03-16 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (44, 5, 374.28, 'USD', 'Transaction TXN-2024-000044', 'completed', 'TXN-2024-000044', '2024-03-17 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (45, 6, 381.65, 'USD', 'Transaction TXN-2024-000045', 'completed', 'TXN-2024-000045', '2024-03-18 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (46, 7, 389.02, 'USD', 'Transaction TXN-2024-000046', 'completed', 'TXN-2024-000046', '2024-03-19 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (47, 8, 396.39, 'USD', 'Transaction TXN-2024-000047', 'completed', 'TXN-2024-000047', '2024-03-20 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (48, 9, 403.76, 'USD', 'Transaction TXN-2024-000048', 'completed', 'TXN-2024-000048', '2024-03-21 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (49, 10, 411.13, 'USD', 'Transaction TXN-2024-000049', 'completed', 'TXN-2024-000049', '2024-03-22 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (50, 11, 418.5, 'USD', 'Transaction TXN-2024-000050', 'pending', 'TXN-2024-000050', '2024-03-23 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (51, 12, 425.87, 'USD', 'Transaction TXN-2024-000051', 'completed', 'TXN-2024-000051', '2024-03-24 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (52, 13, 433.24, 'USD', 'Transaction TXN-2024-000052', 'completed', 'TXN-2024-000052', '2024-03-25 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (53, 14, 440.61, 'USD', 'Transaction TXN-2024-000053', 'completed', 'TXN-2024-000053', '2024-03-26 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (54, 15, 447.98, 'USD', 'Transaction TXN-2024-000054', 'completed', 'TXN-2024-000054', '2024-03-27 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (55, 16, 455.35, 'USD', 'Transaction TXN-2024-000055', 'completed', 'TXN-2024-000055', '2024-03-28 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (56, 17, 462.72, 'USD', 'Transaction TXN-2024-000056', 'completed', 'TXN-2024-000056', '2024-03-01 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (57, 18, 470.09, 'USD', 'Transaction TXN-2024-000057', 'completed', 'TXN-2024-000057', '2024-03-02 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (58, 19, 477.46, 'USD', 'Transaction TXN-2024-000058', 'completed', 'TXN-2024-000058', '2024-03-03 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (59, 20, 484.83, 'USD', 'Transaction TXN-2024-000059', 'completed', 'TXN-2024-000059', '2024-03-04 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (60, 1, 492.2, 'USD', 'Transaction TXN-2024-000060', 'failed', 'TXN-2024-000060', '2024-03-05 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (61, 2, 499.57, 'USD', 'Transaction TXN-2024-000061', 'completed', 'TXN-2024-000061', '2024-04-06 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (62, 3, 506.94, 'USD', 'Transaction TXN-2024-000062', 'completed', 'TXN-2024-000062', '2024-04-07 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (63, 4, 514.31, 'USD', 'Transaction TXN-2024-000063', 'completed', 'TXN-2024-000063', '2024-04-08 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (64, 5, 521.68, 'USD', 'Transaction TXN-2024-000064', 'completed', 'TXN-2024-000064', '2024-04-09 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (65, 6, 529.05, 'USD', 'Transaction TXN-2024-000065', 'completed', 'TXN-2024-000065', '2024-04-10 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (66, 7, 536.42, 'USD', 'Transaction TXN-2024-000066', 'completed', 'TXN-2024-000066', '2024-04-11 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (67, 8, 543.79, 'USD', 'Transaction TXN-2024-000067', 'completed', 'TXN-2024-000067', '2024-04-12 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (68, 9, 551.16, 'USD', 'Transaction TXN-2024-000068', 'completed', 'TXN-2024-000068', '2024-04-13 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (69, 10, 558.53, 'USD', 'Transaction TXN-2024-000069', 'completed', 'TXN-2024-000069', '2024-04-14 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (70, 11, 565.9, 'USD', 'Transaction TXN-2024-000070', 'pending', 'TXN-2024-000070', '2024-04-15 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (71, 12, 573.27, 'USD', 'Transaction TXN-2024-000071', 'completed', 'TXN-2024-000071', '2024-04-16 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (72, 13, 580.64, 'USD', 'Transaction TXN-2024-000072', 'completed', 'TXN-2024-000072', '2024-04-17 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (73, 14, 588.01, 'USD', 'Transaction TXN-2024-000073', 'completed', 'TXN-2024-000073', '2024-04-18 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (74, 15, 595.38, 'USD', 'Transaction TXN-2024-000074', 'completed', 'TXN-2024-000074', '2024-04-19 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (75, 16, 602.75, 'USD', 'Transaction TXN-2024-000075', 'completed', 'TXN-2024-000075', '2024-04-20 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (76, 17, 610.12, 'USD', 'Transaction TXN-2024-000076', 'completed', 'TXN-2024-000076', '2024-04-21 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (77, 18, 617.49, 'USD', 'Transaction TXN-2024-000077', 'completed', 'TXN-2024-000077', '2024-04-22 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (78, 19, 624.86, 'USD', 'Transaction TXN-2024-000078', 'completed', 'TXN-2024-000078', '2024-04-23 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (79, 20, 632.23, 'USD', 'Transaction TXN-2024-000079', 'completed', 'TXN-2024-000079', '2024-04-24 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (80, 1, 639.6, 'USD', 'Transaction TXN-2024-000080', 'failed', 'TXN-2024-000080', '2024-04-25 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (81, 2, 646.97, 'USD', 'Transaction TXN-2024-000081', 'completed', 'TXN-2024-000081', '2024-05-26 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (82, 3, 654.34, 'USD', 'Transaction TXN-2024-000082', 'completed', 'TXN-2024-000082', '2024-05-27 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (83, 4, 661.71, 'USD', 'Transaction TXN-2024-000083', 'completed', 'TXN-2024-000083', '2024-05-28 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (84, 5, 669.08, 'USD', 'Transaction TXN-2024-000084', 'completed', 'TXN-2024-000084', '2024-05-01 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (85, 6, 676.45, 'USD', 'Transaction TXN-2024-000085', 'completed', 'TXN-2024-000085', '2024-05-02 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (86, 7, 683.82, 'USD', 'Transaction TXN-2024-000086', 'completed', 'TXN-2024-000086', '2024-05-03 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (87, 8, 691.19, 'USD', 'Transaction TXN-2024-000087', 'completed', 'TXN-2024-000087', '2024-05-04 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (88, 9, 698.56, 'USD', 'Transaction TXN-2024-000088', 'completed', 'TXN-2024-000088', '2024-05-05 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (89, 10, 705.93, 'USD', 'Transaction TXN-2024-000089', 'completed', 'TXN-2024-000089', '2024-05-06 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (90, 11, 713.3, 'USD', 'Transaction TXN-2024-000090', 'pending', 'TXN-2024-000090', '2024-05-07 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (91, 12, 720.67, 'USD', 'Transaction TXN-2024-000091', 'completed', 'TXN-2024-000091', '2024-05-08 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (92, 13, 728.04, 'USD', 'Transaction TXN-2024-000092', 'completed', 'TXN-2024-000092', '2024-05-09 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (93, 14, 735.41, 'USD', 'Transaction TXN-2024-000093', 'completed', 'TXN-2024-000093', '2024-05-10 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (94, 15, 742.78, 'USD', 'Transaction TXN-2024-000094', 'completed', 'TXN-2024-000094', '2024-05-11 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (95, 16, 750.15, 'USD', 'Transaction TXN-2024-000095', 'completed', 'TXN-2024-000095', '2024-05-12 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (96, 17, 757.52, 'USD', 'Transaction TXN-2024-000096', 'completed', 'TXN-2024-000096', '2024-05-13 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (97, 18, 764.89, 'USD', 'Transaction TXN-2024-000097', 'completed', 'TXN-2024-000097', '2024-05-14 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (98, 19, 772.26, 'USD', 'Transaction TXN-2024-000098', 'completed', 'TXN-2024-000098', '2024-05-15 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (99, 20, 779.63, 'USD', 'Transaction TXN-2024-000099', 'completed', 'TXN-2024-000099', '2024-05-16 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (100, 1, 787.0, 'USD', 'Transaction TXN-2024-000100', 'failed', 'TXN-2024-000100', '2024-05-17 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (101, 2, 794.37, 'USD', 'Transaction TXN-2024-000101', 'completed', 'TXN-2024-000101', '2024-06-18 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (102, 3, 801.74, 'USD', 'Transaction TXN-2024-000102', 'completed', 'TXN-2024-000102', '2024-06-19 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (103, 4, 809.11, 'USD', 'Transaction TXN-2024-000103', 'completed', 'TXN-2024-000103', '2024-06-20 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (104, 5, 816.48, 'USD', 'Transaction TXN-2024-000104', 'completed', 'TXN-2024-000104', '2024-06-21 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (105, 6, 823.85, 'USD', 'Transaction TXN-2024-000105', 'completed', 'TXN-2024-000105', '2024-06-22 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (106, 7, 831.22, 'USD', 'Transaction TXN-2024-000106', 'completed', 'TXN-2024-000106', '2024-06-23 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (107, 8, 838.59, 'USD', 'Transaction TXN-2024-000107', 'completed', 'TXN-2024-000107', '2024-06-24 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (108, 9, 845.96, 'USD', 'Transaction TXN-2024-000108', 'completed', 'TXN-2024-000108', '2024-06-25 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (109, 10, 853.33, 'USD', 'Transaction TXN-2024-000109', 'completed', 'TXN-2024-000109', '2024-06-26 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (110, 11, 860.7, 'USD', 'Transaction TXN-2024-000110', 'pending', 'TXN-2024-000110', '2024-06-27 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (111, 12, 868.07, 'USD', 'Transaction TXN-2024-000111', 'completed', 'TXN-2024-000111', '2024-06-28 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (112, 13, 875.44, 'USD', 'Transaction TXN-2024-000112', 'completed', 'TXN-2024-000112', '2024-06-01 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (113, 14, 882.81, 'USD', 'Transaction TXN-2024-000113', 'completed', 'TXN-2024-000113', '2024-06-02 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (114, 15, 890.18, 'USD', 'Transaction TXN-2024-000114', 'completed', 'TXN-2024-000114', '2024-06-03 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (115, 16, 897.55, 'USD', 'Transaction TXN-2024-000115', 'completed', 'TXN-2024-000115', '2024-06-04 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (116, 17, 904.92, 'USD', 'Transaction TXN-2024-000116', 'completed', 'TXN-2024-000116', '2024-06-05 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (117, 18, 912.29, 'USD', 'Transaction TXN-2024-000117', 'completed', 'TXN-2024-000117', '2024-06-06 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (118, 19, 919.66, 'USD', 'Transaction TXN-2024-000118', 'completed', 'TXN-2024-000118', '2024-06-07 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (119, 20, 927.03, 'USD', 'Transaction TXN-2024-000119', 'completed', 'TXN-2024-000119', '2024-06-08 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (120, 1, 934.4, 'USD', 'Transaction TXN-2024-000120', 'failed', 'TXN-2024-000120', '2024-06-09 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (121, 2, 941.77, 'USD', 'Transaction TXN-2024-000121', 'completed', 'TXN-2024-000121', '2024-07-10 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (122, 3, 949.14, 'USD', 'Transaction TXN-2024-000122', 'completed', 'TXN-2024-000122', '2024-07-11 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (123, 4, 956.51, 'USD', 'Transaction TXN-2024-000123', 'completed', 'TXN-2024-000123', '2024-07-12 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (124, 5, 963.88, 'USD', 'Transaction TXN-2024-000124', 'completed', 'TXN-2024-000124', '2024-07-13 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (125, 6, 971.25, 'USD', 'Transaction TXN-2024-000125', 'completed', 'TXN-2024-000125', '2024-07-14 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (126, 7, 978.62, 'USD', 'Transaction TXN-2024-000126', 'completed', 'TXN-2024-000126', '2024-07-15 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (127, 8, 985.99, 'USD', 'Transaction TXN-2024-000127', 'completed', 'TXN-2024-000127', '2024-07-16 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (128, 9, 993.36, 'USD', 'Transaction TXN-2024-000128', 'completed', 'TXN-2024-000128', '2024-07-17 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (129, 10, 1000.73, 'USD', 'Transaction TXN-2024-000129', 'completed', 'TXN-2024-000129', '2024-07-18 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (130, 11, 1008.1, 'USD', 'Transaction TXN-2024-000130', 'pending', 'TXN-2024-000130', '2024-07-19 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (131, 12, 1015.47, 'USD', 'Transaction TXN-2024-000131', 'completed', 'TXN-2024-000131', '2024-07-20 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (132, 13, 1022.84, 'USD', 'Transaction TXN-2024-000132', 'completed', 'TXN-2024-000132', '2024-07-21 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (133, 14, 1030.21, 'USD', 'Transaction TXN-2024-000133', 'completed', 'TXN-2024-000133', '2024-07-22 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (134, 15, 1037.58, 'USD', 'Transaction TXN-2024-000134', 'completed', 'TXN-2024-000134', '2024-07-23 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (135, 16, 1044.95, 'USD', 'Transaction TXN-2024-000135', 'completed', 'TXN-2024-000135', '2024-07-24 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (136, 17, 1052.32, 'USD', 'Transaction TXN-2024-000136', 'completed', 'TXN-2024-000136', '2024-07-25 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (137, 18, 1059.69, 'USD', 'Transaction TXN-2024-000137', 'completed', 'TXN-2024-000137', '2024-07-26 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (138, 19, 1067.06, 'USD', 'Transaction TXN-2024-000138', 'completed', 'TXN-2024-000138', '2024-07-27 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (139, 20, 1074.43, 'USD', 'Transaction TXN-2024-000139', 'completed', 'TXN-2024-000139', '2024-07-28 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (140, 1, 1081.8, 'USD', 'Transaction TXN-2024-000140', 'failed', 'TXN-2024-000140', '2024-07-01 08:20:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (141, 2, 1089.17, 'USD', 'Transaction TXN-2024-000141', 'completed', 'TXN-2024-000141', '2024-08-02 09:21:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (142, 3, 1096.54, 'USD', 'Transaction TXN-2024-000142', 'completed', 'TXN-2024-000142', '2024-08-03 10:22:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (143, 4, 1103.91, 'USD', 'Transaction TXN-2024-000143', 'completed', 'TXN-2024-000143', '2024-08-04 11:23:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (144, 5, 1111.28, 'USD', 'Transaction TXN-2024-000144', 'completed', 'TXN-2024-000144', '2024-08-05 12:24:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (145, 6, 1118.65, 'USD', 'Transaction TXN-2024-000145', 'completed', 'TXN-2024-000145', '2024-08-06 13:25:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (146, 7, 1126.02, 'USD', 'Transaction TXN-2024-000146', 'completed', 'TXN-2024-000146', '2024-08-07 14:26:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (147, 8, 1133.39, 'USD', 'Transaction TXN-2024-000147', 'completed', 'TXN-2024-000147', '2024-08-08 15:27:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (148, 9, 1140.76, 'USD', 'Transaction TXN-2024-000148', 'completed', 'TXN-2024-000148', '2024-08-09 16:28:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (149, 10, 1148.13, 'USD', 'Transaction TXN-2024-000149', 'completed', 'TXN-2024-000149', '2024-08-10 17:29:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (150, 11, 1155.5, 'USD', 'Transaction TXN-2024-000150', 'pending', 'TXN-2024-000150', '2024-08-11 08:30:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (151, 12, 1162.87, 'USD', 'Transaction TXN-2024-000151', 'completed', 'TXN-2024-000151', '2024-08-12 09:31:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (152, 13, 1170.24, 'USD', 'Transaction TXN-2024-000152', 'completed', 'TXN-2024-000152', '2024-08-13 10:32:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (153, 14, 1177.61, 'USD', 'Transaction TXN-2024-000153', 'completed', 'TXN-2024-000153', '2024-08-14 11:33:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (154, 15, 1184.98, 'USD', 'Transaction TXN-2024-000154', 'completed', 'TXN-2024-000154', '2024-08-15 12:34:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (155, 16, 1192.35, 'USD', 'Transaction TXN-2024-000155', 'completed', 'TXN-2024-000155', '2024-08-16 13:35:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (156, 17, 1199.72, 'USD', 'Transaction TXN-2024-000156', 'completed', 'TXN-2024-000156', '2024-08-17 14:36:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (157, 18, 1207.09, 'USD', 'Transaction TXN-2024-000157', 'completed', 'TXN-2024-000157', '2024-08-18 15:37:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (158, 19, 1214.46, 'USD', 'Transaction TXN-2024-000158', 'completed', 'TXN-2024-000158', '2024-08-19 16:38:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (159, 20, 1221.83, 'USD', 'Transaction TXN-2024-000159', 'completed', 'TXN-2024-000159', '2024-08-20 17:39:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (160, 1, 1229.2, 'USD', 'Transaction TXN-2024-000160', 'failed', 'TXN-2024-000160', '2024-08-21 08:40:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (161, 2, 1236.57, 'USD', 'Transaction TXN-2024-000161', 'completed', 'TXN-2024-000161', '2024-09-22 09:41:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (162, 3, 1243.94, 'USD', 'Transaction TXN-2024-000162', 'completed', 'TXN-2024-000162', '2024-09-23 10:42:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (163, 4, 1251.31, 'USD', 'Transaction TXN-2024-000163', 'completed', 'TXN-2024-000163', '2024-09-24 11:43:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (164, 5, 1258.68, 'USD', 'Transaction TXN-2024-000164', 'completed', 'TXN-2024-000164', '2024-09-25 12:44:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (165, 6, 1266.05, 'USD', 'Transaction TXN-2024-000165', 'completed', 'TXN-2024-000165', '2024-09-26 13:45:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (166, 7, 1273.42, 'USD', 'Transaction TXN-2024-000166', 'completed', 'TXN-2024-000166', '2024-09-27 14:46:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (167, 8, 1280.79, 'USD', 'Transaction TXN-2024-000167', 'completed', 'TXN-2024-000167', '2024-09-28 15:47:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (168, 9, 1288.16, 'USD', 'Transaction TXN-2024-000168', 'completed', 'TXN-2024-000168', '2024-09-01 16:48:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (169, 10, 1295.53, 'USD', 'Transaction TXN-2024-000169', 'completed', 'TXN-2024-000169', '2024-09-02 17:49:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (170, 11, 1302.9, 'USD', 'Transaction TXN-2024-000170', 'pending', 'TXN-2024-000170', '2024-09-03 08:50:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (171, 12, 1310.27, 'USD', 'Transaction TXN-2024-000171', 'completed', 'TXN-2024-000171', '2024-09-04 09:51:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (172, 13, 1317.64, 'USD', 'Transaction TXN-2024-000172', 'completed', 'TXN-2024-000172', '2024-09-05 10:52:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (173, 14, 1325.01, 'USD', 'Transaction TXN-2024-000173', 'completed', 'TXN-2024-000173', '2024-09-06 11:53:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (174, 15, 1332.38, 'USD', 'Transaction TXN-2024-000174', 'completed', 'TXN-2024-000174', '2024-09-07 12:54:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (175, 16, 1339.75, 'USD', 'Transaction TXN-2024-000175', 'completed', 'TXN-2024-000175', '2024-09-08 13:55:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (176, 17, 1347.12, 'USD', 'Transaction TXN-2024-000176', 'completed', 'TXN-2024-000176', '2024-09-09 14:56:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (177, 18, 1354.49, 'USD', 'Transaction TXN-2024-000177', 'completed', 'TXN-2024-000177', '2024-09-10 15:57:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (178, 19, 1361.86, 'USD', 'Transaction TXN-2024-000178', 'completed', 'TXN-2024-000178', '2024-09-11 16:58:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (179, 20, 1369.23, 'USD', 'Transaction TXN-2024-000179', 'completed', 'TXN-2024-000179', '2024-09-12 17:59:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (180, 1, 1376.6, 'USD', 'Transaction TXN-2024-000180', 'failed', 'TXN-2024-000180', '2024-09-13 08:00:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (181, 2, 1383.97, 'USD', 'Transaction TXN-2024-000181', 'completed', 'TXN-2024-000181', '2024-10-14 09:01:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (182, 3, 1391.34, 'USD', 'Transaction TXN-2024-000182', 'completed', 'TXN-2024-000182', '2024-10-15 10:02:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (183, 4, 1398.71, 'USD', 'Transaction TXN-2024-000183', 'completed', 'TXN-2024-000183', '2024-10-16 11:03:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (184, 5, 1406.08, 'USD', 'Transaction TXN-2024-000184', 'completed', 'TXN-2024-000184', '2024-10-17 12:04:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (185, 6, 1413.45, 'USD', 'Transaction TXN-2024-000185', 'completed', 'TXN-2024-000185', '2024-10-18 13:05:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (186, 7, 1420.82, 'USD', 'Transaction TXN-2024-000186', 'completed', 'TXN-2024-000186', '2024-10-19 14:06:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (187, 8, 1428.19, 'USD', 'Transaction TXN-2024-000187', 'completed', 'TXN-2024-000187', '2024-10-20 15:07:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (188, 9, 1435.56, 'USD', 'Transaction TXN-2024-000188', 'completed', 'TXN-2024-000188', '2024-10-21 16:08:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (189, 10, 1442.93, 'USD', 'Transaction TXN-2024-000189', 'completed', 'TXN-2024-000189', '2024-10-22 17:09:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (190, 11, 1450.3, 'USD', 'Transaction TXN-2024-000190', 'pending', 'TXN-2024-000190', '2024-10-23 08:10:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (191, 12, 1457.67, 'USD', 'Transaction TXN-2024-000191', 'completed', 'TXN-2024-000191', '2024-10-24 09:11:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (192, 13, 1465.04, 'USD', 'Transaction TXN-2024-000192', 'completed', 'TXN-2024-000192', '2024-10-25 10:12:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (193, 14, 1472.41, 'USD', 'Transaction TXN-2024-000193', 'completed', 'TXN-2024-000193', '2024-10-26 11:13:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (194, 15, 1479.78, 'USD', 'Transaction TXN-2024-000194', 'completed', 'TXN-2024-000194', '2024-10-27 12:14:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (195, 16, 1487.15, 'USD', 'Transaction TXN-2024-000195', 'completed', 'TXN-2024-000195', '2024-10-28 13:15:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (196, 17, 1494.52, 'USD', 'Transaction TXN-2024-000196', 'completed', 'TXN-2024-000196', '2024-10-01 14:16:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (197, 18, 1501.89, 'USD', 'Transaction TXN-2024-000197', 'completed', 'TXN-2024-000197', '2024-10-02 15:17:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (198, 19, 1509.26, 'USD', 'Transaction TXN-2024-000198', 'completed', 'TXN-2024-000198', '2024-10-03 16:18:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (199, 20, 1516.63, 'USD', 'Transaction TXN-2024-000199', 'completed', 'TXN-2024-000199', '2024-10-04 17:19:00');
INSERT INTO transactions (id, user_id, amount, currency, description, status, reference_id, created_at) VALUES (200, 1, 1524.0, 'USD', 'Transaction TXN-2024-000200', 'failed', 'TXN-2024-000200', '2024-10-05 08:20:00');
SELECT setval('transactions_id_seq', 200);
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (1, 2, 'logout', '/api/v1/logout', '10.0.11.101', '2024-01-02 09:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (2, 3, 'view_report', '/api/v1/view_report', '10.0.12.102', '2024-01-03 10:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (3, 4, 'export_data', '/api/v1/export_data', '10.0.13.103', '2024-01-04 11:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (4, 5, 'update_record', '/api/v1/update_record', '10.0.14.104', '2024-01-05 12:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (5, 6, 'create_user', '/api/v1/create_user', '10.0.10.105', '2024-01-06 13:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (6, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.106', '2024-01-07 14:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (7, 8, 'change_password', '/api/v1/change_password', '10.0.12.107', '2024-01-08 15:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (8, 9, 'api_call', '/api/v1/api_call', '10.0.13.108', '2024-01-09 16:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (9, 10, 'config_change', '/api/v1/config_change', '10.0.14.109', '2024-01-10 17:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (10, 11, 'login', '/api/v1/login', '10.0.10.110', '2024-01-11 18:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (11, 12, 'logout', '/api/v1/logout', '10.0.11.111', '2024-02-12 19:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (12, 13, 'view_report', '/api/v1/view_report', '10.0.12.112', '2024-02-13 20:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (13, 14, 'export_data', '/api/v1/export_data', '10.0.13.113', '2024-02-14 21:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (14, 15, 'update_record', '/api/v1/update_record', '10.0.14.114', '2024-02-15 08:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (15, 16, 'create_user', '/api/v1/create_user', '10.0.10.115', '2024-02-16 09:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (16, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.116', '2024-02-17 10:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (17, 18, 'change_password', '/api/v1/change_password', '10.0.12.117', '2024-02-18 11:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (18, 19, 'api_call', '/api/v1/api_call', '10.0.13.118', '2024-02-19 12:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (19, 20, 'config_change', '/api/v1/config_change', '10.0.14.119', '2024-02-20 13:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (20, 21, 'login', '/api/v1/login', '10.0.10.120', '2024-02-21 14:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (21, 22, 'logout', '/api/v1/logout', '10.0.11.121', '2024-03-22 15:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (22, 23, 'view_report', '/api/v1/view_report', '10.0.12.122', '2024-03-23 16:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (23, 24, 'export_data', '/api/v1/export_data', '10.0.13.123', '2024-03-24 17:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (24, 25, 'update_record', '/api/v1/update_record', '10.0.14.124', '2024-03-25 18:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (25, 1, 'create_user', '/api/v1/create_user', '10.0.10.125', '2024-03-26 19:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (26, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.126', '2024-03-27 20:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (27, 3, 'change_password', '/api/v1/change_password', '10.0.12.127', '2024-03-28 21:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (28, 4, 'api_call', '/api/v1/api_call', '10.0.13.128', '2024-03-01 08:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (29, 5, 'config_change', '/api/v1/config_change', '10.0.14.129', '2024-03-02 09:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (30, 6, 'login', '/api/v1/login', '10.0.10.130', '2024-03-03 10:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (31, 7, 'logout', '/api/v1/logout', '10.0.11.131', '2024-04-04 11:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (32, 8, 'view_report', '/api/v1/view_report', '10.0.12.132', '2024-04-05 12:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (33, 9, 'export_data', '/api/v1/export_data', '10.0.13.133', '2024-04-06 13:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (34, 10, 'update_record', '/api/v1/update_record', '10.0.14.134', '2024-04-07 14:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (35, 11, 'create_user', '/api/v1/create_user', '10.0.10.135', '2024-04-08 15:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (36, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.136', '2024-04-09 16:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (37, 13, 'change_password', '/api/v1/change_password', '10.0.12.137', '2024-04-10 17:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (38, 14, 'api_call', '/api/v1/api_call', '10.0.13.138', '2024-04-11 18:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (39, 15, 'config_change', '/api/v1/config_change', '10.0.14.139', '2024-04-12 19:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (40, 16, 'login', '/api/v1/login', '10.0.10.140', '2024-04-13 20:40:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (41, 17, 'logout', '/api/v1/logout', '10.0.11.141', '2024-05-14 21:41:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (42, 18, 'view_report', '/api/v1/view_report', '10.0.12.142', '2024-05-15 08:42:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (43, 19, 'export_data', '/api/v1/export_data', '10.0.13.143', '2024-05-16 09:43:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (44, 20, 'update_record', '/api/v1/update_record', '10.0.14.144', '2024-05-17 10:44:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (45, 21, 'create_user', '/api/v1/create_user', '10.0.10.145', '2024-05-18 11:45:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (46, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.146', '2024-05-19 12:46:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (47, 23, 'change_password', '/api/v1/change_password', '10.0.12.147', '2024-05-20 13:47:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (48, 24, 'api_call', '/api/v1/api_call', '10.0.13.148', '2024-05-21 14:48:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (49, 25, 'config_change', '/api/v1/config_change', '10.0.14.149', '2024-05-22 15:49:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (50, 1, 'login', '/api/v1/login', '10.0.10.150', '2024-05-23 16:50:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (51, 2, 'logout', '/api/v1/logout', '10.0.11.151', '2024-06-24 17:51:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (52, 3, 'view_report', '/api/v1/view_report', '10.0.12.152', '2024-06-25 18:52:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (53, 4, 'export_data', '/api/v1/export_data', '10.0.13.153', '2024-06-26 19:53:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (54, 5, 'update_record', '/api/v1/update_record', '10.0.14.154', '2024-06-27 20:54:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (55, 6, 'create_user', '/api/v1/create_user', '10.0.10.155', '2024-06-28 21:55:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (56, 7, 'delete_record', '/api/v1/delete_record', '10.0.11.156', '2024-06-01 08:56:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (57, 8, 'change_password', '/api/v1/change_password', '10.0.12.157', '2024-06-02 09:57:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (58, 9, 'api_call', '/api/v1/api_call', '10.0.13.158', '2024-06-03 10:58:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (59, 10, 'config_change', '/api/v1/config_change', '10.0.14.159', '2024-06-04 11:59:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (60, 11, 'login', '/api/v1/login', '10.0.10.160', '2024-06-05 12:00:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (61, 12, 'logout', '/api/v1/logout', '10.0.11.161', '2024-07-06 13:01:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (62, 13, 'view_report', '/api/v1/view_report', '10.0.12.162', '2024-07-07 14:02:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (63, 14, 'export_data', '/api/v1/export_data', '10.0.13.163', '2024-07-08 15:03:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (64, 15, 'update_record', '/api/v1/update_record', '10.0.14.164', '2024-07-09 16:04:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (65, 16, 'create_user', '/api/v1/create_user', '10.0.10.165', '2024-07-10 17:05:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (66, 17, 'delete_record', '/api/v1/delete_record', '10.0.11.166', '2024-07-11 18:06:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (67, 18, 'change_password', '/api/v1/change_password', '10.0.12.167', '2024-07-12 19:07:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (68, 19, 'api_call', '/api/v1/api_call', '10.0.13.168', '2024-07-13 20:08:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (69, 20, 'config_change', '/api/v1/config_change', '10.0.14.169', '2024-07-14 21:09:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (70, 21, 'login', '/api/v1/login', '10.0.10.170', '2024-07-15 08:10:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (71, 22, 'logout', '/api/v1/logout', '10.0.11.171', '2024-08-16 09:11:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (72, 23, 'view_report', '/api/v1/view_report', '10.0.12.172', '2024-08-17 10:12:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (73, 24, 'export_data', '/api/v1/export_data', '10.0.13.173', '2024-08-18 11:13:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (74, 25, 'update_record', '/api/v1/update_record', '10.0.14.174', '2024-08-19 12:14:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (75, 1, 'create_user', '/api/v1/create_user', '10.0.10.175', '2024-08-20 13:15:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (76, 2, 'delete_record', '/api/v1/delete_record', '10.0.11.176', '2024-08-21 14:16:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (77, 3, 'change_password', '/api/v1/change_password', '10.0.12.177', '2024-08-22 15:17:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (78, 4, 'api_call', '/api/v1/api_call', '10.0.13.178', '2024-08-23 16:18:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (79, 5, 'config_change', '/api/v1/config_change', '10.0.14.179', '2024-08-24 17:19:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (80, 6, 'login', '/api/v1/login', '10.0.10.180', '2024-08-25 18:20:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (81, 7, 'logout', '/api/v1/logout', '10.0.11.181', '2024-09-26 19:21:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (82, 8, 'view_report', '/api/v1/view_report', '10.0.12.182', '2024-09-27 20:22:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (83, 9, 'export_data', '/api/v1/export_data', '10.0.13.183', '2024-09-28 21:23:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (84, 10, 'update_record', '/api/v1/update_record', '10.0.14.184', '2024-09-01 08:24:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (85, 11, 'create_user', '/api/v1/create_user', '10.0.10.185', '2024-09-02 09:25:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (86, 12, 'delete_record', '/api/v1/delete_record', '10.0.11.186', '2024-09-03 10:26:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (87, 13, 'change_password', '/api/v1/change_password', '10.0.12.187', '2024-09-04 11:27:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (88, 14, 'api_call', '/api/v1/api_call', '10.0.13.188', '2024-09-05 12:28:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (89, 15, 'config_change', '/api/v1/config_change', '10.0.14.189', '2024-09-06 13:29:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (90, 16, 'login', '/api/v1/login', '10.0.10.190', '2024-09-07 14:30:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (91, 17, 'logout', '/api/v1/logout', '10.0.11.191', '2024-10-08 15:31:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (92, 18, 'view_report', '/api/v1/view_report', '10.0.12.192', '2024-10-09 16:32:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (93, 19, 'export_data', '/api/v1/export_data', '10.0.13.193', '2024-10-10 17:33:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (94, 20, 'update_record', '/api/v1/update_record', '10.0.14.194', '2024-10-11 18:34:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (95, 21, 'create_user', '/api/v1/create_user', '10.0.10.195', '2024-10-12 19:35:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (96, 22, 'delete_record', '/api/v1/delete_record', '10.0.11.196', '2024-10-13 20:36:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (97, 23, 'change_password', '/api/v1/change_password', '10.0.12.197', '2024-10-14 21:37:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (98, 24, 'api_call', '/api/v1/api_call', '10.0.13.198', '2024-10-15 08:38:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (99, 25, 'config_change', '/api/v1/config_change', '10.0.14.199', '2024-10-16 09:39:00');
INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES (100, 1, 'login', '/api/v1/login', '10.0.10.200', '2024-10-17 10:40:00');
SELECT setval('audit_log_id_seq', 100);
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (1, 2, 'sess_0001_bcdef123', '10.0.3.101', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (2, 3, 'sess_0002_cdef1234', '10.0.3.102', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (3, 4, 'sess_0003_def12345', '10.0.3.103', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (4, 5, 'sess_0004_ef123456', '10.0.3.104', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (5, 6, 'sess_0005_f1234567', '10.0.3.105', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (6, 7, 'sess_0006_12345678', '10.0.3.106', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (7, 8, 'sess_0007_23456789', '10.0.3.107', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (8, 9, 'sess_0008_34567890', '10.0.3.108', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (9, 10, 'sess_0009_4567890', '10.0.3.109', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (10, 11, 'sess_0010_567890', '10.0.3.110', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (11, 12, 'sess_0011_67890', '10.0.3.111', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (12, 13, 'sess_0012_7890', '10.0.3.112', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (13, 14, 'sess_0013_890', '10.0.3.113', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (14, 15, 'sess_0014_90', '10.0.3.114', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (15, 16, 'sess_0015_0', '10.0.3.115', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (16, 17, 'sess_0016_abcdef12', '10.0.3.116', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (17, 18, 'sess_0017_bcdef123', '10.0.3.117', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (18, 19, 'sess_0018_cdef1234', '10.0.3.118', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (19, 20, 'sess_0019_def12345', '10.0.3.119', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (20, 21, 'sess_0020_ef123456', '10.0.3.120', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (21, 22, 'sess_0021_f1234567', '10.0.3.121', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (22, 23, 'sess_0022_12345678', '10.0.3.122', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (23, 24, 'sess_0023_23456789', '10.0.3.123', '2024-12-24 17:00:00', '2025-01-24 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (24, 25, 'sess_0024_34567890', '10.0.3.124', '2024-12-25 18:00:00', '2025-01-25 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (25, 1, 'sess_0025_4567890', '10.0.3.125', '2024-12-26 19:00:00', '2025-01-26 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (26, 2, 'sess_0026_567890', '10.0.3.126', '2024-12-27 20:00:00', '2025-01-27 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (27, 3, 'sess_0027_67890', '10.0.3.127', '2024-12-28 21:00:00', '2025-01-28 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (28, 4, 'sess_0028_7890', '10.0.3.128', '2024-12-01 08:00:00', '2025-01-01 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (29, 5, 'sess_0029_890', '10.0.3.129', '2024-12-02 09:00:00', '2025-01-02 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (30, 6, 'sess_0030_90', '10.0.3.130', '2024-12-03 10:00:00', '2025-01-03 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (31, 7, 'sess_0031_0', '10.0.3.131', '2024-12-04 11:00:00', '2025-01-04 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (32, 8, 'sess_0032_abcdef12', '10.0.3.132', '2024-12-05 12:00:00', '2025-01-05 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (33, 9, 'sess_0033_bcdef123', '10.0.3.133', '2024-12-06 13:00:00', '2025-01-06 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (34, 10, 'sess_0034_cdef1234', '10.0.3.134', '2024-12-07 14:00:00', '2025-01-07 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (35, 11, 'sess_0035_def12345', '10.0.3.135', '2024-12-08 15:00:00', '2025-01-08 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (36, 12, 'sess_0036_ef123456', '10.0.3.136', '2024-12-09 16:00:00', '2025-01-09 16:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (37, 13, 'sess_0037_f1234567', '10.0.3.137', '2024-12-10 17:00:00', '2025-01-10 17:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (38, 14, 'sess_0038_12345678', '10.0.3.138', '2024-12-11 18:00:00', '2025-01-11 18:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (39, 15, 'sess_0039_23456789', '10.0.3.139', '2024-12-12 19:00:00', '2025-01-12 19:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (40, 16, 'sess_0040_34567890', '10.0.3.140', '2024-12-13 20:00:00', '2025-01-13 20:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (41, 17, 'sess_0041_4567890', '10.0.3.141', '2024-12-14 21:00:00', '2025-01-14 21:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (42, 18, 'sess_0042_567890', '10.0.3.142', '2024-12-15 08:00:00', '2025-01-15 08:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (43, 19, 'sess_0043_67890', '10.0.3.143', '2024-12-16 09:00:00', '2025-01-16 09:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (44, 20, 'sess_0044_7890', '10.0.3.144', '2024-12-17 10:00:00', '2025-01-17 10:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (45, 21, 'sess_0045_890', '10.0.3.145', '2024-12-18 11:00:00', '2025-01-18 11:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (46, 22, 'sess_0046_90', '10.0.3.146', '2024-12-19 12:00:00', '2025-01-19 12:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (47, 23, 'sess_0047_0', '10.0.3.147', '2024-12-20 13:00:00', '2025-01-20 13:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (48, 24, 'sess_0048_abcdef12', '10.0.3.148', '2024-12-21 14:00:00', '2025-01-21 14:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (49, 25, 'sess_0049_bcdef123', '10.0.3.149', '2024-12-22 15:00:00', '2025-01-22 15:00:00');
INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES (50, 1, 'sess_0050_cdef1234', '10.0.3.150', '2024-12-23 16:00:00', '2025-01-23 16:00:00');
SELECT setval('sessions_id_seq', 50);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (1, 1, '$2b$12$apikeyhash0001', 'Production API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (2, 12, '$2b$12$apikeyhash0002', 'Monitoring', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (3, 19, '$2b$12$apikeyhash0003', 'CI/CD Pipeline', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (4, 22, '$2b$12$apikeyhash0004', 'Admin Tools', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (5, 25, '$2b$12$apikeyhash0005', 'Service Integration', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (6, 6, '$2b$12$apikeyhash0006', 'Engineering API', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (7, 4, '$2b$12$apikeyhash0007', 'Dev Testing', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (8, 9, '$2b$12$apikeyhash0008', 'Analytics', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (9, 13, '$2b$12$apikeyhash0009', 'Sales Dashboard', true);
INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES (10, 8, '$2b$12$apikeyhash0010', 'Marketing API', true);
SELECT setval('api_keys_id_seq', 10);
INSERT INTO config (id, key, value, updated_at) VALUES (1, 'app.name', 'Corp Internal Platform', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (2, 'app.version', '2.4.1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (3, 'app.debug', 'false', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (4, 'app.timezone', 'UTC', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (5, 'auth.session_timeout', '3600', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (6, 'auth.max_attempts', '5', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (7, 'auth.lockout_duration', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (8, 'auth.mfa_required', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (9, 'db.pool_size', '20', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (10, 'db.max_overflow', '10', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (11, 'cache.backend', 'redis', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (12, 'cache.ttl', '300', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (13, 'email.smtp_host', 'smtp.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (14, 'email.smtp_port', '587', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (15, 'email.from_address', 'noreply@corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (16, 'storage.backend', 's3', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (17, 'storage.bucket', 'corp-app-data', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (18, 'storage.region', 'us-east-1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (19, 'logging.level', 'INFO', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (20, 'logging.sentry_dsn', 'https://key@sentry.corp.internal/1', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (21, 'api.rate_limit', '1000', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (22, 'api.key_rotation_days', '90', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (23, 'security.cors_origins', 'https://app.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (24, 'security.csp_policy', 'default-src self', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (25, 'backup.schedule', '0 2 * * *', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (26, 'backup.retention_days', '30', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (27, 'monitoring.endpoint', 'https://prometheus.corp.internal', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (28, 'monitoring.interval', '60', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (29, 'feature.new_dashboard', 'true', '2024-12-01 00:00:00');
INSERT INTO config (id, key, value, updated_at) VALUES (30, 'feature.beta_api_v3', 'false', '2024-12-01 00:00:00');
SELECT setval('config_id_seq', 30);

GRANT ALL ON ALL TABLES IN SCHEMA public TO nagios_check;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO nagios_check;
