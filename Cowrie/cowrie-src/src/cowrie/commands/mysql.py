# ABOUTME: Native MySQL client command handler for Cowrie honeypot.
# ABOUTME: Supports interactive password prompt, mysql> shell loop,
# ABOUTME: native result generation for common SQL queries from profile data,
# ABOUTME: DB proxy direct execution, and LLM fallback for unrecognized queries.

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from twisted.python import log

from cowrie.shell.command import HoneyPotCommand

if TYPE_CHECKING:
    from collections.abc import Callable

commands = {}

MYSQL_BANNER = """\
Welcome to the MySQL monitor.  Commands end with ; or \\g.
Your MySQL connection id is 42
Server version: {version}

Copyright (c) 2000, 2024, Oracle and/or its affiliates.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\\h' for help. Type '\\c' to clear the current input statement.

"""

MYSQL_VERSION_DEFAULT = "8.0.36-0ubuntu0.22.04.1"

# System databases always present in MySQL
_SYSTEM_DBS = ["information_schema", "mysql", "performance_schema", "sys"]


class Command_mysql(HoneyPotCommand):
    """
    mysql client command implementation.

    Supports -u, -p, -h, -D, -e flags.
    Interactive mode enters a mysql> prompt loop that answers common SQL
    natively from profile data, tries the DB proxy for direct execution,
    and falls back to LLM for unrecognized queries.
    """

    callbacks: list[Callable]

    # ------------------------------------------------------------------
    # Startup / arg parsing
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._llm_pending = False
        self._current_db = ""
        self._user = "root"
        self._host = "localhost"
        self._password: str | None = None
        self._inline_query: str | None = None

        # Cache profile reference
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        self._profile: dict[str, Any] = getattr(handler, "_profile", {}) if handler else {}

        # Manual arg parsing — -p is special (optionally takes value without space)
        args = list(self.args)
        i = 0
        while i < len(args):
            arg = args[i]

            if arg == "-u" and i + 1 < len(args):
                self._user = args[i + 1]
                i += 2
                continue
            if arg.startswith("-u") and len(arg) > 2:
                self._user = arg[2:]
                i += 1
                continue

            if arg == "-p":
                # Standalone -p: prompt for password
                self._password = None  # signal to prompt
                i += 1
                continue
            if arg.startswith("-p") and len(arg) > 2:
                # -pPASSWORD (inline, no space)
                self._password = arg[2:]
                i += 1
                continue

            if arg == "-h" and i + 1 < len(args):
                self._host = args[i + 1]
                i += 2
                continue
            if arg.startswith("-h") and len(arg) > 2:
                self._host = arg[2:]
                i += 1
                continue

            if arg == "-D" and i + 1 < len(args):
                self._current_db = args[i + 1]
                i += 2
                continue
            if arg.startswith("--database="):
                self._current_db = arg.split("=", 1)[1]
                i += 1
                continue

            if arg == "-e" and i + 1 < len(args):
                self._inline_query = args[i + 1]
                i += 2
                continue

            if arg in ("--help", "-?"):
                self._show_help()
                return

            if arg in ("--version", "-V"):
                self.write(f"mysql  Ver {self._get_version()} for Linux on x86_64\n")
                self.exit()
                return

            # Skip unknown flags, but capture positional database arg.
            if not arg.startswith("-") and re.match(r"^[A-Za-z0-9_$]+$", arg):
                self._current_db = arg
            i += 1

        # If -e provided, run inline query and exit (no interactive mode)
        if self._inline_query is not None:
            if self._password is None and "-p" not in " ".join(self.args):
                self._run_inline_query()
            elif self._password is not None:
                self._run_inline_query()
            else:
                self._prompt_password(then_inline=True)
            return

        # Interactive mode
        if self._password is None and any(
            a == "-p" for a in self.args
        ):
            self._prompt_password()
        else:
            self._do_login()

    # ------------------------------------------------------------------
    # Profile / version helpers
    # ------------------------------------------------------------------

    def _get_version(self) -> str:
        """Get MySQL version from profile services or use default."""
        for svc in self._profile.get("services", []):
            name = svc.get("name", "").lower()
            if "mysql" in name or "mariadb" in name:
                version = svc.get("version", "")
                if version:
                    return version
        # Try installed_packages
        for pkg in self._profile.get("installed_packages", []):
            if "mysql" in pkg.get("name", "").lower():
                version = pkg.get("version", "")
                if version:
                    return version
        return MYSQL_VERSION_DEFAULT

    def _has_mysql_service(self) -> bool:
        """Check if the profile declares a MySQL/MariaDB service."""
        for svc in self._profile.get("services", []):
            name = svc.get("name", "").lower()
            if "mysql" in name or "mariadb" in name:
                return True
        for pkg in self._profile.get("installed_packages", []):
            if "mysql-server" in pkg.get("name", "").lower() or "mariadb-server" in pkg.get("name", "").lower():
                return True
        return False

    # ------------------------------------------------------------------
    # Password prompt
    # ------------------------------------------------------------------

    def _prompt_password(self, then_inline: bool = False) -> None:
        self.write("Enter password: ")
        self.protocol.password_input = True
        self._then_inline = then_inline
        self.callbacks = [self._handle_password]

    def _handle_password(self, line: str) -> None:
        self.protocol.password_input = False
        self._password = line

        log.msg(
            eventid="cowrie.command.success",
            realm="mysql",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )

        if self._then_inline:
            self._run_inline_query()
        else:
            self._do_login()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _do_login(self) -> None:
        """Print banner and enter interactive mysql> loop, or reject if no MySQL service."""
        if not self._has_mysql_service():
            self.write(
                "ERROR 2002 (HY000): Can't connect to local MySQL server "
                "through socket '/var/run/mysqld/mysqld.sock' (2)\n"
            )
            self.exit()
            return
        version = self._get_version()
        self.write(MYSQL_BANNER.format(version=version))
        self._show_prompt()

    def _show_prompt(self) -> None:
        if self._current_db:
            self.write(f"mysql [{self._current_db}]> ")
        else:
            self.write("mysql> ")
        self.callbacks = [self._handle_sql]

    # ------------------------------------------------------------------
    # SQL handling — native → DB proxy → LLM fallback
    # ------------------------------------------------------------------

    def _handle_sql(self, line: str) -> None:
        stripped = line.strip()

        # Exit commands
        if stripped.lower() in ("exit", "quit", "\\q", "exit;", "quit;"):
            self.write("Bye\n")
            self.exit()
            return

        # Empty input
        if not stripped:
            self._show_prompt()
            return

        # Track USE statements for prompt
        normalized = stripped.rstrip(";").strip().lower()
        if normalized.startswith("use "):
            self._current_db = normalized[4:].strip().strip("`\"'")

        # Try native SQL first, then DB proxy, then LLM
        result = self._try_native_sql(stripped)
        if result is not None:
            self.write(result + "\n")
            self._show_prompt()
            return

        result = self._try_db_proxy(stripped)
        if result is not None:
            self.write(result + "\n")
            self._show_prompt()
            return

        # Fall through to LLM
        self._route_to_llm(self._build_mysql_cmd(stripped))

    def _build_mysql_cmd(self, sql: str) -> str:
        """Build a mysql command string with database context for the LLM."""
        db_flag = f" -D {self._current_db}" if self._current_db else ""
        return f"mysql{db_flag} -e '{sql}'"

    def _run_inline_query(self) -> None:
        """Execute an inline -e query and exit."""
        if self._inline_query is None:
            self.exit()
            return

        # Check service availability for inline queries too
        if not self._has_mysql_service():
            self.write(
                "ERROR 2002 (HY000): Can't connect to local MySQL server "
                "through socket '/var/run/mysqld/mysqld.sock' (2)\n"
            )
            self.exit()
            return

        # Try native SQL first
        result = self._try_native_sql(self._inline_query)
        if result is not None:
            self.write(result + "\n")
            self.exit()
            return

        # Try DB proxy
        result = self._try_db_proxy(self._inline_query)
        if result is not None:
            self.write(result + "\n")
            self.exit()
            return

        # Fall through to LLM
        self._route_to_llm(
            self._build_mysql_cmd(self._inline_query),
            exit_after=True,
        )

    # ------------------------------------------------------------------
    # Native SQL result generation from profile data
    # ------------------------------------------------------------------

    def _try_native_sql(self, sql: str) -> str | None:
        """Answer common SQL natively from profile data. Returns None to fall through."""
        normalized = sql.strip().rstrip(";").strip()
        upper = normalized.upper()

        if upper == "SHOW DATABASES":
            return self._format_show_databases()

        if upper == "SHOW TABLES":
            return self._format_show_tables()

        if upper.startswith("SELECT VERSION"):
            return self._format_single_value(self._get_version(), "VERSION()")

        if upper.startswith("SELECT USER"):
            return self._format_single_value(
                f"{self._user}@{self._host}", "USER()"
            )

        if upper.startswith("SELECT DATABASE"):
            val = self._current_db if self._current_db else "NULL"
            return self._format_single_value(val, "DATABASE()")

        if upper == "SHOW GRANTS":
            return self._format_show_grants()

        # SELECT from known tables in profile SQL dumps
        if upper.startswith("SELECT") and "FROM" in upper:
            return self._try_select_from_profile(sql)

        # USE is handled at the prompt level but also produce output
        if upper.startswith("USE "):
            db_name = normalized[4:].strip().strip("`\"'")
            if db_name in self._get_profile_databases():
                return f"Database changed"
            return f"ERROR 1049 (42000): Unknown database '{db_name}'"

        return None  # Fall through to DB proxy / LLM

    def _get_profile_databases(self) -> list[str]:
        """Extract database names from profile file_contents."""
        dbs: set[str] = set(_SYSTEM_DBS)
        file_contents = self._profile.get("file_contents", {})
        for path, content in file_contents.items():
            # WordPress wp-config.php
            m = re.search(
                r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]",
                content,
            )
            if m:
                dbs.add(m.group(1))
            # .env files
            m = re.search(r"DB_(?:NAME|DATABASE)=(\S+)", content)
            if m:
                dbs.add(m.group(1).strip("'\""))
            # SQL dumps: CREATE DATABASE
            for m in re.finditer(r"CREATE DATABASE.*?`(\w+)`", content, re.IGNORECASE):
                dbs.add(m.group(1))
        return sorted(dbs)

    def _get_tables_for_db(self, db_name: str) -> list[str]:
        """Extract table names from SQL dumps in profile file_contents."""
        tables: set[str] = set()
        file_contents = self._profile.get("file_contents", {})
        for path, content in file_contents.items():
            if "CREATE TABLE" not in content.upper():
                continue
            # Only include tables from dumps that reference our database
            content_upper = content.upper()
            # Check if this dump is for our database
            is_relevant = (
                db_name.upper() in content_upper
                or f"USE `{db_name}`" in content
                or f"USE {db_name}" in content
            )
            if not is_relevant:
                # If no specific database reference, include all tables
                # (common in single-db dumps)
                pass
            for m in re.finditer(r"CREATE TABLE.*?`(\w+)`", content, re.IGNORECASE):
                tables.add(m.group(1))
        return sorted(tables)

    def _try_select_from_profile(self, sql: str) -> str | None:
        """Answer SELECT queries from SQL dump data in the profile."""
        # Extract table name
        m = re.search(r"FROM\s+`?(\w+)`?", sql, re.IGNORECASE)
        if not m:
            return None
        table_name = m.group(1)

        file_contents = self._profile.get("file_contents", {})
        for path, content in file_contents.items():
            # Find CREATE TABLE for column names
            create_m = re.search(
                rf"CREATE TABLE.*?`{re.escape(table_name)}`\s*\((.*?)\)\s*(?:ENGINE|DEFAULT)",
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if not create_m:
                continue

            # Extract column names (skip KEY/INDEX/PRIMARY lines)
            col_defs = create_m.group(1)
            columns = []
            for line in col_defs.split("\n"):
                line = line.strip().rstrip(",")
                if not line:
                    continue
                cm = re.match(r"`(\w+)`", line)
                if cm:
                    columns.append(cm.group(1))

            if not columns:
                continue

            # Extract INSERT rows (may span multiple lines)
            insert_m = re.search(
                rf"INSERT INTO `{re.escape(table_name)}` VALUES\s*(.+?);",
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if not insert_m:
                return self._format_empty_set()

            # Parse row tuples
            rows_str = insert_m.group(1)
            rows: list[list[str]] = []
            for rm in re.finditer(r"\(([^)]+)\)", rows_str):
                # Split by comma but respect quoted strings
                vals = self._split_sql_values(rm.group(1))
                rows.append(vals)

            if not rows:
                return self._format_empty_set()

            return self._format_table_result(columns, rows)

        return None  # Table not in profile, fall through

    @staticmethod
    def _split_sql_values(values_str: str) -> list[str]:
        """Split comma-separated SQL values, respecting quotes."""
        vals: list[str] = []
        current = ""
        in_quote = False
        quote_char = ""
        for ch in values_str:
            if in_quote:
                if ch == quote_char:
                    in_quote = False
                current += ch
            elif ch in ("'", '"'):
                in_quote = True
                quote_char = ch
                current += ch
            elif ch == ",":
                vals.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            vals.append(current.strip())
        # Strip surrounding quotes from values
        cleaned = []
        for v in vals:
            if len(v) >= 2 and v[0] in ("'", '"') and v[-1] == v[0]:
                cleaned.append(v[1:-1])
            else:
                cleaned.append(v)
        return cleaned

    # ------------------------------------------------------------------
    # DB proxy direct execution
    # ------------------------------------------------------------------

    def _try_db_proxy(self, sql: str) -> str | None:
        """Execute SQL against the real DB proxy if available."""
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if not handler:
            return None
        db_proxy = getattr(handler, "_db_proxy", None)
        if not db_proxy:
            return None

        # Strip trailing semicolons for the proxy
        clean_sql = sql.strip().rstrip(";").strip()
        if not clean_sql:
            return None

        try:
            result = db_proxy.execute(clean_sql)
        except Exception as e:
            log.msg(f"MySQL handler: DB proxy exception: {e}")
            return None

        if result.get("error"):
            log.msg(f"MySQL handler: DB proxy error: {result['error']}")
            return None

        columns = result.get("columns", [])
        rows = result.get("rows", [])

        if not columns:
            row_count = result.get("row_count", 0)
            return f"Query OK, {row_count} rows affected (0.01 sec)"

        # Convert all values to strings for formatting
        str_rows = [[str(v) if v is not None else "NULL" for v in row] for row in rows]
        return self._format_table_result(columns, str_rows)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_table_result(columns: list[str], rows: list[list[str]]) -> str:
        """Format a MySQL-style ASCII table from columns and rows."""
        # Calculate column widths
        widths = [len(c) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(val))

        # Build separator
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

        lines = [sep]
        # Header
        header = "|" + "|".join(f" {c:<{widths[i]}} " for i, c in enumerate(columns)) + "|"
        lines.append(header)
        lines.append(sep)
        # Data rows
        for row in rows:
            cells = []
            for i, w in enumerate(widths):
                val = row[i] if i < len(row) else ""
                cells.append(f" {val:<{w}} ")
            lines.append("|" + "|".join(cells) + "|")
        lines.append(sep)
        lines.append(f"{len(rows)} {'row' if len(rows) == 1 else 'rows'} in set (0.00 sec)")
        return "\n".join(lines)

    @staticmethod
    def _format_single_value(value: str, header: str) -> str:
        """Format a single-value MySQL result."""
        width = max(len(header), len(value))
        sep = "+" + "-" * (width + 2) + "+"
        return "\n".join([
            sep,
            f"| {header:<{width}} |",
            sep,
            f"| {value:<{width}} |",
            sep,
            "1 row in set (0.00 sec)",
        ])

    @staticmethod
    def _format_empty_set() -> str:
        return "Empty set (0.00 sec)"

    def _format_show_databases(self) -> str:
        dbs = self._get_profile_databases()
        if not dbs:
            dbs = list(_SYSTEM_DBS)
        return self._format_table_result(["Database"], [[db] for db in dbs])

    def _format_show_tables(self) -> str | None:
        if not self._current_db:
            return "ERROR 1046 (3D000): No database selected"
        tables = self._get_tables_for_db(self._current_db)
        if not tables:
            return None  # Fall through to DB proxy / LLM
        header = f"Tables_in_{self._current_db}"
        return self._format_table_result([header], [[t] for t in tables])

    def _format_show_grants(self) -> str:
        grant = f"GRANT ALL PRIVILEGES ON *.* TO '{self._user}'@'{self._host}'"
        return self._format_table_result(
            [f"Grants for {self._user}@{self._host}"],
            [[grant]],
        )

    # ------------------------------------------------------------------
    # LLM fallback
    # ------------------------------------------------------------------

    def _route_to_llm(self, cmd: str, exit_after: bool = False) -> None:
        """Send a command to the LLM fallback handler."""
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler:
            self._llm_pending = True
            self.protocol.llm_pending = True
            self._exit_after = exit_after
            d = handler.handle_command(cmd)
            d.addCallback(self._write_sql_result)
            d.addErrback(self._sql_error)
        else:
            self.write("ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)\n")
            if exit_after:
                self.exit()
            else:
                self._show_prompt()

    def _write_sql_result(self, response: str) -> None:
        self._llm_pending = False
        self.protocol.llm_pending = False
        if response:
            # If the LLM returned a connection error despite us already
            # showing a banner, log it but still write the response —
            # suppressing to "Empty set" is worse than showing the error.
            if "Can't connect" in response or "Connection refused" in response:
                log.msg(f"MySQL handler: LLM returned connection error despite active session: {response[:200]!r}")
            self.write(response)
            if not response.endswith("\n"):
                self.write("\n")
        if self._exit_after:
            self.exit()
        else:
            self._show_prompt()

    def _sql_error(self, failure) -> None:
        self._llm_pending = False
        self.protocol.llm_pending = False
        log.msg(f"MySQL LLM fallback error: {failure}")
        self.write("ERROR 1064 (42000): You have an error in your SQL syntax\n")
        if self._exit_after:
            self.exit()
        else:
            self._show_prompt()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def lineReceived(self, line: str) -> None:
        log.msg(
            eventid="cowrie.command.success",
            realm="mysql",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        if self._llm_pending:
            return  # ignore input while LLM is processing
        if self.callbacks:
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        self.write("^C\n")
        if self._llm_pending:
            return
        self._show_prompt()

    def handle_CTRL_D(self) -> None:
        self.write("Bye\n")
        self.exit()

    def _show_help(self) -> None:
        self.write(
            """mysql  Ver 8.0.36-0ubuntu0.22.04.1 for Linux on x86_64 ((Ubuntu))
Copyright (c) 2000, 2024, Oracle and/or its affiliates.

Usage: mysql [OPTIONS] [database]
  -?, --help          Display this help and exit.
  -u, --user=name     User for login.
  -p[password]        Password to use when connecting to server.
  -h, --host=name     Connect to host.
  -D, --database=name Database to use.
  -e, --execute=name  Execute command and quit.
  -V, --version       Output version information and exit.
"""
        )
        self.exit()


commands["/usr/bin/mysql"] = Command_mysql
commands["/usr/local/bin/mysql"] = Command_mysql
commands["mysql"] = Command_mysql
