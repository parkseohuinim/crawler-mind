package com.aegis.auth.exception;

import com.aegis.auth.dto.ApiErrorResponse;
import com.aegis.auth.dto.ValidationErrorResponse;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.MalformedJwtException;
import io.jsonwebtoken.security.SecurityException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;

/**
 * 글로벌 예외 처리기
 * 애플리케이션 전체의 예외를 일관된 형태로 처리
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * Validation 에러 처리
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidationErrors(MethodArgumentNotValidException ex) {
        Map<String, String> errors = new HashMap<>();
        
        ex.getBindingResult().getAllErrors().forEach((error) -> {
            String fieldName = ((FieldError) error).getField();
            String errorMessage = error.getDefaultMessage();
            errors.put(fieldName, errorMessage);
        });

        // 첫 번째 에러 메시지를 주 메시지로 사용
        String mainMessage = errors.values().iterator().next();
        
        log.warn("Validation failed: {}", errors);
        
        return ResponseEntity.badRequest().body(new ValidationErrorResponse(
            "VALIDATION_FAILED",
            mainMessage,
            errors,
            System.currentTimeMillis()
        ));
    }

    /**
     * 접근 권한 에러 처리
     */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiErrorResponse> handleAccessDenied(AccessDeniedException ex) {
        log.warn("Access denied: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(new ApiErrorResponse(
            "ACCESS_DENIED",
            "관리자 권한이 필요합니다",
            System.currentTimeMillis()
        ));
    }

    /**
     * 일반적인 IllegalArgumentException 처리
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiErrorResponse> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Invalid argument: {}", ex.getMessage());
        
        return ResponseEntity.badRequest().body(new ApiErrorResponse(
            "INVALID_ARGUMENT",
            ex.getMessage(),
            System.currentTimeMillis()
        ));
    }

    /**
     * JWT 관련 예외 처리
     */
    @ExceptionHandler(ExpiredJwtException.class)
    public ResponseEntity<ApiErrorResponse> handleExpiredJwtException(ExpiredJwtException ex) {
        log.warn("JWT token expired: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "EXPIRED_TOKEN",
            "토큰이 만료되었습니다",
            System.currentTimeMillis()
        ));
    }
    
    @ExceptionHandler(MalformedJwtException.class)
    public ResponseEntity<ApiErrorResponse> handleMalformedJwtException(MalformedJwtException ex) {
        log.warn("Malformed JWT token: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "INVALID_TOKEN",
            "잘못된 형식의 토큰입니다",
            System.currentTimeMillis()
        ));
    }
    
    @ExceptionHandler(SecurityException.class)
    public ResponseEntity<ApiErrorResponse> handleJwtSecurityException(SecurityException ex) {
        log.warn("JWT security error: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "INVALID_TOKEN",
            "토큰 서명이 유효하지 않습니다",
            System.currentTimeMillis()
        ));
    }
    
    @ExceptionHandler(JwtException.class)
    public ResponseEntity<ApiErrorResponse> handleJwtException(JwtException ex) {
        log.warn("JWT error: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "INVALID_TOKEN",
            "유효하지 않은 토큰입니다",
            System.currentTimeMillis()
        ));
    }
    
    /**
     * 인증 관련 예외 처리
     */
    @ExceptionHandler(AuthException.class)
    public ResponseEntity<ApiErrorResponse> handleAuthException(AuthException ex) {
        log.warn("Authentication error [{}]: {}", ex.getErrorCode(), ex.getMessage());
        
        HttpStatus status = switch (ex.getErrorCode()) {
            case "USER_NOT_FOUND", "INVALID_CREDENTIALS" -> HttpStatus.UNAUTHORIZED;
            case "ACCOUNT_INACTIVE" -> HttpStatus.FORBIDDEN;
            case "DUPLICATE_USER" -> HttpStatus.CONFLICT;
            case "INVALID_TOKEN", "EXPIRED_TOKEN" -> HttpStatus.UNAUTHORIZED;
            default -> HttpStatus.BAD_REQUEST;
        };
        
        return ResponseEntity.status(status).body(new ApiErrorResponse(
            ex.getErrorCode(),
            ex.getMessage(),
            System.currentTimeMillis()
        ));
    }
    
    @ExceptionHandler(BadCredentialsException.class)
    public ResponseEntity<ApiErrorResponse> handleBadCredentials(BadCredentialsException ex) {
        log.warn("Bad credentials: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "INVALID_CREDENTIALS",
            "아이디 또는 비밀번호가 올바르지 않습니다",
            System.currentTimeMillis()
        ));
    }
    
    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<ApiErrorResponse> handleAuthenticationException(AuthenticationException ex) {
        log.warn("Authentication failed: {}", ex.getMessage());
        
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(new ApiErrorResponse(
            "AUTHENTICATION_FAILED",
            "인증에 실패했습니다",
            System.currentTimeMillis()
        ));
    }

    /**
     * 예상치 못한 서버 에러 처리
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleGenericError(Exception ex) {
        log.error("Unexpected error occurred", ex);
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(new ApiErrorResponse(
            "INTERNAL_SERVER_ERROR",
            "서버 내부 오류가 발생했습니다",
            System.currentTimeMillis()
        ));
    }
}
