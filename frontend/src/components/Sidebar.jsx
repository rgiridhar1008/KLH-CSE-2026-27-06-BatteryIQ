import React from 'react';
import { LayoutDashboard, Activity, Search, LayoutList, FlaskConical, Cpu, Database } from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, hasResult, result, file }) {
  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard, requiresResult: false },
    { id: 'analysis', label: 'Battery Analysis', icon: Activity, requiresResult: true },
    { id: 'screening', label: 'Level-1 Screening', icon: Search, requiresResult: true },
    { id: 'windows', label: 'Battery Windows', icon: LayoutList, requiresResult: true },
    { id: 'batch', label: 'Batch Experiment', icon: FlaskConical, requiresResult: true },
  ];

  const aiAvoided = result?.ai_calls_avoided || 0;
  const totalWindows = result?.total_windows || 0;
  const aiAvoidancePct = totalWindows > 0 ? (aiAvoided / totalWindows * 100).toFixed(1) : 0;
  const batteryId = file?.name?.includes('battery_') ? file.name.split('_')[1] : 'Unknown';

  return (
    <aside className="dashboard-sidebar">
      <nav className="sidebar-nav">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isDisabled = tab.requiresResult && !hasResult;
          
          return (
            <a
              key={tab.id}
              className={`sidebar-item ${activeTab === tab.id ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={(e) => {
                e.preventDefault();
                if (!isDisabled) {
                  setActiveTab(tab.id);
                }
              }}
              href={`#${tab.id}`}
              style={{
                opacity: isDisabled ? 0.5 : 1,
                cursor: isDisabled ? 'not-allowed' : 'pointer'
              }}
            >
              <Icon size={18} />
              {tab.label}
            </a>
          );
        })}
      </nav>
      
      <div style={{ marginTop: 'auto', padding: '24px' }}>
        <div style={{ 
          background: '#0f172a', 
          border: '1px solid #1e293b', 
          borderLeft: '2px solid #0ea5e9',
          borderRadius: '6px', 
          padding: '16px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
        }}>
          {!result ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', boxShadow: '0 0 8px #10b981' }}></div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.5px' }}>SYSTEM READY</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px', color: '#94a3b8' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Cpu size={14} color="#64748b" /> Qwen2.5 7B</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Database size={14} color="#64748b" /> Ollama • Local</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Activity size={14} color="#64748b" /> Event-Triggered AI</div>
              </div>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0ea5e9', boxShadow: '0 0 8px #0ea5e9' }}></div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#e2e8f0', letterSpacing: '0.5px' }}>ANALYSIS COMPLETE</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px', color: '#94a3b8' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Battery ID</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{batteryId}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Total Rows</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{(totalWindows * 50).toLocaleString()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Windows</span>
                  <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{totalWindows}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>AI Avoided</span>
                  <span style={{ color: '#10b981', fontWeight: 500 }}>{aiAvoidancePct}%</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
