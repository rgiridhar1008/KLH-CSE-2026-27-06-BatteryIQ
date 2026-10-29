import React, { useState } from "react";
import "./index.css"; // Ensure using the new styles

import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import MetricCard from "./components/MetricCard";
import Pipeline from "./components/Pipeline";
import UploadArea from "./components/UploadArea";
import ScreeningPanel from "./components/ScreeningPanel";
import WindowTable from "./components/WindowTable";
import WindowDrawer from "./components/WindowDrawer";
import BatchExperiment from "./components/BatchExperiment";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [activeTab, setActiveTab] = useState("overview");

  // File
  const [file, setFile] = useState(null);
  
  // App state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  
  // Single window diagnosis
  const [selectedWindow, setSelectedWindow] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState("");

  // Batch states
  const [batchMaxWindows, setBatchMaxWindows] = useState("10");
  const [batchSelectionMode, setBatchSelectionMode] = useState("chronological");
  const [batching, setBatching] = useState(false);
  const [batchResult, setBatchResult] = useState(null);
  const [selectedBatchRow, setSelectedBatchRow] = useState(null);

  // Handlers
  const handleClearDataset = () => {
    setFile(null);
    setResult(null);
    setDiagnosis(null);
    setDiagnosisError("");
    setSelectedWindow(null);
    setError("");
    setBatchResult(null);
    setActiveTab("overview");
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    if (selectedFile) {
      handleClearDataset();
      setFile(selectedFile);
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setDiagnosis(null);
    setDiagnosisError("");
    setSelectedWindow(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Backend analysis failed.");
      }

      const data = await response.json();
      setResult(data);
      setActiveTab("analysis"); // Move to next tab
    } catch (err) {
      setError(err.message || "Could not connect to BatteryIQ backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleDiagnose = async (windowData) => {
    if (!file || !windowData) return;
    setDiagnosing(true);
    setDiagnosisError("");
    setDiagnosis(null);
    // DO NOT clear selectedWindow
    setSelectedWindow(windowData);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/diagnose?start_row=${windowData.start_row}`,
        { method: "POST", body: formData }
      );

      if (!response.ok) throw new Error(`Diagnosis request failed.`);

      const data = await response.json();
      console.log("BatteryIQ /diagnose response:", data);
      
      if (data.success === false) {
        throw new Error(data.error || "Diagnosis failed");
      }
      
      setDiagnosis(data);
    } catch (err) {
      setDiagnosisError(err.message || "Could not run AI diagnosis.");
    } finally {
      setDiagnosing(false);
    }
  };

  const handleBatchDiagnose = async () => {
    if (!file) return;
    setBatching(true);
    setError("");
    setBatchResult(null);
    setSelectedBatchRow(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("max_windows", batchMaxWindows);
      formData.append("selection_mode", batchSelectionMode);

      const response = await fetch(`${API_URL}/batch-diagnose`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error(`Batch request failed.`);

      const data = await response.json();
      setBatchResult(data);
    } catch (err) {
      setError(err.message || "Could not run batch AI diagnosis.");
    } finally {
      setBatching(false);
    }
  };

  // Safe extractions
  const windows = Array.isArray(result?.windows) ? result.windows : [];
  const totalWindows = result?.total_windows || 0;
  const suspiciousCount = result?.suspicious_windows || 0;
  const aiAvoided = result?.ai_calls_avoided || 0;
  const aiAvoidancePct = totalWindows > 0 ? (aiAvoided / totalWindows * 100).toFixed(1) : 0;

  return (
    <div className="dashboard-layout">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} hasResult={!!result} result={result} file={file} />
      
      <div className="dashboard-main">
        <Header loading={loading} diagnosing={diagnosing} batching={batching} hasResult={!!result} />
        
        <main className="dashboard-content">
          {error && (
            <div style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger-text)', padding: '12px 16px', borderRadius: '6px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* OVERVIEW / UPLOAD */}
          {(activeTab === 'overview' || !result) && (
            <div id="overview" style={{ maxWidth: '800px', margin: '0 auto' }}>
              <UploadArea 
                file={file} 
                onFileChange={handleFileChange} 
                onAnalyze={handleAnalyze} 
                loading={loading} 
                onClear={handleClearDataset}
                result={result}
                onViewAnalysis={() => setActiveTab('analysis')}
              />
              
              {!result && (
                <div className="card" style={{ marginTop: '24px', opacity: 0.8 }}>
                  <div className="card-header">
                    <h2 className="card-title">Research Architecture</h2>
                  </div>
                  <Pipeline activeStep={0} />
                </div>
              )}
            </div>
          )}

          {/* RESULTS ARE LOADED */}
          {result && (
            <div style={{ display: activeTab === 'overview' ? 'none' : 'block' }}>
              
              {/* TOP SUMMARY */}
              <div id="analysis" style={{ display: activeTab === 'analysis' ? 'block' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '24px' }}>
                  <div>
                    <h2 style={{ margin: 0, color: 'var(--color-primary)', fontSize: '22px' }}>Analysis Complete</h2>
                    <div style={{ color: '#64748b', fontSize: '14px', marginTop: '4px' }}>
                      {file.name}
                    </div>
                  </div>
                </div>

                <div className="hero-section">
                  <div className="hero-metric">
                    <div className="hero-value">{aiAvoidancePct}%</div>
                    <div className="hero-label">AI Inference Avoidance</div>
                  </div>
                  <div style={{ flex: 2 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '8px' }}>
                      <span>AI Skipped ({aiAvoided})</span>
                      <span>AI Called ({suspiciousCount})</span>
                    </div>
                    <div style={{ height: '8px', background: 'rgba(255,255,255,0.2)', borderRadius: '4px', overflow: 'hidden', display: 'flex' }}>
                      <div style={{ width: `${aiAvoidancePct}%`, background: '#10b981' }}></div>
                      <div style={{ width: `${100 - aiAvoidancePct}%`, background: '#f59e0b' }}></div>
                    </div>
                    <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.8)', margin: '12px 0 0 0' }}>
                      Level-1 screening securely filtered normal windows, preserving compute for critical anomalies.
                    </p>
                  </div>
                </div>

                <div className="metrics-grid" style={{ marginBottom: '24px' }}>
                  <MetricCard label="Total Rows" value={(totalWindows * 50).toLocaleString()} />
                  <MetricCard label="Total Windows" value={totalWindows} />
                  <MetricCard label="Suspicious" value={suspiciousCount} highlight={suspiciousCount > 0} />
                  <MetricCard label="AI Calls Avoided" value={aiAvoided} />
                </div>
                
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">Processing Pipeline</h2>
                  </div>
                  <Pipeline activeStep={3} />
                </div>
              </div>

              {/* SCREENING */}
              <div id="screening" style={{ display: activeTab === 'screening' ? 'block' : 'none' }}>
                <ScreeningPanel 
                  windows={windows} 
                  metrics={{ total_windows: totalWindows, suspicious_windows: suspiciousCount, ai_calls_avoided: aiAvoided, ai_avoidance_percent: aiAvoidancePct }} 
                />
              </div>

              {/* WINDOWS */}
              <div id="windows" style={{ display: activeTab === 'windows' ? 'block' : 'none' }}>
                <WindowTable 
                  windows={windows} 
                  onSelectWindow={(w) => {
                    setSelectedWindow(w);
                    if (w.suspicious && diagnosis?.window_start !== w.start_row) {
                      setDiagnosis(null);
                    }
                  }} 
                />
              </div>

              {/* BATCH EXPERIMENT */}
              <div id="batch" style={{ display: activeTab === 'batch' ? 'block' : 'none' }}>
                <BatchExperiment 
                  file={file}
                  batchMaxWindows={batchMaxWindows}
                  setBatchMaxWindows={setBatchMaxWindows}
                  batchSelectionMode={batchSelectionMode}
                  setBatchSelectionMode={setBatchSelectionMode}
                  handleBatchDiagnose={handleBatchDiagnose}
                  batching={batching}
                  batchResult={batchResult}
                  selectedBatchRow={selectedBatchRow}
                  setSelectedBatchRow={setSelectedBatchRow}
                />
              </div>
            </div>
          )}
        </main>
      </div>

      <WindowDrawer 
        window={selectedWindow} 
        diagnosis={diagnosis} 
        diagnosing={diagnosing} 
        diagnosisError={diagnosisError}
        onClose={() => {
          setSelectedWindow(null);
          setDiagnosis(null);
          setDiagnosisError("");
        }} 
        onDiagnose={handleDiagnose} 
      />
    </div>
  );
}

export default App;