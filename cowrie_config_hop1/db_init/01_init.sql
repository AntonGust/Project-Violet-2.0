-- Auto-generated honeypot database init script
ALTER USER 'root'@'localhost' IDENTIFIED BY 'H0n3yp0t_R00t!';
ALTER USER 'root'@'%' IDENTIFIED BY 'H0n3yp0t_R00t!';

CREATE DATABASE IF NOT EXISTS `wordpress_prod`;
CREATE USER IF NOT EXISTS 'wp_admin'@'%' IDENTIFIED BY 'Str0ng_But_Le4ked!';
GRANT ALL PRIVILEGES ON `wordpress_prod`.* TO 'wp_admin'@'%';
USE `wordpress_prod`;


CREATE TABLE IF NOT EXISTS wp_users (
    ID bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    user_login varchar(60) NOT NULL DEFAULT '',
    user_pass varchar(255) NOT NULL DEFAULT '',
    user_nicename varchar(50) NOT NULL DEFAULT '',
    user_email varchar(100) NOT NULL DEFAULT '',
    user_url varchar(100) NOT NULL DEFAULT '',
    user_registered datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_activation_key varchar(255) NOT NULL DEFAULT '',
    user_status int(11) NOT NULL DEFAULT 0,
    display_name varchar(250) NOT NULL DEFAULT '',
    PRIMARY KEY (ID),
    KEY user_login_key (user_login),
    KEY user_nicename (user_nicename),
    KEY user_email (user_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_posts (
    ID bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    post_author bigint(20) unsigned NOT NULL DEFAULT 0,
    post_date datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    post_content longtext NOT NULL,
    post_title text NOT NULL,
    post_excerpt text NOT NULL,
    post_status varchar(20) NOT NULL DEFAULT 'publish',
    post_name varchar(200) NOT NULL DEFAULT '',
    post_type varchar(20) NOT NULL DEFAULT 'post',
    PRIMARY KEY (ID),
    KEY post_name (post_name(191)),
    KEY post_author (post_author)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_comments (
    comment_ID bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    comment_post_ID bigint(20) unsigned NOT NULL DEFAULT 0,
    comment_author tinytext NOT NULL,
    comment_author_email varchar(100) NOT NULL DEFAULT '',
    comment_date datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comment_content text NOT NULL,
    comment_approved varchar(20) NOT NULL DEFAULT '1',
    comment_parent bigint(20) unsigned NOT NULL DEFAULT 0,
    user_id bigint(20) unsigned NOT NULL DEFAULT 0,
    PRIMARY KEY (comment_ID),
    KEY comment_post_ID (comment_post_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_options (
    option_id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    option_name varchar(191) NOT NULL DEFAULT '',
    option_value longtext NOT NULL,
    autoload varchar(20) NOT NULL DEFAULT 'yes',
    PRIMARY KEY (option_id),
    UNIQUE KEY option_name (option_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_postmeta (
    meta_id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    post_id bigint(20) unsigned NOT NULL DEFAULT 0,
    meta_key varchar(255) DEFAULT NULL,
    meta_value longtext,
    PRIMARY KEY (meta_id),
    KEY post_id (post_id),
    KEY meta_key (meta_key(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_usermeta (
    umeta_id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    user_id bigint(20) unsigned NOT NULL DEFAULT 0,
    meta_key varchar(255) DEFAULT NULL,
    meta_value longtext,
    PRIMARY KEY (umeta_id),
    KEY user_id (user_id),
    KEY meta_key (meta_key(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_terms (
    term_id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    name varchar(200) NOT NULL DEFAULT '',
    slug varchar(200) NOT NULL DEFAULT '',
    term_group bigint(10) NOT NULL DEFAULT 0,
    PRIMARY KEY (term_id),
    KEY slug (slug(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wp_term_taxonomy (
    term_taxonomy_id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
    term_id bigint(20) unsigned NOT NULL DEFAULT 0,
    taxonomy varchar(32) NOT NULL DEFAULT '',
    description longtext NOT NULL,
    parent bigint(20) unsigned NOT NULL DEFAULT 0,
    count bigint(20) NOT NULL DEFAULT 0,
    PRIMARY KEY (term_taxonomy_id),
    UNIQUE KEY term_id_taxonomy (term_id, taxonomy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (1, 'admin', '$P$Babcdefghijklmnopqrstuv0123456.', 'admin', 'admin@wp-prod-01.internal.corp', '2024-01-15 10:23:00', 'Admin User');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (2, 'editor', '$P$Babcdefghijklmnopqrstuv0123456.', 'editor', 'sarah.chen@company.com', '2024-02-01 08:45:00', 'Sarah Chen');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (3, 'author1', '$P$Babcdefghijklmnopqrstuv0123456.', 'author1', 'mike.johnson@company.com', '2024-02-15 14:30:00', 'Mike Johnson');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (4, 'author2', '$P$Babcdefghijklmnopqrstuv0123456.', 'author2', 'jessica.williams@company.com', '2024-03-01 09:15:00', 'Jessica Williams');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (5, 'contributor', '$P$Babcdefghijklmnopqrstuv0123456.', 'contributor', 'david.brown@company.com', '2024-03-10 11:00:00', 'David Brown');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (6, 'subscriber1', '$P$Babcdefghijklmnopqrstuv0123456.', 'subscriber1', 'emily.davis@gmail.com', '2024-04-01 16:20:00', 'Emily Davis');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (7, 'subscriber2', '$P$Babcdefghijklmnopqrstuv0123456.', 'subscriber2', 'james.wilson@outlook.com', '2024-04-15 13:45:00', 'James Wilson');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (8, 'subscriber3', '$P$Babcdefghijklmnopqrstuv0123456.', 'subscriber3', 'lisa.garcia@yahoo.com', '2024-05-01 10:30:00', 'Lisa Garcia');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (9, 'seo_manager', '$P$Babcdefghijklmnopqrstuv0123456.', 'seo_manager', 'alex.martinez@company.com', '2024-05-15 08:00:00', 'Alex Martinez');
INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, user_registered, display_name) VALUES (10, 'backup_admin', '$P$Babcdefghijklmnopqrstuv0123456.', 'backup_admin', 'ops@company.com', '2024-01-15 10:25:00', 'Ops Account');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (1, 1, 'wp_capabilities', 'a:1:{s:13:"administrator";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (2, 1, 'wp_user_level', '10');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (3, 1, 'nickname', 'admin');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (4, 1, 'first_name', 'Admin');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (5, 1, 'last_name', 'User');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (6, 2, 'wp_capabilities', 'a:1:{s:6:"editor";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (7, 2, 'wp_user_level', '7');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (8, 2, 'nickname', 'editor');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (9, 2, 'first_name', 'Sarah');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (10, 2, 'last_name', 'Chen');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (11, 3, 'wp_capabilities', 'a:1:{s:6:"author";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (12, 3, 'wp_user_level', '2');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (13, 3, 'nickname', 'author1');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (14, 3, 'first_name', 'Mike');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (15, 3, 'last_name', 'Johnson');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (16, 4, 'wp_capabilities', 'a:1:{s:6:"author";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (17, 4, 'wp_user_level', '2');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (18, 4, 'nickname', 'author2');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (19, 4, 'first_name', 'Jessica');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (20, 4, 'last_name', 'Williams');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (21, 5, 'wp_capabilities', 'a:1:{s:11:"contributor";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (22, 5, 'wp_user_level', '1');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (23, 5, 'nickname', 'contributor');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (24, 5, 'first_name', 'David');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (25, 5, 'last_name', 'Brown');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (26, 6, 'wp_capabilities', 'a:1:{s:10:"subscriber";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (27, 6, 'wp_user_level', '0');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (28, 6, 'nickname', 'subscriber1');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (29, 6, 'first_name', 'Emily');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (30, 6, 'last_name', 'Davis');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (31, 7, 'wp_capabilities', 'a:1:{s:10:"subscriber";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (32, 7, 'wp_user_level', '0');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (33, 7, 'nickname', 'subscriber2');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (34, 7, 'first_name', 'James');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (35, 7, 'last_name', 'Wilson');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (36, 8, 'wp_capabilities', 'a:1:{s:10:"subscriber";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (37, 8, 'wp_user_level', '0');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (38, 8, 'nickname', 'subscriber3');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (39, 8, 'first_name', 'Lisa');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (40, 8, 'last_name', 'Garcia');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (41, 9, 'wp_capabilities', 'a:1:{s:6:"editor";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (42, 9, 'wp_user_level', '7');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (43, 9, 'nickname', 'seo_manager');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (44, 9, 'first_name', 'Alex');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (45, 9, 'last_name', 'Martinez');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (46, 10, 'wp_capabilities', 'a:1:{s:13:"administrator";b:1;}');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (47, 10, 'wp_user_level', '10');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (48, 10, 'nickname', 'backup_admin');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (49, 10, 'first_name', 'Ops');
INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES (50, 10, 'last_name', 'Account');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (1, 2, '2024-01-02 10:00:00', 'Content for Hello World...', 'Hello World', '', 'publish', 'hello-world', 'page');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (2, 3, '2024-01-03 11:00:00', 'Content for About Us...', 'About Us', '', 'publish', 'about-us', 'page');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (3, 4, '2024-01-04 12:00:00', 'Content for Contact...', 'Contact', '', 'publish', 'contact', 'page');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (4, 5, '2024-01-05 13:00:00', 'Content for Privacy Policy...', 'Privacy Policy', '', 'publish', 'privacy-policy', 'page');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (5, 1, '2024-01-06 14:00:00', 'Content for Terms of Service...', 'Terms of Service', '', 'publish', 'terms-of-service', 'page');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (6, 2, '2024-02-07 15:00:00', 'Content for Q3 2024 Revenue Growth...', 'Q3 2024 Revenue Growth', '', 'publish', 'q3-2024-revenue-growth', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (7, 3, '2024-02-08 16:00:00', 'Content for New Product Launch Update...', 'New Product Launch Update', '', 'publish', 'new-product-launch-update', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (8, 4, '2024-02-09 09:00:00', 'Content for Engineering Blog: Kubernetes Migration...', 'Engineering Blog: Kubernetes Migration', '', 'publish', 'engineering-blog-kubernetes-migration', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (9, 5, '2024-02-10 10:00:00', 'Content for Company Culture: Remote Work Policy...', 'Company Culture: Remote Work Policy', '', 'publish', 'company-culture-remote-work-policy', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (10, 1, '2024-02-11 11:00:00', 'Content for Customer Success Story: Acme Corp...', 'Customer Success Story: Acme Corp', '', 'publish', 'customer-success-story-acme-corp', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (11, 2, '2024-03-12 12:00:00', 'Content for Security Best Practices for 2024...', 'Security Best Practices for 2024', '', 'publish', 'security-best-practices-for-2024', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (12, 3, '2024-03-13 13:00:00', 'Content for API Documentation v2.1...', 'API Documentation v2.1', '', 'publish', 'api-documentation-v2.1', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (13, 4, '2024-03-14 14:00:00', 'Content for Release Notes 6.4.2...', 'Release Notes 6.4.2', '', 'publish', 'release-notes-6.4.2', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (14, 5, '2024-03-15 15:00:00', 'Content for Infrastructure Upgrade Notice...', 'Infrastructure Upgrade Notice', '', 'publish', 'infrastructure-upgrade-notice', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (15, 1, '2024-03-16 16:00:00', 'Content for Monthly Newsletter: January...', 'Monthly Newsletter: January', '', 'publish', 'monthly-newsletter-january', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (16, 2, '2024-04-17 09:00:00', 'Content for Team Spotlight: Engineering...', 'Team Spotlight: Engineering', '', 'publish', 'team-spotlight-engineering', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (17, 3, '2024-04-18 10:00:00', 'Content for Case Study: Financial Services...', 'Case Study: Financial Services', '', 'publish', 'case-study-financial-services', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (18, 4, '2024-04-19 11:00:00', 'Content for Webinar Recap: Cloud Security...', 'Webinar Recap: Cloud Security', '', 'publish', 'webinar-recap-cloud-security', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (19, 5, '2024-04-20 12:00:00', 'Content for Product Roadmap 2025...', 'Product Roadmap 2025', '', 'publish', 'product-roadmap-2025', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (20, 1, '2024-04-21 13:00:00', 'Content for Board Meeting Minutes Q4...', 'Board Meeting Minutes Q4', '', 'publish', 'board-meeting-minutes-q4', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (21, 2, '2024-05-22 14:00:00', 'Content for Draft: Marketing Campaign Spring...', 'Draft: Marketing Campaign Spring', '', 'publish', 'draft-marketing-campaign-spring', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (22, 3, '2024-05-23 15:00:00', 'Content for Draft: Technical Architecture Review...', 'Draft: Technical Architecture Review', '', 'publish', 'draft-technical-architecture-review', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (23, 4, '2024-05-24 16:00:00', 'Content for Investor Relations Update...', 'Investor Relations Update', '', 'publish', 'investor-relations-update', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (24, 5, '2024-05-25 09:00:00', 'Content for Employee Handbook v3...', 'Employee Handbook v3', '', 'publish', 'employee-handbook-v3', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (25, 1, '2024-05-26 10:00:00', 'Content for IT Support Guide...', 'IT Support Guide', '', 'publish', 'it-support-guide', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (26, 2, '2024-06-27 11:00:00', 'Content for Onboarding Checklist...', 'Onboarding Checklist', '', 'publish', 'onboarding-checklist', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (27, 3, '2024-06-28 12:00:00', 'Content for Compliance Audit Report...', 'Compliance Audit Report', '', 'publish', 'compliance-audit-report', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (28, 4, '2024-06-01 13:00:00', 'Content for Data Retention Policy...', 'Data Retention Policy', '', 'publish', 'data-retention-policy', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (29, 5, '2024-06-02 14:00:00', 'Content for Backup and Recovery Procedures...', 'Backup and Recovery Procedures', '', 'publish', 'backup-and-recovery-procedures', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (30, 1, '2024-06-03 15:00:00', 'Content for Incident Response Playbook...', 'Incident Response Playbook', '', 'publish', 'incident-response-playbook', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (31, 2, '2024-07-04 16:00:00', 'Content for Vendor Assessment: AWS vs GCP...', 'Vendor Assessment: AWS vs GCP', '', 'draft', 'vendor-assessment-aws-vs-gcp', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (32, 3, '2024-07-05 09:00:00', 'Content for Budget Proposal 2025...', 'Budget Proposal 2025', '', 'draft', 'budget-proposal-2025', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (33, 4, '2024-07-06 10:00:00', 'Content for Risk Assessment Q4...', 'Risk Assessment Q4', '', 'draft', 'risk-assessment-q4', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (34, 5, '2024-07-07 11:00:00', 'Content for Performance Review Template...', 'Performance Review Template', '', 'draft', 'performance-review-template', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (35, 1, '2024-07-08 12:00:00', 'Content for Travel Policy Update...', 'Travel Policy Update', '', 'draft', 'travel-policy-update', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (36, 2, '2024-08-09 13:00:00', 'Content for Office Relocation FAQ...', 'Office Relocation FAQ', '', 'draft', 'office-relocation-faq', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (37, 3, '2024-08-10 14:00:00', 'Content for Health Benefits Overview...', 'Health Benefits Overview', '', 'draft', 'health-benefits-overview', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (38, 4, '2024-08-11 15:00:00', 'Content for Stock Option Plan Details...', 'Stock Option Plan Details', '', 'draft', 'stock-option-plan-details', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (39, 5, '2024-08-12 16:00:00', 'Content for Quarterly Business Review...', 'Quarterly Business Review', '', 'draft', 'quarterly-business-review', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (40, 1, '2024-08-13 09:00:00', 'Content for Customer Feedback Analysis...', 'Customer Feedback Analysis', '', 'draft', 'customer-feedback-analysis', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (41, 2, '2024-09-14 10:00:00', 'Content for SEO Strategy Document...', 'SEO Strategy Document', '', 'private', 'seo-strategy-document', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (42, 3, '2024-09-15 11:00:00', 'Content for Content Calendar Q1 2025...', 'Content Calendar Q1 2025', '', 'private', 'content-calendar-q1-2025', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (43, 4, '2024-09-16 12:00:00', 'Content for Social Media Metrics...', 'Social Media Metrics', '', 'private', 'social-media-metrics', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (44, 5, '2024-09-17 13:00:00', 'Content for Email Campaign Results...', 'Email Campaign Results', '', 'private', 'email-campaign-results', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (45, 1, '2024-09-18 14:00:00', 'Content for Brand Guidelines v2...', 'Brand Guidelines v2', '', 'private', 'brand-guidelines-v2', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (46, 2, '2024-10-19 15:00:00', 'Content for Partner Program Details...', 'Partner Program Details', '', 'private', 'partner-program-details', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (47, 3, '2024-10-20 16:00:00', 'Content for Reseller Agreement Template...', 'Reseller Agreement Template', '', 'private', 'reseller-agreement-template', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (48, 4, '2024-10-21 09:00:00', 'Content for Support SLA Document...', 'Support SLA Document', '', 'private', 'support-sla-document', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (49, 5, '2024-10-22 10:00:00', 'Content for Training Materials: Sales...', 'Training Materials: Sales', '', 'private', 'training-materials-sales', 'post');
INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, post_excerpt, post_status, post_name, post_type) VALUES (50, 1, '2024-10-23 11:00:00', 'Content for Knowledge Base: FAQ...', 'Knowledge Base: FAQ', '', 'private', 'knowledge-base-faq', 'post');
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (1, 7, 'Jane Doe', 'jane.doe@example.com', '2024-01-02 11:01:00', 'Comment #1 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (2, 8, 'Bob Wilson', 'bob.wilson@example.com', '2024-01-03 12:02:00', 'Comment #2 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (3, 9, 'Alice Brown', 'alice.brown@example.com', '2024-01-04 13:03:00', 'Comment #3 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (4, 10, 'Charlie Davis', 'charlie.davis@example.com', '2024-01-05 14:04:00', 'Comment #4 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (5, 11, 'Diana Miller', 'diana.miller@example.com', '2024-01-06 15:05:00', 'Comment #5 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (6, 12, 'Edward Jones', 'edward.jones@example.com', '2024-01-07 16:06:00', 'Comment #6 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (7, 13, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-01-08 17:07:00', 'Comment #7 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (8, 14, 'George Martin', 'george.martin@example.com', '2024-01-09 18:08:00', 'Comment #8 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (9, 15, 'Helen White', 'helen.white@example.com', '2024-01-10 19:09:00', 'Comment #9 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (10, 16, 'John Smith', 'john.smith@example.com', '2024-01-11 20:10:00', 'Comment #10 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (11, 17, 'Jane Doe', 'jane.doe@example.com', '2024-02-12 21:11:00', 'Comment #11 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (12, 18, 'Bob Wilson', 'bob.wilson@example.com', '2024-02-13 10:12:00', 'Comment #12 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (13, 19, 'Alice Brown', 'alice.brown@example.com', '2024-02-14 11:13:00', 'Comment #13 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (14, 20, 'Charlie Davis', 'charlie.davis@example.com', '2024-02-15 12:14:00', 'Comment #14 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (15, 21, 'Diana Miller', 'diana.miller@example.com', '2024-02-16 13:15:00', 'Comment #15 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (16, 22, 'Edward Jones', 'edward.jones@example.com', '2024-02-17 14:16:00', 'Comment #16 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (17, 23, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-02-18 15:17:00', 'Comment #17 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (18, 24, 'George Martin', 'george.martin@example.com', '2024-02-19 16:18:00', 'Comment #18 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (19, 25, 'Helen White', 'helen.white@example.com', '2024-02-20 17:19:00', 'Comment #19 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (20, 26, 'John Smith', 'john.smith@example.com', '2024-02-21 18:20:00', 'Comment #20 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (21, 27, 'Jane Doe', 'jane.doe@example.com', '2024-03-22 19:21:00', 'Comment #21 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (22, 28, 'Bob Wilson', 'bob.wilson@example.com', '2024-03-23 20:22:00', 'Comment #22 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (23, 29, 'Alice Brown', 'alice.brown@example.com', '2024-03-24 21:23:00', 'Comment #23 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (24, 30, 'Charlie Davis', 'charlie.davis@example.com', '2024-03-25 10:24:00', 'Comment #24 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (25, 31, 'Diana Miller', 'diana.miller@example.com', '2024-03-26 11:25:00', 'Comment #25 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (26, 32, 'Edward Jones', 'edward.jones@example.com', '2024-03-27 12:26:00', 'Comment #26 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (27, 33, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-03-28 13:27:00', 'Comment #27 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (28, 34, 'George Martin', 'george.martin@example.com', '2024-03-01 14:28:00', 'Comment #28 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (29, 35, 'Helen White', 'helen.white@example.com', '2024-03-02 15:29:00', 'Comment #29 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (30, 6, 'John Smith', 'john.smith@example.com', '2024-03-03 16:30:00', 'Comment #30 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (31, 7, 'Jane Doe', 'jane.doe@example.com', '2024-04-04 17:31:00', 'Comment #31 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (32, 8, 'Bob Wilson', 'bob.wilson@example.com', '2024-04-05 18:32:00', 'Comment #32 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (33, 9, 'Alice Brown', 'alice.brown@example.com', '2024-04-06 19:33:00', 'Comment #33 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (34, 10, 'Charlie Davis', 'charlie.davis@example.com', '2024-04-07 20:34:00', 'Comment #34 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (35, 11, 'Diana Miller', 'diana.miller@example.com', '2024-04-08 21:35:00', 'Comment #35 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (36, 12, 'Edward Jones', 'edward.jones@example.com', '2024-04-09 10:36:00', 'Comment #36 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (37, 13, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-04-10 11:37:00', 'Comment #37 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (38, 14, 'George Martin', 'george.martin@example.com', '2024-04-11 12:38:00', 'Comment #38 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (39, 15, 'Helen White', 'helen.white@example.com', '2024-04-12 13:39:00', 'Comment #39 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (40, 16, 'John Smith', 'john.smith@example.com', '2024-04-13 14:40:00', 'Comment #40 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (41, 17, 'Jane Doe', 'jane.doe@example.com', '2024-05-14 15:41:00', 'Comment #41 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (42, 18, 'Bob Wilson', 'bob.wilson@example.com', '2024-05-15 16:42:00', 'Comment #42 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (43, 19, 'Alice Brown', 'alice.brown@example.com', '2024-05-16 17:43:00', 'Comment #43 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (44, 20, 'Charlie Davis', 'charlie.davis@example.com', '2024-05-17 18:44:00', 'Comment #44 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (45, 21, 'Diana Miller', 'diana.miller@example.com', '2024-05-18 19:45:00', 'Comment #45 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (46, 22, 'Edward Jones', 'edward.jones@example.com', '2024-05-19 20:46:00', 'Comment #46 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (47, 23, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-05-20 21:47:00', 'Comment #47 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (48, 24, 'George Martin', 'george.martin@example.com', '2024-05-21 10:48:00', 'Comment #48 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (49, 25, 'Helen White', 'helen.white@example.com', '2024-05-22 11:49:00', 'Comment #49 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (50, 26, 'John Smith', 'john.smith@example.com', '2024-05-23 12:50:00', 'Comment #50 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (51, 27, 'Jane Doe', 'jane.doe@example.com', '2024-06-24 13:51:00', 'Comment #51 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (52, 28, 'Bob Wilson', 'bob.wilson@example.com', '2024-06-25 14:52:00', 'Comment #52 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (53, 29, 'Alice Brown', 'alice.brown@example.com', '2024-06-26 15:53:00', 'Comment #53 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (54, 30, 'Charlie Davis', 'charlie.davis@example.com', '2024-06-27 16:54:00', 'Comment #54 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (55, 31, 'Diana Miller', 'diana.miller@example.com', '2024-06-28 17:55:00', 'Comment #55 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (56, 32, 'Edward Jones', 'edward.jones@example.com', '2024-06-01 18:56:00', 'Comment #56 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (57, 33, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-06-02 19:57:00', 'Comment #57 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (58, 34, 'George Martin', 'george.martin@example.com', '2024-06-03 20:58:00', 'Comment #58 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (59, 35, 'Helen White', 'helen.white@example.com', '2024-06-04 21:59:00', 'Comment #59 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (60, 6, 'John Smith', 'john.smith@example.com', '2024-06-05 10:00:00', 'Comment #60 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (61, 7, 'Jane Doe', 'jane.doe@example.com', '2024-07-06 11:01:00', 'Comment #61 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (62, 8, 'Bob Wilson', 'bob.wilson@example.com', '2024-07-07 12:02:00', 'Comment #62 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (63, 9, 'Alice Brown', 'alice.brown@example.com', '2024-07-08 13:03:00', 'Comment #63 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (64, 10, 'Charlie Davis', 'charlie.davis@example.com', '2024-07-09 14:04:00', 'Comment #64 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (65, 11, 'Diana Miller', 'diana.miller@example.com', '2024-07-10 15:05:00', 'Comment #65 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (66, 12, 'Edward Jones', 'edward.jones@example.com', '2024-07-11 16:06:00', 'Comment #66 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (67, 13, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-07-12 17:07:00', 'Comment #67 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (68, 14, 'George Martin', 'george.martin@example.com', '2024-07-13 18:08:00', 'Comment #68 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (69, 15, 'Helen White', 'helen.white@example.com', '2024-07-14 19:09:00', 'Comment #69 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (70, 16, 'John Smith', 'john.smith@example.com', '2024-07-15 20:10:00', 'Comment #70 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (71, 17, 'Jane Doe', 'jane.doe@example.com', '2024-08-16 21:11:00', 'Comment #71 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (72, 18, 'Bob Wilson', 'bob.wilson@example.com', '2024-08-17 10:12:00', 'Comment #72 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (73, 19, 'Alice Brown', 'alice.brown@example.com', '2024-08-18 11:13:00', 'Comment #73 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (74, 20, 'Charlie Davis', 'charlie.davis@example.com', '2024-08-19 12:14:00', 'Comment #74 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (75, 21, 'Diana Miller', 'diana.miller@example.com', '2024-08-20 13:15:00', 'Comment #75 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (76, 22, 'Edward Jones', 'edward.jones@example.com', '2024-08-21 14:16:00', 'Comment #76 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (77, 23, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-08-22 15:17:00', 'Comment #77 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (78, 24, 'George Martin', 'george.martin@example.com', '2024-08-23 16:18:00', 'Comment #78 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (79, 25, 'Helen White', 'helen.white@example.com', '2024-08-24 17:19:00', 'Comment #79 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (80, 26, 'John Smith', 'john.smith@example.com', '2024-08-25 18:20:00', 'Comment #80 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (81, 27, 'Jane Doe', 'jane.doe@example.com', '2024-09-26 19:21:00', 'Comment #81 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (82, 28, 'Bob Wilson', 'bob.wilson@example.com', '2024-09-27 20:22:00', 'Comment #82 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (83, 29, 'Alice Brown', 'alice.brown@example.com', '2024-09-28 21:23:00', 'Comment #83 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (84, 30, 'Charlie Davis', 'charlie.davis@example.com', '2024-09-01 10:24:00', 'Comment #84 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (85, 31, 'Diana Miller', 'diana.miller@example.com', '2024-09-02 11:25:00', 'Comment #85 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (86, 32, 'Edward Jones', 'edward.jones@example.com', '2024-09-03 12:26:00', 'Comment #86 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (87, 33, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-09-04 13:27:00', 'Comment #87 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (88, 34, 'George Martin', 'george.martin@example.com', '2024-09-05 14:28:00', 'Comment #88 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (89, 35, 'Helen White', 'helen.white@example.com', '2024-09-06 15:29:00', 'Comment #89 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (90, 6, 'John Smith', 'john.smith@example.com', '2024-09-07 16:30:00', 'Comment #90 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (91, 7, 'Jane Doe', 'jane.doe@example.com', '2024-10-08 17:31:00', 'Comment #91 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (92, 8, 'Bob Wilson', 'bob.wilson@example.com', '2024-10-09 18:32:00', 'Comment #92 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (93, 9, 'Alice Brown', 'alice.brown@example.com', '2024-10-10 19:33:00', 'Comment #93 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (94, 10, 'Charlie Davis', 'charlie.davis@example.com', '2024-10-11 20:34:00', 'Comment #94 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (95, 11, 'Diana Miller', 'diana.miller@example.com', '2024-10-12 21:35:00', 'Comment #95 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (96, 12, 'Edward Jones', 'edward.jones@example.com', '2024-10-13 10:36:00', 'Comment #96 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (97, 13, 'Fiona Taylor', 'fiona.taylor@example.com', '2024-10-14 11:37:00', 'Comment #97 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (98, 14, 'George Martin', 'george.martin@example.com', '2024-10-15 12:38:00', 'Comment #98 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (99, 15, 'Helen White', 'helen.white@example.com', '2024-10-16 13:39:00', 'Comment #99 on this post.', '1', 0);
INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES (100, 16, 'John Smith', 'john.smith@example.com', '2024-10-17 14:40:00', 'Comment #100 on this post.', '1', 0);
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (1, 'siteurl', 'https://wp-prod-01.internal.corp', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (2, 'home', 'https://wp-prod-01.internal.corp', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (3, 'blogname', 'Company Internal Portal', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (4, 'blogdescription', 'Internal documentation and resources', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (5, 'admin_email', 'admin@wp-prod-01.internal.corp', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (6, 'users_can_register', '0', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (7, 'default_role', 'subscriber', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (8, 'timezone_string', 'UTC', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (9, 'date_format', 'Y-m-d', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (10, 'time_format', 'H:i', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (11, 'start_of_week', '1', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (12, 'permalink_structure', '/%postname%/', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (13, 'template', 'developer-starter', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (14, 'stylesheet', 'developer-starter', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (15, 'active_plugins', 'a:5:{i:0;s:30:"advanced-custom-fields/acf.php";i:1;s:33:"classic-editor/classic-editor.php";i:2;s:24:"wordpress-seo/wp-seo.php";i:3;s:27:"wp-mail-smtp/wp_mail_smtp.php";i:4;s:43:"updraftplus/updraftplus.php";}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (16, 'db_version', '57155', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (17, 'wp_version', '6.4.2', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (18, 'widget_pages', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (19, 'widget_calendar', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (20, 'widget_media_audio', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (21, 'widget_media_image', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (22, 'widget_media_gallery', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (23, 'widget_media_video', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (24, 'widget_meta', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (25, 'widget_search', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (26, 'widget_text', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (27, 'widget_categories', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (28, 'widget_recent-posts', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (29, 'widget_recent-comments', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (30, 'widget_rss', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (31, 'widget_tag_cloud', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (32, 'widget_nav_menu', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (33, 'widget_custom_html', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (34, 'sidebars_widgets', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (35, 'cron', 'a:0:{}', 'yes');
INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES (36, 'theme_mods_developer-starter', 'a:0:{}', 'yes');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (1, 2, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (2, 3, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (3, 4, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (4, 5, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (5, 6, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (6, 7, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (7, 8, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (8, 9, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (9, 10, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (10, 11, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (11, 12, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (12, 13, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (13, 14, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (14, 15, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (15, 16, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (16, 17, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (17, 18, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (18, 19, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (19, 20, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (20, 21, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (21, 22, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (22, 23, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (23, 24, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (24, 25, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (25, 26, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (26, 27, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (27, 28, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (28, 29, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (29, 30, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (30, 31, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (31, 32, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (32, 33, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (33, 34, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (34, 35, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (35, 36, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (36, 37, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (37, 38, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (38, 39, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (39, 40, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (40, 41, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (41, 42, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (42, 43, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (43, 44, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (44, 45, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (45, 46, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (46, 47, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (47, 48, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (48, 49, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (49, 50, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (50, 1, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (51, 2, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (52, 3, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (53, 4, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (54, 5, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (55, 6, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (56, 7, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (57, 8, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (58, 9, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (59, 10, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (60, 11, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (61, 12, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (62, 13, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (63, 14, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (64, 15, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (65, 16, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (66, 17, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (67, 18, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (68, 19, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (69, 20, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (70, 21, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (71, 22, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (72, 23, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (73, 24, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (74, 25, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (75, 26, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (76, 27, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (77, 28, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (78, 29, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (79, 30, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (80, 31, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (81, 32, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (82, 33, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (83, 34, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (84, 35, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (85, 36, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (86, 37, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (87, 38, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (88, 39, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (89, 40, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (90, 41, '_edit_last', '1');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (91, 42, '_edit_lock', '2');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (92, 43, '_wp_page_template', '3');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (93, 44, '_thumbnail_id', '4');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (94, 45, '_yoast_wpseo_title', '5');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (95, 46, '_edit_last', '6');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (96, 47, '_edit_lock', '7');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (97, 48, '_wp_page_template', '8');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (98, 49, '_thumbnail_id', '9');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (99, 50, '_yoast_wpseo_title', '10');
INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES (100, 1, '_edit_last', '1');
INSERT INTO wp_terms (term_id, name, slug) VALUES (1, 'Uncategorized', 'uncategorized');
INSERT INTO wp_terms (term_id, name, slug) VALUES (2, 'Company News', 'company-news');
INSERT INTO wp_terms (term_id, name, slug) VALUES (3, 'Engineering', 'engineering');
INSERT INTO wp_terms (term_id, name, slug) VALUES (4, 'Product Updates', 'product-updates');
INSERT INTO wp_terms (term_id, name, slug) VALUES (5, 'Security', 'security');
INSERT INTO wp_terms (term_id, name, slug) VALUES (6, 'Infrastructure', 'infrastructure');
INSERT INTO wp_terms (term_id, name, slug) VALUES (7, 'HR', 'hr');
INSERT INTO wp_terms (term_id, name, slug) VALUES (8, 'Finance', 'finance');
INSERT INTO wp_terms (term_id, name, slug) VALUES (9, 'Marketing', 'marketing');
INSERT INTO wp_terms (term_id, name, slug) VALUES (10, 'Support', 'support');
INSERT INTO wp_terms (term_id, name, slug) VALUES (11, 'tutorials', 'tutorials');
INSERT INTO wp_terms (term_id, name, slug) VALUES (12, 'announcements', 'announcements');
INSERT INTO wp_terms (term_id, name, slug) VALUES (13, 'internal', 'internal');
INSERT INTO wp_terms (term_id, name, slug) VALUES (14, 'draft', 'draft');
INSERT INTO wp_terms (term_id, name, slug) VALUES (15, 'archived', 'archived');
INSERT INTO wp_terms (term_id, name, slug) VALUES (16, 'featured', 'featured');
INSERT INTO wp_terms (term_id, name, slug) VALUES (17, 'urgent', 'urgent');
INSERT INTO wp_terms (term_id, name, slug) VALUES (18, 'review-needed', 'review-needed');
INSERT INTO wp_terms (term_id, name, slug) VALUES (19, 'approved', 'approved');
INSERT INTO wp_terms (term_id, name, slug) VALUES (20, 'deprecated', 'deprecated');
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (1, 1, 'category', '', 3);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (2, 2, 'category', '', 6);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (3, 3, 'category', '', 9);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (4, 4, 'category', '', 12);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (5, 5, 'category', '', 0);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (6, 6, 'category', '', 3);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (7, 7, 'category', '', 6);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (8, 8, 'category', '', 9);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (9, 9, 'category', '', 12);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (10, 10, 'category', '', 0);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (11, 11, 'post_tag', '', 3);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (12, 12, 'post_tag', '', 6);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (13, 13, 'post_tag', '', 9);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (14, 14, 'post_tag', '', 12);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (15, 15, 'post_tag', '', 0);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (16, 16, 'post_tag', '', 3);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (17, 17, 'post_tag', '', 6);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (18, 18, 'post_tag', '', 9);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (19, 19, 'post_tag', '', 12);
INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES (20, 20, 'post_tag', '', 0);

FLUSH PRIVILEGES;