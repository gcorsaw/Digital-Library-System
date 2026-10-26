# Commands to Run the Digital Library

These instructions run the vanilla web app, FastAPI backend, and PostgreSQL
database together with Docker Compose. From the repository root, this is the
recommended way to run the app.

## Copy the project to your own directory

This copies the complete project folder, including hidden files, into a new
folder in your home directory. It stops rather than merging with a destination
folder that already exists:

```bash
test ! -e "$HOME/Digital-Library-System-copy" || {
  printf 'Destination already exists: %s\n' "$HOME/Digital-Library-System-copy" >&2
  exit 1
}
cp -a /home/grace/Digital-Library-System "$HOME/Digital-Library-System-copy"
```

To choose a different destination, replace both occurrences of
`$HOME/Digital-Library-System-copy` with the directory you want. This is a full
copy, so it also copies `.git`, local environment files such as `.env`, and
installed dependencies such as `.venv` or `node_modules` if they exist. Keep
the copied `.env` private; it may contain passwords and secret keys.

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
forwards `/auth`, `/books`, and `/games` requests to the backend. The backend's
local port is `8001` so it does not conflict with a separate development server
on port `8000`.

Each registered account gets a private PostgreSQL schema in the shared
database. A schema is created empty during registration or on the first
authenticated request for an existing account; the existing shared catalog is
not copied or deleted. The backend database role must have permission to create
schemas.

## Switch Cognito from local to AWS

This keeps the Compose-hosted frontend, backend, and database in place; only
the Cognito provider changes. You need an AWS user pool and a public app client
in the same region. The client must have no client secret and allow
`ALLOW_USER_PASSWORD_AUTH`; the pool must have email verification enabled.

Set the Cognito values in the repository-root `.env`. Leave the AWS endpoint
empty so the backend uses AWS rather than the local emulator:

```dotenv
USE_COGNITO=true
AWS_REGION=<aws-region>
AWS_COGNITO_ENDPOINT=
COGNITO_USER_POOL_ID=<aws-user-pool-id>
COGNITO_CLIENT_ID=<aws-app-client-id>
```

Recreate the backend to load the values, then check its health:

```bash
docker compose up -d --build --force-recreate backend
docker compose ps backend
curl -i http://localhost:8001/health
```

Register through the app at <http://localhost:8080>. AWS sends the confirmation
code through the pool's configured email delivery; the local development code
is not returned in AWS mode. Keep AWS credentials out of `.env` when using the
local backend; use the AWS CLI's standard credential chain or an AWS profile
for Terraform.

### Provision a Cognito pool with this repository's Terraform

The `terraform-aws/` module provisions a Cognito pool and app client but also
creates VPC, load-balancer, S3, and CloudFront resources. Review the complete
plan and AWS costs before applying. It does not deploy the backend or database.
If you already have the module provisioned, skip `apply` and read the existing
outputs instead.

Run from the repository root, replacing the bucket name with a globally unique
name:

```bash
terraform -chdir=terraform-aws init
terraform -chdir=terraform-aws plan \
  -var="frontend_bucket_name=<globally-unique-bucket-name>"
terraform -chdir=terraform-aws apply \
  -var="frontend_bucket_name=<globally-unique-bucket-name>"
```

After applying, retrieve the non-secret Cognito settings and copy them into the
root `.env` as shown above:

```bash
terraform -chdir=terraform-aws output -raw aws_region
terraform -chdir=terraform-aws output -raw cognito_user_pool_id
terraform -chdir=terraform-aws output -raw cognito_client_id
```

To switch back to Cognito Local, restore
`AWS_COGNITO_ENDPOINT=http://cognito-local:9229` in `.env` and recreate the
backend.

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

Recreate the web server after changing frontend files such as `script.js` or
`index.html`, or after changing `nginx.conf`:

```bash
docker compose up -d --force-recreate web_ui
```

Then refresh the browser to load the updated page and JavaScript.

Stop the app while keeping the PostgreSQL data:

```bash
docker compose down
```

Start it again later:

```bash
docker compose up -d
```

## Deploy through GitHub Actions on this computer

The workflow in `.github/workflows/deploy.yml` runs tests and builds images on
GitHub-hosted runners. On a push to `main`, it deploys with Docker Compose on
your Linux self-hosted runner. The app is served at
<http://localhost:8080>; the API health endpoint is
<http://localhost:8001/health>. This is a personal/development deployment:
the computer must remain on, online, and able to run Docker.

### Configure the runner

