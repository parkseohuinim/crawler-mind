package com.aegis.auth.exception;

/**
 * 인증 관련 예외
 * JWT 토큰 및 인증 과정에서 발생하는 예외를 처리
 */
public class AuthException extends RuntimeException {
    
    private final String errorCode;
    
    public AuthException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }
    
    public AuthException(String errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }
    
    public String getErrorCode() {
        return errorCode;
    }
    
    // 특정 인증 예외들
    public static class InvalidTokenException extends AuthException {
        public InvalidTokenException(String message) {
            super("INVALID_TOKEN", message);
        }
    }
    
    public static class ExpiredTokenException extends AuthException {
        public ExpiredTokenException(String message) {
            super("EXPIRED_TOKEN", message);
        }
    }
    
    public static class InvalidCredentialsException extends AuthException {
        public InvalidCredentialsException(String message) {
            super("INVALID_CREDENTIALS", message);
        }
    }
    
    public static class AccountInactiveException extends AuthException {
        public AccountInactiveException(String message) {
            super("ACCOUNT_INACTIVE", message);
        }
    }
    
    public static class UserNotFoundException extends AuthException {
        public UserNotFoundException(String message) {
            super("USER_NOT_FOUND", message);
        }
    }
    
    public static class DuplicateUserException extends AuthException {
        public DuplicateUserException(String message) {
            super("DUPLICATE_USER", message);
        }
    }
}
