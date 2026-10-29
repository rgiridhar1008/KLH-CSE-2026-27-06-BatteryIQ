import React from 'react';

export default function MetricCard({ label, value, highlight = false }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${highlight ? 'metric-highlight' : ''}`}>
        {value}
      </div>
    </div>
  );
}
