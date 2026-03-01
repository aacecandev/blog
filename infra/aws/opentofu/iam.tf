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
