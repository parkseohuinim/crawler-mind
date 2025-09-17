package com.aegis.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 로그인 요청 DTO (Java 21 Record)
 * 사용자 인증을 위한 요청 데이터 구조
 */
public record LoginRequest(
    @NotBlank(message = "사용자명 또는 이메일은 필수입니다")
    @Size(max = 100, message = "사용자명 또는 이메일은 100자를 초과할 수 없습니다")
    String usernameOrEmail,
    
    @NotBlank(message = "비밀번호는 필수입니다")
    @Size(min = 6, max = 100, message = "비밀번호는 6자 이상 100자 이하여야 합니다")
    String password
) {}