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

variable "instance_name" {
  description = "Name tag for the EC2 instance"
  type        = string
  default     = "dev-blog-web"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t4.micro"
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance. If empty, the first default VPC subnet is used."
  type        = string
  default     = ""
}

variable "key_name" {
  description = "Optional EC2 key pair name for SSH access"
  type        = string
  default     = ""
}

variable "route53_zone_name" {
  description = "Public Route53 hosted zone name"
  type        = string
  default     = "aacecan.com"
}

variable "dev_domain_name" {
  description = "Primary blog domain"
  type        = string
  default     = "dev.aacecan.com"
}

variable "www_domain_name" {
  description = "WWW alias domain"
  type        = string
  default     = "www.dev.aacecan.com"
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into the instance"
  type        = string
  default     = ""
}

variable "letsencrypt_email" {
  description = "Email used by Let's Encrypt ACME registration"
  type        = string
  default     = ""
}
