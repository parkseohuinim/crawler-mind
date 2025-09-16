'use client';

import { ProgressStep } from '@/app/_lib/types';

interface ProgressDisplayProps {
  steps: ProgressStep[];
}

export default function ProgressDisplay({ steps }: ProgressDisplayProps) {
  const getStatusIcon = (status: ProgressStep['status']) => {
    switch (status) {
      case 'completed':
        return '✅';
      case 'active':
        return (
          <div className="dots-spinner">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        );
      case 'error':
        return '❌';
      default:
        return '⏳';
    }
  };

  // 메시지에서 URL과 진행도 a/b를 파싱 (예: "크롤링 진행: 2/3 - https://...")
  const parseUrlAndProgress = (message: string) => {
    const urlMatch = message.match(/-\s(https?:\/\/\S+)/);
    const ratioMatch = message.match(/(\d+)\/(\d+)/);
    const url = urlMatch ? urlMatch[1] : null;
    const current = ratioMatch ? parseInt(ratioMatch[1], 10) : null;
    const total = ratioMatch ? parseInt(ratioMatch[2], 10) : null;
    return { url, current, total } as { url: string | null; current: number | null; total: number | null };
  };

  // URL 기준으로 그룹화, URL이 없으면 "전체 작업" 그룹에 배치
  const grouped = steps.reduce<Record<string, { items: ProgressStep[]; current?: number; total?: number }>>((acc, step) => {
    const { url, current, total } = parseUrlAndProgress(step.message);
    const key = url || '전체 작업';
    if (!acc[key]) acc[key] = { items: [] };
    acc[key].items.push(step);
    if (current != null && total != null) {
      acc[key].current = current;
      acc[key].total = total;
    }
    return acc;
  }, {});

  const groupKeys = Object.keys(grouped);

  return (
    <div className="progress-container">
      {groupKeys.map((key) => {
        const group = grouped[key];
        const pct = group.total && group.current ? Math.min(100, Math.max(0, Math.round((group.current / group.total) * 100))) : null;
        return (
          <div key={key} className="progress-group">
            <div className="progress-group-header">
              <div className="progress-group-title">
                {key !== '전체 작업' ? (
                  <a href={key} target="_blank" rel="noopener noreferrer">{key}</a>
                ) : (
                  <span>{key}</span>
                )}
              </div>
              {pct != null && (
                <div className="progress-group-meta">
                  <span className="progress-group-ratio">{group.current}/{group.total}</span>
                  <div className="progress-bar">
                    <div className="progress-bar-fill" style={{ width: pct + '%' }} />
                  </div>
                </div>
              )}
            </div>

            <div className="progress-steps">
              {group.items.map((step) => (
                <div key={step.id} className={`progress-step ${step.status}`}>
                  <div className="progress-icon">{getStatusIcon(step.status)}</div>
                  <span>{step.message}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
