# Kubernetes Deployment Outline

This outline describes a first Kubernetes deployment for the Digital Library
System while keeping the existing Docker Compose setup available for local
development.

## Application components

- **Frontend:** Build the existing HTML, JavaScript, CSS, and Nginx configuration
  into a container image. Run it as a `Deployment` and expose it with a
  `Service`.
- **Backend:** Build the FastAPI application with `Dockerfile.backend`. Run it
  as a `Deployment` and expose it internally with a `Service`.
- **PostgreSQL:** For a local learning cluster, run PostgreSQL with a
  `StatefulSet`, a `Service`, and a persistent volume claim. For production,
  prefer a managed PostgreSQL service.

## Configuration and access

- Put non-sensitive application configuration in a `ConfigMap`.
- Supply database credentials and the JWT signing key through Kubernetes
  `Secret` resources; do not commit real secret values to Git.
- Configure the backend to connect to the PostgreSQL Service on port `5432`.
- Add an `Ingress` later for external HTTP access. Initially, use
  `kubectl port-forward` to test the frontend or backend locally.

## Operational basics

- Add backend readiness and liveness probes using an appropriate health
  endpoint.
- Set CPU and memory requests and limits for the frontend and backend pods.
- Treat database initialization separately: the existing Compose SQL init
  script runs only when PostgreSQL creates a new empty data directory. Plan
  schema migrations and backups before using persistent or production data.

## Suggested implementation order

1. Build and run the backend image in a local Kubernetes cluster.
2. Deploy PostgreSQL for local testing, or configure a managed database.
3. Deploy the frontend image and verify frontend-to-backend routing.
4. Add health probes, resource settings, and external access if needed.
