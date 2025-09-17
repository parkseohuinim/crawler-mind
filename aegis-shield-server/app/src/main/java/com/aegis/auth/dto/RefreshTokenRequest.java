package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * 토큰 갱신 요청 DTO
 */
@Schema(description = "토큰 갱신 요청")
public record RefreshTokenRequest(
    
    @Schema(description = "갱신용 리프레시 토큰", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    @NotBlank(message = "리프레시 토큰은 필수입니다")
    String refreshToken
    
) {
}