Register a Linux runner for this repository in **GitHub → Settings → Actions
→ Runners → New self-hosted runner**. Follow the commands GitHub shows; do not
share the temporary registration token. The workflow expects runner labels
`self-hosted`, `linux`, and `x64`.

Run the runner in the foreground from its installation directory, for example:

```bash
cd "$HOME/Digital-Library-System/actions-runner"
./run.sh
```

Keep that terminal open while waiting for jobs. Alternatively, install it as a
service so it can run without an open terminal. If `./run.sh` is currently
running, stop it with Ctrl+C before installing the service:

```bash
cd "$HOME/Digital-Library-System/actions-runner"
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

The runner account must be able to run `docker compose` without an interactive
sudo prompt. Confirm this from the repository root:

```bash
cd "$HOME/Digital-Library-System"
docker compose version
docker ps
```

Treat a self-hosted runner as privileged: it can execute workflow commands on
your computer. Only run trusted repository workflows on it, and do not run
untrusted pull-request jobs on this runner.

### Add deployment secrets to GitHub

Create the `production` environment under **GitHub → Settings → Environments**
if it does not exist. Add environment secrets named `DB_USER`, `DB_PASSWORD`,
and `JWT_SECRET_KEY`. Their values must match the PostgreSQL credentials used
by this app's Compose configuration. The JWT key must be at least 32 characters.
For an existing database volume, use the same database user and password that
were set when that database was initialized.

You can add each value interactively with GitHub CLI, avoiding secret values in
shell history:

```bash
gh auth status
gh secret set DB_USER --env production
gh secret set DB_PASSWORD --env production
gh secret set JWT_SECRET_KEY --env production
```

Enter the secret value when prompted. Do not put real credentials into this
file, the workflow YAML, or a Git commit. `KUBE_CONFIG` is not used for this
Docker Compose deployment.

### Trigger and monitor a deployment

After the workflow changes and secrets are configured, commit and push to
`main` (or merge a pull request into `main`). The workflow runs tests first;
the self-hosted deploy job starts only after they pass.

```bash
cd "$HOME/Digital-Library-System"
git status
git add .github/workflows/deploy.yml .gitignore README.md COMMAND.md test_main_unit.py
git commit -m "Document self-hosted Compose deployment"
git push origin main
```

Keep the runner online, then monitor the run in the repository's **Actions**
tab. With GitHub CLI, list and watch runs with:

```bash
gh run list --workflow deploy.yml
gh run watch
```

After a successful deploy, verify the app:

```bash
docker compose ps
curl --fail --show-error http://localhost:8080/
curl --fail --show-error http://localhost:8001/health
```

If the deploy fails, inspect the failed workflow step in Actions and check
service logs from the repository root:

```bash
docker compose logs --tail=100 backend
docker compose logs --tail=100 my_postgres_db
```

The workflow runs the test and image-build jobs for pull requests on GitHub's
hosted runners, not on your self-hosted machine. It deploys only after a push
to `main`.

## Run on Kubernetes with Kustomize

These commands deploy the manifests in `k8s/` instead of using Docker Compose.
This walkthrough uses the Minikube cluster and context named `minikube`. It
assumes Docker, Minikube, `kubectl`, and OpenSSL are installed. `kubectl`
includes Kustomize support, so installing the separate `kustomize` command is
optional. Run the commands from the repository root.

If your terminal is currently in the `k8s/` directory, return to the
repository root first:

```bash
cd ..
```

### Check Minikube and kubectl status

Use these commands to check whether Minikube is running and whether `kubectl`
can reach the Minikube cluster:

```bash
minikube status
kubectl config current-context
kubectl cluster-info
kubectl get nodes
kubectl get pods,services,persistentvolumeclaims --all-namespaces
```

`minikube status` reports the Minikube host, kubelet, API server, and kubeconfig
state. `kubectl config current-context` shows which cluster `kubectl` targets;
for this walkthrough it should print `minikube`. `kubectl cluster-info` and
`kubectl get nodes` verify that the Kubernetes API server responds. The final
command summarizes workloads and storage across namespaces. If `kubectl`
reports connection refused, check `minikube status` and start the cluster
before retrying.

### Start Minikube and verify the connection

This starts the existing Minikube cluster; it does not delete or recreate it.
Select its context and confirm that the API server is reachable:

```bash
minikube start
kubectl config use-context minikube
kubectl config current-context
kubectl cluster-info
kubectl get nodes
```

### Build and load the images

Build the images from the repository root, then load them into Minikube:

```bash
docker build -f Dockerfile.backend -t digital-library-backend:local .
docker build -f Dockerfile.frontend -t digital-library-frontend:local .
minikube image load digital-library-backend:local
minikube image load digital-library-frontend:local
```

### Create the Kubernetes Secret

The backend and PostgreSQL manifests both require `library-secrets`. This
copy-and-paste block creates it only if it does not already exist. It generates
a database password and a 32-byte JWT signing key without printing either.
If the Secret already exists, the block leaves it unchanged.

```bash
if kubectl get secret library-secrets >/dev/null 2>&1; then
  echo "Secret library-secrets already exists; leaving it unchanged."
