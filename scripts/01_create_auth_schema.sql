-- ==========================================
-- Step 1: auth_db에 auth 스키마 생성 및 인증 테이블 구축
-- ==========================================

-- 주의: auth_db에 연결한 후 실행하세요
-- \c auth_db

-- 1. auth 스키마 생성
CREATE SCHEMA IF NOT EXISTS auth;

-- 2. auth 스키마에 인증 전용 테이블 생성

-- 2.1. auth.users 테이블 (사용자 정보)
CREATE TABLE auth.users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 업데이트 트리거 함수 생성
CREATE OR REPLACE FUNCTION auth.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- users 테이블 업데이트 트리거 적용
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON auth.users 
    FOR EACH ROW EXECUTE FUNCTION auth.update_updated_at_column();

-- 2.2. auth.roles 테이블 (범용 역할 - 인증 서버용)
CREATE TABLE auth.roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_system BOOLEAN DEFAULT FALSE,  -- 시스템 기본 역할 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.3. auth.user_roles 테이블 (사용자-역할 매핑)
CREATE TABLE auth.user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT NULL,  -- 할당한 관리자 ID
    expires_at TIMESTAMP NULL,  -- 역할 만료 시간 (선택적)
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES auth.roles(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES auth.users(id) ON DELETE SET NULL
);

-- 2.4. auth.user_sessions 테이블 (세션 관리)
CREATE TABLE auth.user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 2.5. auth.user_login_attempts 테이블 (로그인 시도 추적)
CREATE TABLE auth.user_login_attempts (
    id BIGSERIAL PRIMARY KEY,
    username_or_email VARCHAR(100) NOT NULL,
    ip_address INET,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 인덱스 생성 (성능 최적화)
CREATE INDEX idx_auth_users_username ON auth.users(username);
CREATE INDEX idx_auth_users_email ON auth.users(email);
CREATE INDEX idx_auth_users_active ON auth.users(is_active);
CREATE INDEX idx_auth_users_created_at ON auth.users(created_at);

CREATE INDEX idx_auth_roles_name ON auth.roles(name);
CREATE INDEX idx_auth_roles_active ON auth.roles(is_active);

CREATE INDEX idx_auth_user_roles_user_id ON auth.user_roles(user_id);
CREATE INDEX idx_auth_user_roles_role_id ON auth.user_roles(role_id);
CREATE INDEX idx_auth_user_roles_expires_at ON auth.user_roles(expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX idx_auth_user_sessions_user_id ON auth.user_sessions(user_id);
CREATE INDEX idx_auth_user_sessions_token ON auth.user_sessions(session_token);
CREATE INDEX idx_auth_user_sessions_active ON auth.user_sessions(is_active);
CREATE INDEX idx_auth_user_sessions_expires_at ON auth.user_sessions(expires_at);

CREATE INDEX idx_auth_login_attempts_username ON auth.user_login_attempts(username_or_email);
CREATE INDEX idx_auth_login_attempts_ip ON auth.user_login_attempts(ip_address);
CREATE INDEX idx_auth_login_attempts_attempted_at ON auth.user_login_attempts(attempted_at);

-- 4. JWT 생성용 뷰 생성 (인증 서버용)
-- 4.1. 활성 사용자와 역할 정보 뷰
CREATE VIEW auth.active_user_roles_view AS
SELECT 
    u.id as user_id,
    u.username,
    u.email,
    u.full_name,
    u.is_active as user_active,
    r.id as role_id,
    r.name as role_name,
    r.display_name as role_display_name,
    r.description as role_description,
    ur.assigned_at,
    ur.expires_at
FROM auth.users u
JOIN auth.user_roles ur ON u.id = ur.user_id
JOIN auth.roles r ON ur.role_id = r.id
WHERE u.is_active = TRUE 
    AND r.is_active = TRUE
    AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
ORDER BY u.username, r.name;

-- 4.2. 사용자별 역할 목록 뷰 (JWT 생성 시 사용)
CREATE VIEW auth.user_role_summary_view AS
SELECT 
    u.id as user_id,
    u.username,
    u.email,
    u.full_name,
    u.is_active,
    COALESCE(ARRAY_AGG(r.name ORDER BY r.name) FILTER (WHERE r.name IS NOT NULL), ARRAY[]::VARCHAR[]) as roles,
    COALESCE(ARRAY_AGG(r.display_name ORDER BY r.name) FILTER (WHERE r.display_name IS NOT NULL), ARRAY[]::VARCHAR[]) as role_display_names
FROM auth.users u
LEFT JOIN auth.user_roles ur ON u.id = ur.user_id AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
LEFT JOIN auth.roles r ON ur.role_id = r.id AND r.is_active = TRUE
WHERE u.is_active = TRUE
GROUP BY u.id, u.username, u.email, u.full_name, u.is_active;

-- 5. 보안 관련 함수

-- 5.1. 로그인 시도 기록 함수
CREATE OR REPLACE FUNCTION auth.record_login_attempt(
    p_username_or_email VARCHAR(100),
    p_ip_address INET,
    p_success BOOLEAN,
    p_failure_reason VARCHAR(100) DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO auth.user_login_attempts (username_or_email, ip_address, success, failure_reason)
    VALUES (p_username_or_email, p_ip_address, p_success, p_failure_reason);
    
    -- 1주일 이상 된 로그인 시도 기록 자동 삭제
    DELETE FROM auth.user_login_attempts 
    WHERE attempted_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- 5.2. 사용자 마지막 로그인 시간 업데이트 함수
CREATE OR REPLACE FUNCTION auth.update_last_login(p_user_id BIGINT)
RETURNS VOID AS $$
BEGIN
    UPDATE auth.users 
    SET last_login_at = CURRENT_TIMESTAMP 
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- 5.3. 만료된 세션 정리
CREATE OR REPLACE FUNCTION auth.cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM auth.user_sessions 
    WHERE expires_at < CURRENT_TIMESTAMP OR is_active = FALSE;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 6. 완료 메시지
DO $$ 
BEGIN
    RAISE NOTICE '✅ auth_db의 auth 스키마 생성 완료! (인증 전용)';
    RAISE NOTICE '📊 생성된 테이블: auth.users, auth.roles, auth.user_roles, auth.user_sessions, auth.user_login_attempts';
    RAISE NOTICE '🔍 생성된 뷰: auth.active_user_roles_view, auth.user_role_summary_view';
    RAISE NOTICE '⚡ 생성된 인덱스: 성능 최적화를 위한 13개 인덱스';
    RAISE NOTICE '🔧 생성된 함수: auth.record_login_attempt, auth.update_last_login, auth.cleanup_expired_sessions';
    RAISE NOTICE '🎯 범용 인증 서버용 스키마 구조 완성!';
END $$;