package com.aegis.auth.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/protected")
public class ProtectedController {

    @GetMapping("/ping")
    public ResponseEntity<?> ping(Authentication authentication) {
        String username = authentication != null ? String.valueOf(authentication.getPrincipal()) : "anonymous";
        return ResponseEntity.ok(Map.of(
            "ok", true,
            "user", username
        ));
    }
}
