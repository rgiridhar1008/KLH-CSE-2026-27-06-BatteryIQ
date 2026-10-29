import React, { useState } from 'react';
import { UploadCloud, FileSpreadsheet, XCircle, CheckCircle2, AlertCircle, ArrowRight, FolderUp, FileText, Activity } from 'lucide-react';

export default function UploadArea({ file, onFileChange, onAnalyze, loading, onClear, result, onViewAnalysis }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const processFile = (selectedFile) => {
    setUploadError("");
    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith('.csv') && selectedFile.type !== "text/csv") {
      setUploadError("Invalid file type. Please select a CSV battery dataset.");
      return;
    }
    
    onFileChange({ target: { files: [selectedFile] } });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  // Determine current Step
  // 1: Upload (no file)
  // 2: Analyze (file selected, no result)
  // 3: Results (result present)
  const currentStep = result ? 3 : file ? 2 : 1;

  // If we have a result, render the "Analysis Complete" card
  if (result) {
    return (
      <div style={{ padding: '32px', background: '#fff', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-sm)', maxWidth: '600px', margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <CheckCircle2 size={24} color="#10b981" />
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#0f172a', margin: 0 }}>Analysis Complete</h2>
        </div>
        
        <div style={{ background: '#f8fafc', padding: '20px', borderRadius: 'var(--radius-md)', border: '1px solid #e2e8f0', marginBottom: '24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Battery</div>
              <div style={{ fontSize: '15px', color: '#0f172a', fontWeight: 500 }}>
                {file?.name?.includes('battery_') ? file.name.split('_')[1] : 'Unknown'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Total Rows</div>
              <div style={{ fontSize: '15px', color: '#0f172a', fontWeight: 500 }}>
                {(result.total_windows * 50).toLocaleString()}
              </div>
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{ fontSize: '12px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Dataset</div>
              <div style={{ fontSize: '13px', color: '#334155', wordBreak: 'break-all' }}>{file?.name}</div>
            </div>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn btn-primary" onClick={onViewAnalysis} style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}>
            View Analysis <ArrowRight size={16} />
          </button>
          <button className="btn btn-outline" onClick={onClear} style={{ color: '#64748b' }}>
            Change Dataset
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '40px', background: 'var(--color-bg-card)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-sm)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ width: '48px', height: '48px', background: '#e0f2fe', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FolderUp size={24} color="#0ea5e9" />
          </div>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-primary)', margin: '0 0 4px 0' }}>Upload Battery Dataset</h2>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '14px', margin: 0 }}>Select a CSV dataset to begin analysis.</p>
          </div>
        </div>
        <div style={{ fontSize: '12px', fontWeight: 600, color: '#4f46e5', background: '#e0e7ff', padding: '6px 12px', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileText size={14} /> CSV only
        </div>
      </div>
      
      {!file ? (
        <label 
          className="dropzone upload-zone-bg"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          style={{ 
            padding: '40px 20px', 
            height: '240px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            border: `2px dashed ${dragActive ? '#3b82f6' : '#93c5fd'}`,
            transition: 'all 0.2s ease',
            cursor: 'pointer',
            borderRadius: 'var(--radius-md)'
          }}
        >
          <input 
            type="file" 
            accept=".csv" 
            onChange={handleChange} 
            style={{ display: 'none' }} 
          />
          <UploadCloud size={48} color="#3b82f6" style={{ marginBottom: 16 }} />
          <div style={{ fontSize: '16px', fontWeight: 500, color: dragActive ? '#1d4ed8' : '#334155', marginBottom: 8 }}>
            {dragActive ? 'Drop CSV to upload' : 'Drop CSV here or browse files'}
          </div>
          <div className="btn btn-outline" style={{ pointerEvents: 'none', marginTop: '16px', fontSize: '13px' }}>
            Choose CSV
          </div>
        </label>
      ) : (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)', padding: '16px 20px', background: '#f8fafc', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <FileSpreadsheet size={24} color="#10b981" />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
                {file.name}
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                CSV Dataset • {file.size ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'Unknown size'}
              </div>
            </div>
          </div>
          <button 
            onClick={onClear}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: '#3b82f6', 
              fontSize: '13px', 
              fontWeight: 500, 
              cursor: 'pointer',
              padding: '4px 8px'
            }}
          >
            Change
          </button>
        </div>
      )}

      {uploadError && (
        <div style={{ marginTop: '16px', padding: '12px 16px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', color: '#991b1b', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          <AlertCircle size={16} /> {uploadError}
        </div>
      )}
      
      <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
        <button 
          className="btn btn-gradient" 
          onClick={onAnalyze} 
          disabled={!file || loading}
          style={{ padding: '12px 48px', fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <Activity size={18} />
          {loading ? 'Analyzing battery...' : 'Analyze Battery'}
        </button>
      </div>

      {/* Steps Indicator */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '24px', marginTop: '40px', borderTop: '1px solid #f1f5f9', paddingTop: '24px' }}>
        <div style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: currentStep >= 1 ? '#0ea5e9' : '#94a3b8', fontWeight: currentStep >= 1 ? 600 : 400 }}>
          {currentStep > 1 ? (
            <CheckCircle2 size={14} color="#10b981" />
          ) : (
            <span style={{ background: '#0ea5e9', color: 'white', width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>01</span>
          )} 
          Upload
        </div>
        <div style={{ width: '40px', height: '1px', background: currentStep >= 2 ? '#0ea5e9' : '#e2e8f0' }}></div>
        <div style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: currentStep >= 2 ? '#0ea5e9' : '#94a3b8', fontWeight: currentStep >= 2 ? 600 : 400 }}>
          {currentStep > 2 ? (
            <CheckCircle2 size={14} color="#10b981" />
          ) : (
            <span style={{ background: currentStep === 2 ? '#0ea5e9' : '#e2e8f0', color: currentStep === 2 ? 'white' : '#64748b', width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>02</span>
          )} 
          Analyze
        </div>
        <div style={{ width: '40px', height: '1px', background: currentStep >= 3 ? '#0ea5e9' : '#e2e8f0' }}></div>
        <div style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: currentStep >= 3 ? '#0ea5e9' : '#94a3b8', fontWeight: currentStep >= 3 ? 600 : 400 }}>
           <span style={{ background: currentStep === 3 ? '#0ea5e9' : '#e2e8f0', color: currentStep === 3 ? 'white' : '#64748b', width: '20px', height: '20px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>03</span> Results
        </div>
      </div>
    </div>
  );
}
