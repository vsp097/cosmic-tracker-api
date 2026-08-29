# Cosmic Tracker API

A REST API that consumes NASA's public data and lets users register, authenticate, and save their favorite space content.

Built as a learning project to practice backend development with FastAPI, PostgreSQL, and JWT authentication.

## Features

- User registration with password hashing (bcrypt)
- JWT-based authentication with protected routes
- Integration with NASA's public APIs (Astronomy Picture of the Day, Mars Rover Photos)
- Auto-generated interactive documentation (Swagger UI)
- Graceful handling of external API failures

## Tech Stack

- **FastAPI** — web framework
- **PostgreSQL** — database (running in Docker)
- **SQLAlchemy** — ORM
- **python-jose** — JWT token handling
- **passlib + bcrypt** — password hashing

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/` | Health check | No |
| POST | `/auth/register` | Create a new user | No |
| POST | `/auth/login` | Get access token | No |
| GET | `/auth/me` | Get current user | Yes |
| GET | `/space/picture-of-the-day` | NASA's Astronomy Picture of the Day | No |
| GET | `/mars/photos` | Mars rover photos | No |

## Running Locally

1. Clone the repository and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Start the PostgreSQL container:

```bash
docker run --name cosmic-db -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=cosmic_tracker -p 5433:5432 -d postgres
```

3. Create a `.env` file:

Get a free NASA API key at https://api.nasa.gov

4. Run the server:

```bash
uvicorn main:app --reload
```

Interactive docs available at `http://localhost:8000/docs`

## Notes

The Mars Rover Photos endpoint depends on a third-party maintained service that is currently unavailable. The endpoint handles this failure gracefully and returns a clear error message.

## Roadmap

- [ ] Favorites system (save missions and images per user)
- [ ] Exoplanet data with habitability index
- [ ] Space weather (solar flares)
- [ ] Automated tests with pytest
- [ ] Deployment