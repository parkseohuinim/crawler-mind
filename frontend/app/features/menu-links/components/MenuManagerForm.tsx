'use client';

import React, { useState, useEffect } from 'react';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate, MenuLink } from '../types';

interface MenuManagerFormProps {
  menuLinks: MenuLink[];
  managerInfo?: MenuManagerInfo;
  onSubmit: (data: MenuManagerInfoCreate | MenuManagerInfoUpdate) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  isEdit?: boolean;
  getAssignedMenuIds?: () => Promise<number[]>;
}

export default function MenuManagerForm({
  menuLinks,
  managerInfo,
  onSubmit,
  onCancel,
  loading = false,
  isEdit = false
}: MenuManagerFormProps) {
  // 디버깅을 위한 로그
  console.log('MenuManagerForm Debug:', {
    isEdit,
    menuLinksCount: menuLinks.length,
    menuLinks: menuLinks.map(menu => ({ id: menu.id, menu_path: menu.menu_path })),
    managerInfo
  });

  const [formData, setFormData] = useState({
    menu_id: managerInfo?.menu_id || 0,
    team_name: managerInfo?.team_name || '',
    manager_names: managerInfo?.manager_names || ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (managerInfo) {
      setFormData({
        menu_id: managerInfo.menu_id,
        team_name: managerInfo.team_name,
        manager_names: managerInfo.manager_names
      });
    }
  }, [managerInfo]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.menu_id) {
      newErrors.menu_id = '메뉴를 선택해주세요';
    }

    if (!formData.team_name.trim()) {
      newErrors.team_name = '팀명을 입력해주세요';
    }

    if (!formData.manager_names.trim()) {
      newErrors.manager_names = '담당자명을 입력해주세요';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      if (isEdit && managerInfo) {
        await onSubmit({
          team_name: formData.team_name,
          manager_names: formData.manager_names
        } as MenuManagerInfoUpdate);
      } else {
        await onSubmit({
          menu_id: formData.menu_id,
          team_name: formData.team_name,
          manager_names: formData.manager_names
        } as MenuManagerInfoCreate);
      }
    } catch (error) {
      console.error('Form submission error:', error);
    }
  };

  const handleInputChange = (field: string, value: string | number) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="menu-manager-form">
      {!isEdit && (
        <div className="form-group">
          <label htmlFor="menu_id">
            메뉴 선택 *
          </label>
          <select
            id="menu_id"
            value={formData.menu_id}
            onChange={(e) => handleInputChange('menu_id', parseInt(e.target.value))}
            className={errors.menu_id ? 'form-error' : ''}
          >
            <option value={0}>메뉴를 선택하세요</option>
            {menuLinks.map((menu) => (
              <option key={menu.id} value={menu.id}>
                {menu.menu_path}
              </option>
            ))}
          </select>
          {errors.menu_id && (
            <p className="form-error">{errors.menu_id}</p>
          )}
          <p className="form-help">
            담당자가 배정되지 않은 메뉴만 표시됩니다
          </p>
        </div>
      )}

      {isEdit && (
        <div className="form-group">
          <label>현재 메뉴</label>
          <div className="current-menu-display">
            {(() => {
              const currentMenu = menuLinks.find(menu => menu.id === managerInfo?.menu_id);
              return currentMenu?.menu_path?.split('^').join(' > ') || '알 수 없음';
            })()}
          </div>
          <p className="form-help">
            수정 모드에서는 메뉴를 변경할 수 없습니다
          </p>
        </div>
      )}

      <div className="form-group">
        <label htmlFor="team_name">
          팀명 *
        </label>
        <input
          type="text"
          id="team_name"
          value={formData.team_name}
          onChange={(e) => handleInputChange('team_name', e.target.value)}
          placeholder="예: 개발팀, 디자인팀, 기획팀"
          className={errors.team_name ? 'form-error' : ''}
        />
        {errors.team_name && (
          <p className="form-error">{errors.team_name}</p>
        )}
      </div>

      <div className="form-group">
        <label htmlFor="manager_names">
          담당자명 *
        </label>
        <textarea
          id="manager_names"
          value={formData.manager_names}
          onChange={(e) => handleInputChange('manager_names', e.target.value)}
          placeholder="예: 홍길동/김철수/이영희"
          rows={3}
          className={errors.manager_names ? 'form-error' : ''}
        />
        <p className="form-help">
          여러 명의 담당자가 있을 경우 슬래시(/)로 구분하여 입력하세요
        </p>
        {errors.manager_names && (
          <p className="form-error">{errors.manager_names}</p>
        )}
      </div>

      <div className="form-actions">
        <button
          type="button"
          onClick={onCancel}
          disabled={loading}
          className="cancel-button"
        >
          취소
        </button>
        <button
          type="submit"
          disabled={loading}
          className="submit-button"
        >
          {loading ? '처리 중...' : isEdit ? '수정' : '생성'}
        </button>
      </div>
    </form>
  );
}
