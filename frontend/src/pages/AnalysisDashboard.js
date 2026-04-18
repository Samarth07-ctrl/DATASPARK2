// ==============================================================================
// File: frontend/src/pages/AnalysisDashboard.js
// Purpose: "Before vs After" visual report with Recharts + custom heatmaps.
//          Includes: Missing Values Heatmap, Distribution Histograms,
//          Correlation Matrix, and original stat/chart comparisons.
// ==============================================================================

import React, { useState, useMemo, useEffect } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Download, Loader, AlertTriangle, CheckCircle, Activity, CornerDownLeft,
  Grid3X3, BarChart3, GitBranch, ChevronLeft, ChevronRight
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  PieChart, Pie, Cell, Tooltip
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/api';

// =============================================================================
// SUB-COMPONENT: Missing Values Heatmap
// =============================================================================
const MissingValuesHeatmap = ({ dataBefore, dataAfter }) => {
  const [showAfter, setShowAfter] = useState(false);
  const active = showAfter ? dataAfter : dataBefore;

  if (!active || !active.columns || !active.data || active.data.length === 0) {
    return null;
  }

  const cols = active.columns;
  const rows = active.data;

  return (
    <div className="viz-card viz-heatmap-card">
      <div className="viz-card-header">
        <div className="viz-card-title-group">
          <Grid3X3 size={20} className="viz-card-icon" />
          <h3 className="viz-card-title">Missing Values Heatmap</h3>
        </div>
        <div className="viz-toggle-group">
          <button
            className={`viz-toggle-btn ${!showAfter ? 'active' : ''}`}
            onClick={() => setShowAfter(false)}
          >Before</button>
          <button
            className={`viz-toggle-btn ${showAfter ? 'active' : ''}`}
            onClick={() => setShowAfter(true)}
          >After</button>
        </div>
      </div>
      <p className="viz-card-subtitle">
        {showAfter ? 'Post-processing' : 'Raw data'} — {active.sampled_rows} sampled from {active.total_rows.toLocaleString()} rows
      </p>
      <div className="heatmap-scroll-container">
        <div className="heatmap-grid" style={{
          gridTemplateColumns: `80px repeat(${cols.length}, 1fr)`,
        }}>
          {/* Column headers */}
          <div className="heatmap-corner" />
          {cols.map((col, i) => (
            <div key={i} className="heatmap-col-label" title={col}>
              {col.length > 8 ? col.slice(0, 7) + '…' : col}
            </div>
          ))}

          {/* Data rows */}
          {rows.map((row, rowIdx) => (
            <React.Fragment key={rowIdx}>
              <div className="heatmap-row-label">Row {rowIdx + 1}</div>
              {row.map((cell, colIdx) => (
                <div
                  key={colIdx}
                  className={`heatmap-cell ${cell === 1 ? 'missing' : 'present'}`}
                  title={`${cols[colIdx]}: ${cell === 1 ? 'MISSING' : 'Present'}`}
                />
              ))}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="heatmap-legend">
        <span className="heatmap-legend-item">
          <span className="heatmap-swatch present" /> Present
        </span>
        <span className="heatmap-legend-item">
          <span className="heatmap-swatch missing" /> Missing
        </span>
      </div>
    </div>
  );
};

// =============================================================================
// SUB-COMPONENT: Distribution Histograms (Before vs After)
// =============================================================================
const DistributionHistograms = ({ histogramsBefore, histogramsAfter }) => {
  const [selectedIdx, setSelectedIdx] = useState(0);

  // Build a unified column list
  const columnNames = useMemo(() => {
    const names = new Set();
    (histogramsBefore || []).forEach(h => names.add(h.column_name));
    (histogramsAfter || []).forEach(h => names.add(h.column_name));
    return Array.from(names);
  }, [histogramsBefore, histogramsAfter]);

  const currentCol = columnNames[selectedIdx] || columnNames[0];
  const beforeHist = (histogramsBefore || []).find(h => h.column_name === currentCol);
  const afterHist = (histogramsAfter || []).find(h => h.column_name === currentCol);

  // Merge before/after bins into one chart dataset
  const chartData = useMemo(() => {
    const maxBins = Math.max(
      beforeHist?.bins?.length || 0,
      afterHist?.bins?.length || 0
    );
    const data = [];
    for (let i = 0; i < maxBins; i++) {
      const bBin = beforeHist?.bins?.[i];
      const aBin = afterHist?.bins?.[i];
      const label = bBin
        ? `${bBin.bin_start.toFixed(1)}`
        : aBin
          ? `${aBin.bin_start.toFixed(1)}`
          : `${i}`;
      data.push({
        range: label,
        Before: bBin?.count || 0,
        After: aBin?.count || 0,
      });
    }
    return data;
  }, [beforeHist, afterHist]);

  const prev = () => setSelectedIdx(i => Math.max(0, i - 1));
  const next = () => setSelectedIdx(i => Math.min(columnNames.length - 1, i + 1));

  if (columnNames.length === 0) return null;

  return (
    <div className="viz-card">
      <div className="viz-card-header">
        <div className="viz-card-title-group">
          <BarChart3 size={20} className="viz-card-icon" />
          <h3 className="viz-card-title">Distribution: Before vs After</h3>
        </div>
        <div className="viz-column-nav">
          <button className="viz-nav-btn" onClick={prev} disabled={selectedIdx === 0}>
            <ChevronLeft size={16} />
          </button>
          <span className="viz-nav-label">
            {currentCol}
            <small>{selectedIdx + 1} / {columnNames.length}</small>
          </span>
          <button className="viz-nav-btn" onClick={next} disabled={selectedIdx === columnNames.length - 1}>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      <div className="viz-chart-body">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} barGap={0}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="range" stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '0.5rem' }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Legend />
            <Bar dataKey="Before" fill="rgba(239, 68, 68, 0.7)" radius={[3, 3, 0, 0]} />
            <Bar dataKey="After" fill="rgba(16, 185, 129, 0.7)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

// =============================================================================
// SUB-COMPONENT: Correlation Matrix Heatmap
// =============================================================================
const CorrelationHeatmap = ({ dataBefore, dataAfter }) => {
  const [showAfter, setShowAfter] = useState(false);
  const active = showAfter ? dataAfter : dataBefore;

  if (!active || !active.columns || active.columns.length < 2) return null;

  const cols = active.columns;
  const matrix = active.matrix;

  // Color interpolation: -1 (blue) → 0 (dark) → 1 (red)
  const getColor = (val) => {
    if (val === null || val === undefined) return 'rgba(30, 41, 59, 0.5)';
    const v = Math.max(-1, Math.min(1, val));
    if (v >= 0) {
      const intensity = Math.round(v * 200);
      return `rgba(239, ${68 + (1 - v) * 100}, 68, ${0.15 + v * 0.75})`;
    } else {
      const absV = Math.abs(v);
      return `rgba(59, ${130 + (1 - absV) * 80}, 246, ${0.15 + absV * 0.75})`;
    }
  };

  return (
    <div className="viz-card viz-correlation-card">
      <div className="viz-card-header">
        <div className="viz-card-title-group">
          <GitBranch size={20} className="viz-card-icon" />
          <h3 className="viz-card-title">Correlation Matrix</h3>
        </div>
        <div className="viz-toggle-group">
          <button
            className={`viz-toggle-btn ${!showAfter ? 'active' : ''}`}
            onClick={() => setShowAfter(false)}
          >Before</button>
          <button
            className={`viz-toggle-btn ${showAfter ? 'active' : ''}`}
            onClick={() => setShowAfter(true)}
          >After</button>
        </div>
      </div>
      <p className="viz-card-subtitle">Pearson correlation between {cols.length} numeric features</p>
      <div className="corr-scroll-container">
        <div className="corr-grid" style={{
          gridTemplateColumns: `100px repeat(${cols.length}, 1fr)`,
        }}>
          {/* Corner + column headers */}
          <div className="corr-corner" />
          {cols.map((col, i) => (
            <div key={i} className="corr-col-label" title={col}>
              {col.length > 6 ? col.slice(0, 5) + '…' : col}
            </div>
          ))}

          {/* Data rows */}
          {matrix.map((row, rowIdx) => (
            <React.Fragment key={rowIdx}>
              <div className="corr-row-label" title={cols[rowIdx]}>
                {cols[rowIdx].length > 10 ? cols[rowIdx].slice(0, 9) + '…' : cols[rowIdx]}
              </div>
              {row.map((val, colIdx) => (
                <div
                  key={colIdx}
                  className="corr-cell"
                  style={{ background: getColor(val) }}
                  title={`${cols[rowIdx]} × ${cols[colIdx]}: ${val !== null ? val.toFixed(3) : 'N/A'}`}
                >
                  {val !== null ? (Math.abs(val) > 0.01 ? val.toFixed(2) : '0') : '—'}
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="corr-legend">
        <span className="corr-legend-label">-1.0</span>
        <div className="corr-legend-gradient" />
        <span className="corr-legend-label">+1.0</span>
      </div>
    </div>
  );
};


// =============================================================================
// MAIN DASHBOARD COMPONENT
// =============================================================================
const AnalysisDashboard = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { jobId: urlJobId } = useParams();
  const { token } = useAuth();
  const [isDownloading, setIsDownloading] = useState(false);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [historicalError, setHistoricalError] = useState('');
  const [fetchedData, setFetchedData] = useState(null);

  // --- Source 1: Fresh processing data passed via location.state ---
  const stateData = useMemo(() => location.state?.analysisData, [location.state]);
  const stateFilename = useMemo(() => location.state?.filename || '', [location.state]);

  // --- Source 2: Historical data fetched from API when URL has :jobId ---
  useEffect(() => {
    if (urlJobId && !stateData) {
      const fetchHistorical = async () => {
        setHistoricalLoading(true);
        setHistoricalError('');
        try {
          const response = await fetch(`${API_URL}/analysis/job/${urlJobId}`, {
            headers: { 'Authorization': `Bearer ${token}` },
          });
          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to load historical analysis');
          }
          const data = await response.json();
          setFetchedData(data);
        } catch (err) {
          setHistoricalError(err.message);
        } finally {
          setHistoricalLoading(false);
        }
      };
      fetchHistorical();
    }
  }, [urlJobId, stateData, token]);

  // --- Unified data resolution: state takes priority, then fetched ---
  const resolvedData = stateData || fetchedData;
  const analysisData = resolvedData?.analysis;
  const vizData = resolvedData?.visualization_data;
  const jobId = resolvedData?.job_id || (urlJobId ? parseInt(urlJobId) : null);
  const filename = stateFilename || fetchedData?.filename || 'processed_file';

  const { before = [], after = [] } = analysisData || {};

  const beforeChartData = useMemo(() => {
    return before.map(col => ({ name: col.name, Missing: col.missing, Outliers: col.outliers }));
  }, [before]);

  const afterChartData = useMemo(() => {
    return after.map(col => ({ name: col.name, Missing: col.missing, Outliers: col.outliers }));
  }, [after]);

  const pieData = useMemo(() => {
    if (!analysisData) return [];
    const beforeMissing = before.reduce((acc, col) => acc + col.missing, 0);
    const afterMissing = after.reduce((acc, col) => acc + col.missing, 0);
    const beforeOutliers = before.reduce((acc, col) => acc + col.outliers, 0);
    const afterOutliers = after.reduce((acc, col) => acc + col.outliers, 0);

    return [
      { name: 'Missing (Before)', value: beforeMissing, fill: '#EF4444' },
      { name: 'Missing (After)', value: afterMissing, fill: '#10B981' },
      { name: 'Outliers (Before)', value: beforeOutliers, fill: '#F59E0B' },
      { name: 'Outliers (After)', value: afterOutliers, fill: '#3B82F6' },
    ].filter(entry => entry.value > 0);
  }, [analysisData, before, after]);

  const meanMedianData = useMemo(() => {
    return after.filter(col => col.mean !== null && before.find(b => b.name === col.name && b.mean !== null));
  }, [after, before]);

  useEffect(() => {
    // Only redirect if we have no data AND we're not loading AND there's no URL param to fetch
    if (!analysisData && !historicalLoading && !urlJobId) {
      navigate('/upload', { replace: true });
    }
  }, [analysisData, historicalLoading, urlJobId, navigate]);

  const downloadFile = async () => {
    if (!jobId) return;
    setIsDownloading(true);
    try {
      const response = await fetch(`${API_URL}/download/job/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // Try to extract filename from Content-Disposition header (set by backend)
      const disposition = response.headers.get('content-disposition');
      let downloadFilename = '';
      if (disposition) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches?.[1]) {
          downloadFilename = matches[1].replace(/['"]/g, '');
        }
      }
      
      // Fallback: construct from the filename prop, guaranteeing .csv extension
      if (!downloadFilename) {
        const baseName = filename.replace(/\.csv$/i, '');
        downloadFilename = `cleaned_${baseName}.csv`;
      }

      a.download = downloadFilename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup: remove temporary element and revoke object URL
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download error:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  if (historicalLoading || (!analysisData && (urlJobId || historicalError))) {
    return (
      <div className="loading-container centered-container">
        {historicalError ? (
          <>
            <AlertTriangle size={48} className="icon-red" />
            <h2 className="loading-title" style={{ color: '#ef4444' }}>Failed to Load Analysis</h2>
            <p className="loading-subtitle">{historicalError}</p>
            <button onClick={() => navigate('/dashboard')} className="btn btn-secondary" style={{ marginTop: '1.5rem' }}>
              <CornerDownLeft size={16} />
              Back to Dashboard
            </button>
          </>
        ) : (
          <>
            <div className="loading-animation">
              <div className="loading-spinner"></div>
            </div>
            <h2 className="loading-title">Loading Historical Analysis...</h2>
            <p className="loading-subtitle">Recomputing visualizations from saved data</p>
          </>
        )}
      </div>
    );
  }
  
  const totalMissingBefore = before.reduce((acc, col) => acc + col.missing, 0);
  const totalMissingAfter = after.reduce((acc, col) => acc + col.missing, 0);
  const totalOutliersBefore = before.reduce((acc, col) => acc + col.outliers, 0);
  const totalOutliersAfter = after.reduce((acc, col) => acc + col.outliers, 0);
  
  const StatCard = ({ icon, title, value, unit }) => (
    <div className="stat-card">
      <div className="stat-icon">
        {icon}
      </div>
      <div>
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value} {unit}</div>
      </div>
    </div>
  );

  return (
    <div className="analysis-dashboard-page">
      <div className="app-container">
        <div className="dashboard-header">
          <div>
            <h1 className="dashboard-title">Processing Complete: Before vs. After</h1>
            <p className="dashboard-subtitle">Visual impact report for <strong>{filename}</strong></p>
          </div>
          <div className="dashboard-actions">
            <Link to="/upload" className="btn btn-secondary">
              <CornerDownLeft size={20} />
              Process Another File
            </Link>
            <button onClick={downloadFile} disabled={isDownloading} className="btn btn-primary">
              {isDownloading ? <Loader size={20} className="spinner" /> : <Download size={20} />}
              {isDownloading ? 'Downloading...' : 'Download Cleaned CSV'}
            </button>
          </div>
        </div>

        {/* === Stat Cards === */}
        <div className="stats-grid">
          <StatCard
            icon={<AlertTriangle size={24} className="icon-red" />}
            title="Missing Values (Before)"
            value={totalMissingBefore.toLocaleString()}
          />
          <StatCard
            icon={<CheckCircle size={24} className="icon-green" />}
            title="Missing Values (After)"
            value={totalMissingAfter.toLocaleString()}
            unit={totalMissingBefore > totalMissingAfter ? `(${((totalMissingBefore - totalMissingAfter) / totalMissingBefore * 100).toFixed(0)}% ↓)` : ''}
          />
          <StatCard
            icon={<Activity size={24} className="icon-yellow" />}
            title="Outliers Detected (Before)"
            value={totalOutliersBefore.toLocaleString()}
          />
          <StatCard
            icon={<CheckCircle size={24} className="icon-green" />}
            title="Outliers Handled (After)"
            value={totalOutliersAfter.toLocaleString()}
            unit={totalOutliersBefore > totalOutliersAfter ? `(${((totalOutliersBefore - totalOutliersAfter) / totalOutliersBefore * 100).toFixed(0)}% ↓)` : ''}
          />
        </div>

        {/* === Feature 2: Advanced Visualizations === */}
        {vizData && (
          <div className="viz-section">
            <h2 className="viz-section-title">Advanced Visual Analysis</h2>

            {/* Missing Values Heatmap */}
            <MissingValuesHeatmap
              dataBefore={vizData.missing_matrix_before}
              dataAfter={vizData.missing_matrix_after}
            />

            {/* Distribution Histograms */}
            <DistributionHistograms
              histogramsBefore={vizData.histograms_before}
              histogramsAfter={vizData.histograms_after}
            />

            {/* Correlation Matrix */}
            <CorrelationHeatmap
              dataBefore={vizData.correlation_before}
              dataAfter={vizData.correlation_after}
            />
          </div>
        )}

        {/* === Original Charts (kept for backward compat) === */}
        <div className="chart-grid">
          <div className="chart-container-large">
            <h3 className="chart-title">Data Quality: Before Processing</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={beforeChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
                <Legend />
                <Bar dataKey="Missing" fill="#EF4444" />
                <Bar dataKey="Outliers" fill="#F59E0B" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          
          <div className="chart-container-large">
            <h3 className="chart-title">Data Quality: After Processing</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={afterChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
                <Legend />
                <Bar dataKey="Missing" fill="#10B981" />
                <Bar dataKey="Outliers" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-grid">
          <div className="chart-container-small">
            <h3 className="chart-title">Total Issues Comparison</h3>
             <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-container-small">
            <h3 className="chart-title">Mean vs. Median (After)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={meanMedianData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
                <Legend />
                <Bar dataKey="mean" fill="#8B5CF6" />
                <Bar dataKey="median" fill="#EC4899" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </div>
  );
};

export default AnalysisDashboard;
