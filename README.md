# Cosmic Tracker API

[![tests](https://github.com/vsp097/cosmic-tracker-api/actions/workflows/tests.yml/badge.svg)](https://github.com/vsp097/cosmic-tracker-api/actions/workflows/tests.yml)

**Live demo:** https://cosmic-tracker-api.onrender.com/docs
(Note: hosted on Render's free tier — first request may take ~30s to wake up)

A REST API that consumes NASA's public data and lets users register, authenticate, and save their favorite space content.

Built as a learning project to practice backend development with FastAPI, PostgreSQL, and JWT authentication.

## Features

- User registration with password hashing (bcrypt)
- JWT-based authentication with protected routes
- Integration with NASA's public APIs (Astronomy Picture of the Day, Mars Rover Photos, solar flares)
- Exoplanet data enriched with an Earth similarity index and a size/temperature classification
- Auto-generated interactive documentation (Swagger UI), usable end to end — including the **Authorize** button
- Graceful handling of external API failures: timeouts, unreachable upstreams and error responses are all translated into explicit status codes instead of a generic 500
- In-memory caching of the exoplanet archive queries, so the statistics endpoints don't re-query a public research archive on every request
- Automated tests that run on SQLite, with no database to install

## Tech Stack

- **FastAPI** — web framework
- **PostgreSQL** — database (via Docker Compose for local development)
- **SQLAlchemy** — ORM
- **python-jose** — JWT token handling
- **passlib + bcrypt** — password hashing
- **pytest** — test suite, run on every push via GitHub Actions

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/` | Health check | No |
| POST | `/auth/register` | Create a new user | No |
| POST | `/auth/login` | Get an access token (JSON body) | No |
| POST | `/auth/token` | Get an access token (OAuth2 form) | No |
| GET | `/auth/me` | Get current user | Yes |
| GET | `/space/picture-of-the-day` | NASA's Astronomy Picture of the Day | No |
| GET | `/mars/photos` | Mars rover photos | No |
| GET | `/exoplanets` | List exoplanets with Earth similarity index | No |
| GET | `/exoplanets/habitable` | Potentially habitable planets, ranked | No |
| GET | `/exoplanets/stats/by-year` | Discoveries per year | No |
| GET | `/exoplanets/stats/summary` | Aggregate statistics | No |
| GET | `/space-weather/flares` | Recent solar flares | No |
| POST | `/favorites` | Create a favorite | Yes |
| GET | `/favorites` | List current user's favorites | Yes |
| DELETE | `/favorites/{id}` | Delete a favorite | Yes |

### Why there are two login endpoints

`/auth/login` takes a JSON body (`{"email": ..., "password": ...}`), which is the
natural shape for a front-end or a script.

`/auth/token` takes an `application/x-www-form-urlencoded` body with `username`
and `password` fields, because that is what the OAuth2 password flow specifies —
and therefore what Swagger UI's **Authorize** button sends. Without a
form-accepting endpoint at the declared `tokenUrl`, that button fails with a
validation error and the protected routes can't be tried from the docs page.

Both return the same bearer token. `username` is the user's email.

## Running Locally

1. Clone the repository and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

2. Start PostgreSQL:

```bash
docker compose up -d
```

3. Create your `.env` file:

```bash
cp .env.example .env
```

Then edit it. The required variables are documented in
[`.env.example`](.env.example): `DATABASE_URL`, `SECRET_KEY` and `NASA_API_KEY`
(a free key is available at https://api.nasa.gov). The app fails on startup with
an explicit message if any of them is missing, rather than breaking later at
request time.

4. Run the server:

```bash
uvicorn main:app --reload
```

Interactive docs available at `http://localhost:8000/docs`.

## Testing

```bash
pytest -v
```

The tests run against an in-memory SQLite database through FastAPI's dependency
override mechanism (see [`conftest.py`](conftest.py)), so they need no running
PostgreSQL instance, touch no development data, and run unchanged in CI.

## Notes

The Mars Rover Photos endpoint depends on a third-party maintained service that is
currently unavailable. The endpoint handles this failure gracefully and returns a
clear error message.

## Earth Similarity Index

The `earth_similarity` score returned by the exoplanet endpoints is a simplified index based only on a planet's radius and equilibrium temperature compared to Earth's own values. It does not replace the scientific habitability models used in real research, which also account for atmosphere composition, host star type, orbital stability, and other factors.

## Roadmap

- [x] Favorites system (save missions and images per user)
- [x] Exoplanet data with habitability index
- [x] Space weather (solar flares)
- [x] Automated tests with pytest
- [x] Deployment
- [x] Continuous integration (tests on every push)
- [ ] Rate limiting on the public endpoints
- [ ] Database migrations with Alembic
