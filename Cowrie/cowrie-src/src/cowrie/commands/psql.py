# ABOUTME: Native PostgreSQL psql client command handler for Cowrie honeypot.
# ABOUTME: Supports interactive password prompt, postgres=# shell loop,
# ABOUTME: backslash meta-commands (\l, \dt, \du, \d, \c, \q),
# ABOUTME: native result generation from profile data,
# ABOUTME: DB proxy direct execution, and LLM fallback for unrecognized queries.

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from twisted.python import log

from cowrie.shell.command import HoneyPotCommand

if TYPE_CHECKING:
    from collections.abc import Callable

commands = {}

PSQL_VERSION_DEFAULT = "14.11"

# System databases always present in PostgreSQL
_SYSTEM_DBS = ["postgres", "template0", "template1"]


class Command_psql(HoneyPotCommand):
    """
    psql client command implementation.

    Supports -U, -h, -d, -p, -c, -l flags and backslash meta-commands.
    Interactive mode enters a postgres=# prompt loop that answers common
    queries natively from profile data, tries the DB proxy for direct
    execution, and falls back to LLM for unrecognized queries.
    """

    callbacks: list[Callable]

    # ------------------------------------------------------------------
    # Startup / arg parsing
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._llm_pending = False
        self._current_db = "postgres"
        self._user = "postgres"
        self._host = "localhost"
        self._port = "5432"
        self._password: str | None = None
        self._inline_query: str | None = None
        self._list_dbs = False
        self._exit_after = False

        # Cache profile reference
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        self._profile: dict[str, Any] = (
            getattr(handler, "_profile", {}) if handler else {}
        )

        args = list(self.args)
        i = 0
        while i < len(args):
            arg = args[i]

            if arg == "-U" and i + 1 < len(args):
                self._user = args[i + 1]
                i += 2
                continue

            if arg == "-h" and i + 1 < len(args):
                self._host = args[i + 1]
                i += 2
                continue

            if arg == "-p" and i + 1 < len(args):
                self._port = args[i + 1]
                i += 2
                continue

            if arg == "-d" and i + 1 < len(args):
                self._current_db = args[i + 1]
                i += 2
                continue

            if arg == "-c" and i + 1 < len(args):
                self._inline_query = args[i + 1]
                i += 2
                continue

            if arg == "-W":
                # Force password prompt
                self._password = None
                i += 1
                continue

            if arg == "-w":
                # Never prompt for password
                self._password = ""
                i += 1
                continue

            if arg == "-l":
                self._list_dbs = True
                i += 1
                continue

            if arg in ("--help", "-?"):
                self._show_help()
                return

            if arg in ("--version", "-V"):
                self.write(f"psql (PostgreSQL) {self._get_version()}\n")
                self.exit()
                return

            # Positional: database or "dbname user"
            if not arg.startswith("-"):
                if re.match(r"^[A-Za-z0-9_]+$", arg):
                    self._current_db = arg
                i += 1
                continue

            i += 1

        # -l: list databases and exit
        if self._list_dbs:
            if not self._has_postgres_service():
                self._write_connection_error()
                return
            result = self._format_list_databases()
            self.write(result + "\n")
            self.exit()
            return

        # -c: inline query
        if self._inline_query is not None:
            if self._password is None and "-W" in self.args:
                self._prompt_password(then_inline=True)
            else:
                self._run_inline_query()
            return

        # Interactive mode
        if self._password is None and "-W" in [str(a) for a in self.args]:
            self._prompt_password()
        else:
            self._do_login()

    # ------------------------------------------------------------------
    # Profile / version helpers
    # ------------------------------------------------------------------

    def _get_version(self) -> str:
        for pkg in self._profile.get("installed_packages", []):
            name = pkg.get("name", "").lower()
            if "postgresql" in name and "server" in name:
                v = pkg.get("version", "")
                if v:
                    # Extract major.minor from e.g. "14.11-1PGDG.rhel7"
                    m = re.match(r"(\d+\.\d+)", v)
                    return m.group(1) if m else v
        for svc in self._profile.get("services", []):
            name = svc.get("name", "").lower()
            if "postgresql" in name or "postgres" in name:
                v = svc.get("version", "")
                if v:
                    return v
        return PSQL_VERSION_DEFAULT

    def _has_postgres_service(self) -> bool:
        for svc in self._profile.get("services", []):
            name = svc.get("name", "").lower()
            if "postgres" in name or "postmaster" in name:
                return True
        for pkg in self._profile.get("installed_packages", []):
            name = pkg.get("name", "").lower()
            if "postgresql" in name and "server" in name:
                return True
        return False

    # ------------------------------------------------------------------
    # Password prompt
    # ------------------------------------------------------------------

    def _prompt_password(self, then_inline: bool = False) -> None:
        self.write(f"Password for user {self._user}: ")
        self.protocol.password_input = True
        self._then_inline = then_inline
        self.callbacks = [self._handle_password]

    def _handle_password(self, line: str) -> None:
        self.protocol.password_input = False
        self._password = line

        log.msg(
            eventid="cowrie.command.success",
            realm="psql",
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
        if not self._has_postgres_service():
            self._write_connection_error()
            return
        version = self._get_version()
        self.write(
            f"psql ({version})\n"
            f"SSL connection (protocol: TLSv1.3, cipher: TLS_AES_256_GCM_SHA384,"
            f" compression: off)\n"
            f'Type "help" for help.\n\n'
        )
        self._show_prompt()

    def _write_connection_error(self) -> None:
        self.write(
            f'psql: error: connection to server on host "{self._host}"'
            f" ({self._host}), port {self._port} failed:"
            f" Connection refused\n"
            f"\tIs the server running on that host and accepting"
            f" TCP/IP connections?\n"
        )
        self.exit()

    def _show_prompt(self) -> None:
        # Superuser gets =#, regular user gets =>
        suffix = "#" if self._user in ("postgres", "root") else ">"
        self.write(f"{self._current_db}={suffix} ")
        self.callbacks = [self._handle_input]

    # ------------------------------------------------------------------
    # Input handling — route backslash commands vs SQL
    # ------------------------------------------------------------------

    def _handle_input(self, line: str) -> None:
        stripped = line.strip()

        if not stripped:
            self._show_prompt()
            return

        # Exit commands
        if stripped.lower() in ("\\q", "exit", "quit"):
            self.exit()
            return

        # Backslash meta-commands
        if stripped.startswith("\\"):
            self._handle_backslash(stripped)
            return

        # SQL statement
        self._handle_sql(stripped)

    def _handle_backslash(self, cmd: str) -> None:
        parts = cmd.split(None, 1)
        meta = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if meta in ("\\l", "\\list"):
            result = self._format_list_databases()
            self.write(result + "\n")
            self._show_prompt()
            return

        if meta in ("\\dt", "\\dt+"):
            result = self._format_list_tables()
            if result:
                self.write(result + "\n")
            else:
                self.write("Did not find any relations.\n")
            self._show_prompt()
            return

        if meta in ("\\du", "\\du+"):
            result = self._format_list_roles()
            self.write(result + "\n")
            self._show_prompt()
            return

        if meta in ("\\d",) and arg:
            # Describe specific table — fall through to LLM
            self._route_to_llm(f"psql -d {self._current_db} -c '\\d {arg}'")
            return

        if meta == "\\c" or meta == "\\connect":
            if arg:
                db_name = arg.split()[0]
                self._current_db = db_name
                self.write(
                    f'You are now connected to database "{db_name}"'
                    f' as user "{self._user}".\n'
                )
            self._show_prompt()
            return

        if meta == "\\conninfo":
            self.write(
                f'You are connected to database "{self._current_db}"'
                f' as user "{self._user}" on host "{self._host}"'
                f" (address \"{self._host}\") at port \"{self._port}\".\n"
                f"SSL connection (protocol: TLSv1.3, cipher:"
                f" TLS_AES_256_GCM_SHA384, compression: off)\n"
            )
            self._show_prompt()
            return

        if meta == "\\?":
            self.write(
                "General\n"
                "  \\conninfo     display info about current connection\n"
                "  \\q            quit psql\n"
                "\n"
                "Informational\n"
                "  \\d[+] [NAME]  describe table or list relations\n"
                "  \\dt[+]        list tables\n"
                "  \\du[+]        list roles\n"
                "  \\l[+]         list databases\n"
                "\n"
                "Connection\n"
                "  \\c[onnect] DB connect to new database\n"
            )
            self._show_prompt()
            return

        # Unknown backslash command — route to LLM
        self._route_to_llm(f"psql -d {self._current_db} -c '{cmd}'")

    # ------------------------------------------------------------------
    # SQL handling — native → DB proxy → LLM fallback
    # ------------------------------------------------------------------

    def _handle_sql(self, line: str) -> None:
        stripped = line.strip()

        # Try native SQL first
        result = self._try_native_sql(stripped)
        if result is not None:
            self.write(result + "\n")
            self._show_prompt()
            return

        # Try DB proxy
        result = self._try_db_proxy(stripped)
        if result is not None:
            self.write(result + "\n")
            self._show_prompt()
            return

        # Fall through to LLM
        self._route_to_llm(self._build_psql_cmd(stripped))

    def _build_psql_cmd(self, sql: str) -> str:
        return f"psql -d {self._current_db} -c '{sql}'"

    def _run_inline_query(self) -> None:
        if self._inline_query is None:
            self.exit()
            return

        if not self._has_postgres_service():
            self._write_connection_error()
            return

        # Check for backslash command in -c
        if self._inline_query.strip().startswith("\\"):
            # Handle \l, \dt etc. inline
            cmd = self._inline_query.strip()
            if cmd in ("\\l", "\\list"):
                self.write(self._format_list_databases() + "\n")
                self.exit()
                return
            if cmd in ("\\dt", "\\dt+"):
                result = self._format_list_tables()
                if result:
                    self.write(result + "\n")
                else:
                    self.write("Did not find any relations.\n")
                self.exit()
                return

        # Try native
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

        # LLM fallback
        self._route_to_llm(
            self._build_psql_cmd(self._inline_query),
            exit_after=True,
        )

    # ------------------------------------------------------------------
    # Native SQL result generation from profile data
    # ------------------------------------------------------------------

    def _try_native_sql(self, sql: str) -> str | None:
        normalized = sql.strip().rstrip(";").strip()
        upper = normalized.upper()

        if upper.startswith("SELECT VERSION"):
            version = self._get_version()
            val = (
                f"PostgreSQL {version} on x86_64-pc-linux-gnu,"
                f" compiled by gcc (GCC) 7.3.1 20180303"
                f" (Red Hat 7.3.1-5), 64-bit"
            )
            return self._format_pg_table(["version"], [[val]])

        if upper.startswith("SELECT CURRENT_USER") or upper == "SELECT USER":
            return self._format_pg_table(["current_user"], [[self._user]])

        if upper.startswith("SELECT CURRENT_DATABASE"):
            return self._format_pg_table(
                ["current_database"], [[self._current_db]]
            )

        if upper == "SELECT DATNAME FROM PG_DATABASE":
            dbs = self._get_profile_databases()
            return self._format_pg_table(
                ["datname"], [[db] for db in dbs]
            )

        if upper.startswith("SELECT TABLENAME FROM PG_TABLES"):
            tables = self._get_tables_for_db()
            if tables:
                return self._format_pg_table(
                    ["tablename"], [[t] for t in tables]
                )
            return self._format_pg_table(["tablename"], [])

        # MySQL syntax used in psql — return proper PostgreSQL error
        if upper.startswith("SHOW "):
            return f'ERROR:  syntax error at or near "SHOW"\nLINE 1: {sql.strip()}\n        ^'

        return None

    def _get_profile_databases(self) -> list[str]:
        dbs: set[str] = set(_SYSTEM_DBS)
        file_contents = self._profile.get("file_contents", {})
        for path, content in file_contents.items():
            # .pgpass format: host:port:database:user:password
            if ".pgpass" in path:
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(":")
                        if len(parts) >= 3 and parts[2] != "*":
                            dbs.add(parts[2])
            # CREATE DATABASE statements
            for m in re.finditer(
                r"CREATE\s+DATABASE\s+(\w+)", content, re.IGNORECASE
            ):
                dbs.add(m.group(1))
            # GRANT CONNECT ON DATABASE
            for m in re.finditer(
                r"ON\s+DATABASE\s+(\w+)", content, re.IGNORECASE
            ):
                dbs.add(m.group(1))
            # pg_hba.conf database column
            if "pg_hba" in path:
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] not in (
                            "all", "replication", "sameuser",
                        ):
                            dbs.add(parts[1])
        return sorted(dbs)

    def _get_tables_for_db(self) -> list[str]:
        tables: set[str] = set()
        file_contents = self._profile.get("file_contents", {})
        for path, content in file_contents.items():
            if "CREATE TABLE" not in content.upper():
                continue
            for m in re.finditer(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)[\"`]?",
                content,
                re.IGNORECASE,
            ):
                tables.add(m.group(1))
        return sorted(tables)

    # ------------------------------------------------------------------
    # DB proxy direct execution
    # ------------------------------------------------------------------

    def _try_db_proxy(self, sql: str) -> str | None:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if not handler:
            return None
        db_proxy = getattr(handler, "_db_proxy", None)
        if not db_proxy:
            return None

        clean_sql = sql.strip().rstrip(";").strip()
        if not clean_sql:
            return None

        # Don't send backslash commands to the proxy
        if clean_sql.startswith("\\"):
            return None

        try:
            result = db_proxy.execute(clean_sql)
        except Exception as e:
            log.msg(f"psql handler: DB proxy exception: {e}")
            return None

        if result.get("error"):
            log.msg(f"psql handler: DB proxy error: {result['error']}")
            return None

        columns = result.get("columns", [])
        rows = result.get("rows", [])

        if not columns:
            row_count = result.get("row_count", 0)
            if row_count:
                return f"INSERT 0 {row_count}" if "INSERT" in sql.upper() else f"UPDATE {row_count}"
            return "OK"

        str_rows = [
            [str(v) if v is not None else "" for v in row] for row in rows
        ]
        return self._format_pg_table(columns, str_rows)

    # ------------------------------------------------------------------
    # Formatting helpers — PostgreSQL style
    # ------------------------------------------------------------------

    @staticmethod
    def _format_pg_table(columns: list[str], rows: list[list[str]]) -> str:
        """Format a PostgreSQL-style table with pipe separators."""
        if not columns:
            return "(0 rows)"

        # Calculate column widths
        widths = [len(c) for c in columns]
        for row in rows:
            for i, val in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(val))

        # Header
        header = " | ".join(f"{c:<{widths[i]}}" for i, c in enumerate(columns))
        separator = "-+-".join("-" * w for w in widths)

        lines = [" " + header, "-" + separator + "-"]

        for row in rows:
            cells = []
            for i, w in enumerate(widths):
                val = row[i] if i < len(row) else ""
                cells.append(f"{val:<{w}}")
            lines.append(" " + " | ".join(cells))

        row_count = len(rows)
        lines.append(f"({row_count} {'row' if row_count == 1 else 'rows'})")
        return "\n".join(lines)

    def _format_list_databases(self) -> str:
        dbs = self._get_profile_databases()
        rows = []
        for db in dbs:
            owner = "postgres"
            encoding = "UTF8"
            collate = "en_US.UTF-8"
            rows.append([db, owner, encoding, collate])
        return self._format_pg_table(
            ["Name", "Owner", "Encoding", "Collate"],
            rows,
        )

    def _format_list_tables(self) -> str | None:
        tables = self._get_tables_for_db()
        if not tables:
            return None
        rows = [[" public", t, "table", self._user] for t in tables]
        return self._format_pg_table(
            ["Schema", "Name", "Type", "Owner"], rows
        )

    def _format_list_roles(self) -> str:
        roles = []
        for u in self._profile.get("users", []):
            name = u.get("name", "")
            shell = u.get("shell", "")
            if "nologin" in shell or "false" in shell:
                continue
            attrs = []
            if name == "postgres" or name == "root":
                attrs.append("Superuser")
            if name in ("postgres", "root", "dba"):
                attrs.append("Create role")
                attrs.append("Create DB")
            roles.append([name, ", ".join(attrs) if attrs else "", "{}"])

        # Always include postgres if not already present
        role_names = [r[0] for r in roles]
        if "postgres" not in role_names:
            roles.insert(
                0, ["postgres", "Superuser, Create role, Create DB", "{}"]
            )

        return self._format_pg_table(
            ["Role name", "Attributes", "Member of"], roles
        )

    # ------------------------------------------------------------------
    # LLM fallback
    # ------------------------------------------------------------------

    def _route_to_llm(self, cmd: str, exit_after: bool = False) -> None:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler:
            self._llm_pending = True
            self.protocol.llm_pending = True
            self._exit_after = exit_after
            d = handler.handle_command(cmd)
            d.addCallback(self._write_sql_result)
            d.addErrback(self._sql_error)
        else:
            self._write_connection_error()

    def _write_sql_result(self, response: str) -> None:
        self._llm_pending = False
        self.protocol.llm_pending = False
        if response:
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
        log.msg(f"psql LLM fallback error: {failure}")
        self.write("ERROR:  syntax error\n")
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
            realm="psql",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        if self._llm_pending:
            return
        if self.callbacks:
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        self.write("^C\n")
        if self._llm_pending:
            return
        self._show_prompt()

    def handle_CTRL_D(self) -> None:
        self.exit()

    def _show_help(self) -> None:
        self.write(
            f"psql is the PostgreSQL interactive terminal.\n\n"
            f"Usage:\n"
            f"  psql [OPTION]... [DBNAME [USERNAME]]\n\n"
            f"General options:\n"
            f"  -c, --command=COMMAND    run only single command\n"
            f"  -d, --dbname=DBNAME      database name to connect to\n"
            f"  -V, --version            output version information, then exit\n"
            f"  -?, --help               show this help, then exit\n\n"
            f"Connection options:\n"
            f"  -h, --host=HOSTNAME      database server host\n"
            f"  -p, --port=PORT          database server port\n"
            f"  -U, --username=USERNAME  database user name\n"
            f"  -w, --no-password        never prompt for password\n"
            f"  -W, --password           force password prompt\n"
            f"  -l, --list               list available databases, then exit\n"
        )
        self.exit()


commands["/usr/bin/psql"] = Command_psql
commands["/usr/local/bin/psql"] = Command_psql
commands["psql"] = Command_psql
