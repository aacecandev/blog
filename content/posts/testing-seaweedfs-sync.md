---

title: "Testing SeaweedFS Sync"
date: "2026-03-01"
description: "A dummy post to verify the GitLab CI sync-posts pipeline uploads content to SeaweedFS correctly."
tags: ["test", "ci", "seaweedfs"]
---

# Testing SeaweedFS Sync

This post exists to trigger the `sync-posts` CI job and verify that blog content is uploaded to SeaweedFS via the GitLab pipeline.

## What This Validates

- The `aws-cli` image can reach the SeaweedFS S3 endpoint inside the K3s cluster
- The `s3 sync` command creates the bucket and uploads markdown files
- The backend can read this post back from SeaweedFS using the S3-compatible API

If you're reading this on the blog, the pipeline works.
