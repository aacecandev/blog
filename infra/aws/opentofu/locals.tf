locals {
  selected_subnet_id = var.subnet_id != "" ? var.subnet_id : sort(data.aws_subnets.default.ids)[0]
  caddy_email        = var.letsencrypt_email != "" ? var.letsencrypt_email : "dev@${var.route53_zone_name}"
}
