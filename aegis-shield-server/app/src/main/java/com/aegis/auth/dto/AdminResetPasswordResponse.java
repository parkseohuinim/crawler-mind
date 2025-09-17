package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 관리자용 비밀번호 재설정 응답 DTO
 */
@Schema(description = "관리자용 비밀번호 재설정 응답")
public record AdminResetPasswordResponse(
    
    @Schema(description = "재설정 성공 여부", example = "true")
    boolean success,
    
    @Schema(description = "결과 메시지", example = "Password reset successfully for user: user123")
    String message,
    
    @Schema(description = "응답 시간 (Unix timestamp)", example = "1726471200000")
    long timestamp
    
) {
}
