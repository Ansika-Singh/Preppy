import React from 'react';
import { Cpu, Cloud, ShieldAlert, Zap } from 'lucide-react';
import { LearnStatus } from '../types';

interface StatusChipProps {
  status: LearnStatus | null;
}

export const StatusChip: React.FC<StatusChipProps> = ({ status }) => {
  if (!status) {
    return (
      <div className="status-chip loading" title="Connecting to AI engine...">
        <Zap size={14} className="spin" />
        <span>Connecting...</span>
      </div>
    );
  }

  if (!status.is_connected) {
    return (
      <div className="status-chip disconnected" title="No AI provider reachable. Deterministic features remain available.">
        <ShieldAlert size={14} className="text-warning" />
        <span>Offline Mode (Deterministic)</span>
      </div>
    );
  }

  return (
    <div className="status-chip-container">
      <div className={`status-chip ${status.is_cloud ? 'cloud' : 'local'}`} title={status.is_cloud ? 'Using cloud AI provider (check your provider terms)' : 'Using private local model'}>
        {status.is_cloud ? <Cloud size={14} /> : <Cpu size={14} />}
        <span className="provider-name">{status.active_provider}</span>
        <span className="privacy-badge">{status.is_cloud ? 'Cloud' : 'Local'}</span>
      </div>
      <div className="budget-chip" title={`Session AI Budget: ${status.call_budget_remaining} calls remaining of ${status.call_budget_total}`}>
        <Zap size={13} />
        <span>{status.call_budget_remaining} calls left</span>
      </div>
    </div>
  );
};

