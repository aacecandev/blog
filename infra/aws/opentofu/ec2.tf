data "aws_ami" "blog" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["dev-blog-*"]
  }

  filter {
    name   = "tag:Project"
    values = ["dev-blog"]
  }

  filter {
    name   = "tag:ManagedBy"
    values = ["packer"]
  }
}

resource "aws_iam_role" "blog_ec2" {
  name               = "${var.instance_name}-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name        = "${var.instance_name}-role"
    Project     = "dev-blog"
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}

resource "aws_security_group" "blog_web" {
  name        = "${var.instance_name}-sg"
  description = "Security group for dev blog web instance"
  vpc_id      = data.aws_vpc.default.id

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

  dynamic "ingress" {
    for_each = var.allowed_ssh_cidr != "" ? [var.allowed_ssh_cidr] : []
    content {
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.instance_name}-sg"
    Project     = "dev-blog"
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}

resource "aws_instance" "blog_web" {
  ami                    = data.aws_ami.blog.id
  instance_type          = var.instance_type
  subnet_id              = local.selected_subnet_id
  vpc_security_group_ids = [aws_security_group.blog_web.id]
  iam_instance_profile   = aws_iam_instance_profile.blog_ec2.name
  key_name               = var.key_name != "" ? var.key_name : null

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    encrypted = true
  }

  user_data = <<-EOT
    #!/bin/bash
    set -euxo pipefail

    cat > /opt/dev-blog/.env <<ENVFILE
    API_IMAGE=${aws_ecr_repository.backend.repository_url}:latest
    WEB_IMAGE=${aws_ecr_repository.frontend.repository_url}:latest
    AWS_REGION=${var.aws_region}
    S3_BUCKET_NAME=${var.bucket_name}
    CONTENT_PREFIX=${var.content_prefix}
    DOMAIN=${var.dev_domain_name}
    WWW_DOMAIN=${var.www_domain_name}
    CADDY_EMAIL=${local.caddy_email}
    CORS_ORIGINS='["https://${var.dev_domain_name}","https://${var.www_domain_name}"]'
    ENVFILE

    chown ec2-user:ec2-user /opt/dev-blog/.env

    systemctl start dev-blog.service
  EOT

  tags = {
    Name        = var.instance_name
    Project     = "dev-blog"
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}

resource "aws_eip" "blog_vip" {
  domain = "vpc"

  tags = {
    Name        = "${var.instance_name}-vip"
    Project     = "dev-blog"
    Environment = var.environment
    ManagedBy   = "opentofu"
  }
}

resource "aws_eip_association" "blog_vip" {
  allocation_id = aws_eip.blog_vip.id
  instance_id   = aws_instance.blog_web.id
}
