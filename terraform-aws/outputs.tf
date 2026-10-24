# AWS region containing the Cognito user pool.
output "aws_region" {
  description = "AWS region containing the Cognito user pool."
  value       = var.aws_region
}

# Cognito user-pool ID for application configuration.
output "cognito_user_pool_id" {
  description = "User-pool ID to configure as COGNITO_USER_POOL_ID."
  value       = aws_cognito_user_pool.library_pool.id
}

# Public Cognito app-client ID for application configuration.
output "cognito_client_id" {
  description = "Public app-client ID to configure as COGNITO_CLIENT_ID."
  value       = aws_cognito_user_pool_client.library_client.id
}

# Cognito issuer URL used to validate access tokens.
output "cognito_issuer" {
  description = "Issuer URL used to validate Cognito access tokens."
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.library_pool.id}"
}

# Name of the S3 bucket that stores the frontend.
output "frontend_bucket_name" {
  description = "S3 bucket created for the frontend."
  value       = aws_s3_bucket.frontend.bucket
}

# HTTPS URL of the CloudFront frontend distribution.
output "frontend_url" {
  description = "CloudFront URL for the frontend."
  value       = "https://${aws_cloudfront_distribution.cdn.domain_name}"
}

# Public DNS name of the API load balancer.
output "backend_load_balancer_dns" {
  description = "Public DNS name of the API load balancer."
  value       = aws_alb.external_lb.dns_name
}

# HTTPS API URL, or null when a custom domain is not configured.
output "backend_api_url" {
  description = "HTTPS API base URL when a custom domain has been configured."
  value       = var.api_certificate_arn == null || var.api_domain_name == null ? null : "https://${var.api_domain_name}"
}
