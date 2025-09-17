package com.aegis.auth.dto;

import com.aegis.auth.entity.User;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 사용자 정보 DTO (Java 21 Record)
 * 클라이언트에 전달할 사용자 정보를 캡슐화
 */
public record UserDto(
    Long id,
    String username,
    String email,
    String fullName,
    Boolean isActive,
    Boolean isVerified,
    LocalDateTime lastLoginAt,
    LocalDateTime createdAt,
    List<String> roles
) {
    
    public static UserDto from(User user) {
        return new UserDto(
            user.getId(),
            user.getUsername(),
            user.getEmail(),
            user.getFullName(),
            user.getIsActive(),
            user.getIsVerified(),
            user.getLastLoginAt(),
            user.getCreatedAt(),
            List.of() // 기본값으로 빈 리스트, 실제 역할은 별도로 설정
        );
    }
    
    public static UserDto from(User user, List<String> roles) {
        return new UserDto(
            user.getId(),
            user.getUsername(),
            user.getEmail(),
            user.getFullName(),
            user.getIsActive(),
            user.getIsVerified(),
            user.getLastLoginAt(),
            user.getCreatedAt(),
            roles != null ? roles : List.of()
        );
    }
}