else
  DB_USER=postgres
  DB_PASSWORD="$(openssl rand -hex 24)"
  JWT_SECRET_KEY="$(openssl rand -hex 32)"
  kubectl create secret generic library-secrets \
    --from-literal=DB_USER="$DB_USER" \
    --from-literal=DB_PASSWORD="$DB_PASSWORD" \
    --from-literal=JWT_SECRET_KEY="$JWT_SECRET_KEY"
  unset DB_USER DB_PASSWORD JWT_SECRET_KEY
fi
```

The generated database password is stored in the Secret and used by PostgreSQL
and the backend. Keep the Secret private. To check its key names without
printing values, run:

```bash
kubectl describe secret library-secrets
```

### Apply the manifests and wait for readiness

Apply the resources:

```bash
kubectl apply -k k8s/
```

Wait for PostgreSQL to become ready **before restarting the backend**. This
avoids the backend's initial startup racing Kubernetes DNS and the database:

```bash
kubectl rollout status statefulset/postgres --timeout=180s
kubectl rollout restart deployment/backend
kubectl rollout status deployment/backend --timeout=180s
kubectl rollout status deployment/frontend --timeout=180s
```

Review the final Pod, Service, and storage status:

```bash
kubectl get pods,services,persistentvolumeclaims
```

### Initialize the PostgreSQL schema

The Kubernetes PostgreSQL manifest does not automatically load the project's
SQL initialization script. For a new, empty database, initialize it after
PostgreSQL is ready:

```bash
kubectl exec -i statefulset/postgres -- sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < digital-library-system.sql
```

**Warning:** `digital-library-system.sql` drops and recreates application
tables and adds sample data. Run it only against a new database or when you
intentionally want to reset those tables. Do not rerun it on a database
containing data you need to keep.

### Fix or rotate the JWT secret

If registration fails with an error saying `JWT_SECRET_KEY` must be at least
32 characters, update the existing Secret with a newly generated key and
restart the backend. This invalidates existing login tokens:

```bash
JWT_SECRET_KEY="$(openssl rand -hex 32)"
kubectl create secret generic library-secrets \
  --from-literal=JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  --dry-run=client -o yaml |
  kubectl apply -f -
unset JWT_SECRET_KEY
kubectl rollout restart deployment/backend
kubectl rollout status deployment/backend --timeout=180s
```

### Open the frontend

The frontend Service listens on port 8081 and forwards traffic to the
container's port 80. Forward it to port 8081 on your computer:

```bash
kubectl port-forward service/frontend 8081:8081
```

Keep that command running while using the app at
<http://localhost:8081>. Press Ctrl+C to stop port forwarding.

### Diagnose a backend startup failure

This block finds the current backend Pod by its label, prints its events and
the previous crashed container's logs, then shows Secret key names without
revealing Secret values:

```bash
POD="$(kubectl get pods -l app=backend -o jsonpath='{.items[0].metadata.name}')"
if [ -n "$POD" ]; then
  kubectl describe pod "$POD"
  kubectl logs "$POD" -c backend --previous --tail=100
  kubectl logs "$POD" -c backend --tail=100
else
  echo "No backend Pod found."
