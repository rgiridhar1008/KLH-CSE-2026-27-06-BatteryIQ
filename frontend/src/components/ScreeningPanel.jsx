import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

export default function ScreeningPanel({ windows, metrics }) {
  if (!windows || windows.length === 0) return null;

  const data = windows.map((w, i) => ({
    name: `W${w.window}`,
    window: w.window,
    start: w.start_row,
    end: w.end_row,
    score: Number(w.score).toFixed(4),
    rawScore: Number(w.score),
    status: w.suspicious ? 'Suspicious' : 'Normal',
  }));

  const threshold = 1.0; // Typical default, could be dynamic from backend

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      return (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', padding: '12px', borderRadius: '6px', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
          <p style={{ margin: '0 0 4px 0', fontWeight: 'bold' }}>Window #{dataPoint.window}</p>
          <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b' }}>Rows {dataPoint.start}–{dataPoint.end}</p>
          <p style={{ margin: '0 0 4px 0', fontSize: '13px' }}>Score: <span style={{ fontWeight: 'bold' }}>{dataPoint.score}</span></p>
          <p style={{ margin: '0', fontSize: '12px', fontWeight: 'bold', color: dataPoint.status === 'Suspicious' ? '#f59e0b' : '#10b981' }}>{dataPoint.status}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">Level-1 Screening Distribution</h2>
          <div className="card-subtitle">Anomaly score per 50-row window</div>
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: '24px' }}>
        <div style={{ flex: '1', height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} tickMargin={10} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={threshold} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Threshold', fill: '#ef4444', fontSize: 11 }} />
              <Line 
                type="monotone" 
                dataKey="rawScore" 
                stroke="#6366f1" 
                strokeWidth={2}
                dot={(props) => {
                  const { cx, cy, payload } = props;
                  if (payload.status === 'Suspicious') {
                    return <circle cx={cx} cy={cy} r={4} fill="#f59e0b" stroke="#fff" strokeWidth={1} key={payload.name} />;
                  }
                  return <circle cx={cx} cy={cy} r={2} fill="#6366f1" stroke="none" key={payload.name} />;
                }}
                activeDot={{ r: 6 }} 
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        <div style={{ width: '220px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 'bold', marginBottom: '8px', textTransform: 'uppercase' }}>Screening Metrics</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
              <span>Total Windows</span><strong>{metrics.total_windows}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px', color: '#f59e0b' }}>
              <span>Suspicious</span><strong>{metrics.suspicious_windows}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px', color: '#10b981' }}>
              <span>Normal</span><strong>{metrics.ai_calls_avoided}</strong>
            </div>
          </div>
          
          <div style={{ background: '#e0e7ff', padding: '16px', borderRadius: '6px', border: '1px solid #c7d2fe', textAlign: 'center' }}>
            <div style={{ fontSize: '12px', color: '#3730a3', fontWeight: 'bold', marginBottom: '4px', textTransform: 'uppercase' }}>AI Avoidance</div>
            <div style={{ fontSize: '28px', fontWeight: '700', color: '#312e81' }}>{metrics.ai_avoidance_percent ?? 0}%</div>
            <div style={{ fontSize: '11px', color: '#4338ca', marginTop: '4px' }}>Windows safely skipped</div>
          </div>
        </div>
      </div>
    </div>
  );
}
