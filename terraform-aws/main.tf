# terraform-aws/main.tf

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_cloudfront_cache_policy" "api_caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "api_forward_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# ==========================================
# NETWORKING STRATEGY LAYERS (VPC BLOCK)
# ==========================================

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "digital-library-vpc" }
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "library-gateway" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public_rt.id
}

# ==========================================
# SECURITY GROUP POLICIES
# ==========================================

resource "aws_security_group" "lb_sg" {
  name        = "load-balancer-security-rules"
  description = "Allows wide inbound HTTP routing limits down to proxy entry targets"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ==========================================
# APPLICATION LOAD BALANCER COMPONENT
# ==========================================

resource "aws_alb" "external_lb" {
  name               = "library-routing-proxy-balancer"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.lb_sg.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_lb_target_group" "api_tg" {
  name        = "backend-service-routing-pool"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http_entry" {
  load_balancer_arn = aws_alb.external_lb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = var.api_certificate_arn == null ? "fixed-response" : "redirect"

    dynamic "redirect" {
      for_each = var.api_certificate_arn == null ? [] : [true]
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "fixed_response" {
      for_each = var.api_certificate_arn == null ? [true] : []
      content {
        content_type = "text/plain"
        message_body = "HTTPS certificate required for API access."
        status_code  = "503"
      }
    }
  }
}

resource "aws_lb_listener" "https_entry" {
  count             = var.api_certificate_arn == null ? 0 : 1
  load_balancer_arn = aws_alb.external_lb.arn
  port              = "443"
  protocol          = "HTTPS"
  certificate_arn   = var.api_certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  lifecycle {
    precondition {
      condition     = var.api_domain_name != null && trimspace(var.api_domain_name) != ""
      error_message = "api_domain_name is required when api_certificate_arn is configured."
    }
  }

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}

# ==========================================
# AWS COGNITO SECURE VERIFICATION SYSTEMS
# ==========================================

resource "aws_cognito_user_pool" "library_pool" {
  name = "digital-library-cognito-pool"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

}

resource "aws_cognito_user_pool_client" "library_client" {
  name         = "library-app-client"
  user_pool_id = aws_cognito_user_pool.library_pool.id

  read_attributes  = ["email", "email_verified"]
  write_attributes = ["email"]

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]
  prevent_user_existence_errors = "ENABLED"
}

# ==========================================
# S3 FRONTEND BUCKET LAYER
# ==========================================

resource "aws_s3_bucket" "frontend" {
  bucket = var.frontend_bucket_name
}

resource "aws_s3_bucket_public_access_block" "block_public" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ==========================================
# CLOUDFRONT DISTRIBUTION SETUP
# ==========================================

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "frontend-s3-oac"
  description                       = "Allows secure interaction maps out between cloudfront edge layers and S3 buckets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "cdn" {
  lifecycle {
    precondition {
      condition = (
        (var.api_certificate_arn == null) == (var.api_domain_name == null) &&
        (var.api_domain_name == null || trimspace(var.api_domain_name) != "")
      )
      error_message = "Set a non-empty api_domain_name and api_certificate_arn together, or leave both unset."
    }
  }

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-Static-Frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  dynamic "origin" {
    for_each = var.api_certificate_arn != null && var.api_domain_name != null ? [true] : []
    content {
      domain_name = var.api_domain_name
      origin_id   = "Backend-API"

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-Static-Frontend"

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  dynamic "ordered_cache_behavior" {
    for_each = var.api_certificate_arn != null && var.api_domain_name != null ? [
      "/auth/*",
      "/books*",
      "/games*",
      "/health",
    ] : []
    content {
      path_pattern             = ordered_cache_behavior.value
      target_origin_id         = "Backend-API"
      viewer_protocol_policy   = "redirect-to-https"
      allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods           = ["GET", "HEAD", "OPTIONS"]
      cache_policy_id          = data.aws_cloudfront_cache_policy.api_caching_disabled.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.api_forward_viewer_except_host.id
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Environment = "Production" }
}

# S3 Policy linking distribution connection tunnels together smoothly
resource "aws_s3_bucket_policy" "allow_cloudfront" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.cdn.arn
          }
        }
      }
    ]
  })
}