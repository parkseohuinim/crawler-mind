package com.aegis.auth.service;

import com.aegis.auth.dto.LoginRequest;
import com.aegis.auth.dto.LoginResponse;
import com.aegis.auth.dto.UserDto;
import com.aegis.auth.entity.User;
import com.aegis.auth.exception.AuthException;
import com.aegis.auth.util.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 인증 서비스
 * JWT 기반 인증 및 토큰 관리를 담당하는 핵심 서비스
 */
@Service
@RequiredArgsConstructor
@Transactional
@Slf4j
public class AuthService {
    
    private final UserService userService;
    private final JwtUtil jwtUtil;
    
    public LoginResponse login(LoginRequest request) {
        log.info("Login attempt for user: {}", request.usernameOrEmail());
        
        User user = userService.findByUsernameOrEmail(request.usernameOrEmail())
                .orElseThrow(() -> {
                    log.warn("Login failed - user not found: {}", request.usernameOrEmail());
                    return new AuthException.UserNotFoundException("사용자를 찾을 수 없습니다");
                });
        
        if (!user.isAccountActive()) {
            log.warn("Login failed - account inactive: {}", user.getUsername());
            throw new AuthException.AccountInactiveException("계정이 비활성화되었거나 인증되지 않았습니다");
        }
        
        if (!userService.validatePassword(user, request.password())) {
            log.warn("Login failed - invalid password for user: {}", user.getUsername());
            throw new AuthException.InvalidCredentialsException("아이디 또는 비밀번호가 올바르지 않습니다");
        }
        
        // 마지막 로그인 시간 업데이트
        userService.updateLastLogin(user);
        
        // 사용자 역할 조회
        List<String> roles = userService.getRoleNamesByUserId(user.getId());
        log.debug("User {} has roles: {}", user.getUsername(), roles);
        
        // JWT 토큰 생성
        String accessToken = jwtUtil.generateAccessToken(user.getId(), user.getUsername(), roles);
        String refreshToken = jwtUtil.generateRefreshToken(user.getId());
        
        log.info("Login successful for user: {}", user.getUsername());
        return new LoginResponse(
                accessToken,
                refreshToken,
                UserDto.from(user, roles),
                roles,
                jwtUtil.extractExpiration(accessToken)
        );
    }
    
    public LoginResponse refreshToken(String refreshToken) {
        log.debug("Token refresh requested");
        
        if (!jwtUtil.validateToken(refreshToken) || !jwtUtil.isRefreshToken(refreshToken)) {
            log.warn("Token refresh failed - invalid refresh token");
            throw new AuthException.InvalidTokenException("유효하지 않은 리프레시 토큰입니다");
        }
        
        Long userId = jwtUtil.extractUserId(refreshToken);
        User user = userService.findByIdWithRoles(userId)
                .orElseThrow(() -> {
                    log.warn("Token refresh failed - user not found: {}", userId);
                    return new AuthException.UserNotFoundException("사용자를 찾을 수 없습니다");
                });
        
        if (!user.isAccountActive()) {
            log.warn("Token refresh failed - account inactive: {}", user.getUsername());
            throw new AuthException.AccountInactiveException("계정이 비활성화되었습니다");
        }
        
        // 사용자 역할 조회
        List<String> roles = userService.getRoleNamesByUserId(user.getId());
        
        // 새로운 액세스 토큰 생성
        String newAccessToken = jwtUtil.generateAccessToken(user.getId(), user.getUsername(), roles);
        
        log.info("Token refreshed successfully for user: {}", user.getUsername());
        return new LoginResponse(
                newAccessToken,
                refreshToken, // 리프레시 토큰은 그대로 유지
                UserDto.from(user, roles),
                roles,
                jwtUtil.extractExpiration(newAccessToken)
        );
    }
    
    public boolean validateAccessToken(String token) {
        boolean isValid = jwtUtil.validateToken(token) && jwtUtil.isAccessToken(token);
        log.debug("Access token validation result: {}", isValid);
        return isValid;
    }
    
    /**
     * 토큰에서 사용자명 추출
     * @param token JWT 액세스 토큰
     * @return 사용자명 또는 null (토큰이 유효하지 않은 경우)
     */
    public String getUsernameFromToken(String token) {
        try {
            if (validateAccessToken(token)) {
                return jwtUtil.extractUsername(token);
            }
            return null;
        } catch (Exception e) {
            log.warn("Failed to extract username from token: {}", e.getMessage());
            return null;
        }
    }
}