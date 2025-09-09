'use client';

import React, { useState, useEffect } from 'react';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate } from '@/app/_lib/domains/menuLink';
import ModernForm, { 
  ModernFormGroup, 
  ModernFormRow, 
  ModernFormLabel, 
  ModernFormInput, 
  ModernFormActions, 
  ModernFormButton 
} from '@/app/_components/ui/ModernForm';

interface MenuLinkFormProps {
  menuLink?: MenuLink | null;
  onSubmit: (data: MenuLinkCreate | MenuLinkUpdate) => void;
  onCancel: () => void;
  loading: boolean;
  isEdit?: boolean;
}

export default function MenuLinkForm({ 
  menuLink, 
  onSubmit, 
  onCancel, 
  loading, 
  isEdit = false 
}: MenuLinkFormProps) {
  const [formData, setFormData] = useState<MenuLinkCreate | MenuLinkUpdate>({
    document_id: '',
    menu_path: '',
    pc_url: '',
    mobile_url: '',
    created_by: 'admin',
  });

  useEffect(() => {
    if (isEdit && menuLink) {
      setFormData({
        document_id: menuLink.document_id || '',
        menu_path: menuLink.menu_path,
        pc_url: menuLink.pc_url || '',
        mobile_url: menuLink.mobile_url || '',
        updated_by: 'admin',
      });
    } else if (!isEdit) {
      setFormData({
        document_id: '',
        menu_path: '',
        pc_url: '',
        mobile_url: '',
        created_by: 'admin',
      });
    }
  }, [isEdit, menuLink]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const handleInputChange = (field: keyof MenuLinkCreate, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <ModernForm
      title={isEdit ? '메뉴 링크 수정' : '메뉴 링크 생성'}
      subtitle={isEdit ? '기존 메뉴 링크 정보를 수정합니다' : '새로운 메뉴 링크를 생성합니다'}
      icon={
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
        </svg>
      }
      onSubmit={handleSubmit}
    >
      <ModernFormGroup>
        <ModernFormLabel htmlFor="document_id">문서 ID</ModernFormLabel>
        <ModernFormInput
          type="text"
          id="document_id"
          value={formData.document_id}
          onChange={(e) => handleInputChange('document_id', e.target.value)}
          placeholder="예: DOC001, GUIDE_2024_01"
          maxLength={50}
          help="해당 메뉴와 연관된 문서의 고유 ID (선택사항)"
        />
      </ModernFormGroup>
      
      <ModernFormGroup>
        <ModernFormLabel htmlFor="menu_path" required>메뉴 경로</ModernFormLabel>
        <ModernFormInput
          type="text"
          id="menu_path"
          value={formData.menu_path}
          onChange={(e) => handleInputChange('menu_path', e.target.value)}
          placeholder="예: 고객지원^공지이용안내^서비스안내"
          required
          help="각 메뉴 단계를 ^ 기호로 구분하여 입력하세요"
        />
      </ModernFormGroup>
      
      <ModernFormRow>
        <ModernFormGroup>
          <ModernFormLabel htmlFor="pc_url">PC URL</ModernFormLabel>
          <ModernFormInput
            type="url"
            id="pc_url"
            value={formData.pc_url}
            onChange={(e) => handleInputChange('pc_url', e.target.value)}
            placeholder="https://example.com/pc-page"
            help="데스크톱/PC에서 접근할 URL"
          />
        </ModernFormGroup>
        
        <ModernFormGroup>
          <ModernFormLabel htmlFor="mobile_url">모바일 URL</ModernFormLabel>
          <ModernFormInput
            type="url"
            id="mobile_url"
            value={formData.mobile_url}
            onChange={(e) => handleInputChange('mobile_url', e.target.value)}
            placeholder="https://m.example.com/mobile-page"
            help="모바일 기기에서 접근할 URL (선택사항)"
          />
        </ModernFormGroup>
      </ModernFormRow>
      
      <ModernFormActions>
        <ModernFormButton
          type="button"
          variant="secondary"
          onClick={onCancel}
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
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
              <polyline points="17,21 17,13 7,13 7,21"></polyline>
              <polyline points="7,3 7,8 15,8"></polyline>
            </svg>
          }
        >
          {isEdit ? '수정하기' : '생성하기'}
        </ModernFormButton>
      </ModernFormActions>
    </ModernForm>
  );
}
