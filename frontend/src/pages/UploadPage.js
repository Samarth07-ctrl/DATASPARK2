// ==============================================================================
// File: frontend/src/pages/UploadPage.js
// Purpose: CSV upload via dropzone → AI analysis table → action selection →
//          triggers processing and navigates to the analysis dashboard.
// ==============================================================================

import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import {
  UploadCloud, BarChart2, Zap, Loader, X,
  AlertTriangle, CheckCircle, Sparkles,
  Target, Brain, ChevronDown, Scale, TriangleAlert
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/api';

// Context-aware objective options
const OBJECTIVES = [
  { value: '', label: 'Select your objective...', disabled: true },
  { value: 'eda', label: 'Exploratory Data Analysis (EDA)' },
  { value: 'machine_learning', label: 'Machine Learning' },
  { value: 'bi_reporting', label: 'BI / Reporting' },
];

const MODEL_TYPES = [
  { value: '', label: 'Select model type...', disabled: true },
  { value: 'tree_based', label: 'Tree-Based / XGBoost' },
  { value: 'linear_models', label: 'Linear Models (Regression, SVM)' },
  { value: 'deep_learning', label: 'Deep Learning / Neural Nets' },
];

const UploadPage = () => {
  const [analysisData, setAnalysisData] = useState(null);
  const [processingActions, setProcessingActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [objective, setObjective] = useState('');
  const [modelType, setModelType] = useState('');
  const [targetColumn, setTargetColumn] = useState('');
  const [imbalanceData, setImbalanceData] = useState(null);
  const [imbalanceLoading, setImbalanceLoading] = useState(false);
  const [applySmote, setApplySmote] = useState(false);
  const { token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // --- Feature 4: Load from History ---
  useEffect(() => {
    if (location.state?.historicalAnalysis) {
      const data = location.state.historicalAnalysis;
      setAnalysisData(data);
      // Auto-populate actions if any exist
      if (data.column_analysis) {
        const autoActions = data.column_analysis
          .filter(col => col.ai_recommendation && col.ai_recommendation !== 'no_action')
          .map(col => ({ column: col.column_name, action: col.ai_recommendation }));
        setProcessingActions(autoActions);
      }
      
      // Clear state so reload doesn't trigger it again
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (objective) {
        formData.append('objective', objective);
      }
      if (objective === 'machine_learning' && modelType) {
        formData.append('model_type', modelType);
      }

      const response = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to analyze file');
      }

      const data = await response.json();
      setAnalysisData(data);
      // Auto-populate actions based on AI recommendation
      const autoActions = data.column_analysis
        .filter(col => col.ai_recommendation && col.ai_recommendation !== 'no_action')
        .map(col => ({ column: col.column_name, action: col.ai_recommendation }));
      setProcessingActions(autoActions);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, objective, modelType]);

  // --- Feature 3: Check for class imbalance when target column changes ---
  const checkImbalance = async (columnName) => {
    if (!columnName || !analysisData?.file_id) {
      setImbalanceData(null);
      setApplySmote(false);
      return;
    }
    setImbalanceLoading(true);
    try {
      const response = await fetch(`${API_URL}/detect-imbalance`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          file_id: analysisData.file_id,
          target_column: columnName,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setImbalanceData(data);
        // Auto-enable SMOTE for severe imbalance
        if (data.imbalance_severity === 'severe') {
          setApplySmote(true);
        }
      } else {
        setImbalanceData(null);
      }
    } catch (err) {
      console.error('Imbalance check failed:', err);
      setImbalanceData(null);
    } finally {
      setImbalanceLoading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv']
    },
    multiple: false
  });

  const addAction = (column, action) => {
    const newAction = { column, action };
    setProcessingActions(prev => {
      const existingIndex = prev.findIndex(a => a.column === column);
      
      if (action === "no_action") {
        return prev.filter(a => a.column !== column);
      }
      
      if (existingIndex > -1) {
        const updatedActions = [...prev];
        updatedActions[existingIndex] = newAction;
        return updatedActions;
      }
      
      return [...prev, newAction];
    });
  };

  const removeAction = (columnName) => {
    setProcessingActions(prev => prev.filter(a => a.column !== columnName));
    const select = document.getElementById(`select-${columnName}`);
    if(select) {
      select.value = "no_action";
    }
  };

  const processData = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          actions: processingActions,
          file_id: analysisData.file_id,
          target_column: targetColumn || null,
          apply_smote: applySmote,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to process data');
      }

      const dashboardData = await response.json();
      navigate('/dashboard/analysis', { state: { analysisData: dashboardData, filename: analysisData.filename } });

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const resetUpload = () => {
    setAnalysisData(null);
    setProcessingActions([]);
    setError('');
    setTargetColumn('');
    setImbalanceData(null);
    setApplySmote(false);
  };

  const StatCard = ({ title, value }) => (
    <div className="stat-card">
      <div className="stat-title">{title}</div>
      <div className="stat-value">{value}</div>
    </div>
  );

  return (
    <div className="upload-page">
      <div className="upload-container">
        
        {!analysisData && !loading && (
          <>
            <div className="upload-header">
              <h1 className="main-title">Upload & Clean Your Data</h1>
              <p className="subtitle">
                Transform your raw data into clean, analysis-ready datasets with AI-powered intelligence.
              </p>
            </div>

            {/* === Context-Aware Objective Panel === */}
            <div className="context-panel">
              <div className="context-panel-header">
                <div className="context-panel-icon">
                  <Target size={20} />
                </div>
                <div>
                  <h3 className="context-panel-title">What's your goal?</h3>
                  <p className="context-panel-subtitle">Help our AI tailor recommendations to your use-case</p>
                </div>
              </div>
              <div className="context-panel-body">
                <div className="context-select-group">
                  <label className="context-label" htmlFor="objective-select">
                    <Brain size={14} />
                    Analysis Objective
                  </label>
                  <div className="context-select-wrapper">
                    <select
                      id="objective-select"
                      className="context-select"
                      value={objective}
                      onChange={(e) => {
                        setObjective(e.target.value);
                        if (e.target.value !== 'machine_learning') {
                          setModelType('');
                        }
                      }}
                    >
                      {OBJECTIVES.map(opt => (
                        <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="context-select-arrow" />
                  </div>
                </div>

                {objective === 'machine_learning' && (
                  <div className="context-select-group context-select-animate">
                    <label className="context-label" htmlFor="model-type-select">
                      <Zap size={14} />
                      Target Model Type
                    </label>
                    <div className="context-select-wrapper">
                      <select
                        id="model-type-select"
                        className="context-select"
                        value={modelType}
                        onChange={(e) => setModelType(e.target.value)}
                      >
                        {MODEL_TYPES.map(opt => (
                          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={16} className="context-select-arrow" />
                    </div>
                  </div>
                )}

                {objective && (
                  <div className="context-badge">
                    <Sparkles size={14} />
                    <span>
                      {objective === 'eda' && 'AI will prioritize data quality insights and exploratory recommendations.'}
                      {objective === 'machine_learning' && !modelType && 'Select a model type to unlock model-specific AI guidance.'}
                      {objective === 'machine_learning' && modelType === 'tree_based' && 'AI will skip scaling, prefer label encoding, and focus on missing value handling.'}
                      {objective === 'machine_learning' && modelType === 'linear_models' && 'AI will enforce standard scaling, flag multicollinearity, and recommend one-hot encoding.'}
                      {objective === 'machine_learning' && modelType === 'deep_learning' && 'AI will enforce MinMax [0,1] scaling and flag high-cardinality features.'}
                      {objective === 'bi_reporting' && 'AI will preserve human-readable formats and suggest datetime extraction.'}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="dropzone-container">
              <div
                {...getRootProps()}
                className={`dropzone ${isDragActive ? 'active' : ''}`}
              >
                <input {...getInputProps()} />
                <div className="dropzone-content">
                  <div className="dropzone-icon">
                    <UploadCloud size={64} />
                    <div className="upload-pulse"></div>
                  </div>
                  {isDragActive ? (
                    <div className="dropzone-text">
                      <h3>Drop your file here</h3>
                      <p>Release to start processing</p>
                    </div>
                  ) : (
                    <div className="dropzone-text">
                      <h3>Drag & drop your CSV file here</h3>
                      <p>or click to browse your files</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="upload-features">
                <div className="upload-feature">
                  <CheckCircle size={16} />
                  <span>Secure & Private</span>
                </div>
                <div className="upload-feature">
                  <CheckCircle size={16} />
                  <span>AI-Powered Analysis</span>
                </div>
                <div className="upload-feature">
                  <CheckCircle size={16} />
                  <span>Instant Results</span>
                </div>
              </div>
            </div>
          </>
        )}

        {loading && !analysisData && (
          <div className="centered-container">
            <div className="loading-animation">
              <div className="loading-spinner"></div>
              <div className="loading-dots">
                <div className="dot"></div>
                <div className="dot"></div>
                <div className="dot"></div>
              </div>
            </div>
            <h2 className="loading-title">Our AI is examining your dataset...</h2>
            <p className="loading-subtitle">This may take a moment for large files. Please wait.</p>
          </div>
        )}

        {analysisData && (
          <div className="dashboard-container">
            <div className="stats-grid">
              <StatCard title="Rows" value={analysisData.row_count.toLocaleString()} />
              <StatCard title="Columns" value={analysisData.column_count} />
              <StatCard title="File" value={analysisData.filename} />
              <StatCard title="Issues Found" value={analysisData.column_analysis.filter(col => col.is_problematic).length} />
            </div>

            <div className="analysis-layout">
              <div className="column-details-panel">
                <div className="panel-header">
                  <h3>AI Column Analysis</h3>
                  <button onClick={resetUpload} className="reset-button">
                    <X size={16} />
                    Upload New File
                  </button>
                </div>
                
                <div className="table-container">
                  <table className="analysis-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Missing</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysisData.column_analysis.map((col, index) => (
                        <tr key={index} className={col.is_problematic ? 'problematic' : ''}>
                          <td>
                            <div className="column-info">
                              <strong>{col.column_name}</strong>
                              <small>{col.data_type} | {col.unique_values} unique</small>
                            </div>
                            {col.ai_insights && (
                              <div className="ai-insight-box">
                                <Sparkles size={14} />
                                <strong>AI Insight:</strong> {col.ai_insights}
                              </div>
                            )}
                          </td>
                          <td>
                            <span className={`missing-percentage ${col.missing_percentage > 50 ? 'high' : col.missing_percentage > 20 ? 'medium' : 'low'}`}>
                              {col.missing_percentage}%
                            </span>
                          </td>
                          <td>
                            {(col.suggestions.length > 0 || col.ai_recommendation) ? (
                              <select
                                id={`select-${col.column_name}`}
                                onChange={(e) => addAction(col.column_name, e.target.value)}
                                value={processingActions.find(a => a.column === col.column_name)?.action || col.recommended_action || "no_action"}
                              >
                                <option value="no_action">No Action</option>
                                {col.suggestions.map((suggestion, i) => (
                                  <option key={i} value={suggestion}>
                                    {suggestion.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                    {suggestion === col.ai_recommendation && ' (AI Rec)'}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span>No actions needed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* === Feature 3: Target Variable & Imbalance Detection === */}
              {objective === 'machine_learning' && (
                <div className="imbalance-panel">
                  <div className="panel-header">
                    <h3><Scale size={18} /> Target Variable & Class Balance</h3>
                  </div>
                  <div className="imbalance-panel-body">
                    <div className="context-select-group">
                      <label className="context-label" htmlFor="target-column-select">
                        <Target size={14} />
                        Select Target Column
                      </label>
                      <div className="context-select-wrapper">
                        <select
                          id="target-column-select"
                          className="context-select"
                          value={targetColumn}
                          onChange={(e) => {
                            setTargetColumn(e.target.value);
                            checkImbalance(e.target.value);
                          }}
                        >
                          <option value="">Select target column...</option>
                          {analysisData.column_analysis.map((col, i) => (
                            <option key={i} value={col.column_name}>
                              {col.column_name} ({col.data_type}, {col.unique_values} unique)
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={16} className="context-select-arrow" />
                      </div>
                    </div>

                    {imbalanceLoading && (
                      <div className="imbalance-loading">
                        <Loader size={16} className="spinner" />
                        <span>Analyzing class distribution...</span>
                      </div>
                    )}

                    {imbalanceData && !imbalanceLoading && (
                      <div className={`imbalance-result ${imbalanceData.imbalance_severity}`}>
                        <div className="imbalance-header">
                          {imbalanceData.imbalance_severity === 'severe' ? (
                            <TriangleAlert size={20} className="imbalance-icon severe" />
                          ) : imbalanceData.imbalance_severity === 'moderate' ? (
                            <AlertTriangle size={20} className="imbalance-icon moderate" />
                          ) : (
                            <CheckCircle size={20} className="imbalance-icon balanced" />
                          )}
                          <div>
                            <strong>
                              {imbalanceData.imbalance_severity === 'severe' && 'Severe Class Imbalance Detected!'}
                              {imbalanceData.imbalance_severity === 'moderate' && 'Moderate Class Imbalance'}
                              {imbalanceData.imbalance_severity === 'balanced' && 'Classes Are Balanced'}
                            </strong>
                            <p>
                              Majority class "{imbalanceData.majority_class}" has {imbalanceData.majority_percentage}% of samples
                            </p>
                          </div>
                        </div>

                        {/* Class Distribution Bars */}
                        <div className="class-dist-bars">
                          {Object.entries(imbalanceData.class_percentages).map(([cls, pct]) => (
                            <div key={cls} className="class-bar-row">
                              <span className="class-bar-label">{cls}</span>
                              <div className="class-bar-track">
                                <div
                                  className="class-bar-fill"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="class-bar-pct">{pct}%</span>
                            </div>
                          ))}
                        </div>

                        {/* SMOTE Toggle */}
                        {imbalanceData.is_imbalanced && (
                          <div className="smote-toggle-container">
                            <div className="smote-info">
                              <strong>Apply SMOTE Balancing</strong>
                              <p>Synthetic Minority Over-sampling will generate new samples to balance your dataset before download.</p>
                            </div>
                            <label className="smote-switch">
                              <input
                                type="checkbox"
                                checked={applySmote}
                                onChange={(e) => setApplySmote(e.target.checked)}
                              />
                              <span className="smote-slider" />
                            </label>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {processingActions.length > 0 && (
                <div className="processing-actions-panel">
                  <div className="panel-header">
                    <h3>Selected Actions ({processingActions.length})</h3>
                  </div>
                  <div className="actions-list">
                    {processingActions.map((action, index) => (
                      <div key={index} className="action-item">
                        <span>
                          <strong>{action.column}</strong>: {action.action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </span>
                        <button onClick={() => removeAction(action.column)} className="remove-action">
                          <X size={16} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={processData}
                    disabled={loading}
                    className="process-button"
                  >
                    {loading ? (
                      <>
                        <Loader className="spinner" size={16} />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Zap size={16} />
                        Process & View Dashboard
                      </>
                    )}
                  </button>
                </div>
              )}

              {processingActions.length === 0 && (
                <div className="no-actions">
                  <Zap size={48} />
                  <h3>No actions selected.</h3>
                  <p>Our AI has not flagged any critical issues. You can select actions from the dropdowns above or click Process to see the dashboard.</p>
                  <button
                    onClick={processData}
                    disabled={loading}
                    className="process-button"
                  >
                    {loading ? (
                      <>
                        <Loader className="spinner" size={16} />
                        Processing...
                      </>
                    ) : (
                      <>
                        <BarChart2 size={16} />
                        View Dashboard Anyway
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="error-container">
            <AlertTriangle size={24} />
            <p>{error}</p>
            <button onClick={resetUpload} className="error-retry-button">
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadPage;
