"""
Configuración de pytest.

Lo importante de este archivo: los tests corren sobre SQLite en memoria, no
sobre la base de datos de desarrollo. Eso significa que `pytest` funciona en
una máquina limpia sin levantar Postgres, y por lo tanto puede correr en
integración continua.

Las variables de entorno se definen antes de importar la aplicación, porque
`database.py` y `auth.py` fallan a propósito al arrancar si faltan.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "clave-solo-para-tests")
os.environ.setdefault("NASA_API_KEY", "DEMO_KEY")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import models  # noqa: E402,F401  (registra las tablas en Base.metadata)
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402

# StaticPool mantiene una sola conexión viva, que es lo que hace que una base
# SQLite en memoria sobreviva entre requests dentro del mismo test.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def create_test_schema():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
