# --- RDS PostgreSQL ---
resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.common_tags
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.prefix}-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true
  deletion_protection    = false
  storage_encrypted      = true
  tags                   = local.common_tags
}

# --- ElastiCache Redis ---
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.prefix}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.common_tags
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.prefix}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.1"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
  tags                 = local.common_tags
}

# --- EFS (shared media volume: voice/music/editor output) ---
resource "aws_efs_file_system" "media" {
  encrypted = true
  tags      = merge(local.common_tags, { Name = "${local.prefix}-media" })
}

resource "aws_efs_mount_target" "media" {
  count           = 2
  file_system_id  = aws_efs_file_system.media.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# --- Secrets Manager: app secrets ---
resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.prefix}/app"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY        = var.secret_key
    DASHSCOPE_API_KEY = var.dashscope_api_key
    GEMINI_API_KEY    = var.gemini_api_key
    DB_PASSWORD       = var.db_password
  })
}
