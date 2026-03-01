data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
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
