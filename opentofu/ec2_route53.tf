data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

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

data "aws_route53_zone" "public" {
  name         = var.route53_zone_name
  private_zone = false
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "blog_s3_read" {
  statement {
    sid = "ListBlogBucket"

    actions = [
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.blog_content.arn,
    ]
  }

  statement {
    sid = "ReadBlogPosts"

    actions = [
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.blog_content.arn}/${trim(var.content_prefix, "/")}/*",
    ]
  }
}

locals {
  selected_subnet_id = var.subnet_id != "" ? var.subnet_id : sort(data.aws_subnets.default.ids)[0]
  caddy_email        = var.letsencrypt_email != "" ? var.letsencrypt_email : "dev@${var.route53_zone_name}"
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

resource "aws_iam_role_policy_attachment" "blog_ec2_ssm" {
  role       = aws_iam_role.blog_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "blog_ec2_ecr_read" {
  role       = aws_iam_role.blog_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy" "blog_ec2_s3_read" {
  name   = "${var.instance_name}-s3-read"
  role   = aws_iam_role.blog_ec2.id
  policy = data.aws_iam_policy_document.blog_s3_read.json
}

resource "aws_iam_instance_profile" "blog_ec2" {
  name = "${var.instance_name}-profile"
  role = aws_iam_role.blog_ec2.name
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

  instance_market_options {
    market_type = "spot"

    spot_options {
      spot_instance_type             = "persistent"
      instance_interruption_behavior = "stop"
    }
  }

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
    API_IMAGE=733077684693.dkr.ecr.eu-west-1.amazonaws.com/dev-blog-api:latest
    WEB_IMAGE=733077684693.dkr.ecr.eu-west-1.amazonaws.com/dev-blog-web:latest
    AWS_REGION=${var.aws_region}
    S3_BUCKET_NAME=${var.bucket_name}
    CONTENT_PREFIX=${var.content_prefix}
    DOMAIN=${var.dev_domain_name}
    WWW_DOMAIN=${var.www_domain_name}
    CADDY_EMAIL=${local.caddy_email}
    CORS_ORIGINS='["https://${var.dev_domain_name}","https://${var.www_domain_name}"]'
    ENVFILE

    chown ec2-user:ec2-user /opt/dev-blog/.env

    ECR_REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${var.aws_region}.amazonaws.com
    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin "$ECR_REGISTRY"
    cd /opt/dev-blog && docker compose up -d
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

resource "aws_route53_record" "dev" {
  zone_id = data.aws_route53_zone.public.zone_id
  name    = var.dev_domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.blog_vip.public_ip]
}

resource "aws_route53_record" "www_dev" {
  zone_id = data.aws_route53_zone.public.zone_id
  name    = var.www_domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.blog_vip.public_ip]
}
