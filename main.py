from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests
import os
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



