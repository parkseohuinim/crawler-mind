package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.Map;

/**
 * Validation 에러 상세 응답 DTO
 */
@Schema(description = "Validation 에러 상세 응답")
public record ValidationErrorResponse(
    
    @Schema(description = "에러 코드", example = "VALIDATION_FAILED")
    String error,
    
    @Schema(description = "주 에러 메시지", example = "비밀번호는 최소 6자 이상이어야 합니다")
    String message,
    
    @Schema(description = "필드별 에러 상세", example = "{\"newPassword\": \"비밀번호는 최소 6자 이상이어야 합니다\"}")
    Map<String, String> fieldErrors,
    
    @Schema(description = "에러 발생 시간 (Unix timestamp)", example = "1726471200000")
    long timestamp
    
) {
}
