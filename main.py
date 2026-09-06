from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from auth import hash_password, verify_password, create_access_token
from schemas import UserCreate, UserResponse, Token
from database import get_db, engine, Base
from models import User
from schemas import UserCreate, UserResponse
from auth import hash_password
from models import User, Favorite
from schemas import UserCreate, UserResponse, Token, FavoriteCreate, FavoriteResponse
load_dotenv()
from services import calculate_similarity, classify_planet
NASA_API_KEY = os.getenv("NASA_API_KEY")

app = FastAPI(title="Cosmic Tracker API", version="0.1.0")

Base.metadata.create_all(bind=engine)  # crea las tablas si no existen
from fastapi.security import OAuth2PasswordBearer
from auth import hash_password, verify_password, create_access_token, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return user

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Cosmic Tracker API running"}


@app.get("/debug/key")
def debug_key():
    if NASA_API_KEY:
        return {"key_loaded": True, "key_preview": NASA_API_KEY[:4] + "..." + NASA_API_KEY[-4:]}
    else:
        return {"key_loaded": False}


@app.get("/mars/photos")
def get_mars_photos(sol: int = 1000, rover: str = "curiosity"):
    url = f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover}/photos"
    params = {"sol": sol, "api_key": NASA_API_KEY}
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Error de NASA API: {response.text}")

    data = response.json()
    photos = data.get("photos", [])
    resultado = [
        {"id": foto["id"], "img_src": foto["img_src"], "earth_date": foto["earth_date"], "camera": foto["camera"]["full_name"]}
        for foto in photos
    ]
    return {"sol": sol, "rover": rover, "total_fotos": len(resultado), "fotos": resultado}


@app.get("/space/picture-of-the-day")
def get_apod(date: str = None):
    url = "https://api.nasa.gov/planetary/apod"
    params = {"api_key": NASA_API_KEY}
    if date:
        params["date"] = date

    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Error de NASA API: {response.text}")

    data = response.json()
    return {
        "title": data.get("title"),
        "date": data.get("date"),
        "explanation": data.get("explanation"),
        "image_url": data.get("url"),
        "media_type": data.get("media_type")
    }


@app.get("/space-weather/flares")
def get_solar_flares(start_date: str = None, end_date: str = None):
    if end_date is None:
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    url = "https://api.nasa.gov/DONKI/FLR"
    params = {"startDate": start_date, "endDate": end_date, "api_key": NASA_API_KEY}
    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Error de NASA API: {response.text}")

    data = response.json()
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
def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.post("/favorites", response_model=FavoriteResponse)
def create_favorite(
    favorite: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.item_type == favorite.item_type,
        Favorite.item_id == favorite.item_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Este item ya está en tus favoritos")

    new_favorite = Favorite(
        user_id=current_user.id,
        item_type=favorite.item_type,
        item_id=favorite.item_id,
        title=favorite.title,
        image_url=favorite.image_url
    )

    db.add(new_favorite)
    db.commit()
    db.refresh(new_favorite)
    return new_favorite


@app.get("/favorites", response_model=list[FavoriteResponse])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Favorite).filter(Favorite.user_id == current_user.id).all()


@app.delete("/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    favorite = db.query(Favorite).filter(
        Favorite.id == favorite_id,
        Favorite.user_id == current_user.id
    ).first()

    if not favorite:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")

    db.delete(favorite)
    db.commit()
    return {"detail": "Favorito eliminado"}


def fetch_exoplanets(limit: int = 100):
    """Consulta el archivo de exoplanetas de la NASA."""
    url = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"

    query = f"""
        SELECT TOP {limit}
            pl_name, hostname, disc_year, pl_rade, pl_bmasse, pl_eqt, sy_dist
        FROM ps
        WHERE pl_rade IS NOT NULL AND pl_eqt IS NOT NULL
        ORDER BY disc_year DESC
    """

    response = requests.get(url, params={"query": query, "format": "json"}, timeout=30)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudo consultar el archivo de exoplanetas")

    return response.json()


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
        "classification": classify_planet(radius, temp)
    }


@app.get("/exoplanets")
def get_exoplanets(limit: int = 20):
    data = fetch_exoplanets(limit)
    resultado = [enrich_planet(p) for p in data]
    return {"count": len(resultado), "exoplanets": resultado}


@app.get("/exoplanets/habitable")
def get_habitable_exoplanets(limit: int = 10):
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
        "exoplanets": habitable[:limit]
    }


@app.get("/exoplanets/stats/by-year")
def get_exoplanets_stats_by_year():
    data = fetch_exoplanets(1000)
    enriched = [enrich_planet(p) for p in data]

    counts = {}
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
        "too_cold": 0
    }
    for p in enriched:
        if p["classification"] in by_classification:
            by_classification[p["classification"]] += 1

    if enriched:
        average_similarity = round(sum(p["earth_similarity"] for p in enriched) / len(enriched), 3)
    else:
        average_similarity = 0.0

    habitable = [p for p in enriched if p["classification"] == "potentially_habitable"]
    most_earth_like = max(habitable, key=lambda p: p["earth_similarity"]) if habitable else None

    return {
        "total_analyzed": len(enriched),
        "by_classification": by_classification,
        "average_similarity": average_similarity,
        "most_earth_like": most_earth_like
    }