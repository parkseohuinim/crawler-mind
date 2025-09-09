'use client';

import React, { useState, useEffect } from 'react';
import { MenuManagerInfo, MenuManagerInfoCreate, MenuManagerInfoUpdate } from '@/app/_lib/domains/menuManagerInfo';
import { MenuLink } from '@/app/_lib/domains/menuLink';
import ModernForm, { 
  ModernFormGroup, 
  ModernFormRow, 
  ModernFormLabel, 
  ModernFormInput, 
  ModernFormSelect,
  ModernFormActions, 
  ModernFormButton 
} from '@/app/_components/ui/ModernForm';

interface MenuManagerInfoFormProps {
  menuLinks: MenuLink[];
  menuManagerInfo?: MenuManagerInfo;
  onSubmit: (data: MenuManagerInfoCreate | MenuManagerInfoUpdate) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  isEdit?: boolean;
}

export default function MenuManagerInfoForm({
  menuLinks,
  menuManagerInfo,
  onSubmit,
  onCancel,
  loading = false,
  isEdit = false
}: MenuManagerInfoFormProps) {
  const [formData, setFormData] = useState({
    menu_id: menuManagerInfo?.menu_id || 0,
    team_name: menuManagerInfo?.team_name || '',
    manager_names: menuManagerInfo?.manager_names || ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (menuManagerInfo) {
      setFormData({
        menu_id: menuManagerInfo.menu_id,
        team_name: menuManagerInfo.team_name,
        manager_names: menuManagerInfo.manager_names
      });
    }
  }, [menuManagerInfo]);

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
      if (isEdit && menuManagerInfo) {
        await onSubmit({
          team_name: formData.team_name,
          manager_names: formData.manager_names,
          updated_by: 'admin'
        } as MenuManagerInfoUpdate);
      } else {
        await onSubmit({
          menu_id: formData.menu_id,
          team_name: formData.team_name,
          manager_names: formData.manager_names,
          created_by: 'admin'
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
    <ModernForm
      title={isEdit ? '매니저 정보 수정' : '매니저 정보 생성'}
      subtitle={isEdit ? '기존 매니저 정보를 수정합니다' : '새로운 매니저 정보를 생성합니다'}
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      }
      onSubmit={handleSubmit}
    >
      {!isEdit && (
        <ModernFormGroup>
          <ModernFormLabel htmlFor="menu_id" required>메뉴 선택</ModernFormLabel>
          <ModernFormSelect
            id="menu_id"
            value={formData.menu_id.toString()}
            onChange={(e) => handleInputChange('menu_id', parseInt(e.target.value))}
            error={errors.menu_id}
            help="담당자가 배정되지 않은 메뉴만 표시됩니다"
          >
            <option value="0">메뉴를 선택하세요</option>
            {menuLinks.map((menu) => (
              <option key={menu.id} value={menu.id}>
                {menu.menu_path.split('^').join(' > ')}
              </option>
            ))}
          </ModernFormSelect>
        </ModernFormGroup>
      )}

      {isEdit && (
        <ModernFormGroup>
          <ModernFormLabel>현재 메뉴</ModernFormLabel>
          <div className="modern-form-input" style={{ background: '#f7fafc', color: '#718096' }}>
            {(() => {
              const currentMenu = menuLinks.find(menu => menu.id === menuManagerInfo?.menu_id);
              return currentMenu?.menu_path?.split('^').join(' > ') || '알 수 없음';
            })()}
          </div>
          <div className="modern-form-help">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            수정 모드에서는 메뉴를 변경할 수 없습니다
          </div>
        </ModernFormGroup>
      )}

      <ModernFormRow>
        <ModernFormGroup>
          <ModernFormLabel htmlFor="team_name" required>팀명</ModernFormLabel>
          <ModernFormInput
            type="text"
            id="team_name"
            value={formData.team_name}
            onChange={(e) => handleInputChange('team_name', e.target.value)}
            placeholder="예: 개발팀, 디자인팀, 기획팀"
            error={errors.team_name}
          />
        </ModernFormGroup>
        
        <ModernFormGroup>
          <ModernFormLabel htmlFor="manager_names" required>담당자명</ModernFormLabel>
          <ModernFormInput
            type="text"
            id="manager_names"
            value={formData.manager_names}
            onChange={(e) => handleInputChange('manager_names', e.target.value)}
            placeholder="예: 홍길동/김철수/이영희"
            error={errors.manager_names}
            help="여러 명의 담당자가 있을 경우 슬래시(/)로 구분하여 입력하세요"
          />
        </ModernFormGroup>
      </ModernFormRow>
      
      <ModernFormActions>
        <ModernFormButton
          type="button"
          variant="secondary"
          onClick={onCancel}
          disabled={loading}
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          }
        >
          취소
        </ModernFormButton>
        <ModernFormButton
          type="submit"
          variant="primary"
          loading={loading}
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          }
        >
          {isEdit ? '수정하기' : '생성하기'}
        </ModernFormButton>
      </ModernFormActions>
    </ModernForm>
  );
}
