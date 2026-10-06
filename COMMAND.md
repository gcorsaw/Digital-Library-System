# Commands to Run the Digital Library

These instructions run the vanilla web app, FastAPI backend, and PostgreSQL
database together with Docker Compose. From the repository root, this is the
recommended way to run the app.

## One-time setup

Open a terminal in the repository:

```bash
cd /home/grace/Digital-Library-System
```

If you do not already have a local `.env` file, copy the example:

```bash
cp .env.example .env
```

Open `.env` and set your database name, user, and password. Set
`JWT_SECRET_KEY` to a private random value at least 32 characters long. You can
generate one with:

```bash
openssl rand -hex 32
```

Keep `.env` private; it contains credentials and is excluded from Git. Do not
paste its values into chats, screenshots, or source files.

You need Docker with the Compose plugin installed. Check that it is available:

```bash
docker --version
docker compose version
```

## Start the complete app

Build the backend image and start the database, API, and web server:

```bash
docker compose up --build -d
```

Check that all services are running:

```bash
docker compose ps
```

Open the app:

- Web app: <http://localhost:8080>
- API health check: <http://localhost:8001/health>
- API documentation: <http://localhost:8001/docs>

The browser sends API requests to the same origin as the web app. Nginx
forwards `/auth` and `/books` requests to the backend. The backend's local port
is `8001` so it does not conflict with a separate development server on port
`8000`.

## Everyday commands

Follow logs from all services:

```bash
docker compose logs -f
```

Follow just the API logs:

```bash
docker compose logs -f backend
```

Check the API health endpoint:

```bash
curl http://localhost:8001/health
```

Restart the services without rebuilding:

```bash
docker compose restart
```

Rebuild and restart after changing backend code or the Dockerfile:

```bash
docker compose up --build -d
```

Recreate the web server after changing the frontend files or `nginx.conf`:

```bash
docker compose up -d --force-recreate web_ui
```

Stop the app while keeping the PostgreSQL data:

```bash
docker compose down
```

Start it again later:

```bash
docker compose up -d
```

## Database data warning

PostgreSQL data is stored in the `pgdata` Docker volume. The SQL initialization
file runs automatically only when that volume is first created.

To permanently erase the database and start with a fresh one, run:

```bash
docker compose down -v
docker compose up --build -d
```

**The `down -v` command deletes the database volume and all data in it.** Do
not run it unless you intend to erase the database.

## Run backend unit tests

With `uv` installed, run the focused backend unit tests from the repository
root:

```bash
uv run pytest -q test_main_unit.py
```

The database-backed tests in `test_main.py` require a separate PostgreSQL test
database whose name ends in `_test`. They rebuild test tables, so do not point
`TEST_DB_NAME` at your normal application database. The test role also needs
permission to create a schema in that test database.

## Troubleshooting

See recent service logs:

```bash
docker compose logs --tail 100 backend web_ui my_postgres_db
```

If a port is already in use, check these ports: web `8080`, backend `8001`, and
PostgreSQL `5440`. Stop the other process using the conflicting port, or update
the corresponding host-side port in `docker-compose.yaml`.

If you change backend settings such as `JWT_SECRET_KEY` in `.env`, recreate the
backend so it picks up the new values:

```bash
docker compose up -d --force-recreate backend
```

Changing the database username or password in `.env` does not update credentials
inside an already initialized PostgreSQL volume. Update the database role to
match before restarting the backend with changed database credentials.

If signup reports a database permission error, inspect the backend logs first:

```bash
docker compose logs --tail 100 backend
```

The API database role must have permission to use the application tables and
their identity sequences. An existing `pgdata` volume keeps its original
database owners and grants; changing `.env` does not reinitialize or change
those existing database permissions.
