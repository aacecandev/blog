output "bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.blog_content.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.blog_content.arn
}

output "bucket_region" {
  description = "AWS region of the S3 bucket"
  value       = aws_s3_bucket.blog_content.region
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.blog_web.id
}

output "ec2_private_ip" {
  description = "Private IP of the EC2 instance"
  value       = aws_instance.blog_web.private_ip
}

output "vip_public_ip" {
  description = "Elastic IP (VIP) attached to the EC2 instance"
  value       = aws_eip.blog_vip.public_ip
}

output "dev_record_fqdn" {
  description = "Route53 FQDN for dev domain"
  value       = aws_route53_record.dev.fqdn
}

output "www_record_fqdn" {
  description = "Route53 FQDN for www dev domain"
  value       = aws_route53_record.www_dev.fqdn
}
