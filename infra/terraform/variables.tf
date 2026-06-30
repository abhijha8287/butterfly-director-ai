variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
  default     = "staging"
}

variable "ecr_image_tag" {
  description = "Docker image tag to deploy (injected by CI)"
  type        = string
  default     = "latest"
}

# --- Database ---
variable "db_instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "butterfly_director"
}

variable "db_username" {
  type    = string
  default = "butterfly"
}

variable "db_password" {
  description = "RDS master password — set via TF_VAR_db_password or tfvars, never hardcode"
  type        = string
  sensitive   = true
}

# --- ElastiCache ---
variable "redis_node_type" {
  type    = string
  default = "cache.t3.micro"
}

# --- ECS task sizing ---
variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "worker_cpu" {
  type    = number
  default = 512
}

variable "worker_memory" {
  type    = number
  default = 1024
}

# --- Application secrets (sensitive — pass via environment or CI secrets) ---
variable "secret_key" {
  description = "FastAPI secret key"
  type        = string
  sensitive   = true
}

variable "dashscope_api_key" {
  description = "DashScope API key (for Wan/CosyVoice)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key (used when LLM_PROVIDER=gemini)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "llm_provider" {
  description = "LLM provider: qwen or gemini"
  type        = string
  default     = "gemini"
}

variable "gemini_model" {
  type    = string
  default = "gemini-2.0-flash"
}
