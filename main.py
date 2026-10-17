import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from database import Base, engine, get_db
from models import Favorite, User
from schemas import (
    FavoriteCreate,
    FavoriteResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from services import calculate_similarity, classify_planet

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY")
NASA_TIMEOUT = 15

app = FastAPI(title="Cosmic Tracker API", version="0.2.0")

Base.metadata.create_all(bind=engine)  # crea las tablas si no existen

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


# ============================================================
# Helpers
# ============================================================

def nasa_get(url: str, params: dict) -> dict | list:
    """
    Llama a una API de la NASA y traduce cualquier falla de red en un 502.

    Sin esto, un upstream lento o caído deja el worker colgado y devuelve un
    500 sin explicacion. El timeout es lo que evita que una API externa
    bloquee la nuestra.
    """
    if not NASA_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="NASA_API_KEY no está configurada en el servidor",
        )

    params = {**params, "api_key": NASA_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=NASA_TIMEOUT)
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="La API de la NASA no respondió a tiempo")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo contactar la API de la NASA")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Error de la API de la NASA ({response.status_code})",
        )

    return response.json()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return user


# ============================================================
# Health
# ============================================================

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Cosmic Tracker API running"}


# ============================================================
# Autenticacion
# ============================================================

@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    hashed = hash_password(user.password)
    new_user = User(email=user.email, hashed_password=hashed)

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    db.refresh(new_user)
    return new_user


