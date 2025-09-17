package com.aegis.auth.util;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;

/**
 * JWT 토큰 유틸리티
 * Aegis Shield의 JWT 토큰 생성, 검증, 파싱을 담당하는 핵심 컴포넌트
 */
@Component
public class JwtUtil {
    
    @Value("${jwt.secret}")
    private String secret;
    
    @Value("${jwt.access-token-validity}")
    private long accessTokenValidityInSeconds;
    
    @Value("${jwt.refresh-token-validity}")
    private long refreshTokenValidityInSeconds;
    
    @Value("${jwt.issuer}")
    private String issuer;
    
    private SecretKey key;
    
    @PostConstruct
    public void init() {
        this.key = Keys.hmacShaKeyFor(secret.getBytes());
    }
    
    public String generateAccessToken(Long userId, String username, List<String> roles) {
        Date expiration = new Date(System.currentTimeMillis() + accessTokenValidityInSeconds * 1000);
        
        return Jwts.builder()
                .subject(userId.toString())
                .claim("username", username)
                .claim("roles", roles)
                .claim("type", "access")
                .issuer(issuer)
                .issuedAt(new Date())
                .expiration(expiration)
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }
    
    public String generateRefreshToken(Long userId) {
        Date expiration = new Date(System.currentTimeMillis() + refreshTokenValidityInSeconds * 1000);
        
        return Jwts.builder()
                .subject(userId.toString())
                .claim("type", "refresh")
                .issuer(issuer)
                .issuedAt(new Date())
                .expiration(expiration)
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }
    
    public Claims extractClaims(String token) {
        return Jwts.parser()
                .verifyWith(key)
                .requireIssuer(issuer)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
    
    public Long extractUserId(String token) {
        return Long.valueOf(extractClaims(token).getSubject());
    }
    
    public String extractUsername(String token) {
        return extractClaims(token).get("username", String.class);
    }
    
    @SuppressWarnings("unchecked")
    public List<String> extractRoles(String token) {
        return extractClaims(token).get("roles", List.class);
    }
    
    public String extractTokenType(String token) {
        return extractClaims(token).get("type", String.class);
    }
    
    public LocalDateTime extractExpiration(String token) {
        Date expiration = extractClaims(token).getExpiration();
        return expiration.toInstant().atZone(ZoneId.systemDefault()).toLocalDateTime();
    }
    
    public boolean isTokenExpired(String token) {
        try {
            return extractClaims(token).getExpiration().before(new Date());
        } catch (ExpiredJwtException e) {
            return true;
        }
    }
    
    public boolean validateToken(String token) {
        try {
            extractClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }
    
    public boolean isAccessToken(String token) {
        return "access".equals(extractTokenType(token));
    }
    
    public boolean isRefreshToken(String token) {
        return "refresh".equals(extractTokenType(token));
    }
}