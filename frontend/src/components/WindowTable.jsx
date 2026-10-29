import React, { useState } from 'react';
import { Search, Filter, ArrowUpDown, Layers } from 'lucide-react';

export default function WindowTable({ windows, onSelectWindow }) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');
  const [sort, setSort] = useState('Window');
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(20);

  if (!windows || windows.length === 0) return null;

  // Filter
  let filtered = windows.filter(w => {
    if (filter === 'Normal' && w.suspicious) return false;
    if (filter === 'Suspicious' && !w.suspicious) return false;
    if (search && !w.window.toString().includes(search)) return false;
    return true;
  });

  // Sort
  if (sort === 'Score High → Low') {
    filtered.sort((a, b) => Number(b.score) - Number(a.score));
  } else if (sort === 'Score Low → High') {
    filtered.sort((a, b) => Number(a.score) - Number(b.score));
  } else {
    filtered.sort((a, b) => a.window - b.window);
  }

  // Paginate
  const isAll = rowsPerPage === 'all';
  const effectiveRowsPerPage = isAll ? filtered.length || 1 : rowsPerPage;
  const totalPages = Math.ceil(filtered.length / effectiveRowsPerPage) || 1;
  const currentData = filtered.slice((page - 1) * effectiveRowsPerPage, page * effectiveRowsPerPage);

  const startEntry = filtered.length === 0 ? 0 : (page - 1) * effectiveRowsPerPage + 1;
  const endEntry = Math.min(page * effectiveRowsPerPage, filtered.length);

  return (
    <div className="card">
      <div className="card-header" style={{ alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <h2 className="card-title">Battery Windows</h2>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: '#f1f5f9', padding: '6px 12px', borderRadius: '4px' }}>
            <Search size={14} color="#64748b" style={{ marginRight: '6px' }} />
            <input 
              type="text" 
              placeholder="Search window..." 
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: '13px', width: '120px' }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} color="#64748b" />
            <select value={filter} onChange={e => { setFilter(e.target.value); setPage(1); }} className="form-control" style={{ padding: '4px 8px' }}>
              <option value="All">All Status</option>
              <option value="Normal">Normal</option>
              <option value="Suspicious">Suspicious</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowUpDown size={14} color="#64748b" />
            <select value={sort} onChange={e => { setSort(e.target.value); setPage(1); }} className="form-control" style={{ padding: '4px 8px' }}>
              <option value="Window">Window #</option>
              <option value="Score High → Low">Score High → Low</option>
              <option value="Score Low → High">Score Low → High</option>
            </select>
          </div>
        </div>
      </div>

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Window #</th>
              <th>Row Range</th>
              <th>Anomaly Score</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {currentData.length === 0 && (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>No windows match the current filters.</td>
              </tr>
            )}
            {currentData.map(w => (
              <tr key={w.window} className={w.suspicious ? 'row-suspicious' : 'row-normal'} onClick={() => onSelectWindow(w)}>
                <td style={{ fontWeight: 500 }}>#{w.window}</td>
                <td style={{ color: '#64748b' }}>{w.start_row}–{w.end_row}</td>
                <td>{Number(w.score).toFixed(4)}</td>
                <td>
                  {w.suspicious ? (
                    <span className="badge badge-warning">Suspicious</span>
                  ) : (
                    <span className="badge badge-success">Normal</span>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>
                  {w.suspicious && (
                    <span style={{ color: '#0ea5e9', fontSize: '13px', fontWeight: 500 }}>Diagnose →</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} color="#64748b" />
            <select 
              value={rowsPerPage} 
              onChange={e => { 
                setRowsPerPage(e.target.value === 'all' ? 'all' : Number(e.target.value)); 
                setPage(1); 
              }} 
              className="form-control" 
              style={{ padding: '2px 6px', fontSize: '13px' }}
            >
              <option value={10}>10 rows</option>
              <option value={20}>20 rows</option>
              <option value={50}>50 rows</option>
              <option value={100}>100 rows</option>
              <option value="all">All</option>
            </select>
          </div>
          <div style={{ fontSize: '13px', color: '#64748b' }}>
            Showing {startEntry} to {endEntry} of {filtered.length} entries
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-outline" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ padding: '4px 10px' }}>Prev</button>
          <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: '13px', margin: '0 8px' }}>Page {page} of {totalPages}</span>
          <button className="btn btn-outline" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ padding: '4px 10px' }}>Next</button>
        </div>
      </div>
    </div>
  );
}
