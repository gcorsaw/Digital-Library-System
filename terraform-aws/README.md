# AWS and Cognito deployment

This Terraform module provisions the Cognito user pool and public app client,
along with the repository's VPC, load balancer, S3 bucket, and CloudFront
distribution. It does not provision PostgreSQL or deploy/register a backend
workload with the load balancer. Those services must be deployed separately
and attached to the API target group before end-to-end authentication works.

## Provision resources

Use an AWS profile or another standard AWS credential provider with permission
to create the resources in this module. Choose an S3 bucket name that is
globally unique:

```sh
terraform init
terraform plan -var="frontend_bucket_name=<globally-unique-bucket-name>"
terraform apply -var="frontend_bucket_name=<globally-unique-bucket-name>"
```

To route browser API requests securely through CloudFront, supply an ACM
certificate ARN and `api_domain_name`. The certificate must cover that DNS
name and exist in the same AWS region as the load balancer. Point the API DNS
name to the load balancer. CloudFront then forwards `/auth/*`, `/books*`,
`/games*`, and `/health` to the API over HTTPS with caching disabled. Without
these optional values, the HTTP listener returns `503` and CloudFront serves
only the static frontend:

```sh
terraform apply \
  -var="frontend_bucket_name=<globally-unique-bucket-name>" \
  -var="api_certificate_arn=<acm-certificate-arn>" \
  -var="api_domain_name=<api-domain-name>"
```

The API target group is configured for EC2 instances on port 8000, but this
module does not create instances or register targets. Deploy the backend on
reachable infrastructure and register healthy targets in that target group;
otherwise API requests will fail even though Cognito and the frontend
infrastructure exist.

The module outputs `aws_region`, `cognito_user_pool_id`, and
`cognito_client_id`. Set those values and `USE_COGNITO=true` in the backend
environment. Cognito IDs are identifiers, not secrets. Keep `JWT_SECRET_KEY`,
database credentials, and other secrets in a Kubernetes Secret or a local
environment file; do not commit them.

The Kubernetes frontend image uses the root-level `index.html`, `script.js`,
and `styles.css`, served by Nginx. Its API calls use same-origin paths, so the
Nginx configuration proxies them to the in-cluster `backend` Service. The
Angular app under `angular-library-user-interface/` is a separate frontend and
is not what `Dockerfile.frontend` packages.

For a Kubernetes test deployment, update the `backend-config` ConfigMap in
`k8s/backend.yaml` with the Terraform outputs and set `USE_COGNITO` to
`"true"`, then apply the ConfigMap and restart the backend. After Terraform has
been applied, this command block copies the non-secret Cognito outputs
into the Kubernetes ConfigMap. Run it from the repository root:

```sh
AWS_REGION="$(terraform -chdir=terraform-aws output -raw aws_region)"
COGNITO_USER_POOL_ID="$(terraform -chdir=terraform-aws output -raw cognito_user_pool_id)"
COGNITO_CLIENT_ID="$(terraform -chdir=terraform-aws output -raw cognito_client_id)"
kubectl patch configmap backend-config --type merge \
  -p "{\"data\":{\"USE_COGNITO\":\"true\",\"AWS_REGION\":\"$AWS_REGION\",\"COGNITO_USER_POOL_ID\":\"$COGNITO_USER_POOL_ID\",\"COGNITO_CLIENT_ID\":\"$COGNITO_CLIENT_ID\"}}"
unset AWS_REGION COGNITO_USER_POOL_ID COGNITO_CLIENT_ID
kubectl rollout restart deployment/backend
kubectl rollout status deployment/backend --timeout=180s
```

The cluster needs outbound HTTPS access to Cognito. The deployed root-level
static frontend already offers local and Cognito signup/sign-in choices. For a
public AWS deployment, publish the root-level `index.html`, `script.js`, and
`styles.css` to the Terraform S3 bucket and ensure `api_domain_name` resolves
to the load balancer with a valid certificate. CloudFront then routes the
frontend's same-origin API paths to that HTTPS API domain.

When changing the frontend for Minikube, rebuild and reload its image before
restarting the frontend Deployment:

```sh
docker build -f Dockerfile.frontend -t digital-library-frontend:local .
minikube image load digital-library-frontend:local
kubectl rollout restart deployment/frontend
kubectl rollout status deployment/frontend --timeout=180s
```

Cognito sign-up requires email confirmation. The pool's default email delivery
is suitable for initial testing; configure Amazon SES and its verified sender
before relying on production-scale email delivery.
