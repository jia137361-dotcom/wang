CREATE TABLE IF NOT EXISTS pin_performance (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(64),
    campaign_id VARCHAR(64),
    pinterest_pin_id VARCHAR(128),
    board_id VARCHAR(128),
    product_type VARCHAR(80),
    niche VARCHAR(120),
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    destination_url VARCHAR(1024),
    image_url VARCHAR(1024),
    content_prompt TEXT NOT NULL,
    visual_prompt TEXT,
    model_name VARCHAR(160),
    prompt_version VARCHAR(40) NOT NULL DEFAULT 'v1',
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    strategy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    impressions INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    outbound_clicks INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    reactions INTEGER NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    save_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    engagement_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    published_at TIMESTAMPTZ,
    metrics_updated_at TIMESTAMPTZ,
    content_hash VARCHAR(64),
    title_hash VARCHAR(64),
    description_hash VARCHAR(64),
    content_batch_id VARCHAR(64),
    variant_angle VARCHAR(160),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_pin_performance_pinterest_pin_id
    ON pin_performance (pinterest_pin_id)
    WHERE pinterest_pin_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_pin_performance_account_published
    ON pin_performance (account_id, published_at);

CREATE INDEX IF NOT EXISTS ix_pin_performance_niche_product
    ON pin_performance (niche, product_type);

CREATE INDEX IF NOT EXISTS ix_pin_performance_account_id
    ON pin_performance (account_id);

CREATE INDEX IF NOT EXISTS ix_pin_performance_campaign_id
    ON pin_performance (campaign_id);

CREATE INDEX IF NOT EXISTS ix_pin_performance_product_type
    ON pin_performance (product_type);

CREATE INDEX IF NOT EXISTS ix_pin_performance_niche
    ON pin_performance (niche);

CREATE INDEX IF NOT EXISTS ix_pin_performance_content_hash
    ON pin_performance (content_hash);

CREATE INDEX IF NOT EXISTS ix_pin_performance_title_hash
    ON pin_performance (title_hash);

CREATE INDEX IF NOT EXISTS ix_pin_performance_content_batch_id
    ON pin_performance (content_batch_id);

CREATE INDEX IF NOT EXISTS ix_pin_performance_description_hash
    ON pin_performance (description_hash);

CREATE TABLE IF NOT EXISTS global_strategy (
    id SERIAL PRIMARY KEY,
    scope VARCHAR(120) NOT NULL,
    strategy JSONB NOT NULL DEFAULT '{}'::jsonb,
    version VARCHAR(40) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_global_strategy_scope
    ON global_strategy (scope);

CREATE UNIQUE INDEX IF NOT EXISTS ux_global_strategy_scope
    ON global_strategy (scope);

CREATE TABLE IF NOT EXISTS social_account (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL UNIQUE,
    platform VARCHAR(40) NOT NULL DEFAULT 'pinterest',
    display_name VARCHAR(120),
    adspower_profile_id VARCHAR(120),
    proxy_region VARCHAR(80),
    risk_status VARCHAR(40) NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_social_account_account_id
    ON social_account (account_id);

CREATE TABLE IF NOT EXISTS campaign (
    id SERIAL PRIMARY KEY,
    campaign_id VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    niche VARCHAR(120),
    product_type VARCHAR(80),
    audience VARCHAR(240),
    season VARCHAR(80),
    offer VARCHAR(240),
    destination_url VARCHAR(1024),
    status VARCHAR(40) NOT NULL DEFAULT 'draft',
    notes TEXT,
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_campaign_campaign_id
    ON campaign (campaign_id);

CREATE INDEX IF NOT EXISTS ix_campaign_niche
    ON campaign (niche);

CREATE INDEX IF NOT EXISTS ix_campaign_product_type
    ON campaign (product_type);

CREATE INDEX IF NOT EXISTS ix_campaign_status
    ON campaign (status);

CREATE TABLE IF NOT EXISTS publish_job (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL UNIQUE,
    account_id VARCHAR(64) NOT NULL,
    campaign_id VARCHAR(64),
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    board_name VARCHAR(160) NOT NULL,
    image_path VARCHAR(1024) NOT NULL,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    destination_url VARCHAR(1024),
    product_type VARCHAR(80) NOT NULL,
    niche VARCHAR(120) NOT NULL,
    audience VARCHAR(240) NOT NULL,
    season VARCHAR(80),
    offer VARCHAR(240),
    error_message TEXT,
    pin_performance_id INTEGER,
    content_hash VARCHAR(64),
    title_hash VARCHAR(64),
    description_hash VARCHAR(64),
    content_batch_id VARCHAR(64),
    variant_angle VARCHAR(160),
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_publish_job_job_id
    ON publish_job (job_id);

CREATE INDEX IF NOT EXISTS ix_publish_job_account_id
    ON publish_job (account_id);

CREATE INDEX IF NOT EXISTS ix_publish_job_campaign_id
    ON publish_job (campaign_id);

CREATE INDEX IF NOT EXISTS ix_publish_job_status
    ON publish_job (status);

CREATE INDEX IF NOT EXISTS ix_publish_job_content_hash
    ON publish_job (content_hash);

CREATE INDEX IF NOT EXISTS ix_publish_job_title_hash
    ON publish_job (title_hash);

CREATE INDEX IF NOT EXISTS ix_publish_job_content_batch_id
    ON publish_job (content_batch_id);

CREATE INDEX IF NOT EXISTS ix_publish_job_description_hash
    ON publish_job (description_hash);

CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(40) NOT NULL DEFAULT 'volcengine',
    model_name VARCHAR(160) NOT NULL,
    account_id VARCHAR(64),
    campaign_id VARCHAR(64),
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_estimate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    request_type VARCHAR(80) NOT NULL DEFAULT 'chat',
    request_id VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_token_usage_provider
    ON token_usage (provider);

CREATE INDEX IF NOT EXISTS ix_token_usage_model_name
    ON token_usage (model_name);

CREATE INDEX IF NOT EXISTS ix_token_usage_account_id
    ON token_usage (account_id);

CREATE INDEX IF NOT EXISTS ix_token_usage_campaign_id
    ON token_usage (campaign_id);

CREATE INDEX IF NOT EXISTS ix_token_usage_request_type
    ON token_usage (request_type);

-- ============================================================
-- scheduled_task and account_policy tables are managed by
-- Alembic migration: migrations/versions/0003_scheduled_task.py
-- The commented DDL below is kept as reference only.
-- Use `alembic upgrade head` for production schema management.
-- ============================================================

-- CREATE TABLE IF NOT EXISTS scheduled_task (
--     id SERIAL PRIMARY KEY,
--     task_id VARCHAR(64) NOT NULL UNIQUE,
--     task_type VARCHAR(40) NOT NULL,
--     platform VARCHAR(40) NOT NULL DEFAULT 'pinterest',
--     account_id VARCHAR(64),
--     campaign_id VARCHAR(64),
--     status VARCHAR(40) NOT NULL DEFAULT 'pending',
--     priority INTEGER NOT NULL DEFAULT 0,
--     scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
--     started_at TIMESTAMPTZ,
--     finished_at TIMESTAMPTZ,
--     attempt_count INTEGER NOT NULL DEFAULT 0,
--     max_attempts INTEGER NOT NULL DEFAULT 3,
--     next_retry_at TIMESTAMPTZ,
--     locked_by VARCHAR(64),
--     lock_until TIMESTAMPTZ,
--     heartbeat_at TIMESTAMPTZ,
--     celery_task_id VARCHAR(128),
--     payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
--     result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
--     error_message TEXT,
--     error_type VARCHAR(40),
--     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
--     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
--
-- CREATE INDEX IF NOT EXISTS ix_scheduled_task_task_id ON scheduled_task (task_id);
-- CREATE INDEX IF NOT EXISTS ix_st_status_scheduled ON scheduled_task (status, scheduled_at);
-- CREATE INDEX IF NOT EXISTS ix_st_account_status ON scheduled_task (account_id, status);
-- CREATE INDEX IF NOT EXISTS ix_st_locked_by ON scheduled_task (locked_by);
-- CREATE INDEX IF NOT EXISTS ix_scheduled_task_task_type ON scheduled_task (task_type);
-- CREATE INDEX IF NOT EXISTS ix_scheduled_task_campaign_id ON scheduled_task (campaign_id);
--
-- CREATE TABLE IF NOT EXISTS account_policy (
--     id SERIAL PRIMARY KEY,
--     account_id VARCHAR(64) NOT NULL UNIQUE,
--     platform VARCHAR(40) NOT NULL DEFAULT 'pinterest',
--     daily_max_posts INTEGER NOT NULL DEFAULT 3,
--     min_post_interval_min INTEGER NOT NULL DEFAULT 60,
--     allowed_timezone_start VARCHAR(5) DEFAULT '09:00',
--     allowed_timezone_end VARCHAR(5) DEFAULT '22:00',
--     auto_reply_enabled BOOLEAN NOT NULL DEFAULT false,
--     warmup_sessions_per_day INTEGER NOT NULL DEFAULT 2,
--     warmup_duration_min INTEGER NOT NULL DEFAULT 15,
--     cooldown_until TIMESTAMPTZ,
--     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
--     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
--
-- CREATE INDEX IF NOT EXISTS ix_account_policy_account_id ON account_policy (account_id);
