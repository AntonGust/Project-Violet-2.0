# ABOUTME: Database proxy for the honeypot fake-database service.
# ABOUTME: Connects to the real DB container and executes queries, returning
# ABOUTME: results for injection into LLM context. Uses pymysql/pg8000 (pure Python).

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_DIAG_LOG = os.path.join(os.environ.get("COWRIE_HOME", "/cowrie"), "cowrie-git", "var", "db_proxy_diag.log")


def _diag(msg: str) -> None:
    """Write diagnostic message to a file in the mounted var directory."""
    try:
        with open(_DIAG_LOG, "a") as f:
            from datetime import datetime, timezone
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n")
    except Exception:
        pass

MAX_RESULT_ROWS = 100


class DBProxy:
    """
    Executes SQL queries against the honeypot database container.
    Used by the LLM fallback to inject real query results into context.
    """

    def __init__(
        self,
        engine: str,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        self._engine = engine
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._conn: Any = None

    def _connect(self) -> None:
        """Lazy-connect to the database."""
        if self._conn is not None:
            return

        _diag(f"Attempting {self._engine} connection to {self._host}:{self._port} user={self._user} db={self._database}")

        if self._engine == "mysql":
            import pymysql
            self._conn = pymysql.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                connect_timeout=5,
                read_timeout=5,
                charset="utf8mb4",
            )
            _diag("MySQL connection established successfully")
        else:
            import pg8000
            self._conn = pg8000.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                timeout=5,
            )
            _diag("PostgreSQL connection established successfully")

    def _close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def execute(self, sql: str, timeout: float = 5.0) -> dict[str, Any]:
        """
        Execute a SQL statement and return results.

        Returns:
            {
                "columns": ["id", "user_login", ...],
                "rows": [[1, "admin", ...], ...],
                "row_count": 5,
                "error": None | "error message",
            }
        """
        try:
            self._connect()
            cursor = self._conn.cursor()
            cursor.execute(sql)

            # Check if statement returns rows
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchmany(MAX_RESULT_ROWS)
                # Convert to plain lists for serialization
                rows = [list(row) for row in rows]
                row_count = cursor.rowcount if cursor.rowcount >= 0 else len(rows)
            else:
                columns = []
                rows = []
                row_count = cursor.rowcount if cursor.rowcount >= 0 else 0
                # Commit for DML statements
                self._conn.commit()

            cursor.close()
            return {
                "columns": columns,
                "rows": rows,
                "row_count": row_count,
                "error": None,
            }

        except Exception as e:
            # Reset connection on error
            self._close()
            error_msg = str(e)
            _diag(f"execute error ({type(e).__name__}): {error_msg}")
            logger.warning(f"DBProxy execute error ({type(e).__name__}): {error_msg}")
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": error_msg,
            }

    def discover(self) -> dict[str, Any]:
        """
        Run discovery queries for LLM context injection.
        Returns schema overview: databases, tables, row counts.
        """
        try:
            self._connect()
            cursor = self._conn.cursor()

            if self._engine == "mysql":
                return self._discover_mysql(cursor)
            else:
                return self._discover_postgres(cursor)

        except Exception as e:
            self._close()
            logger.warning(f"DBProxy discover error: {e}")
            return {"engine": self._engine, "databases": [], "error": str(e)}

    def _discover_mysql(self, cursor: Any) -> dict[str, Any]:
        """MySQL schema discovery."""
        cursor.execute("SHOW DATABASES")
        all_dbs = [row[0] for row in cursor.fetchall()]
        # Filter out system databases
        skip = {"information_schema", "mysql", "performance_schema", "sys"}
        databases = []

        for db_name in all_dbs:
            if db_name in skip:
                continue
            db_info: dict[str, Any] = {"name": db_name, "tables": []}
            try:
                cursor.execute(f"USE `{db_name}`")
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                    count = cursor.fetchone()[0]
                    db_info["tables"].append({"name": table, "row_count": count})
            except Exception:
                pass
            databases.append(db_info)

        cursor.close()
        return {"engine": "mysql", "databases": databases}

    def _discover_postgres(self, cursor: Any) -> dict[str, Any]:
        """PostgreSQL schema discovery."""
        # Get tables in current database
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        tables_info = []
        for (table_name,) in cursor.fetchall():
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                count = cursor.fetchone()[0]
                tables_info.append({"name": table_name, "row_count": count})
            except Exception:
                tables_info.append({"name": table_name, "row_count": -1})

        cursor.close()
        return {
            "engine": "postgresql",
            "databases": [{"name": self._database, "tables": tables_info}],
        }
