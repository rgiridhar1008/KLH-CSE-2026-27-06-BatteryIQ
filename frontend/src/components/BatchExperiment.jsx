import React from 'react';
import { FlaskConical, CheckCircle2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';

export default function BatchExperiment({ 
  file, 
  batchMaxWindows, 
  setBatchMaxWindows, 
  batchSelectionMode, 
  setBatchSelectionMode,
  handleBatchDiagnose,
  batching,
  batchResult,
  selectedBatchRow,
  setSelectedBatchRow 
}) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FlaskConical size={18} color="#0ea5e9" />
            Qwen 7B Batch Experiment
          </h2>
          <div className="card-subtitle">Evaluate multiple suspicious windows using local Ollama inference.</div>
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end', marginBottom: '24px', background: '#f8fafc', padding: '16px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Max Qwen Windows</label>
          <select className="form-control" value={batchMaxWindows} onChange={(e) => setBatchMaxWindows(e.target.value)}>
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="40">40</option>
            <option value="all">ALL</option>
          </select>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">Selection Mode</label>
          <select className="form-control" value={batchSelectionMode} onChange={(e) => setBatchSelectionMode(e.target.value)}>
            <option value="chronological">Chronological</option>
            <option value="highest_score">Highest Score</option>
            <option value="spread">Spread</option>
          </select>
        </div>

        <button 
          className="btn btn-primary" 
          onClick={handleBatchDiagnose} 
          disabled={!file || batching}
        >
          {batching ? 'Running Batch Experiment...' : 'Run Experiment'}
        </button>
      </div>

      {batchResult && batchResult.experiment && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: '#10b981', fontWeight: 600 }}>
            <CheckCircle2 size={16} /> Experiment Summary
          </div>
          <div className="metrics-grid" style={{ marginBottom: '24px' }}>
            <div className="metric-card" style={{ background: '#f1f5f9' }}>
              <div className="metric-label">Total Windows</div>
              <div className="metric-value" style={{ fontSize: '20px' }}>{batchResult.experiment.total_windows}</div>
            </div>
            <div className="metric-card" style={{ background: '#fef3c7', borderColor: '#fde68a' }}>
              <div className="metric-label">Suspicious Windows</div>
              <div className="metric-value" style={{ fontSize: '20px', color: '#b45309' }}>{batchResult.experiment.suspicious_windows}</div>
            </div>
            <div className="metric-card" style={{ background: '#e0e7ff', borderColor: '#c7d2fe' }}>
              <div className="metric-label">Qwen Windows</div>
              <div className="metric-value" style={{ fontSize: '20px', color: '#4338ca' }}>{batchResult.experiment.selected_windows}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">AI Avoided</div>
              <div className="metric-value" style={{ fontSize: '20px' }}>{batchResult.experiment.ai_avoidance_percent}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Avg DDP Retention</div>
              <div className="metric-value" style={{ fontSize: '20px' }}>{batchResult.experiment.average_ddp_retention}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Avg Qwen Inference</div>
              <div className="metric-value" style={{ fontSize: '20px' }}>{batchResult.experiment.average_inference_time}s</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">JSON Success</div>
              <div className="metric-value" style={{ fontSize: '20px' }}>{batchResult.experiment.json_success_rate}%</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '24px', marginBottom: '24px' }}>
            <div style={{ flex: 1, background: '#f8fafc', padding: '16px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#64748b', textTransform: 'uppercase', marginBottom: '12px' }}>Qwen Severity Distribution</div>
              <div style={{ height: '200px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={
                    ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(level => ({
                      name: level,
                      count: batchResult.results.filter(r => r.ai_result.anomaly_level === level).length
                    }))
                  }>
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <RechartsTooltip cursor={{ fill: 'transparent' }} contentStyle={{ fontSize: '12px' }} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {
                        ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((entry, index) => {
                          const colors = ['#10b981', '#f59e0b', '#ef4444', '#7f1d1d'];
                          return <Cell key={`cell-${index}`} fill={colors[index]} />;
                        })
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <h3 style={{ fontSize: '15px', color: '#0f172a', marginBottom: '12px' }}>Diagnosis Results</h3>
          <div className="data-table-container" style={{ border: '1px solid #e2e8f0', borderRadius: '6px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Level-1 Score</th>
                  <th>DDP Retention</th>
                  <th>Qwen Severity</th>
                  <th>Consistency</th>
                  <th>Inference Time</th>
                </tr>
              </thead>
              <tbody>
                {batchResult.results.map((r, i) => (
                  <React.Fragment key={i}>
                    <tr 
                      className={selectedBatchRow === i ? 'row-normal' : ''}
                      style={{ background: selectedBatchRow === i ? '#f8fafc' : 'transparent' }}
                      onClick={() => setSelectedBatchRow(selectedBatchRow === i ? null : i)}
                    >
                      <td style={{ fontWeight: 500 }}>#{r.window}</td>
                      <td>{Number(r.level1.anomaly_score).toFixed(4)}</td>
                      <td>{r.ddp.retention_percent}%</td>
                      <td>
                        <span className={`badge ${
                          r.ai_result.anomaly_level === 'CRITICAL' || r.ai_result.anomaly_level === 'HIGH' ? 'badge-danger' :
                          r.ai_result.anomaly_level === 'MEDIUM' ? 'badge-warning' : 'badge-success'
                        }`}>
                          {r.ai_result.anomaly_level || 'UNKNOWN'}
                        </span>
                      </td>
                      <td>{r.ai_result.level1_consistency || 'N/A'}</td>
                      <td>{Number(r.inference_seconds).toFixed(2)}s</td>
                    </tr>
                    {selectedBatchRow === i && (
                      <tr style={{ background: '#f8fafc' }}>
                        <td colSpan="6" style={{ padding: '16px', borderTop: 'none' }}>
                          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '16px' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                              <div>
                                <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Diagnosis</div>
                                <div style={{ fontSize: '13px', color: '#0f172a' }}>{r.ai_result.diagnosis || r.ai_result.fault_type || 'N/A'}</div>
                              </div>
                              <div>
                                <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Recommendation</div>
                                <div style={{ fontSize: '13px', color: '#0f172a' }}>{r.ai_result.recommendation || r.ai_result.recommended_action || 'N/A'}</div>
                              </div>
                            </div>
                            
                            <div style={{ marginTop: '16px' }}>
                              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Reason</div>
                              <div style={{ fontSize: '13px', color: '#334155' }}>{r.ai_result.reason || 'N/A'}</div>
                            </div>
                            
                            <div style={{ marginTop: '16px' }}>
                              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Evidence</div>
                              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#334155' }}>
                                {(r.ai_result.evidence || []).map((ev, idx) => (
                                  <li key={idx} style={{ marginBottom: '2px' }}>{typeof ev === 'object' ? JSON.stringify(ev) : ev}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
