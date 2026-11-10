# Kubernetes Deployment Outline

This outline describes a first Kubernetes deployment for the Digital Library
System while keeping the existing Docker Compose setup available for local
development.

## Application components

- **Frontend:** Build the root HTML, JavaScript, CSS, and Nginx configuration
  into a container image. Nginx serves the UI on port `80` and proxies `/auth`,
  `/books`, and `/games` to the backend Service, keeping browser API requests
  on the same origin.
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
- The frontend Service listens on port `8081` and targets container port `80`.
  Its Nginx API proxy targets the in-cluster `backend:8000` Service.

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

## Local cluster deployment

The manifests expect images named `digital-library-backend:local` and
`digital-library-frontend:local`, plus a Secret named `library-secrets` with
`DB_USER`, `DB_PASSWORD`, and a `JWT_SECRET_KEY` of at least 32 characters.
Create the Secret in the namespace where the application will run; do not put
real values in the manifests or source control. For example:

```sh
kubectl create secret generic library-secrets \
  --from-literal=DB_USER='<database-user>' \
  --from-literal=DB_PASSWORD='<database-password>' \
  --from-literal=JWT_SECRET_KEY='<at-least-32-character-signing-key>'
```

Build both images from the repository root, then make them available to the
selected cluster (for example, `minikube image load` or the equivalent for the
local cluster):

```sh
docker build -t digital-library-backend:local -f Dockerfile.backend .
docker build -t digital-library-frontend:local \
  -f Dockerfile.frontend .
# For Minikube, load the locally built images into its node:
minikube image load digital-library-backend:local
minikube image load digital-library-frontend:local
kubectl apply -k k8s/
kubectl port-forward service/frontend 8081:8081
```

For another local cluster, use its equivalent image-loading command before
applying the manifests.

Open `http://localhost:8081`. The frontend sends API requests through its Nginx
proxy, so the browser does not need to resolve the backend Service name or use
a hard-coded localhost API address. PostgreSQL uses a persistent volume claim;
the cluster must have a storage provisioner that can satisfy it.
