import React from 'react';
import { X, Cpu, AlertTriangle, ShieldCheck, Search, Activity, FileText, BrainCircuit } from 'lucide-react';

export default function WindowDrawer({ window, diagnosis, diagnosing, diagnosisError, onClose, onDiagnose }) {
  if (!window) return null;

  return (
    <>
      <div className={`drawer-overlay ${window ? 'open' : ''}`} onClick={onClose}></div>
      <div className={`drawer ${window ? 'open' : ''}`}>
        
        <div className="drawer-header">
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', color: '#0f172a' }}>Window #{window.window}</h2>
            <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>Rows {window.start_row}–{window.end_row}</div>
          </div>
          <button className="btn btn-outline" onClick={onClose} style={{ padding: '6px', border: 'none' }}>
            <X size={20} />
          </button>
        </div>

        <div className="drawer-body">
          {/* LEVEL 1 INFO */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>Level-1 Screening</div>
              {window.suspicious ? (
                <span className="badge badge-warning">Suspicious</span>
              ) : (
                <span className="badge badge-success">Normal</span>
              )}
            </div>
            
            <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
              <div className="info-row">
                <div className="info-row-label">Anomaly Score</div>
                <div className="info-row-value" style={{ fontWeight: 'bold' }}>{Number(window.score).toFixed(4)}</div>
              </div>
              <div className="info-row" style={{ marginBottom: 0 }}>
                <div className="info-row-label">Triggered Features</div>
                <div className="info-row-value">
                  {window.triggered_features && window.triggered_features.length > 0 ? (
                    window.triggered_features.join(", ")
                  ) : (
                    <span style={{ color: '#94a3b8' }}>None</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* DDP INFO */}
          {diagnosis && diagnosis.ddp && (
            <div style={{ marginBottom: '24px' }}>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#334155', marginBottom: '12px' }}>Adaptive Downsampling (DDP)</div>
              
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '8px' }}>
                  <span>Original Rows: <strong>{diagnosis.ddp.original_rows}</strong></span>
                  <span>Retained: <strong>{diagnosis.ddp.retained_rows}</strong></span>
                </div>
                
                <div className="reduction-vis">
                  <div className="reduction-bar-full">
                    <div className="reduction-bar-retained" style={{ width: `${Math.max(2, diagnosis.ddp.retention_percent)}%` }}></div>
                  </div>
                  <div style={{ textAlign: 'right', fontSize: '12px', fontWeight: 'bold', color: '#0ea5e9' }}>
                    {diagnosis.ddp.retention_percent}% Retention
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>VDD Mean</div>
                    <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{Number(diagnosis.ddp.vdd_mean).toFixed(4)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>CDD Mean</div>
                    <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{Number(diagnosis.ddp.cdd_mean).toFixed(4)}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* LOADING & ERROR STATES */}
          {diagnosing && (
            <div style={{ padding: '24px', textAlign: 'center', background: '#f8fafc', borderRadius: '6px', border: '1px dashed #cbd5e1', marginBottom: '24px' }}>
              <div style={{ color: '#0ea5e9', fontWeight: 600, marginBottom: '8px' }}>Running Qwen 7B Diagnosis...</div>
              <div style={{ fontSize: '13px', color: '#64748b' }}>Please wait while the model analyzes the battery window data.</div>
            </div>
          )}

          {diagnosisError && (
            <div style={{ padding: '16px', background: '#fee2e2', borderRadius: '6px', border: '1px solid #fca5a5', marginBottom: '24px', color: '#991b1b' }}>
              <div style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <AlertTriangle size={16} /> Qwen Diagnosis Error
              </div>
              <div style={{ fontSize: '13px' }}>{diagnosisError}</div>
            </div>
          )}

          {/* QWEN DIAGNOSIS INFO */}
          {!diagnosing && !diagnosisError && diagnosis && diagnosis.ai_result ? (
            <div className="ai-report">
              <div className="ai-report-header">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BrainCircuit size={16} color="#6366f1" />
                    <h3 style={{ margin: 0, fontSize: '15px', color: '#312e81' }}>Level-2 AI Diagnosis</h3>
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                    Qwen2.5 7B • Local Ollama
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  {diagnosis.ai_result.anomaly_level === 'CRITICAL' || diagnosis.ai_result.anomaly_level === 'HIGH' ? (
                    <span className="badge badge-danger" style={{ fontSize: '14px', padding: '6px 12px' }}>{diagnosis.ai_result.anomaly_level || 'UNKNOWN'}</span>
                  ) : diagnosis.ai_result.anomaly_level === 'MEDIUM' ? (
                    <span className="badge badge-warning" style={{ fontSize: '14px', padding: '6px 12px' }}>{diagnosis.ai_result.anomaly_level}</span>
                  ) : (
                    <span className="badge badge-success" style={{ fontSize: '14px', padding: '6px 12px' }}>{diagnosis.ai_result.anomaly_level || 'UNKNOWN'}</span>
                  )}
                </div>
              </div>
              
              <div className="ai-report-body">
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Diagnosis</div>
                  <div style={{ fontSize: '14px', color: '#0f172a' }}>{diagnosis.ai_result.diagnosis || diagnosis.ai_result.fault_type || 'No diagnosis returned.'}</div>
                </div>
                
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Reason</div>
                  <div style={{ fontSize: '14px', color: '#334155', lineHeight: 1.5 }}>{diagnosis.ai_result.reason ?? 'No reason returned.'}</div>
                </div>
                
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px' }}>Evidence</div>
                  <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: '#334155', lineHeight: 1.5 }}>
                    {(Array.isArray(diagnosis.ai_result.evidence) ? diagnosis.ai_result.evidence : []).map((ev, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{typeof ev === 'object' ? JSON.stringify(ev) : ev}</li>
                    ))}
                  </ul>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', background: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Level-1 Consistency</div>
                    <div style={{ fontWeight: 'bold', fontSize: '12px' }}>{diagnosis.ai_result.level1_consistency || 'Not available'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Recommendation</div>
                    <div style={{ fontWeight: 'bold', fontSize: '12px' }}>{diagnosis.ai_result.recommendation || diagnosis.ai_result.recommended_action || 'Not available'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Confidence</div>
                    <div style={{ fontWeight: 'bold', fontSize: '12px' }}>
                      {diagnosis.ai_result.confidence != null ? `${(diagnosis.ai_result.confidence * 100).toFixed(0)}%` : "Not available"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: '#64748b' }}>Inference Time</div>
                    <div style={{ fontWeight: 'bold', fontSize: '12px' }}>
                      {diagnosis.ai_result.inference_seconds ? `${Number(diagnosis.ai_result.inference_seconds).toFixed(2)}s` : 'Not available'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          
        </div>

        <div className="drawer-footer">
          {window.suspicious && (
            <button 
              className="btn btn-ai" 
              onClick={() => onDiagnose(window)} 
              disabled={diagnosing}
              style={{ width: '100%', padding: '12px', fontSize: '14px' }}
            >
              {diagnosing ? 'Running Qwen 7B Diagnosis...' : diagnosis ? 'Run AI Diagnosis Again' : 'Run AI Diagnosis'}
            </button>
          )}
          {(!window.suspicious) && (
            <div style={{ textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
              Normal windows do not require AI diagnosis.
            </div>
          )}
          {diagnosis && !diagnosing && !diagnosisError && (
             <div style={{ textAlign: 'center', color: '#10b981', fontSize: '13px', fontWeight: 500, marginTop: '8px' }}>
             Diagnosis complete
           </div>
          )}
        </div>
      </div>
    </>
  );
}
