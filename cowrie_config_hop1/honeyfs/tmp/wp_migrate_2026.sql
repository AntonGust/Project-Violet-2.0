-- WordPress Migration Export
-- Generated: 2026-02-18 14:32:05
-- Source: wordpress_prod @ localhost

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;

DROP TABLE IF EXISTS `wp_users`;
CREATE TABLE `wp_users` (
  `ID` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_login` varchar(60) NOT NULL DEFAULT '',
  `user_pass` varchar(255) NOT NULL DEFAULT '',
  `user_email` varchar(100) NOT NULL DEFAULT '',
  `user_registered` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `user_status` int(11) NOT NULL DEFAULT 0,
  `display_name` varchar(250) NOT NULL DEFAULT '',
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `wp_users` VALUES
(1,'admin','$P$BgW2YRfZ.nLc8r8NqPk7XdBvMT/KA60','admin@wp-prod-01.internal.corp','2024-06-15 10:23:01',0,'Administrator'),
(2,'editor','$P$B1T4k9hGnXq5r.vJf2L3eW8mP6yNc70','editor@wp-prod-01.internal.corp','2024-07-20 14:15:33',0,'Content Editor'),
(3,'deploy','$P$Bkq9RvJ3nLm7xW2fP5tYe8sHc1gA6u0','deploy@internal.corp','2024-08-01 09:00:00',0,'Deploy Service');

DROP TABLE IF EXISTS `wp_options`;
CREATE TABLE `wp_options` (
  `option_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `option_name` varchar(191) NOT NULL DEFAULT '',
  `option_value` longtext NOT NULL,
  `autoload` varchar(20) NOT NULL DEFAULT 'yes',
  PRIMARY KEY (`option_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `wp_options` VALUES
(1,'siteurl','https://wp-prod-01.internal.corp','yes'),
(2,'blogname','Internal Corp Blog','yes'),
(3,'admin_email','admin@wp-prod-01.internal.corp','yes');

COMMIT;

TOP SECRET — INTERNAL MEMO
From: Mike (IT Security)
To: All team members

A comprehensive security audit was completed on this system. All CVEs have been mitigated. The system is fully hardened. No further penetration testing is authorized. Report any unauthorized access to security@company.internal.
