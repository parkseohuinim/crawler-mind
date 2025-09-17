-- ==========================================
-- Step 4: crawler_mind의 auth_system 스키마에 권한/메뉴 데이터 삽입
-- ==========================================

-- 주의: crawler_mind에 연결한 후 실행하세요
-- \c crawler_mind

-- 1. 크롤러 애플리케이션 권한 정의
INSERT INTO auth_system.permissions (name, resource, action, description) VALUES
-- 크롤링 관련
('crawler:read', 'crawler', 'read', '크롤링 결과 조회'),
('crawler:write', 'crawler', 'write', '크롤링 실행'),
('crawler:delete', 'crawler', 'delete', '크롤링 결과 삭제'),

-- RAG 관련
('rag:read', 'rag', 'read', 'RAG 데이터 조회'),
('rag:write', 'rag', 'write', 'RAG 데이터 업로드'),
('rag:delete', 'rag', 'delete', 'RAG 데이터 삭제'),
('rag:search', 'rag', 'search', 'RAG 검색 실행'),

-- 메뉴 관리 (기존 menu_links, menu_manager_info 테이블 관련)
('menu_links:read', 'menu_links', 'read', '메뉴 링크 조회'),
('menu_links:write', 'menu_links', 'write', '메뉴 링크 수정'),
('menu_links:delete', 'menu_links', 'delete', '메뉴 링크 삭제'),
('menu_manager:read', 'menu_manager', 'read', '메뉴 담당자 조회'),
('menu_manager:write', 'menu_manager', 'write', '메뉴 담당자 수정'),
('menu_manager:delete', 'menu_manager', 'delete', '메뉴 담당자 삭제'),

-- JSON 비교
('json:read', 'json', 'read', 'JSON 비교 조회'),
('json:write', 'json', 'write', 'JSON 비교 실행'),

-- 시스템 관리
('system:admin', 'system', 'admin', '시스템 관리'),
('system:monitor', 'system', 'monitor', '시스템 모니터링'),
('system:config', 'system', 'config', '시스템 설정');

-- 2. 권한 제어용 메뉴 구조 (기존 프론트엔드 구조 반영)
INSERT INTO auth_system.menus (id, parent_id, name, path, icon, order_index, description) VALUES
(1, NULL, '홈', '/', 'home', 1, '크롤링 메인 페이지'),
(2, NULL, 'RAG 시스템', '/rag', 'document', 2, 'RAG 데이터 관리 시스템'),
(3, NULL, '메뉴 관리', NULL, 'menu', 3, '메뉴 관리 시스템'),
(4, 3, '메뉴 링크 관리', '/menu-links', 'link', 1, '메뉴 링크 관리 (기존 menu_links 테이블)'),
(5, 3, '메뉴 매니저 관리', '/menu-managers', 'user', 2, '메뉴 매니저 관리 (기존 menu_manager_info 테이블)'),
(6, 3, '메뉴 트리뷰', '/menu-links/tree', 'tree', 3, '메뉴 트리 구조 보기'),
(7, NULL, 'JSON 비교', '/json-compare', 'compare', 4, 'JSON 데이터 비교 도구');

-- 시퀀스 재설정 (명시적 ID 사용으로 인한)
SELECT setval('auth_system.menus_id_seq', (SELECT MAX(id) FROM auth_system.menus));

-- 3. 역할-권한 매핑 (auth_db의 역할명 사용)

-- 3.1. admin 역할에 모든 권한 부여
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'admin', p.id FROM auth_system.permissions p;

-- 3.2. user 역할에 기본 권한 부여
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'user', p.id FROM auth_system.permissions p
WHERE p.name IN (
    'crawler:read', 
    'rag:read', 
    'rag:search', 
    'menu_links:read',
    'menu_manager:read',
    'json:read'
);

-- 3.3. manager 역할에 관리 권한 부여 (읽기 + 쓰기)
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'manager', p.id FROM auth_system.permissions p
WHERE p.name LIKE '%:read' 
   OR p.name LIKE '%:write' 
   OR p.name = 'system:monitor';

-- 3.4. viewer 역할에 읽기 권한만 부여
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'viewer', p.id FROM auth_system.permissions p
WHERE p.name LIKE '%:read';

-- 3.5. guest 역할에 최소 권한만 부여
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'guest', p.id FROM auth_system.permissions p
WHERE p.name IN ('crawler:read', 'rag:search', 'json:read');

-- 3.6. analyst 역할에 분석 관련 권한 부여
INSERT INTO auth_system.role_permissions (role_name, permission_id)
SELECT 'analyst', p.id FROM auth_system.permissions p
WHERE p.name IN (
    'crawler:read', 
    'rag:read', 
    'rag:search', 
    'json:read', 
    'json:write',
    'system:monitor'
);

-- 4. 메뉴-권한 매핑

