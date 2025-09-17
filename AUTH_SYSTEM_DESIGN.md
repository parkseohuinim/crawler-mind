# 새로운 스키마 설계

## 스키마 구조

### 1. `auth` 스키마 (auth_db 내)
```
auth_db/
├── auth.users                    -- 사용자 정보
├── auth.roles                    -- 역할 정보
├── auth.user_roles              -- 사용자-역할 매핑
├── auth.user_sessions           -- 세션 관리
└── auth.user_login_attempts     -- 로그인 시도 기록
```

### 2. `crawler_mind` 스키마 (crawler_mind 내 - 기존 테이블 유지)
```
crawler_mind/
├── public.menu_links            -- 🔒 기존 테이블 (보존)
├── public.menu_manager_info     -- 🔒 기존 테이블 (보존)
└── ... (기타 기존 테이블들)
```

### 3. `auth_system` 스키마 (crawler_mind 내 - 새로운 권한 시스템)
```
crawler_mind/
├── auth_system.permissions      -- 권한 정보
├── auth_system.menus           -- 메뉴 구조 (권한용)
├── auth_system.role_permissions -- 역할-권한 매핑
└── auth_system.menu_permissions -- 메뉴-권한 매핑
```

## 명명 규칙

### 기존 테이블 (보존)
- `menu_links` - 실제 메뉴 링크 데이터
- `menu_manager_info` - 메뉴 담당자 정보

### 새로운 권한 테이블 (auth_system 스키마)
- `auth_system.permissions` - 시스템 권한
- `auth_system.menus` - 권한 제어용 메뉴 구조
- `auth_system.role_permissions` - 역할별 권한
- `auth_system.menu_permissions` - 메뉴별 필요 권한

## 동작 방식

1. **인증**: `auth_db.auth.*` 테이블들 사용
2. **권한 확인**: `crawler_mind.auth_system.*` 테이블들 사용  
3. **실제 데이터**: `crawler_mind.public.*` 테이블들 사용

이렇게 하면:
- 기존 중요 테이블 완전 보존
- 권한 시스템과 실제 데이터 분리
- 명명 충돌 방지
- 확장성 확보

# Aegis Shield - Enterprise Authentication Server Design

## 1. 시스템 아키텍처 개요

```
Frontend (Next.js) 
    ↓ JWT Token (user + roles)
Aegis Shield Server (Spring Boot) ← Enterprise 인증 서버
    ↓ JWT Validation (user + roles only)
MCP Client (FastAPI) ← 애플리케이션 서버
    ↓ 역할 기반 권한/메뉴 계산
    ↓ MCP Protocol
MCP Server (FastMCP) ← 기존 크롤링 서버
    ↓
PostgreSQL (같은 인스턴스)
├── auth_db (범용 인증) ← 순수 인증 정보만
│   ├── users (사용자 정보)
│   ├── roles (역할 정보)
│   ├── user_roles (사용자-역할 매핑)
│   ├── user_sessions (사용자 세션)
│   └── user_login_attempts (로그인 시도 기록)
└── crawler_mind (애플리케이션 DB) ← 애플리케이션별 권한/메뉴
    ├── permissions (권한 정보)
    ├── menus (메뉴 정보)  
    ├── role_permissions (역할-권한 매핑)
    ├── menu_permissions (메뉴-권한 매핑)
    ├── 크롤링 관련 테이블
    └── RAG 관련 테이블
```

## 2. Aegis Shield Server 설계

### 2.1 프로젝트 구조
```
aegis-shield-server/
├── app/
│   ├── build.gradle (Spring Boot 3.3.5 + Java 21)
│   └── src/main/
│       ├── java/com/aegis/auth/
│       │   ├── AegisShieldApplication.java
│       │   ├── config/
│       │   │   └── SecurityConfig.java
│       │   ├── controller/
│       │   │   └── AuthController.java
│       │   ├── service/
│       │   │   ├── AuthService.java
│       │   │   └── UserService.java
│       │   ├── repository/
│       │   │   ├── UserRepository.java
│       │   │   ├── RoleRepository.java
│       │   │   └── UserRoleRepository.java
│       │   ├── entity/
│       │   │   ├── User.java
│       │   │   ├── Role.java
│       │   │   └── UserRole.java
│       │   ├── dto/
│       │   │   ├── LoginRequest.java
│       │   │   ├── LoginResponse.java
│       │   │   └── UserDto.java
│       │   └── util/
│       │       └── JwtUtil.java
│       └── resources/
│           └── application.yml
├── gradle/
├── gradlew
├── gradlew.bat
└── settings.gradle
```

### 2.2 주요 설정 (application.yml)
```yaml
server:
  port: 8080
  servlet:
    context-path: /aegis

spring:
  application:
    name: aegis-shield-server
  datasource:
    url: jdbc:postgresql://100.119.125.34:5432/auth_db
    username: ${DB_USERNAME:admin}
    password: ${DB_PASSWORD:199084}
  jpa:
    hibernate:
      ddl-auto: validate
    database-platform: org.hibernate.dialect.PostgreSQLDialect
  threads:
    virtual:
      enabled: true

jwt:
  secret: ${JWT_SECRET:AegisShield2024SecretKeyForEnterpriseAuthentication!@#$}
  access-token-validity: 3600    # 1시간 (초)
  refresh-token-validity: 604800 # 7일 (초)
  issuer: "aegis-shield-server"

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
      base-path: /actuator

cors:
  allowed-origins:
    - http://localhost:3000
    - http://127.0.0.1:3000
    - http://localhost:8000
    - http://127.0.0.1:8000
```

