package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 관리자용 비밀번호 강제 재설정 요청 DTO
 */
@Schema(description = "관리자용 비밀번호 강제 재설정 요청")
public record AdminResetPasswordRequest(
    
    @Schema(description = "대상 사용자명 또는 이메일", example = "user123")
    @NotBlank(message = "사용자명 또는 이메일은 필수입니다")
    String usernameOrEmail,
    
    @Schema(description = "새 비밀번호 (최소 6자)", example = "newPassword123!")
    @NotBlank(message = "새 비밀번호는 필수입니다")
    @Size(min = 6, message = "비밀번호는 최소 6자 이상이어야 합니다")
    String newPassword
    
) {
}
