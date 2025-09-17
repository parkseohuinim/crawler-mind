package com.aegis.auth.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 토큰 유효성 검증 응답 DTO
 */
@Schema(description = "토큰 유효성 검증 응답")
public record TokenValidationResponse(
    
    @Schema(description = "토큰 유효성 여부", example = "true")
    boolean valid,
    
    @Schema(description = "사용자 정보 (토큰이 유효한 경우)")
    UserDto user,
    
    @Schema(description = "응답 시간 (Unix timestamp)", example = "1726471200000")
    long timestamp
    
) {
}
