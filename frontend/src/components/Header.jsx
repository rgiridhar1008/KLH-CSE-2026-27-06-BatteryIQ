import React from 'react';
import { Activity, Cpu } from 'lucide-react';

export default function Header({ loading, diagnosing, batching, hasResult }) {
  let statusText = "Ready";
  let statusColor = "#94a3b8"; // Neutral gray

  if (loading) {
    statusText = "Analyzing";
    statusColor = "#f59e0b"; // Amber
  } else if (diagnosing || batching) {
    statusText = "AI Diagnosis Running";
    statusColor = "#6366f1"; // Indigo
  } else if (hasResult) {
    statusText = "Analysis Complete";
    statusColor = "#10b981"; // Green
  }

  return (
    <header className="dashboard-header">
      <div className="header-brand">
        <img src="/logo.png" alt="BatteryIQ Logo" style={{ height: '56px', width: 'auto' }} />
        <span className="header-subtitle">Event-Triggered AI Battery Monitoring</span>
      </div>
      <div className="header-status">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span className="status-dot" style={{ backgroundColor: statusColor }}></span>
          {statusText}
        </div>
        <div style={{ color: '#64748b' }}>|</div>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <Cpu size={14} style={{ marginRight: 6 }} />
          Qwen2.5 7B • Ollama • Local
        </div>
      </div>
    </header>
  );
}
