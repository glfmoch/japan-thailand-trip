"""
load_to_postgres.py

Loads cleaned DataFrames into PostgreSQL via SQLAlchemy.

Expects a DATABASE_URL environment variable (or .env file) of the form:
    postgresql://user:password@host:port/dbname

TODO: run create_schema() once, then call load_visits() and load_spending()
      after parse_timeline.py and the spending parser are implemented.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text


# ── Schema ────────────────────────────────────────────────────────────────────

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cities (
    city_id     SERIAL PRIMARY KEY,
    city        TEXT NOT NULL,
    country     TEXT NOT NULL,
    region      TEXT,
    UNIQUE (city, country)
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id            SERIAL PRIMARY KEY,
    city_id             INT REFERENCES cities(city_id),
    location_name       TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    arrival_datetime    TIMESTAMP WITH TIME ZONE,
    departure_datetime  TIMESTAMP WITH TIME ZONE,
    duration_hours      NUMERIC(6, 2),
    source              TEXT DEFAULT 'timeline'
);

CREATE TABLE IF NOT EXISTS spending (
    spend_id        SERIAL PRIMARY KEY,
    city_id         INT REFERENCES cities(city_id),
    spend_date      DATE NOT NULL,
    category        TEXT,
    description     TEXT,
    amount_local    NUMERIC(10, 2),
    currency        CHAR(3),
    amount_usd      NUMERIC(10, 2)
);
"""


# ── Connection ────────────────────────────────────────────────────────────────

def get_engine():
    """Build a SQLAlchemy engine from DATABASE_URL env var."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError(
            "DATABASE_URL not set. "
            "Add it to your .env file: postgresql://user:pw@host:port/db"
        )
    return create_engine(url)


# ── Schema setup ─────────────────────────────────────────────────────────────

def create_schema(engine=None):
    """Create all tables if they don't exist. Safe to run multiple times."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text(CREATE_SCHEMA_SQL))
    print("Schema created (or already exists).")


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_cities(df: pd.DataFrame, engine=None):
    """
    Upsert unique (city, country) pairs into the cities lookup table.
    df must have columns: city, country. Optional column: region.
    """
    # TODO: implement upsert logic (INSERT ... ON CONFLICT DO NOTHING)
    raise NotImplementedError("Fill in once parse_timeline.py is working.")


def load_visits(df: pd.DataFrame, engine=None):
    """
    Insert parsed visit records into the visits table.
    df must match the visits schema. city_id resolved from cities table.
    """
    # TODO: implement — resolve city_id foreign key, then bulk insert
    raise NotImplementedError("Fill in once parse_timeline.py is working.")


def load_spending(df: pd.DataFrame, engine=None):
    """
    Insert spending records into the spending table.
    df must match the spending schema.
    """
    # TODO: implement
    raise NotImplementedError("Fill in once spending CSV parser is ready.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = get_engine()
    create_schema(engine)
    print("Ready. Run load_visits() and load_spending() with parsed DataFrames.")
