data "aws_caller_identity" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  ecr_image   = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${aws_ecr_repository.api.name}:${var.ecr_image_tag}"
  redis_url   = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379"
  db_url_async = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
  db_url_sync  = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

# --- ECS cluster ---
resource "aws_ecs_cluster" "main" {
  name = "${local.prefix}-cluster"
  tags = local.common_tags

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]
}

# --- CloudWatch log group ---
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.prefix}"
  retention_in_days = 14
  tags              = local.common_tags
}

# --- IAM: ECS task execution role ---
resource "aws_iam_role" "ecs_execution" {
  name = "${local.prefix}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "read-app-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.app.arn]
    }]
  })
}

# --- IAM: ECS task role (what running code can do) ---
resource "aws_iam_role" "ecs_task" {
  name = "${local.prefix}-ecs-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy" "ecs_task_logs" {
  name = "write-logs"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = ["${aws_cloudwatch_log_group.app.arn}:*"]
    }]
  })
}

# --- Shared environment for all tasks ---
locals {
  shared_env = [
    { name = "ENV",                    value = var.environment },
    { name = "DEBUG",                  value = "false" },
    { name = "LOG_JSON",               value = "true" },
    { name = "DATABASE_URL",           value = local.db_url_async },
    { name = "DATABASE_URL_SYNC",      value = local.db_url_sync },
    { name = "REDIS_URL",              value = "${local.redis_url}/0" },
    { name = "CELERY_BROKER_URL",      value = "${local.redis_url}/1" },
    { name = "CELERY_RESULT_BACKEND",  value = "${local.redis_url}/2" },
    { name = "MEDIA_ROOT",             value = "/app/media" },
    { name = "LLM_PROVIDER",           value = var.llm_provider },
    { name = "GEMINI_MODEL",           value = var.gemini_model },
    { name = "DASHSCOPE_BASE_URL",     value = "https://dashscope-intl.aliyuncs.com" },
    { name = "DASHSCOPE_WS_BASE_URL",  value = "wss://dashscope-intl.aliyuncs.com" },
    { name = "WAN_MODEL",              value = "wan2.6-t2v" },
    { name = "VIDEO_PROVIDER",         value = "wan" },
    { name = "VOICE_PROVIDER",         value = "dashscope" },
    { name = "MUSIC_PROVIDER",         value = "none" },
    { name = "FFMPEG_BINARY",          value = "ffmpeg" },
    { name = "FFPROBE_BINARY",         value = "ffprobe" },
  ]

  # Secrets injected from Secrets Manager at task startup
  shared_secrets = [
    {
      name      = "SECRET_KEY"
      valueFrom = "${aws_secretsmanager_secret.app.arn}:SECRET_KEY::"
    },
    {
      name      = "DASHSCOPE_API_KEY"
      valueFrom = "${aws_secretsmanager_secret.app.arn}:DASHSCOPE_API_KEY::"
    },
    {
      name      = "GEMINI_API_KEY"
      valueFrom = "${aws_secretsmanager_secret.app.arn}:GEMINI_API_KEY::"
    },
  ]

  efs_volume_config = [{
    name = "media"
    efs_volume_configuration = [{
      file_system_id     = aws_efs_file_system.media.id
      transit_encryption = "ENABLED"
    }]
  }]
}

# --- API task definition ---
resource "aws_ecs_task_definition" "api" {
  family                   = "${local.prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  tags                     = local.common_tags

  volume {
    name = "media"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.media.id
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([{
    name      = "api"
    image     = local.ecr_image
    essential = true
    command   = ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = local.shared_env
    secrets     = local.shared_secrets
    mountPoints = [{ sourceVolume = "media", containerPath = "/app/media" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/v1/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

# --- Worker task definition ---
resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  tags                     = local.common_tags

  volume {
    name = "media"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.media.id
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([{
    name        = "worker"
    image       = local.ecr_image
    essential   = true
    command     = ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "story,timeline,storyboard,video,voice,music,editing,maintenance", "--loglevel=info"]
    environment = local.shared_env
    secrets     = local.shared_secrets
    mountPoints = [{ sourceVolume = "media", containerPath = "/app/media" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

# --- Beat task definition ---
resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  tags                     = local.common_tags

  container_definitions = jsonencode([{
    name        = "beat"
    image       = local.ecr_image
    essential   = true
    command     = ["celery", "-A", "app.workers.celery_app", "beat", "--loglevel=info"]
    environment = local.shared_env
    secrets     = local.shared_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "beat"
      }
    }
  }])
}

# --- ALB ---
resource "aws_lb" "main" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  tags               = local.common_tags
}

resource "aws_lb_target_group" "api" {
  name        = "${local.prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/v1/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = local.common_tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- ECS services ---
resource "aws_ecs_service" "api" {
  name            = "${local.prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  tags            = local.common_tags

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.api.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http, aws_efs_mount_target.media]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  tags            = local.common_tags

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.worker.id]
  }

  depends_on = [aws_efs_mount_target.media]
}

resource "aws_ecs_service" "beat" {
  name            = "${local.prefix}-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  tags            = local.common_tags

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.worker.id]
  }
}
