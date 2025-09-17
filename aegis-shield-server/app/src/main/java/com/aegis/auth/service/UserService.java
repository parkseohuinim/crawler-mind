package com.aegis.auth.service;

import com.aegis.auth.entity.User;
import com.aegis.auth.exception.AuthException;
import com.aegis.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

/**
 * 사용자 서비스
 * 사용자 관련 비즈니스 로직을 처리하는 서비스 계층
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class UserService {
    
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    
    public Optional<User> findByUsernameOrEmail(String usernameOrEmail) {
        log.debug("Searching user by username or email: {}", usernameOrEmail);
        return userRepository.findByUsernameOrEmail(usernameOrEmail);
    }
    
    public Optional<User> findById(Long userId) {
        return userRepository.findById(userId);
    }
    
    public Optional<User> findByIdWithRoles(Long userId) {
        return userRepository.findByIdWithRoles(userId);
    }
    
    public boolean existsByUsername(String username) {
        return userRepository.existsByUsername(username);
    }
    
    public boolean existsByEmail(String email) {
        return userRepository.existsByEmail(email);
    }
    
    public boolean validatePassword(User user, String password) {
        boolean isValid = passwordEncoder.matches(password, user.getPasswordHash());
        log.debug("Password validation for user {}: {}", user.getUsername(), isValid);
        return isValid;
    }
    
    @Transactional
    public void updateLastLogin(User user) {
        log.info("Updating last login time for user: {}", user.getUsername());
        user.updateLastLogin();
        userRepository.save(user);
    }
    
    @Transactional
    public User createUser(String username, String email, String password, String fullName) {
        if (existsByUsername(username)) {
            throw new AuthException.DuplicateUserException("이미 존재하는 사용자명입니다: " + username);
        }
        if (existsByEmail(email)) {
            throw new AuthException.DuplicateUserException("이미 존재하는 이메일입니다: " + email);
        }
        
        User user = User.builder()
                .username(username)
                .email(email)
                .passwordHash(passwordEncoder.encode(password))
                .fullName(fullName)
                .isActive(true)
                .isVerified(false)
                .build();
                
        User savedUser = userRepository.save(user);
        log.info("Created new user: {}", savedUser.getUsername());
        return savedUser;
    }
    
    public List<String> getRoleNamesByUserId(Long userId) {
        return userRepository.findByIdWithRoles(userId)
                .map(user -> user.getUserRoles().stream()
                        .filter(ur -> !ur.isExpired())
                        .map(ur -> ur.getRole().getName())
                        .toList())
                .orElse(List.of());
    }

    @Transactional
    public boolean resetPassword(String usernameOrEmail, String newRawPassword) {
        return userRepository.findByUsernameOrEmail(usernameOrEmail)
            .map(user -> {
                user.setPasswordHash(passwordEncoder.encode(newRawPassword));
                userRepository.save(user);
                log.info("Password reset for user: {}", user.getUsername());
                return true;
            })
            .orElse(false);
    }
}