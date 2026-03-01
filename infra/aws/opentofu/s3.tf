# S3 bucket for personal dev blog markdown posts
# Stores blog content with versioning and encryption enabled
# Backend reads posts via IAM credentials (not public access)

resource "aws_s3_bucket" "blog_content" { #trivy:ignore:AVD-AWS-0089 Logging unnecessary for personal blog content bucket
  bucket = var.bucket_name

  tags = {
    Project     = "dev-blog"
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}

# Enable versioning for content safety
resource "aws_s3_bucket_versioning" "blog_content" {
  bucket = aws_s3_bucket.blog_content.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "blog_content" { #trivy:ignore:AVD-AWS-0132 AES256 sufficient for personal blog, KMS overkill
  bucket = aws_s3_bucket.blog_content.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "blog_content" {
  bucket = aws_s3_bucket.blog_content.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Create the content prefix folder
resource "aws_s3_object" "content_prefix" {
  bucket = aws_s3_bucket.blog_content.id
  key    = var.content_prefix
}
