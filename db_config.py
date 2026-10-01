"""Centralized database configuration and connection management.

Centralizes database connection parameter resolution from environment variables,
ensuring consistent credential management, standard validation, and safe error handling
across all pipeline execution scripts.
"""

import os
import sys
from typing import Any, Dict
import psycopg2


def get_db_credentials(require_password: bool = True) -> Dict[str, Any]:
    """Retrieve database connection parameters from environment variables.

    Parameters:
        require_password: When True, enforces that DB_PASSWORD or DBT_PASSWORD is provided.

    Returns:
        Dict[str, Any]: Dictionary containing dbname, user, password, host, and port.

    Raises:
        ValueError: If require_password is True and no password environment variable is set.
    """
    password = os.getenv("DB_PASSWORD") or os.getenv("DBT_PASSWORD")
    if require_password and not password:
        raise ValueError(
            "Database credentials absent: 'DB_PASSWORD' (or 'DBT_PASSWORD') environment variable "
            "is not set. Please set your database password in the environment or via a .env file."
        )

    return {
        "dbname": os.getenv("DB_NAME", os.getenv("DBT_DBNAME", "analytics_pipeline")),
        "user": os.getenv("DB_USER", os.getenv("DBT_USER", "postgres")),
        "password": password,
        "host": os.getenv("DB_HOST", os.getenv("DBT_HOST", "localhost")),
        "port": os.getenv("DB_PORT", os.getenv("DBT_PORT", "5432")),
    }


def get_db_connection(
    dbname: str | None = None,
    require_password: bool = True,
    autocommit: bool = False,
) -> psycopg2.extensions.connection:
    """Establish and return a psycopg2 database connection.

    Parameters:
        dbname: Optional database name override (e.g. 'postgres' for bootstrap operations).
        require_password: When True, enforces password validation via get_db_credentials.
        autocommit: When True, enables autocommit on the returned connection.

    Returns:
        psycopg2.extensions.connection: An open PostgreSQL connection.
    """
    creds = get_db_credentials(require_password=require_password)
    target_dbname = dbname or creds["dbname"]

    try:
        conn = psycopg2.connect(
            dbname=target_dbname,
            user=creds["user"],
            password=creds["password"],
            host=creds["host"],
            port=creds["port"],
        )
        if autocommit:
            conn.autocommit = True
        return conn
    except psycopg2.OperationalError as e:
        sys.exit(
            f"Database connection failed to {creds['host']}:{creds['port']}/{target_dbname}: {e}\n"
            f"Ensure PostgreSQL is running and environment variables (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME) are properly set."
        )
