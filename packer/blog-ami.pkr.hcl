packer {
  required_plugins {
    amazon = {
      version = ">= 1.3.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "ami_name_prefix" {
  type    = string
  default = "dev-blog"
}

data "amazon-ami" "al2023" {
  filters = {
    name                = "al2023-ami-*-x86_64"
    virtualization-type = "hvm"
    root-device-type    = "ebs"
  }
  most_recent = true
  owners      = ["amazon"]
  region      = var.aws_region
}

locals {
  timestamp = formatdate("YYYYMMDD-hhmmss", timestamp())
}

source "amazon-ebs" "blog" {
  ami_name      = "${var.ami_name_prefix}-${local.timestamp}"
  instance_type = var.instance_type
  region        = var.aws_region
  source_ami    = data.amazon-ami.al2023.id

  ssh_username = "ec2-user"

  tags = {
    Name        = "${var.ami_name_prefix}-${local.timestamp}"
    Project     = "dev-blog"
    ManagedBy   = "packer"
    BaseAMI     = data.amazon-ami.al2023.id
  }

  run_tags = {
    Name = "packer-build-${var.ami_name_prefix}"
  }

  launch_block_device_mappings {
    device_name           = "/dev/xvda"
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
}

build {
  sources = ["source.amazon-ebs.blog"]

  provisioner "shell" {
    inline = [
      "sudo dnf update -y",
      "sudo dnf install -y docker amazon-ssm-agent",

      "sudo mkdir -p /usr/libexec/docker/cli-plugins",
      "sudo curl -fsSL \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/libexec/docker/cli-plugins/docker-compose",
      "sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose",

      "sudo systemctl enable docker",
      "sudo systemctl enable amazon-ssm-agent",
      "sudo usermod -aG docker ec2-user",

      "sudo mkdir -p /opt/dev-blog",
      "sudo chown ec2-user:ec2-user /opt/dev-blog",

      "docker compose version",
    ]
  }

  provisioner "file" {
    content     = <<-CADDY
      {
        email {$CADDY_EMAIL}
      }

      {$DOMAIN}, {$WWW_DOMAIN} {
        encode gzip

        @api path /api/*
        handle @api {
          uri strip_prefix /api
          reverse_proxy api:8000
        }

        handle {
          reverse_proxy web:80
        }
      }
    CADDY
    destination = "/opt/dev-blog/Caddyfile"
  }

  provisioner "file" {
    content     = <<-COMPOSE
      services:
        api:
          image: $${API_IMAGE}
          restart: unless-stopped
          environment:
            DEV_BLOG_ENVIRONMENT: prod
            DEV_BLOG_AWS_REGION: $${AWS_REGION}
            DEV_BLOG_S3_BUCKET: $${S3_BUCKET_NAME}
            DEV_BLOG_S3_PREFIX: $${CONTENT_PREFIX}
            DEV_BLOG_CONTENT_DIR: ""
            DEV_BLOG_CACHE_TTL_SECONDS: "300"
            DEV_BLOG_CORS_ORIGINS: $${CORS_ORIGINS}
          expose:
            - "8000"

        web:
          image: $${WEB_IMAGE}
          restart: unless-stopped
          depends_on:
            - api

        caddy:
          image: caddy:2
          restart: unless-stopped
          depends_on:
            - api
            - web
          ports:
            - "80:80"
            - "443:443"
          environment:
            DOMAIN: $${DOMAIN}
            WWW_DOMAIN: $${WWW_DOMAIN}
            CADDY_EMAIL: $${CADDY_EMAIL}
          volumes:
            - /opt/dev-blog/Caddyfile:/etc/caddy/Caddyfile:ro
            - caddy_data:/data
            - caddy_config:/config

      volumes:
        caddy_data:
        caddy_config:
    COMPOSE
    destination = "/opt/dev-blog/docker-compose.yml"
  }
}
