package com.aegis.auth.controller;

import com.aegis.auth.dto.*;
import com.aegis.auth.entity.User;
import com.aegis.auth.exception.AuthException;
import com.aegis.auth.service.AuthService;
import com.aegis.auth.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 인증 컨트롤러
 * Aegis Shield의 REST API 엔드포인트를 제공하는 컨트롤러
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"})
@Tag(name = "Authentication", description = "사용자 인증 및 토큰 관리 API")
public class AuthController {
    
    private final AuthService authService;
    private final UserService userService;
    private final PasswordEncoder passwordEncoder;
    
    /**
     * 사용자 로그인
     * @param request 로그인 요청 정보
     * @return JWT 토큰 및 사용자 정보
     */
    @Operation(summary = "사용자 로그인", description = "사용자명/이메일과 비밀번호로 로그인하여 JWT 토큰을 발급받습니다")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "로그인 성공", 
                    content = @Content(schema = @Schema(implementation = LoginResponse.class))),
        @ApiResponse(responseCode = "400", description = "로그인 실패", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    @PostMapping("/login")
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        LoginResponse response = authService.login(request);
        return ResponseEntity.ok(response);
    }
    
    /**
     * 토큰 갱신
     * @param request 리프레시 토큰 정보
     * @return 새로운 액세스 토큰
     */
    @Operation(summary = "토큰 갱신", description = "리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급받습니다")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "토큰 갱신 성공", 
                    content = @Content(schema = @Schema(implementation = LoginResponse.class))),
        @ApiResponse(responseCode = "400", description = "토큰 갱신 실패", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    @PostMapping("/refresh")
    public ResponseEntity<LoginResponse> refresh(@Valid @RequestBody RefreshTokenRequest request) {
        LoginResponse response = authService.refreshToken(request.refreshToken());
        return ResponseEntity.ok(response);
    }
    
    /**
     * 토큰 유효성 검증
     * Authorization 헤더의 Bearer 토큰을 검증하고 사용자 정보를 반환합니다
     * @return 토큰 유효성 결과 및 사용자 정보
     */
    @Operation(summary = "토큰 유효성 검증", description = "Authorization 헤더의 JWT Bearer 토큰 유효성을 검증하고 사용자 정보를 반환합니다")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "토큰 검증 완료", 
                    content = @Content(schema = @Schema(implementation = TokenValidationResponse.class))),
        @ApiResponse(responseCode = "401", description = "토큰이 없거나 잘못된 형식", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    @PostMapping("/validate")
    public ResponseEntity<TokenValidationResponse> validateToken(@RequestHeader("Authorization") String authorizationHeader) {
        // Bearer 토큰 추출
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            throw new AuthException.InvalidTokenException("Authorization header with Bearer token is required");
        }
        
        String token = authorizationHeader.substring(7); // "Bearer " 제거
        boolean isValid = authService.validateAccessToken(token);
        
        UserDto user = null;
        if (isValid) {
            // 토큰이 유효한 경우 사용자 정보 조회
            String username = authService.getUsernameFromToken(token);
            if (username != null) {
                Optional<User> userEntity = userService.findByUsernameOrEmail(username);
                if (userEntity.isPresent()) {
                    User foundUser = userEntity.get();
                    List<String> roles = userService.getRoleNamesByUserId(foundUser.getId());
                    user = UserDto.from(foundUser, roles);
                }
            }
        }
        
        return ResponseEntity.ok(new TokenValidationResponse(
            isValid,
            user,
            System.currentTimeMillis()
        ));
    }
    
    /**
     * 로그아웃
     * JWT는 상태가 없으므로 클라이언트에서 토큰을 삭제하면 됨
     * @return 로그아웃 성공 메시지
     */
    @Operation(summary = "로그아웃", description = "사용자 로그아웃 (클라이언트에서 토큰 삭제 필요)")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "로그아웃 성공")
    })
    @PostMapping("/logout")
    public ResponseEntity<?> logout() {
        return ResponseEntity.ok(Map.of(
            "message", "Successfully logged out",
            "timestamp", System.currentTimeMillis()
        ));
    }
    
    /**
     * 관리자용 비밀번호 강제 재설정
     * @param request 사용자 정보 및 새 비밀번호
     * @return 재설정 결과
     */
    @Operation(summary = "관리자용 비밀번호 재설정", description = "관리자가 특정 사용자의 비밀번호를 강제로 재설정합니다")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "비밀번호 재설정 성공", 
                    content = @Content(schema = @Schema(implementation = AdminResetPasswordResponse.class))),
        @ApiResponse(responseCode = "400", description = "재설정 실패", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @ApiResponse(responseCode = "403", description = "관리자 권한 필요", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    @PostMapping("/admin/reset-password")
    @PreAuthorize("hasAuthority('admin')")
    public ResponseEntity<AdminResetPasswordResponse> adminResetPassword(@Valid @RequestBody AdminResetPasswordRequest request) {
        // 현재 인증된 관리자 정보 가져오기
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        String adminUsername = authentication.getName();
        
        log.info("Admin {} attempting to reset password for user: {}", adminUsername, request.usernameOrEmail());
        
        // UserService의 resetPassword 메소드 사용
        boolean success = userService.resetPassword(request.usernameOrEmail(), request.newPassword());
        
        if (success) {
            log.info("Password reset successful by admin {} for user: {}", adminUsername, request.usernameOrEmail());
            return ResponseEntity.ok(new AdminResetPasswordResponse(
                true,
                "Password reset successfully for user: " + request.usernameOrEmail(),
                System.currentTimeMillis()
            ));
        } else {
            log.warn("Password reset failed by admin {} - user not found: {}", adminUsername, request.usernameOrEmail());
            throw new IllegalArgumentException("User not found: " + request.usernameOrEmail());
        }
    }

    /**
     * 회원가입
     */
    @Operation(summary = "회원가입", description = "새로운 사용자 계정을 생성합니다")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "회원가입 성공"),
        @ApiResponse(responseCode = "400", description = "회원가입 실패", 
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> register(@Valid @RequestBody RegisterRequest request) {
        var user = userService.createUser(request.username(), request.email(), request.password(), request.fullName());
        return ResponseEntity.ok(Map.of(
            "id", user.getId(),
            "username", user.getUsername(),
            "email", user.getEmail()
        ));
    }
}