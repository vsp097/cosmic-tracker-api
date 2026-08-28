from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests
import os
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User
from schemas import UserCreate, UserResponse
from auth import hash_password

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY")

app = FastAPI(title="Cosmic Tracker API", version="0.1.0")

Base.metadata.create_all(bind=engine)  # crea las tablas si no existen


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