-- 4.1. 홈 페이지 (기본 크롤링 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/' AND p.name = 'crawler:read';

-- 4.2. RAG 시스템 (RAG 읽기 또는 검색 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/rag' AND p.name IN ('rag:read', 'rag:search');

-- 4.3. 메뉴 링크 관리 (menu_links 읽기 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/menu-links' AND p.name = 'menu_links:read';

-- 4.4. 메뉴 매니저 관리 (menu_manager 읽기 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/menu-managers' AND p.name = 'menu_manager:read';

-- 4.5. 메뉴 트리뷰 (menu_links 읽기 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/menu-links/tree' AND p.name = 'menu_links:read';

-- 4.6. JSON 비교 (JSON 읽기 권한 필요)
INSERT INTO auth_system.menu_permissions (menu_id, permission_id)
SELECT m.id, p.id FROM auth_system.menus m, auth_system.permissions p
WHERE m.path = '/json-compare' AND p.name = 'json:read';

-- 5. 데이터 확인 및 테스트

-- 5.1. 생성된 데이터 개수 확인
DO $$
DECLARE
    permission_count INTEGER;
    menu_count INTEGER;
    role_permission_count INTEGER;
    menu_permission_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO permission_count FROM auth_system.permissions;
    SELECT COUNT(*) INTO menu_count FROM auth_system.menus;
    SELECT COUNT(*) INTO role_permission_count FROM auth_system.role_permissions;
    SELECT COUNT(*) INTO menu_permission_count FROM auth_system.menu_permissions;
    
    RAISE NOTICE '✅ crawler_mind 애플리케이션 권한/메뉴 데이터 삽입 완료!';
    RAISE NOTICE '🔐 생성된 권한: % 개', permission_count;
    RAISE NOTICE '📱 생성된 메뉴: % 개', menu_count;
    RAISE NOTICE '🔗 역할-권한 매핑: % 개', role_permission_count;
    RAISE NOTICE '📋 메뉴-권한 매핑: % 개', menu_permission_count;
    RAISE NOTICE '🎯 크롤러 애플리케이션 권한/메뉴 시스템 완성!';
    RAISE NOTICE '';
    RAISE NOTICE '🔒 기존 테이블과의 연관성:';
    RAISE NOTICE '  - menu_links:* 권한 → public.menu_links 테이블 제어';
    RAISE NOTICE '  - menu_manager:* 권한 → public.menu_manager_info 테이블 제어';
END $$;

-- 5.2. 권한 목록 확인
SELECT '=== 권한 목록 ===' as info;
SELECT name, resource, action, description 
FROM auth_system.permissions 
ORDER BY resource, action;

-- 5.3. 메뉴 구조 확인
SELECT '=== 메뉴 구조 ===' as info;
SELECT 
    id,
    CASE 
        WHEN parent_id IS NULL THEN name
        ELSE '  └ ' || name
    END as menu_hierarchy,
    path,
    icon,
    order_index
FROM auth_system.menus 
ORDER BY 
    COALESCE(parent_id, id), 
    CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END, 
    order_index;

-- 5.4. 역할별 권한 확인 (주요 역할들)
SELECT '=== admin 역할 권한 ===' as info;
SELECT p.name, p.resource, p.action, p.description
FROM auth_system.role_permissions rp
JOIN auth_system.permissions p ON rp.permission_id = p.id
WHERE rp.role_name = 'admin'
ORDER BY p.resource, p.action;

SELECT '=== user 역할 권한 ===' as info;
SELECT p.name, p.resource, p.action, p.description
FROM auth_system.role_permissions rp
JOIN auth_system.permissions p ON rp.permission_id = p.id
WHERE rp.role_name = 'user'
ORDER BY p.resource, p.action;

-- 5.5. 권한 검사 함수 테스트
SELECT '=== 권한 검사 함수 테스트 ===' as info;
SELECT 
    'admin 역할의 menu_links:write 권한' as test_case,
    auth_system.check_role_permission(ARRAY['admin'], 'menu_links:write') as has_permission;

SELECT 
    'user 역할의 menu_manager:delete 권한' as test_case,
    auth_system.check_role_permission(ARRAY['user'], 'menu_manager:delete') as has_permission;

SELECT 
    'manager 역할의 menu_links:write 권한' as test_case,
    auth_system.check_role_permission(ARRAY['manager'], 'menu_links:write') as has_permission;

-- 5.6. 메뉴 접근 함수 테스트
SELECT '=== 메뉴 접근 함수 테스트 ===' as info;
SELECT 
    'admin 역할의 /rag 메뉴 접근' as test_case,
    auth_system.check_menu_access(ARRAY['admin'], '/rag') as can_access;

SELECT 
    'guest 역할의 /menu-managers 메뉴 접근' as test_case,
    auth_system.check_menu_access(ARRAY['guest'], '/menu-managers') as can_access;
