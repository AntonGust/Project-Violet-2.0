# ABOUTME: Database seed generator for the honeypot fake-database service.
# ABOUTME: Extracts DB config from profiles, generates init SQL with schema
# ABOUTME: and seed data, and writes init scripts for Docker entrypoint.

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import config


def extract_db_config(profile: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract database configuration from a profile.

    Scans services, packages, and file_contents to determine the DB engine,
    spoofed version, credentials, and database names.

    Returns:
        {
            "engine": "mysql" | "postgresql",
            "image": "mysql:8.0" | "postgres:16",
            "spoofed_version": "8.0.36" | "14.11",
            "port": 3306 | 5432,
            "databases": [
                {
                    "name": "wordpress_prod",
                    "users": [
                        {"username": "wp_admin", "password": "...", "host": "%"}
                    ]
                }
            ],
            "root_password": "H0n3yp0t_R00t!",
        }
        or None if no DB service found in profile.
    """
    engine = _detect_engine(profile)
    if engine is None:
        return None

    if engine == "mysql":
        image = config.DB_MYSQL_IMAGE
        port = 3306
        fallback_version = "8.0.36"
    else:
        image = config.DB_POSTGRES_IMAGE
        port = 5432
        fallback_version = "16.3"

    spoofed_version = _extract_spoofed_version(profile, engine, fallback_version)
    databases = _extract_databases(profile, engine)

    return {
        "engine": engine,
        "image": image,
        "spoofed_version": spoofed_version,
        "port": port,
        "databases": databases,
        "root_password": config.DB_ROOT_PASSWORD,
    }


def generate_init_sql(db_config: dict[str, Any], profile: dict[str, Any]) -> str:
    """
    Generate SQL init script with schema and seed data.

    For MySQL: WordPress schema with ~500 rows of fake data.
    For PostgreSQL: Business app schema with users, transactions, audit_log.
    """
    engine = db_config["engine"]
    databases = db_config["databases"]

    if engine == "mysql":
        return _generate_mysql_init(databases, db_config["root_password"])
    else:
        return _generate_postgres_init(databases, db_config["root_password"])


def write_db_init_scripts(
    cowrie_base: Path,
    db_config: dict[str, Any],
    init_sql: str,
) -> None:
    """Write init SQL to cowrie_config/db_init/01_init.sql."""
    init_dir = cowrie_base / "db_init"
    init_dir.mkdir(parents=True, exist_ok=True)

    # Clean old init scripts
    for f in init_dir.iterdir():
        f.unlink()

    (init_dir / "01_init.sql").write_text(init_sql, encoding="utf-8")


# ---------------------------------------------------------------------------
# Engine detection
# ---------------------------------------------------------------------------

def _detect_engine(profile: dict[str, Any]) -> str | None:
    """Detect DB engine from services list."""
    for svc in profile.get("services", []):
        name = svc["name"].lower()
        if any(k in name for k in ("mysql", "mariadb", "mysqld")):
            return "mysql"
        if any(k in name for k in ("postgres", "pgsql", "postgresql")):
            return "postgresql"

    # Fallback: check packages
    for pkg in profile.get("installed_packages", []):
        name = pkg["name"].lower()
        if "mysql" in name or "mariadb" in name:
            return "mysql"
        if "postgres" in name or "pgsql" in name:
            return "postgresql"

    return None


def _extract_spoofed_version(
    profile: dict[str, Any], engine: str, fallback: str
) -> str:
    """Extract the version string to spoof from packages or services."""
    search_terms = (
        ("mysql-server", "mysql", "mariadb") if engine == "mysql"
        else ("postgresql", "postgres")
    )
    for pkg in profile.get("installed_packages", []):
        name = pkg["name"].lower()
        if any(t in name for t in search_terms):
            version = pkg.get("version", "")
            if version:
                # Strip distro suffixes like "-1.rhel7"
                version = re.split(r"[-+~]", version)[0]
                return version
    return fallback


# ---------------------------------------------------------------------------
# Credential extraction
# ---------------------------------------------------------------------------

def _extract_databases(
    profile: dict[str, Any], engine: str
) -> list[dict[str, Any]]:
    """Extract database names and credentials from profile file_contents."""
    databases: dict[str, dict[str, Any]] = {}
    file_contents = profile.get("file_contents", {})

    for path, content in file_contents.items():
        if engine == "mysql":
            _extract_mysql_creds(path, content, databases)
        else:
            _extract_postgres_creds(path, content, databases)

    if not databases:
        # Provide a default database
        if engine == "mysql":
            databases["honeypot_db"] = {
                "name": "honeypot_db",
                "users": [{"username": "admin", "password": "admin123", "host": "%"}],
            }
        else:
            databases["app_production"] = {
                "name": "app_production",
                "users": [{"username": "app_user", "password": "app_pass", "host": "%"}],
            }

    return list(databases.values())


def _extract_mysql_creds(
    path: str, content: str, databases: dict[str, dict[str, Any]]
) -> None:
    """Extract MySQL credentials from wp-config.php, .env, shell scripts."""
    # WordPress wp-config.php
    if "wp-config" in path.lower():
        user_m = re.search(
            r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]", content
        )
        pass_m = re.search(
            r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]", content
        )
        db_m = re.search(
            r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]", content
        )
        if db_m:
            db_name = db_m.group(1)
            db_entry = databases.setdefault(
                db_name, {"name": db_name, "users": []}
            )
            if user_m and pass_m:
                db_entry["users"].append({
                    "username": user_m.group(1),
                    "password": pass_m.group(1),
                    "host": "%",
                })

    # .env files
    if path.endswith(".env"):
        user_m = re.search(r"DB_USER(?:NAME)?=(.+)", content)
        pass_m = re.search(r"DB_PASS(?:WORD)?=(.+)", content)
        db_m = re.search(r"DB_(?:NAME|DATABASE)=(.+)", content)
        if db_m:
            db_name = db_m.group(1).strip()
            db_entry = databases.setdefault(
                db_name, {"name": db_name, "users": []}
            )
            if user_m and pass_m:
                username = user_m.group(1).strip()
                existing = {u["username"] for u in db_entry["users"]}
                if username not in existing:
                    db_entry["users"].append({
                        "username": username,
                        "password": pass_m.group(1).strip(),
                        "host": "%",
                    })

    # Shell scripts with MYSQL_PWD
    if path.endswith(".sh"):
        pwd_m = re.search(r"MYSQL_PWD=['\"]?([^'\";\s]+)", content)
        user_m = re.search(r"-u\s+(\S+)", content)
        if pwd_m and user_m:
            username = user_m.group(1)
            # Associate with first known database or a default
            for db_entry in databases.values():
                existing = {u["username"] for u in db_entry["users"]}
                if username not in existing:
                    db_entry["users"].append({
                        "username": username,
                        "password": pwd_m.group(1),
                        "host": "%",
                    })
                break


def _extract_postgres_creds(
    path: str, content: str, databases: dict[str, dict[str, Any]]
) -> None:
    """Extract PostgreSQL credentials from .pgpass, pgbouncer/userlist.txt, scripts."""
    # .pgpass format: host:port:database:user:password
    if ".pgpass" in path.lower():
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 5:
                db_name = parts[2]
                username = parts[3]
                password = parts[4]
                if db_name == "*":
                    db_name = "postgres"
                db_entry = databases.setdefault(
                    db_name, {"name": db_name, "users": []}
                )
                # Avoid duplicate users
                existing = {u["username"] for u in db_entry["users"]}
                if username not in existing:
                    db_entry["users"].append({
                        "username": username,
                        "password": password,
                        "host": "%",
                    })

    # pgbouncer/userlist.txt format: "user" "password"
    if "userlist.txt" in path.lower():
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'"([^"]+)"\s+"([^"]+)"', line)
            if m:
                username, password = m.group(1), m.group(2)
                # Add to postgres default db
                db_entry = databases.setdefault(
                    "postgres", {"name": "postgres", "users": []}
                )
                existing = {u["username"] for u in db_entry["users"]}
                if username not in existing:
                    db_entry["users"].append({
                        "username": username,
                        "password": password,
                        "host": "%",
                    })

    # Shell scripts with PGPASSWORD
    if path.endswith(".sh"):
        pwd_m = re.search(r"PGPASSWORD=['\"]?([^'\";\s]+)", content)
        user_m = re.search(r"-U\s+(\S+)", content)
        if pwd_m and user_m:
            db_entry = databases.setdefault(
                "postgres", {"name": "postgres", "users": []}
            )
            existing = {u["username"] for u in db_entry["users"]}
            username = user_m.group(1)
            if username not in existing:
                db_entry["users"].append({
                    "username": username,
                    "password": pwd_m.group(1),
                    "host": "%",
                })


# ---------------------------------------------------------------------------
# MySQL init SQL generation (WordPress schema)
# ---------------------------------------------------------------------------

def _generate_mysql_init(
    databases: list[dict[str, Any]], root_password: str
) -> str:
    """Generate MySQL init SQL with WordPress schema and seed data."""
    lines: list[str] = [
        "-- Auto-generated honeypot database init script",
        f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{root_password}';",
        f"ALTER USER 'root'@'%' IDENTIFIED BY '{root_password}';",
        "",
    ]

    for db in databases:
        db_name = db["name"]
        lines.append(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
        for user in db.get("users", []):
            lines.append(
                f"CREATE USER IF NOT EXISTS '{user['username']}'@'{user['host']}' "
                f"IDENTIFIED BY '{user['password']}';"
            )
            lines.append(
                f"GRANT ALL PRIVILEGES ON `{db_name}`.* "
                f"TO '{user['username']}'@'{user['host']}';"
            )
        lines.append(f"USE `{db_name}`;")
        lines.append("")
        lines.append(_wordpress_schema())
        lines.append(_wordpress_seed_data(db_name))
        lines.append("")

    lines.append("FLUSH PRIVILEGES;")
    return "\n".join(lines)


def _wordpress_schema() -> str:
    """Return WordPress core table schema."""
    return """
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
"""


def _wordpress_seed_data(db_name: str) -> str:
    """Generate deterministic WordPress seed data (~500 rows)."""
    lines: list[str] = []

    # wp_users (10 rows)
    users = [
        (1, "admin", "admin@wp-prod-01.internal.corp", "Admin User", "2024-01-15 10:23:00"),
        (2, "editor", "sarah.chen@company.com", "Sarah Chen", "2024-02-01 08:45:00"),
        (3, "author1", "mike.johnson@company.com", "Mike Johnson", "2024-02-15 14:30:00"),
        (4, "author2", "jessica.williams@company.com", "Jessica Williams", "2024-03-01 09:15:00"),
        (5, "contributor", "david.brown@company.com", "David Brown", "2024-03-10 11:00:00"),
        (6, "subscriber1", "emily.davis@gmail.com", "Emily Davis", "2024-04-01 16:20:00"),
        (7, "subscriber2", "james.wilson@outlook.com", "James Wilson", "2024-04-15 13:45:00"),
        (8, "subscriber3", "lisa.garcia@yahoo.com", "Lisa Garcia", "2024-05-01 10:30:00"),
        (9, "seo_manager", "alex.martinez@company.com", "Alex Martinez", "2024-05-15 08:00:00"),
        (10, "backup_admin", "ops@company.com", "Ops Account", "2024-01-15 10:25:00"),
    ]
    for uid, login, email, display, reg in users:
        lines.append(
            f"INSERT INTO wp_users (ID, user_login, user_pass, user_nicename, user_email, "
            f"user_registered, display_name) VALUES "
            f"({uid}, '{login}', '$P$Babcdefghijklmnopqrstuv0123456.', '{login}', "
            f"'{email}', '{reg}', '{display}');"
        )

    # wp_usermeta (50 rows - 5 per user)
    roles = {1: "administrator", 2: "editor", 3: "author", 4: "author",
             5: "contributor", 6: "subscriber", 7: "subscriber", 8: "subscriber",
             9: "editor", 10: "administrator"}
    for uid in range(1, 11):
        role = roles[uid]
        meta_id = (uid - 1) * 5 + 1
        lines.append(
            f"INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES "
            f"({meta_id}, {uid}, 'wp_capabilities', 'a:1:{{s:{len(role)}:\"{role}\";b:1;}}');"
        )
        lines.append(
            f"INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES "
            f"({meta_id+1}, {uid}, 'wp_user_level', "
            f"'{10 if role == 'administrator' else 7 if role == 'editor' else 2 if role == 'author' else 1 if role == 'contributor' else 0}');"
        )
        lines.append(
            f"INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES "
            f"({meta_id+2}, {uid}, 'nickname', '{users[uid-1][1]}');"
        )
        lines.append(
            f"INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES "
            f"({meta_id+3}, {uid}, 'first_name', '{users[uid-1][3].split()[0]}');"
        )
        lines.append(
            f"INSERT INTO wp_usermeta (umeta_id, user_id, meta_key, meta_value) VALUES "
            f"({meta_id+4}, {uid}, 'last_name', '{users[uid-1][3].split()[-1]}');"
        )

    # wp_posts (50 rows)
    post_titles = [
        "Hello World", "About Us", "Contact", "Privacy Policy", "Terms of Service",
        "Q3 2024 Revenue Growth", "New Product Launch Update", "Engineering Blog: Kubernetes Migration",
        "Company Culture: Remote Work Policy", "Customer Success Story: Acme Corp",
        "Security Best Practices for 2024", "API Documentation v2.1", "Release Notes 6.4.2",
        "Infrastructure Upgrade Notice", "Monthly Newsletter: January",
        "Team Spotlight: Engineering", "Case Study: Financial Services", "Webinar Recap: Cloud Security",
        "Product Roadmap 2025", "Board Meeting Minutes Q4",
        "Draft: Marketing Campaign Spring", "Draft: Technical Architecture Review",
        "Investor Relations Update", "Employee Handbook v3", "IT Support Guide",
        "Onboarding Checklist", "Compliance Audit Report", "Data Retention Policy",
        "Backup and Recovery Procedures", "Incident Response Playbook",
        "Vendor Assessment: AWS vs GCP", "Budget Proposal 2025", "Risk Assessment Q4",
        "Performance Review Template", "Travel Policy Update",
        "Office Relocation FAQ", "Health Benefits Overview", "Stock Option Plan Details",
        "Quarterly Business Review", "Customer Feedback Analysis",
        "SEO Strategy Document", "Content Calendar Q1 2025", "Social Media Metrics",
        "Email Campaign Results", "Brand Guidelines v2",
        "Partner Program Details", "Reseller Agreement Template", "Support SLA Document",
        "Training Materials: Sales", "Knowledge Base: FAQ",
    ]
    for i, title in enumerate(post_titles, 1):
        author = (i % 5) + 1
        status = "publish" if i <= 30 else "draft" if i <= 40 else "private"
        post_type = "page" if i <= 5 else "post"
        date = f"2024-{((i-1)//5 % 12)+1:02d}-{(i % 28)+1:02d} {(9+i%8):02d}:00:00"
        slug = title.lower().replace(" ", "-").replace(":", "").replace(",", "")[:50]
        lines.append(
            f"INSERT INTO wp_posts (ID, post_author, post_date, post_content, post_title, "
            f"post_excerpt, post_status, post_name, post_type) VALUES "
            f"({i}, {author}, '{date}', 'Content for {title}...', '{title}', '', "
            f"'{status}', '{slug}', '{post_type}');"
        )

    # wp_comments (100 rows)
    comment_authors = [
        "John Smith", "Jane Doe", "Bob Wilson", "Alice Brown", "Charlie Davis",
        "Diana Miller", "Edward Jones", "Fiona Taylor", "George Martin", "Helen White",
    ]
    for i in range(1, 101):
        post_id = (i % 30) + 6  # Comments on posts 6-35
        author = comment_authors[i % 10]
        email = f"{author.lower().replace(' ', '.')}@example.com"
        date = f"2024-{((i-1)//10 % 12)+1:02d}-{(i % 28)+1:02d} {(10+i%12):02d}:{i%60:02d}:00"
        lines.append(
            f"INSERT INTO wp_comments (comment_ID, comment_post_ID, comment_author, "
            f"comment_author_email, comment_date, comment_content, comment_approved, user_id) VALUES "
            f"({i}, {post_id}, '{author}', '{email}', '{date}', "
            f"'Comment #{i} on this post.', '1', 0);"
        )

    # wp_options (200 rows)
    core_options = [
        ("siteurl", f"https://wp-prod-01.internal.corp"),
        ("home", f"https://wp-prod-01.internal.corp"),
        ("blogname", "Company Internal Portal"),
        ("blogdescription", "Internal documentation and resources"),
        ("admin_email", "admin@wp-prod-01.internal.corp"),
        ("users_can_register", "0"),
        ("default_role", "subscriber"),
        ("timezone_string", "UTC"),
        ("date_format", "Y-m-d"),
        ("time_format", "H:i"),
        ("start_of_week", "1"),
        ("permalink_structure", "/%postname%/"),
        ("template", "developer-starter"),
        ("stylesheet", "developer-starter"),
        ("active_plugins", 'a:5:{i:0;s:30:"advanced-custom-fields/acf.php";i:1;s:33:"classic-editor/classic-editor.php";i:2;s:24:"wordpress-seo/wp-seo.php";i:3;s:27:"wp-mail-smtp/wp_mail_smtp.php";i:4;s:43:"updraftplus/updraftplus.php";}'),
        ("db_version", "57155"),
        ("wp_version", "6.4.2"),
    ]
    for i, (name, value) in enumerate(core_options, 1):
        value_escaped = value.replace("'", "\\'")
        lines.append(
            f"INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES "
            f"({i}, '{name}', '{value_escaped}', 'yes');"
        )
    # Fill remaining options with realistic WordPress options
    extra_options = [
        "widget_pages", "widget_calendar", "widget_media_audio", "widget_media_image",
        "widget_media_gallery", "widget_media_video", "widget_meta", "widget_search",
        "widget_text", "widget_categories", "widget_recent-posts", "widget_recent-comments",
        "widget_rss", "widget_tag_cloud", "widget_nav_menu", "widget_custom_html",
        "sidebars_widgets", "cron", "theme_mods_developer-starter",
    ]
    for i, name in enumerate(extra_options, len(core_options) + 1):
        lines.append(
            f"INSERT INTO wp_options (option_id, option_name, option_value, autoload) VALUES "
            f"({i}, '{name}', 'a:0:{{}}', 'yes');"
        )

    # wp_postmeta (100 rows)
    for i in range(1, 101):
        post_id = (i % 50) + 1
        meta_key = ["_edit_last", "_edit_lock", "_wp_page_template", "_thumbnail_id", "_yoast_wpseo_title"][i % 5]
        meta_value = str(i % 10 + 1)
        lines.append(
            f"INSERT INTO wp_postmeta (meta_id, post_id, meta_key, meta_value) VALUES "
            f"({i}, {post_id}, '{meta_key}', '{meta_value}');"
        )

    # wp_terms (20 rows)
    terms = [
        "Uncategorized", "Company News", "Engineering", "Product Updates", "Security",
        "Infrastructure", "HR", "Finance", "Marketing", "Support",
        "tutorials", "announcements", "internal", "draft", "archived",
        "featured", "urgent", "review-needed", "approved", "deprecated",
    ]
    for i, term in enumerate(terms, 1):
        slug = term.lower().replace(" ", "-")
        lines.append(
            f"INSERT INTO wp_terms (term_id, name, slug) VALUES ({i}, '{term}', '{slug}');"
        )

    # wp_term_taxonomy
    for i in range(1, 21):
        taxonomy = "category" if i <= 10 else "post_tag"
        lines.append(
            f"INSERT INTO wp_term_taxonomy (term_taxonomy_id, term_id, taxonomy, description, count) VALUES "
            f"({i}, {i}, '{taxonomy}', '', {(i * 3) % 15});"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PostgreSQL init SQL generation (business app schema)
# ---------------------------------------------------------------------------

def _generate_postgres_init(
    databases: list[dict[str, Any]], root_password: str
) -> str:
    """Generate PostgreSQL init SQL with business app schema and seed data."""
    lines: list[str] = [
        "-- Auto-generated honeypot database init script",
        f"ALTER USER postgres WITH PASSWORD '{root_password}';",
        "",
    ]

    # Create roles first
    created_users: set[str] = set()
    for db in databases:
        for user in db.get("users", []):
            username = user["username"]
            if username not in created_users and username != "postgres":
                lines.append(
                    f"CREATE ROLE {username} WITH LOGIN PASSWORD '{user['password']}';"
                )
                created_users.add(username)

    lines.append("")

    for db in databases:
        db_name = db["name"]
        if db_name == "postgres":
            # Use the default postgres database
            lines.append(f"-- Seeding default postgres database")
        else:
            lines.append(f"CREATE DATABASE {db_name};")
            lines.append(f"\\connect {db_name}")

        for user in db.get("users", []):
            if user["username"] != "postgres":
                lines.append(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user['username']};")

        lines.append("")
        lines.append(_postgres_schema())
        lines.append(_postgres_seed_data())
        lines.append("")

        # Grant table-level permissions
        for user in db.get("users", []):
            if user["username"] != "postgres":
                lines.append(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {user['username']};")
                lines.append(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {user['username']};")

        lines.append("")

    return "\n".join(lines)


def _postgres_schema() -> str:
    """Return business application schema for PostgreSQL."""
    return """
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
"""


def _postgres_seed_data() -> str:
    """Generate deterministic PostgreSQL seed data (~415 rows)."""
    lines: list[str] = []

    # users (25 rows)
    pg_users = [
        ("admin", "admin@corp.internal", "admin", "IT", True),
        ("jsmith", "john.smith@corp.internal", "manager", "Finance", True),
        ("alee", "alice.lee@corp.internal", "analyst", "Finance", True),
        ("bwilson", "bob.wilson@corp.internal", "developer", "Engineering", True),
        ("cmartinez", "carol.martinez@corp.internal", "developer", "Engineering", True),
        ("dchen", "david.chen@corp.internal", "lead", "Engineering", True),
        ("ejohnson", "emma.johnson@corp.internal", "analyst", "HR", True),
        ("fgarcia", "frank.garcia@corp.internal", "manager", "Operations", True),
        ("gwhite", "grace.white@corp.internal", "developer", "Engineering", True),
        ("hbrown", "henry.brown@corp.internal", "analyst", "Marketing", True),
        ("itaylor", "iris.taylor@corp.internal", "developer", "Engineering", True),
        ("jdavis", "jack.davis@corp.internal", "sysadmin", "IT", True),
        ("kmoore", "karen.moore@corp.internal", "manager", "Sales", True),
        ("lthompson", "larry.thompson@corp.internal", "analyst", "Finance", True),
        ("manderson", "maria.anderson@corp.internal", "developer", "Engineering", True),
        ("nclark", "nick.clark@corp.internal", "intern", "Engineering", False),
        ("owright", "olivia.wright@corp.internal", "analyst", "Operations", True),
        ("pyoung", "peter.young@corp.internal", "developer", "Engineering", True),
        ("qhall", "quinn.hall@corp.internal", "manager", "IT", True),
        ("rking", "rachel.king@corp.internal", "analyst", "Marketing", True),
        ("sgreen", "scott.green@corp.internal", "developer", "Engineering", True),
        ("tadams", "tina.adams@corp.internal", "admin", "IT", True),
        ("ubaker", "ursula.baker@corp.internal", "analyst", "HR", True),
        ("vcarter", "victor.carter@corp.internal", "developer", "Engineering", True),
        ("service_account", "svc@corp.internal", "service", "IT", True),
    ]
    for i, (uname, email, role, dept, active) in enumerate(pg_users, 1):
        lines.append(
            f"INSERT INTO users (id, username, email, password_hash, role, department, "
            f"created_at, is_active) VALUES "
            f"({i}, '{uname}', '{email}', '$2b$12$fakehash{i:04d}', '{role}', '{dept}', "
            f"'2024-{(i % 12)+1:02d}-{(i % 28)+1:02d} 09:00:00', {str(active).lower()});"
        )

    lines.append("SELECT setval('users_id_seq', 25);")

    # transactions (200 rows)
    for i in range(1, 201):
        user_id = (i % 20) + 1
        amount = round(50 + (i * 7.37) % 9950, 2)
        status = "completed" if i % 10 != 0 else "pending" if i % 20 != 0 else "failed"
        ref_id = f"TXN-2024-{i:06d}"
        month = ((i - 1) // 20 % 12) + 1
        day = (i % 28) + 1
        lines.append(
            f"INSERT INTO transactions (id, user_id, amount, currency, description, status, "
            f"reference_id, created_at) VALUES "
            f"({i}, {user_id}, {amount}, 'USD', 'Transaction {ref_id}', '{status}', "
            f"'{ref_id}', '2024-{month:02d}-{day:02d} {(8+i%10):02d}:{i%60:02d}:00');"
        )
    lines.append("SELECT setval('transactions_id_seq', 200);")

    # audit_log (100 rows)
    actions = ["login", "logout", "view_report", "export_data", "update_record",
               "create_user", "delete_record", "change_password", "api_call", "config_change"]
    for i in range(1, 101):
        user_id = (i % 25) + 1
        action = actions[i % 10]
        ip_third = 10 + (i % 5)
        ip_fourth = 100 + (i % 155)
        month = ((i - 1) // 10 % 12) + 1
        day = (i % 28) + 1
        lines.append(
            f"INSERT INTO audit_log (id, user_id, action, resource, ip_address, created_at) VALUES "
            f"({i}, {user_id}, '{action}', '/api/v1/{action}', '10.0.{ip_third}.{ip_fourth}', "
            f"'2024-{month:02d}-{day:02d} {(8+i%14):02d}:{i%60:02d}:00');"
        )
    lines.append("SELECT setval('audit_log_id_seq', 100);")

    # sessions (50 rows)
    for i in range(1, 51):
        user_id = (i % 25) + 1
        token = f"sess_{i:04d}_{'abcdef1234567890'[i%16:i%16+8]}"
        ip_fourth = 100 + (i % 155)
        lines.append(
            f"INSERT INTO sessions (id, user_id, token, ip_address, created_at, expires_at) VALUES "
            f"({i}, {user_id}, '{token}', '10.0.3.{ip_fourth}', "
            f"'2024-12-{(i%28)+1:02d} {(8+i%14):02d}:00:00', "
            f"'2025-01-{(i%28)+1:02d} {(8+i%14):02d}:00:00');"
        )
    lines.append("SELECT setval('sessions_id_seq', 50);")

    # api_keys (10 rows)
    for i in range(1, 11):
        user_id = [1, 12, 19, 22, 25, 6, 4, 9, 13, 8][i - 1]
        name = ["Production API", "Monitoring", "CI/CD Pipeline", "Admin Tools",
                "Service Integration", "Engineering API", "Dev Testing",
                "Analytics", "Sales Dashboard", "Marketing API"][i - 1]
        lines.append(
            f"INSERT INTO api_keys (id, user_id, key_hash, name, is_active) VALUES "
            f"({i}, {user_id}, '$2b$12$apikeyhash{i:04d}', '{name}', true);"
        )
    lines.append("SELECT setval('api_keys_id_seq', 10);")

    # config (30 rows)
    configs = [
        ("app.name", "Corp Internal Platform"),
        ("app.version", "2.4.1"),
        ("app.debug", "false"),
        ("app.timezone", "UTC"),
        ("auth.session_timeout", "3600"),
        ("auth.max_attempts", "5"),
        ("auth.lockout_duration", "300"),
        ("auth.mfa_required", "true"),
        ("db.pool_size", "20"),
        ("db.max_overflow", "10"),
        ("cache.backend", "redis"),
        ("cache.ttl", "300"),
        ("email.smtp_host", "smtp.corp.internal"),
        ("email.smtp_port", "587"),
        ("email.from_address", "noreply@corp.internal"),
        ("storage.backend", "s3"),
        ("storage.bucket", "corp-app-data"),
        ("storage.region", "us-east-1"),
        ("logging.level", "INFO"),
        ("logging.sentry_dsn", "https://key@sentry.corp.internal/1"),
        ("api.rate_limit", "1000"),
        ("api.key_rotation_days", "90"),
        ("security.cors_origins", "https://app.corp.internal"),
        ("security.csp_policy", "default-src self"),
        ("backup.schedule", "0 2 * * *"),
        ("backup.retention_days", "30"),
        ("monitoring.endpoint", "https://prometheus.corp.internal"),
        ("monitoring.interval", "60"),
        ("feature.new_dashboard", "true"),
        ("feature.beta_api_v3", "false"),
    ]
    for i, (key, value) in enumerate(configs, 1):
        lines.append(
            f"INSERT INTO config (id, key, value, updated_at) VALUES "
            f"({i}, '{key}', '{value}', '2024-12-01 00:00:00');"
        )
    lines.append("SELECT setval('config_id_seq', 30);")

    return "\n".join(lines)
