'use client';

import React, { useState, useEffect } from 'react';
import { MenuLink, MenuLinkCreate, MenuLinkUpdate } from '../types';

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
    <form onSubmit={handleSubmit} className="modal-form">
      <div className="form-group">
        <label htmlFor="document_id">문서 ID</label>
        <div className="input-with-tooltip">
          <input
            type="text"
            id="document_id"
            value={formData.document_id}
            onChange={(e) => handleInputChange('document_id', e.target.value)}
            maxLength={50}
          />
          <div className="input-tooltip">
            <div className="tooltip-bubble">
              <strong>문서 ID (선택사항)</strong>
              <br />• 해당 메뉴와 연관된 문서의 고유 ID
              <br />• 예시: DOC001, GUIDE_2024_01
              <br />• 최대 50자까지 입력 가능
              <br />• 비워두어도 됩니다
            </div>
          </div>
        </div>
      </div>
      
      <div className="form-group">
        <label htmlFor="menu_path">메뉴 경로 *</label>
        <div className="input-with-tooltip">
          <input
            type="text"
            id="menu_path"
            value={formData.menu_path}
            onChange={(e) => handleInputChange('menu_path', e.target.value)}
            required
          />
          <div className="input-tooltip">
            <div className="tooltip-bubble">
              <strong>메뉴 경로 입력 방법</strong>
              <br />• 각 메뉴 단계를 ^ 기호로 구분
              <br />• 예시: 고객지원^공지이용안내^서비스안내
              <br />• 최상위부터 하위 메뉴 순서로 입력
            </div>
          </div>
        </div>
      </div>
      
      <div className="form-group">
        <label htmlFor="pc_url">PC URL</label>
        <div className="input-with-tooltip">
          <input
            type="url"
            id="pc_url"
            value={formData.pc_url}
            onChange={(e) => handleInputChange('pc_url', e.target.value)}
          />
          <div className="input-tooltip">
            <div className="tooltip-bubble">
              <strong>PC 웹사이트 URL</strong>
              <br />• 데스크톱/PC에서 접근할 URL
              <br />• 예시: http://help.kt.com/serviceinfo/ServiceJoinGuideL2.do
              <br />• http:// 또는 https://로 시작해야 함
            </div>
          </div>
        </div>
      </div>
      
      <div className="form-group">
        <label htmlFor="mobile_url">모바일 URL</label>
        <div className="input-with-tooltip">
          <input
            type="url"
            id="mobile_url"
            value={formData.mobile_url}
            onChange={(e) => handleInputChange('mobile_url', e.target.value)}
          />
          <div className="input-tooltip">
            <div className="tooltip-bubble">
              <strong>모바일 웹사이트 URL</strong>
              <br />• 모바일 기기에서 접근할 URL
              <br />• 예시: https://m.kt.com/serviceinfo/guide
              <br />• PC URL과 다른 경우에만 입력 (선택사항)
            </div>
          </div>
        </div>
      </div>
      
      <div className="modal-actions">
        <button
          type="button"
          onClick={onCancel}
          className="cancel-button"
        >
          취소
        </button>
        <button type="submit" className="submit-button" disabled={loading}>
          {loading ? (isEdit ? '수정 중...' : '생성 중...') : (isEdit ? '수정' : '생성')}
        </button>
      </div>
    </form>
  );
}
