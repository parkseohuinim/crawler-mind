package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * API 에러 응답 DTO
 */
@Schema(description = "API 에러 응답")
public record ApiErrorResponse(
    
    @Schema(description = "에러 코드", example = "AUTHENTICATION_FAILED")
    String error,
    
    @Schema(description = "에러 메시지", example = "Invalid username or password")
    String message,
    
    @Schema(description = "에러 발생 시간 (Unix timestamp)", example = "1726471200000")
    long timestamp
    
) {
}
