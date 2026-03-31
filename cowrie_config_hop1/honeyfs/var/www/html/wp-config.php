<?php
define('DB_NAME', 'wordpress_prod');
define('DB_USER', 'wp_admin');
define('DB_PASSWORD', 'Str0ng_But_Le4ked!');
define('DB_HOST', 'localhost');
define('DB_CHARSET', 'utf8mb4');
$table_prefix = 'wp_';
define('AUTH_KEY', 'put your unique phrase here');
define('SECURE_AUTH_KEY', 'put your unique phrase here');
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
if ( ! defined('ABSPATH') ) {
    define('ABSPATH', __DIR__ . '/');
}
require_once ABSPATH . 'wp-settings.php';