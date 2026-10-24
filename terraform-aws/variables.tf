variable "aws_region" {
  description = "AWS region used for the application infrastructure and Cognito user pool."
  type        = string
  default     = "us-east-1"
}

variable "frontend_bucket_name" {
  description = "Globally unique S3 bucket name for the static frontend."
  type        = string

  validation {
    condition     = length(var.frontend_bucket_name) >= 3 && length(var.frontend_bucket_name) <= 63
    error_message = "The frontend bucket name must be between 3 and 63 characters."
  }
}

variable "api_certificate_arn" {
  description = "ACM certificate ARN for the HTTPS API listener and CloudFront API origin."
  type        = string
  default     = null
  nullable    = true
}

variable "api_domain_name" {
  description = "DNS name covered by api_certificate_arn and pointed at the API load balancer."
  type        = string
  default     = null
  nullable    = true
}
