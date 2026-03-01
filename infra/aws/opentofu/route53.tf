data "aws_route53_zone" "public" {
  name         = var.route53_zone_name
  private_zone = false
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