fi
kubectl describe secret library-secrets
```

If the previous container has no logs yet, `kubectl logs ... --previous` may
report that no previous container is available; the current-container logs
printed next are still useful.

### Stop or restart Minikube

When you are finished using the cluster, stop it without deleting its
resources or persistent database volume:

```bash
minikube stop
```

Start the same cluster again later:

```bash
minikube start
kubectl config use-context minikube
kubectl cluster-info
```

Do not remove the Minikube Docker container with `docker rm`; Minikube manages
that container as the Kubernetes node. `minikube delete` permanently removes
the cluster and its stored data, including the PostgreSQL data. Run it only
when you intentionally want to discard the whole cluster.

To remove the deployed resources later:

```bash
kubectl delete -k k8s/
```

Deleting the manifests does not necessarily delete PostgreSQL's persistent
volume claim or its data. Delete the claim only if you intentionally want to
erase that data:

```bash
kubectl delete persistentvolumeclaim postgres-data-postgres-0
```

## GitHub branch, pull, merge, and push commands

Run these from the repository root. Replace `main` with the repository's
default branch if it uses a different name, and replace the example feature
branch name with one that describes your work.

Check your current branch, working-tree changes, and GitHub remote:

```bash
git status
git branch --show-current
git remote -v
```

If no remote is listed, add your GitHub repository as `origin` (replace the
URL with your repository's URL):

```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git
```

Get the latest default branch and create a feature branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/describe-your-change
```

Stage and commit your changes:

```bash
git add .
git status
git commit -m "Describe your change"
```

Push the new branch to GitHub and set its upstream, so later pushes can use
`git push`:

```bash
git push -u origin feature/describe-your-change
```

To update your feature branch with the latest default branch, first fetch the
latest remote commits, then merge them into your feature branch:

```bash
git switch feature/describe-your-change
git fetch origin
git merge origin/main
```

If there are merge conflicts, edit the files to resolve the marked sections,
then stage the resolved files and complete the merge:

```bash
git status
git add path/to/resolved-file
git commit
```

Push the updated feature branch:

```bash
git push
```

You can then open a pull request on GitHub to merge the feature branch into
`main`. After the pull request is merged, update your local default branch:

```bash
git switch main
git pull --ff-only origin main
```

Alternatively, to merge locally instead of using a GitHub pull request, update
`main`, merge the feature branch, and push `main`:

```bash
git switch main
git pull --ff-only origin main
git merge --no-ff feature/describe-your-change
git push origin main
```

Review `git status` and the changes before committing or pushing. Do not commit
`.env` or other credentials.

### Common branch problems

If Git will not let you switch branches because you have uncommitted changes,
either commit them or temporarily stash them. To stash tracked and untracked
files:

```bash
git status
git stash push -u -m "work in progress"
git switch feature/describe-your-change
```

Restore the stashed changes when ready:

```bash
git stash list
git stash pop
```

If the branch already exists locally and `git switch -c` says it cannot create
it, switch to it without `-c`:

```bash
git switch feature/describe-your-change
```

If the branch exists on GitHub but not locally, fetch it and create a local
branch that tracks the remote:

```bash
git fetch origin
git switch --track origin/feature/describe-your-change
```

If a push is rejected because the remote branch has commits you do not have,
fetch and merge the remote branch, resolve any conflicts, then push again:

```bash
git fetch origin
git merge origin/feature/describe-your-change
git push
```

If a merge has conflicts, use `git status` to see which files need attention.
Edit each file to resolve the conflict markers, then stage the resolved files
and finish the merge:

```bash
git status
git add path/to/resolved-file
git commit
```

If you want to cancel a merge before completing it, run:

```bash
git merge --abort
```

If GitHub says you cannot push to a protected default branch, do not force
push. Create or switch to a feature branch, push that branch, and open a pull
request:

```bash
git switch -c feature/describe-your-change
git push -u origin feature/describe-your-change
```

### Delete a branch

Before deleting a branch, check its status and make sure any work you want to
keep has been merged or pushed:

```bash
git status
git branch --merged main
git branch -vv
```

To delete a local branch, first switch to a different branch. The safe `-d`
option deletes the branch only if Git considers it fully merged:

```bash
git switch main
git branch -d feature/describe-your-change
```

To also delete the branch from GitHub:

```bash
git push origin --delete feature/describe-your-change
git fetch --prune origin
```

If Git says the branch is not fully merged, do not immediately force-delete
it. Review commits that are not in `main` and preserve any work you need:

```bash
git log --oneline main..feature/describe-your-change
git diff main...feature/describe-your-change
```

Merge or push the branch if its changes should be kept. Only if you have
confirmed that you no longer need its unmerged changes, delete the local branch
with the force option:

```bash
git branch -D feature/describe-your-change
```

If Git says the branch is currently checked out, switch to another branch
first. If GitHub refuses to delete a remote branch, check that you have write
permission and that branch protection rules allow deletion.

Avoid `git push --force` and commands that discard local changes unless you
understand exactly what will be lost. Check `git status` before recovery
commands.

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
permission to create schemas in that test database.

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