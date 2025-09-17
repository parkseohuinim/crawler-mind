package com.aegis.auth.repository;

import com.aegis.auth.entity.UserRole;
import com.aegis.auth.entity.UserRoleId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 사용자-역할 매핑 Repository
 * 사용자와 역할 간의 매핑 관계 데이터 접근을 위한 JPA Repository 인터페이스
 */
@Repository
public interface UserRoleRepository extends JpaRepository<UserRole, UserRoleId> {
    
    @Query("SELECT ur FROM UserRole ur JOIN FETCH ur.role WHERE ur.user.id = :userId")
    List<UserRole> findByUserId(@Param("userId") Long userId);
    
    @Query("SELECT ur FROM UserRole ur JOIN FETCH ur.user WHERE ur.role.id = :roleId")
    List<UserRole> findByRoleId(@Param("roleId") Long roleId);
    
    @Query("SELECT ur FROM UserRole ur JOIN FETCH ur.role r " +
           "WHERE ur.user.id = :userId AND r.isActive = true " +
           "AND (ur.expiresAt IS NULL OR ur.expiresAt > CURRENT_TIMESTAMP)")
    List<UserRole> findActiveUserRolesByUserId(@Param("userId") Long userId);
    
    @Query("SELECT COUNT(ur) FROM UserRole ur WHERE ur.role.id = :roleId")
    long countByRoleId(@Param("roleId") Long roleId);
    
    boolean existsByUserIdAndRoleId(Long userId, Long roleId);
}