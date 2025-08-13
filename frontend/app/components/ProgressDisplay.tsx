'use client';

import { ProgressStep } from '../types';

interface ProgressDisplayProps {
  steps: ProgressStep[];
}

export default function ProgressDisplay({ steps }: ProgressDisplayProps) {
  const getStatusIcon = (status: ProgressStep['status']) => {
    switch (status) {
      case 'completed':
        return '✅';
      case 'active':
        return <div className="loading-spinner" />;
      case 'error':
        return '❌';
      default:
        return '⏳';
    }
  };

  return (
    <div className="progress-container">
      {steps.map((step) => (
        <div key={step.id} className={`progress-step ${step.status}`}>
          <div className="progress-icon">
            {getStatusIcon(step.status)}
          </div>
          <span>{step.message}</span>
        </div>
      ))}
    </div>
  );
}
