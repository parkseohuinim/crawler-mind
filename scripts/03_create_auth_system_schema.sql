-- ==========================================
-- Step 3: crawler_mind에 auth_system 스키마 생성 (기존 테이블 보존)
-- ==========================================

-- 주의: crawler_mind에 연결한 후 실행하세요
-- \c crawler_mind

-- 0. 기존 테이블 확인 및 보존 확인
DO $$
DECLARE
    menu_links_count INTEGER;
    menu_manager_count INTEGER;
BEGIN
    -- 기존 중요 테이블들의 존재 및 데이터 확인
    SELECT COUNT(*) INTO menu_links_count FROM information_schema.tables 
    WHERE table_name = 'menu_links' AND table_schema = 'public';
    
    SELECT COUNT(*) INTO menu_manager_count FROM information_schema.tables 
    WHERE table_name = 'menu_manager_info' AND table_schema = 'public';
    
    RAISE NOTICE '🔍 기존 테이블 확인:';
    RAISE NOTICE '  - menu_links 존재: %', CASE WHEN menu_links_count > 0 THEN 'YES' ELSE 'NO' END;
    RAISE NOTICE '  - menu_manager_info 존재: %', CASE WHEN menu_manager_count > 0 THEN 'YES' ELSE 'NO' END;
    
    IF menu_links_count > 0 THEN
        RAISE NOTICE '✅ 기존 menu_links 테이블이 보존됩니다';
    END IF;
    
    IF menu_manager_count > 0 THEN
        RAISE NOTICE '✅ 기존 menu_manager_info 테이블이 보존됩니다';
    END IF;
END $$;

-- 1. auth_system 스키마 생성 (권한 관리 전용)
CREATE SCHEMA IF NOT EXISTS auth_system;

-- 2. auth_system 스키마에 권한 관리 테이블 생성

-- 2.1. auth_system.permissions 테이블 (애플리케이션별 권한)
CREATE TABLE auth_system.permissions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    resource VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2.2. auth_system.menus 테이블 (권한 제어용 메뉴 구조)
CREATE TABLE auth_system.menus (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT NULL,
    name VARCHAR(100) NOT NULL,
    path VARCHAR(255),
    icon VARCHAR(100),
    order_index INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_visible BOOLEAN DEFAULT TRUE,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES auth_system.menus(id) ON DELETE CASCADE
);

-- 2.3. auth_system.role_permissions 테이블 (역할-권한 매핑, 역할명으로 참조)
CREATE TABLE auth_system.role_permissions (
    role_name VARCHAR(50) NOT NULL,  -- auth_db.auth.roles.name 참조 (외래키 아님)
    permission_id BIGINT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_name, permission_id),
    FOREIGN KEY (permission_id) REFERENCES auth_system.permissions(id) ON DELETE CASCADE
);

-- 2.4. auth_system.menu_permissions 테이블 (메뉴-권한 매핑)
CREATE TABLE auth_system.menu_permissions (
    menu_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    PRIMARY KEY (menu_id, permission_id),
    FOREIGN KEY (menu_id) REFERENCES auth_system.menus(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES auth_system.permissions(id) ON DELETE CASCADE
);

-- 3. 인덱스 생성 (성능 최적화)
CREATE INDEX idx_auth_permissions_name ON auth_system.permissions(name);
CREATE INDEX idx_auth_permissions_resource_action ON auth_system.permissions(resource, action);
CREATE INDEX idx_auth_permissions_active ON auth_system.permissions(is_active);

CREATE INDEX idx_auth_menus_parent_id ON auth_system.menus(parent_id);
CREATE INDEX idx_auth_menus_path ON auth_system.menus(path) WHERE path IS NOT NULL;
CREATE INDEX idx_auth_menus_active ON auth_system.menus(is_active);
CREATE INDEX idx_auth_menus_visible ON auth_system.menus(is_visible);
CREATE INDEX idx_auth_menus_order_index ON auth_system.menus(order_index);

CREATE INDEX idx_auth_role_permissions_role_name ON auth_system.role_permissions(role_name);
CREATE INDEX idx_auth_role_permissions_permission_id ON auth_system.role_permissions(permission_id);

CREATE INDEX idx_auth_menu_permissions_menu_id ON auth_system.menu_permissions(menu_id);
CREATE INDEX idx_auth_menu_permissions_permission_id ON auth_system.menu_permissions(permission_id);

-- 4. 권한 계산용 뷰 생성

-- 4.1. 역할별 권한 목록 뷰
CREATE VIEW auth_system.role_permissions_view AS
SELECT 
    rp.role_name,
    p.id as permission_id,
    p.name as permission_name,
    p.resource,
    p.action,
    p.description as permission_description
FROM auth_system.role_permissions rp
JOIN auth_system.permissions p ON rp.permission_id = p.id
WHERE p.is_active = TRUE
ORDER BY rp.role_name, p.resource, p.action;

-- 4.2. 메뉴별 필요 권한 뷰
CREATE VIEW auth_system.menu_permissions_view AS
SELECT 
    m.id as menu_id,
    m.name as menu_name,
    m.path,
    m.icon,
    m.order_index,
    m.parent_id,
    p.id as permission_id,
    p.name as permission_name,
    p.resource,
    p.action
FROM auth_system.menus m
JOIN auth_system.menu_permissions mp ON m.id = mp.menu_id
JOIN auth_system.permissions p ON mp.permission_id = p.id
WHERE m.is_active = TRUE 
    AND m.is_visible = TRUE 
    AND p.is_active = TRUE
ORDER BY m.order_index, m.name;

-- 4.3. 역할기반 접근 가능한 메뉴 뷰 (동적 계산용)
CREATE VIEW auth_system.accessible_menus_by_role_view AS
SELECT DISTINCT
    rp.role_name,
    m.id as menu_id,
    m.parent_id,
    m.name as menu_name,
    m.path,
    m.icon,
    m.order_index,
    m.description
FROM auth_system.role_permissions rp
JOIN auth_system.menu_permissions mp ON rp.permission_id = mp.permission_id
JOIN auth_system.menus m ON mp.menu_id = m.id
WHERE m.is_active = TRUE 
    AND m.is_visible = TRUE
ORDER BY rp.role_name, m.order_index, m.name;

-- 5. 권한 검사 함수들

-- 5.1. 역할 기반 권한 확인 함수
CREATE OR REPLACE FUNCTION auth_system.check_role_permission(
    p_role_names TEXT[],
    p_permission_name VARCHAR(100)
) RETURNS BOOLEAN AS $$
DECLARE
    permission_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM auth_system.role_permissions rp
        JOIN auth_system.permissions p ON rp.permission_id = p.id
        WHERE rp.role_name = ANY(p_role_names)
            AND p.name = p_permission_name
            AND p.is_active = TRUE
    ) INTO permission_exists;
    
    RETURN permission_exists;
