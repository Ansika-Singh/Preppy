import React from 'react';
import { MasteryBand } from '../types';

interface MasteryBadgeProps {
  mastery: number;
  band: MasteryBand;
  size?: 'sm' | 'md' | 'lg';
}

export const MasteryBadge: React.FC<MasteryBadgeProps> = ({ mastery, band, size = 'md' }) => {
  const pct = Math.round(mastery * 100);

  const getBandLabel = (b: MasteryBand) => {
    switch (b) {
      case 'strong':
        return 'Strong';
      case 'moderate':
        return 'Moderate';
      case 'weak':
        return 'Weak';
      case 'insufficient_evidence':
      default:
        return 'Insufficient Evidence';
    }
  };

  const getBandClass = (b: MasteryBand) => {
    switch (b) {
      case 'strong':
        return 'band-strong';
      case 'moderate':
        return 'band-moderate';
      case 'weak':
        return 'band-weak';
      case 'insufficient_evidence':
      default:
        return 'band-insufficient';
    }
  };

  return (
    <div className={`mastery-badge-wrap ${size} ${getBandClass(band)}`}>
      <span className="mastery-pct">{band === 'insufficient_evidence' ? '—' : `${pct}%`}</span>
      <span className="mastery-label">{getBandLabel(band)}</span>
    </div>
  );
};

