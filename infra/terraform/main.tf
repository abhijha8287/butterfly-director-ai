terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment and configure once you have an S3 bucket for state.
  # backend "s3" {
  #   bucket         = "your-tf-state-bucket"
  #   key            = "butterfly-director/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "your-tf-lock-table"
  # }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name   = "butterfly-director"
  env    = var.environment
  prefix = "${local.name}-${local.env}"

  common_tags = {
    Project     = local.name
    Environment = local.env
    ManagedBy   = "terraform"
  }
}
