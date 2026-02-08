variable "bucket_name" {
  description = "Name of the S3 bucket for storing blog posts"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region for the S3 bucket"
  type        = string
  default     = "eu-west-1"
}

variable "content_prefix" {
  description = "S3 prefix for blog post content"
  type        = string
  default     = "posts/"
}
