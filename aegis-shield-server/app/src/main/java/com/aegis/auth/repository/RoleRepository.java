package com.aegis.auth.repository;

import com.aegis.auth.entity.Role;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 역할 Repository
 * 역할 데이터 접근을 위한 JPA Repository 인터페이스
 */
@Repository
public interface RoleRepository extends JpaRepository<Role, Long> {
    
    Optional<Role> findByName(String name);
    
    boolean existsByName(String name);
    
    @Query("SELECT r FROM Role r WHERE r.isActive = true ORDER BY r.name")
    List<Role> findAllActiveRoles();
    
    @Query("SELECT r FROM Role r WHERE r.isSystem = true AND r.isActive = true ORDER BY r.name")
    List<Role> findSystemRoles();
    
    @Query("SELECT r FROM Role r WHERE r.isSystem = false AND r.isActive = true ORDER BY r.name")
    List<Role> findCustomRoles();
}