import React from 'react';
import { Database, Search, AlertTriangle, Filter, BrainCircuit, FileCheck2 } from 'lucide-react';

export default function Pipeline({ activeStep = 0 }) {
  const steps = [
    { id: 1, title: 'Battery Data', desc: 'CSV input', icon: Database },
    { id: 2, title: 'Level-1', desc: 'Screening', icon: Search },
    { id: 3, title: 'Event Trigger', desc: 'Suspicious?', icon: AlertTriangle },
    { id: 4, title: 'DDP', desc: 'Reduce data', icon: Filter },
    { id: 5, title: 'Qwen 7B', desc: 'Diagnose', icon: BrainCircuit },
    { id: 6, title: 'Result', desc: 'Explain', icon: FileCheck2 },
  ];

  return (
    <div className="pipeline-container">
      {steps.map((step) => {
        const Icon = step.icon;
        const isActive = activeStep >= step.id;
        return (
          <div key={step.id} className={`pipeline-step ${isActive ? 'active' : ''}`}>
            <div className="pipeline-icon-wrapper">
              <Icon size={20} />
            </div>
            <div style={{ marginTop: 8 }}>
              <div className="pipeline-title">{step.title}</div>
              <div className="pipeline-desc">{step.desc}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