@app.post("/auth/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login con JSON. Pensado para clientes propios (apps, scripts)."""
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/token", response_model=Token)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login por formulario, según el flujo OAuth2 password.

    Este es el endpoint que usa el boton "Authorize" de la documentación
    interactiva, que manda los datos como formulario y no como JSON. El campo
    `username` es el email.
    """
    db_user = db.query(User).filter(User.email == form_data.username).first()

    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# ============================================================
# Datos de la NASA
# ============================================================

@app.get("/space/picture-of-the-day")
def get_apod(date: str | None = None):
    params = {}
    if date:
        params["date"] = date

    data = nasa_get("https://api.nasa.gov/planetary/apod", params)

    return {
        "title": data.get("title"),
        "date": data.get("date"),
        "explanation": data.get("explanation"),
        "image_url": data.get("url"),
        "media_type": data.get("media_type"),
    }


@app.get("/mars/photos")
def get_mars_photos(
    sol: int = Query(1000, ge=0, le=5000),
    rover: str = Query("curiosity", pattern="^(curiosity|opportunity|spirit|perseverance)$"),
):
    url = f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover}/photos"
    data = nasa_get(url, {"sol": sol})

    photos = data.get("photos", [])
    resultado = [
        {
            "id": foto["id"],
            "img_src": foto["img_src"],
            "earth_date": foto["earth_date"],
            "camera": foto["camera"]["full_name"],
        }
        for foto in photos
    ]
    return {"sol": sol, "rover": rover, "total_fotos": len(resultado), "fotos": resultado}


@app.get("/space-weather/flares")
def get_solar_flares(start_date: str | None = None, end_date: str | None = None):
    now = datetime.now(timezone.utc)
    if end_date is None:
        end_date = now.strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    data = nasa_get(
        "https://api.nasa.gov/DONKI/FLR",
        {"startDate": start_date, "endDate": end_date},
    )

    flares = [
        {
            "id": flare.get("flrID"),
            "begin_time": flare.get("beginTime"),
            "peak_time": flare.get("peakTime"),
            "class_type": flare.get("classType"),
            "source_location": flare.get("sourceLocation"),
        }
        for flare in data
    ]

    flares.sort(key=lambda f: f["begin_time"] or "", reverse=True)

    return {"count": len(flares), "flares": flares}


# ============================================================
# Favoritos (por usuario)
# ============================================================

@app.post("/favorites", response_model=FavoriteResponse)
def create_favorite(
    favorite: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user.id,
            Favorite.item_type == favorite.item_type,
            Favorite.item_id == favorite.item_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(status_code=400, detail="Este item ya está en tus favoritos")

    new_favorite = Favorite(
        user_id=current_user.id,
        item_type=favorite.item_type,
        item_id=favorite.item_id,
        title=favorite.title,
        image_url=favorite.image_url,
    )

    db.add(new_favorite)
    db.commit()
    db.refresh(new_favorite)
    return new_favorite


@app.get("/favorites", response_model=list[FavoriteResponse])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Favorite).filter(Favorite.user_id == current_user.id).all()


@app.delete("/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    favorite = (
        db.query(Favorite)
        .filter(Favorite.id == favorite_id, Favorite.user_id == current_user.id)
        .first()
    )

    if not favorite:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")

    db.delete(favorite)
    db.commit()
    return {"detail": "Favorito eliminado"}


# ============================================================
# Exoplanetas
# ============================================================

EXOPLANET_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
EXOPLANET_CACHE_TTL = 3600  # segundos
_exoplanet_cache: dict[int, tuple[float, list]] = {}


def fetch_exoplanets(limit: int = 100) -> list:
    """
    Consulta el archivo de exoplanetas de la NASA, con caché en memoria.

    El caché importa: las rutas de estadísticas piden 1000 filas, y sin cache
    cada visita a la documentación dispara una consulta completa al archivo de
    Caltech. Una hora de TTL es de sobra, porque el catálogo cambia por dias,
    no por segundos.
    """
    now = time.monotonic()
    cached = _exoplanet_cache.get(limit)
    if cached is not None and now - cached[0] < EXOPLANET_CACHE_TTL:
        return cached[1]

    query = f"""
        SELECT TOP {int(limit)}
            pl_name, hostname, disc_year, pl_rade, pl_bmasse, pl_eqt, sy_dist
        FROM ps
        WHERE pl_rade IS NOT NULL AND pl_eqt IS NOT NULL
        ORDER BY disc_year DESC
    """

    try:
        response = requests.get(
            EXOPLANET_URL,
            params={"query": query, "format": "json"},
            timeout=30,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="No se pudo consultar el archivo de exoplanetas",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="No se pudo consultar el archivo de exoplanetas",
        )

    data = response.json()
    _exoplanet_cache[limit] = (now, data)
    return data


def enrich_planet(p: dict) -> dict:
    """Agrega índice de similitud y clasificación a un planeta."""
    radius = p.get("pl_rade")
    temp = p.get("pl_eqt")

    return {
        "name": p.get("pl_name"),
        "host_star": p.get("hostname"),
        "discovery_year": p.get("disc_year"),
        "radius_earth": radius,
        "mass_earth": p.get("pl_bmasse"),
        "temperature_k": temp,
        "distance_parsecs": p.get("sy_dist"),
        "earth_similarity": calculate_similarity(radius, temp),
        "classification": classify_planet(radius, temp),
    }


@app.get("/exoplanets")
def get_exoplanets(limit: int = Query(20, ge=1, le=100)):
    data = fetch_exoplanets(limit)
    resultado = [enrich_planet(p) for p in data]
    return {"count": len(resultado), "exoplanets": resultado}


@app.get("/exoplanets/habitable")
def get_habitable_exoplanets(limit: int = Query(10, ge=1, le=100)):
    """
    Devuelve los exoplanetas más parecidos a la Tierra,
    ordenados por índice de similitud.
    """
    data = fetch_exoplanets(500)
    enriched = [enrich_planet(p) for p in data]

    habitable = [p for p in enriched if p["classification"] == "potentially_habitable"]
    habitable.sort(key=lambda p: p["earth_similarity"], reverse=True)

    return {
        "count": len(habitable[:limit]),
        "total_analyzed": len(enriched),
        "exoplanets": habitable[:limit],
    }


@app.get("/exoplanets/stats/by-year")
def get_exoplanets_stats_by_year():
    data = fetch_exoplanets(1000)
    enriched = [enrich_planet(p) for p in data]

    counts: dict[int, int] = {}
    for p in enriched:
        year = p["discovery_year"]
        if year is None:
            continue
        counts[year] = counts.get(year, 0) + 1

    by_year = [
        {"year": year, "count": count}
        for year, count in sorted(counts.items(), reverse=True)
    ]

    return {"total": len(enriched), "by_year": by_year}


@app.get("/exoplanets/stats/summary")
def get_exoplanets_stats_summary():
    data = fetch_exoplanets(1000)
    enriched = [enrich_planet(p) for p in data]

    by_classification = {
        "gas_giant": 0,
        "mini_neptune": 0,
        "potentially_habitable": 0,
        "too_hot": 0,
        "too_cold": 0,
    }
    for p in enriched:
        if p["classification"] in by_classification:
            by_classification[p["classification"]] += 1

    if enriched:
        average_similarity = round(
            sum(p["earth_similarity"] for p in enriched) / len(enriched), 3
        )
    else:
        average_similarity = 0.0

    habitable = [p for p in enriched if p["classification"] == "potentially_habitable"]
    most_earth_like = (
        max(habitable, key=lambda p: p["earth_similarity"]) if habitable else None
    )

    return {
        "total_analyzed": len(enriched),
        "by_classification": by_classification,
        "average_similarity": average_similarity,
        "most_earth_like": most_earth_like,
    }
