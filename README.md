# MyApp

## Digital Library app

Run the vanilla frontend, API, and database together from the repository root:

```bash
docker compose up --build -d
```

Open [http://localhost:8080](http://localhost:8080). The frontend sends API
requests to the same origin, and Nginx proxies `/auth`, `/books`, and `/games`
to the backend. Each account has a private PostgreSQL schema in the shared
database; schemas are created empty when a user registers or first signs in.
Existing shared catalog data is left untouched and is not copied into personal
schemas. The backend API is also available locally at
[http://localhost:8001](http://localhost:8001); this avoids conflicting with a
locally running `uv run fastapi dev` server on port 8000.

To apply frontend or Nginx configuration changes, recreate the web service:

```bash
docker compose up -d --force-recreate web_ui
```

This project was generated with [Angular CLI](https://github.com/angular/angular-cli) version 17.3.17.

## Development server

Run `ng serve` for a dev server. Navigate to `http://localhost:4200/`. The application will automatically reload if you change any of the source files.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory.

## Running unit tests

Run `ng test` to execute the unit tests via [Karma](https://karma-runner.github.io).

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via a platform of your choice. To use this command, you need to first add a package that implements end-to-end testing capabilities.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI Overview and Command Reference](https://angular.io/cli) page.
