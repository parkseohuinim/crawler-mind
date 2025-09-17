-- ==========================================
-- Step 2: auth_db의 auth 스키마에 기본 인증 데이터 삽입
-- ==========================================

-- 주의: auth_db에 연결한 후 실행하세요
-- \c auth_db

-- 1. 범용 역할 생성 (다양한 애플리케이션에서 사용 가능)
INSERT INTO auth.roles (name, display_name, description, is_system) VALUES
('admin', '시스템 관리자', '모든 시스템의 관리자 권한', true),
('user', '일반 사용자', '기본 사용자 권한', true),
('guest', '게스트', '제한된 읽기 권한만 가진 게스트', true),
('manager', '관리자', '특정 영역의 관리 권한', false),
('viewer', '조회 전용', '읽기 전용 권한', false),
('developer', '개발자', '개발 관련 권한', false),
('analyst', '분석가', '데이터 분석 권한', false),
('moderator', '운영자', '콘텐츠 운영 권한', false);

-- 2. 기본 관리자 계정 생성
-- 패스워드: admin123 -> BCrypt 해시값
INSERT INTO auth.users (username, email, password_hash, full_name, is_verified) VALUES
('admin', 'admin@crawler-mind.com', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM5lE/OGwDRlT2/lFJ5K', '시스템 관리자', true);

-- 3. 테스트용 일반 사용자 계정 생성
-- 패스워드: user123 -> BCrypt 해시값
INSERT INTO auth.users (username, email, password_hash, full_name, is_verified) VALUES
('user', 'user@crawler-mind.com', '$2a$10$Ip02fy6NiXxE6D.LqR6TAuOaM5ZWZs2N.U9JZ0/x4Dox/BnYDGQ0W', '일반 사용자', true);

-- 4. 테스트용 매니저 계정 생성
-- 패스워드: manager123 -> BCrypt 해시값
INSERT INTO auth.users (username, email, password_hash, full_name, is_verified) VALUES
('manager', 'manager@crawler-mind.com', '$2a$10$85YWKpJPiZ5OkWsQpjK9TOBmSKBbwI1l.C5YdEjP0ZE7oqIQBnlgq', '매니저', true);

-- 5. 사용자-역할 매핑
-- admin 사용자에게 admin 역할 부여
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.id, r.id 
FROM auth.users u, auth.roles r
WHERE u.username = 'admin' AND r.name = 'admin';

-- user 사용자에게 user 역할 부여
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.id, r.id 
FROM auth.users u, auth.roles r
WHERE u.username = 'user' AND r.name = 'user';

-- manager 사용자에게 manager, user 역할 부여 (다중 역할 테스트)
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.id, r.id 
FROM auth.users u, auth.roles r
WHERE u.username = 'manager' AND r.name IN ('manager', 'user');

-- 6. 데이터 확인 쿼리
DO $$
DECLARE
    user_count INTEGER;
    role_count INTEGER;
    mapping_count INTEGER;
BEGIN
    -- 생성된 데이터 개수 확인
    SELECT COUNT(*) INTO user_count FROM auth.users;
    SELECT COUNT(*) INTO role_count FROM auth.roles;
    SELECT COUNT(*) INTO mapping_count FROM auth.user_roles;
    
    RAISE NOTICE '✅ auth_db 기본 데이터 삽입 완료!';
    RAISE NOTICE '👥 생성된 사용자: % 명', user_count;
    RAISE NOTICE '🎭 생성된 역할: % 개', role_count;
    RAISE NOTICE '🔗 사용자-역할 매핑: % 개', mapping_count;
    RAISE NOTICE '';
    RAISE NOTICE '📋 생성된 계정 정보:';
    RAISE NOTICE '  - admin (admin@crawler-mind.com) 패스워드: admin123';
    RAISE NOTICE '  - user (user@crawler-mind.com) 패스워드: user123';
    RAISE NOTICE '  - manager (manager@crawler-mind.com) 패스워드: manager123';
    RAISE NOTICE '';
    RAISE NOTICE '🎯 범용 인증 서버 기본 데이터 설정 완료!';
END $$;

-- 7. 생성된 사용자 및 역할 확인 (테스트용)
SELECT '=== 사용자 목록 ===' as info;
SELECT username, email, full_name, is_active, is_verified, created_at 
FROM auth.users 
ORDER BY username;

SELECT '=== 역할 목록 ===' as info;
SELECT name, display_name, description, is_system, is_active 
FROM auth.roles 
ORDER BY is_system DESC, name;

SELECT '=== 사용자-역할 매핑 ===' as info;
SELECT u.username, r.name as role_name, r.display_name, ur.assigned_at
FROM auth.user_roles ur
JOIN auth.users u ON ur.user_id = u.id
JOIN auth.roles r ON ur.role_id = r.id
ORDER BY u.username, r.name;

-- 8. JWT 생성용 뷰 테스트
SELECT '=== JWT 생성용 사용자 정보 ===' as info;
SELECT user_id, username, email, full_name, roles, role_display_names
FROM auth.user_role_summary_view
ORDER BY username;