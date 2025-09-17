package com.aegis.auth.dto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 로그인 응답 DTO (Java 21 Record)
 * 성공적인 인증 후 클라이언트에 전달되는 정보
 */
public record LoginResponse(
    String accessToken,
    String refreshToken,
    UserDto user,
    List<String> roles,
    LocalDateTime expiresAt
) {}