END;
$$ LANGUAGE plpgsql;

-- 5.2. 역할 기반 메뉴 접근 가능 여부 확인 함수
CREATE OR REPLACE FUNCTION auth_system.check_menu_access(
    p_role_names TEXT[],
    p_menu_path VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    access_allowed BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 
        FROM auth_system.accessible_menus_by_role_view amv
        WHERE amv.role_name = ANY(p_role_names)
            AND amv.path = p_menu_path
    ) INTO access_allowed;
    
    RETURN access_allowed;
END;
$$ LANGUAGE plpgsql;

-- 5.3. 역할별 권한 목록 조회 함수
CREATE OR REPLACE FUNCTION auth_system.get_role_permissions(
    p_role_names TEXT[]
) RETURNS TABLE (
    permission_name VARCHAR(100),
    resource VARCHAR(50),
    action VARCHAR(50),
    description VARCHAR(255)
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        p.name,
        p.resource,
        p.action,
        p.description
    FROM auth_system.role_permissions rp
    JOIN auth_system.permissions p ON rp.permission_id = p.id
    WHERE rp.role_name = ANY(p_role_names)
        AND p.is_active = TRUE
    ORDER BY p.resource, p.action;
END;
$$ LANGUAGE plpgsql;

-- 5.4. 역할별 접근 가능한 메뉴 조회 함수
CREATE OR REPLACE FUNCTION auth_system.get_accessible_menus(
    p_role_names TEXT[]
) RETURNS TABLE (
    menu_id BIGINT,
    parent_id BIGINT,
    name VARCHAR(100),
    path VARCHAR(255),
    icon VARCHAR(100),
    order_index INT,
    description VARCHAR(255)
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        amv.menu_id,
        amv.parent_id,
        amv.menu_name,
        amv.path,
        amv.icon,
        amv.order_index,
        amv.description
    FROM auth_system.accessible_menus_by_role_view amv
    WHERE amv.role_name = ANY(p_role_names)
    ORDER BY amv.order_index, amv.menu_name;
END;
$$ LANGUAGE plpgsql;

-- 6. 완료 메시지
DO $$ 
BEGIN
    RAISE NOTICE '✅ crawler_mind의 auth_system 스키마 생성 완료!';
    RAISE NOTICE '📊 생성된 테이블: auth_system.permissions, auth_system.menus, auth_system.role_permissions, auth_system.menu_permissions';
    RAISE NOTICE '🔍 생성된 뷰: auth_system.role_permissions_view, auth_system.menu_permissions_view, auth_system.accessible_menus_by_role_view';
    RAISE NOTICE '⚡ 생성된 인덱스: 성능 최적화를 위한 12개 인덱스';
    RAISE NOTICE '🔧 생성된 함수: auth_system.check_role_permission, auth_system.check_menu_access, auth_system.get_role_permissions, auth_system.get_accessible_menus';
    RAISE NOTICE '🎯 애플리케이션별 권한/메뉴 관리 시스템 구축 완료!';
    RAISE NOTICE '';
    RAISE NOTICE '🔒 기존 테이블 보존 상태:';
    RAISE NOTICE '  - public.menu_links (보존됨)';
    RAISE NOTICE '  - public.menu_manager_info (보존됨)';
    RAISE NOTICE '  - 기타 기존 테이블들 (모두 보존됨)';
END $$;
