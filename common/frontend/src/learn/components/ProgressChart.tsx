import React from 'react';

interface Snapshot {
  snapshot_at: number;
  mastery: number;
}

interface ProgressChartProps {
  history: Snapshot[];
  title?: string;
}

export const ProgressChart: React.FC<ProgressChartProps> = ({ history, title = 'Mastery Progress' }) => {
  if (!history || history.length < 2) {
    return (
      <div className="progress-chart-empty">
        <p className="empty-chart-text">Chart activates after 2 or more diagnostic attempts. Real data only.</p>
      </div>
    );
  }

  // Sort chronologically
  const sorted = [...history].sort((a, b) => a.snapshot_at - b.snapshot_at);
  const width = 340;
  const height = 120;
  const padding = 20;

  const minTime = sorted[0].snapshot_at;
  const maxTime = sorted[sorted.length - 1].snapshot_at;
  const timeRange = maxTime === minTime ? 1 : maxTime - minTime;

  const points = sorted.map((pt) => {
    const x = padding + ((pt.snapshot_at - minTime) / timeRange) * (width - 2 * padding);
    const y = height - padding - pt.mastery * (height - 2 * padding);
    return `${x},${y}`;
  });

  const pathD = `M ${points.join(' L ')}`;

  return (
    <div className="progress-chart-container">
      <div className="chart-header">
        <h4>{title}</h4>
        <span className="chart-latest">Latest: {Math.round(sorted[sorted.length - 1].mastery * 100)}%</span>
      </div>
      <svg width={width} height={height} className="progress-svg" viewBox={`0 0 ${width} ${height}`}>
        {/* Threshold lines */}
        <line
          x1={padding}
          y1={height - padding - 0.75 * (height - 2 * padding)}
          x2={width - padding}
          y2={height - padding - 0.75 * (height - 2 * padding)}
          className="svg-guide-line strong-line"
          strokeDasharray="4 4"
        />
        <line
          x1={padding}
          y1={height - padding - 0.4 * (height - 2 * padding)}
          x2={width - padding}
          y2={height - padding - 0.4 * (height - 2 * padding)}
          className="svg-guide-line weak-line"
          strokeDasharray="4 4"
        />
        {/* Data curve */}
        <path d={pathD} fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" />
        {/* Dots */}
        {sorted.map((pt, i) => {
          const x = padding + ((pt.snapshot_at - minTime) / timeRange) * (width - 2 * padding);
          const y = height - padding - pt.mastery * (height - 2 * padding);
          return <circle key={i} cx={x} cy={y} r="4" fill="var(--text-strong)" stroke="var(--accent)" strokeWidth="2" />;
        })}
      </svg>
      <div className="chart-legend">
        <span className="legend-item strong">75% Strong</span>
        <span className="legend-item weak">40% Weak</span>
      </div>
    </div>
  );
};