### 2.3 의존성 (build.gradle)
```gradle
plugins {
    id 'org.springframework.boot' version '3.3.5'
    id 'io.spring.dependency-management' version '1.1.6'
    id 'java'
}

dependencies {
    // Spring Boot Starters
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-security'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    
    // JWT
    implementation 'io.jsonwebtoken:jjwt-api:0.12.3'
    runtimeOnly 'io.jsonwebtoken:jjwt-impl:0.12.3'
    runtimeOnly 'io.jsonwebtoken:jjwt-jackson:0.12.3'
    
    // Database
    runtimeOnly 'org.postgresql:postgresql:42.7.1'
    
    // Development Tools
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'
    developmentOnly 'org.springframework.boot:spring-boot-devtools'
    
    // Test
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.security:spring-security-test'
    testImplementation 'org.testcontainers:junit-jupiter'
    testImplementation 'org.testcontainers:postgresql'
}
```

## 3. API 엔드포인트 설계

### 3.1 인증 API (/aegis/api/auth)
```
POST /aegis/api/auth/login      - 사용자 로그인
POST /aegis/api/auth/refresh    - 토큰 갱신
POST /aegis/api/auth/validate   - 토큰 유효성 검증
POST /aegis/api/auth/logout     - 로그아웃
GET  /aegis/api/auth/status     - 서비스 상태 확인
```

### 3.2 모니터링 API (/aegis/actuator)
```
GET /aegis/actuator/health      - 서비스 헬스 체크
GET /aegis/actuator/info        - 서비스 정보
GET /aegis/actuator/metrics     - 메트릭 정보
GET /aegis/actuator/prometheus  - Prometheus 메트릭
```

## 4. JWT 토큰 구조

### 4.1 Access Token
```json
{
  "sub": "1",
  "username": "admin",
  "roles": ["admin", "user"],
  "type": "access",
  "iss": "aegis-shield-server",
  "iat": 1726471200,
  "exp": 1726474800
}
```

### 4.2 Refresh Token
```json
{
  "sub": "1",
  "type": "refresh",
  "iss": "aegis-shield-server",
  "iat": 1726471200,
  "exp": 1727076000
}
```

## 5. 데이터베이스 스키마

### 5.1 auth_db 스키마
```sql
-- 사용자 테이블
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 역할 테이블
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 사용자-역할 매핑
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by BIGINT,
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);
```

### 5.2 crawler_mind 애플리케이션 스키마
```sql
-- 권한 테이블
CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description VARCHAR(255),
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true
);

-- 메뉴 테이블
CREATE TABLE menus (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    path VARCHAR(255),
    icon VARCHAR(100),
    parent_id BIGINT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    FOREIGN KEY (parent_id) REFERENCES menus(id)
);

-- 역할-권한 매핑
CREATE TABLE role_permissions (
    role_name VARCHAR(50) NOT NULL,
    permission_id BIGINT NOT NULL,
    PRIMARY KEY (role_name, permission_id),
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
);

-- 메뉴-권한 매핑
CREATE TABLE menu_permissions (
    menu_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    PRIMARY KEY (menu_id, permission_id),
    FOREIGN KEY (menu_id) REFERENCES menus(id),
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
);
```

## 6. 보안 설계

### 6.1 JWT 보안
- HS256 알고리즘 사용
- 강력한 Secret Key (256비트 이상)
- Access Token: 1시간 유효
- Refresh Token: 7일 유효
- 토큰 타입별 검증 로직

### 6.2 비밀번호 보안
- BCrypt 해싱 (기본 강도 10)
- 최소 6자리 이상 요구사항
- 사용자명/이메일과 다른 값

### 6.3 CORS 설정
- 허용된 Origin만 접근 가능
- 개발환경: localhost:3000, localhost:8000
- 프로덕션: 별도 설정 필요

## 7. 클라이언트 통합 가이드

### 7.1 로그인 플로우
```javascript
// 1. 로그인 요청
const loginResponse = await fetch('/aegis/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    usernameOrEmail: 'admin',
    password: 'password'
  })
});

// 2. 응답 처리
const { accessToken, refreshToken, user, roles, expiresAt } = await loginResponse.json();

// 3. 토큰 저장
localStorage.setItem('accessToken', accessToken);
localStorage.setItem('refreshToken', refreshToken);
```

### 7.2 API 요청에 토큰 추가
```javascript
const response = await fetch('/api/protected-resource', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
  }
});
```

### 7.3 토큰 갱신
```javascript
const refreshResponse = await fetch('/aegis/api/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    refreshToken: localStorage.getItem('refreshToken')
  })
});
```

## 8. 운영 및 모니터링

### 8.1 헬스 체크
```bash
curl http://localhost:8080/aegis/actuator/health
```

### 8.2 메트릭 수집
- Spring Boot Actuator를 통한 기본 메트릭
- Prometheus 엔드포인트 제공
- 커스텀 메트릭 추가 가능

### 8.3 로깅
- 구조화된 로깅 (JSON 형태)
- 로그 레벨별 분리
- 파일 및 콘솔 출력
- 민감정보 마스킹

## 9. 배포 및 확장

### 9.1 Docker 컨테이너화 준비
```dockerfile
FROM openjdk:21-jdk
COPY app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app.jar"]
```

### 9.2 환경별 설정
- 개발: application-dev.yml
- 스테이징: application-staging.yml
- 프로덕션: application-prod.yml

### 9.3 확장성 고려사항
- 다중 인스턴스 배포 가능 (Stateless)
- Redis를 통한 세션 공유 (향후 확장)
- Load Balancer 지원