// ==============================================================================
// File: frontend/src/pages/ImageProcessing.js
// Purpose: Multi-step wizard for image dataset processing.
//          Steps: Upload ZIP → Configure actions → Processing → Download
// ==============================================================================

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Image, Upload, Loader, X, AlertTriangle, CheckCircle, Download
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_URL } from '../config/api';

const ImageProcessing = () => {
  const { token } = useAuth();
  const [currentStep, setCurrentStep] = useState('upload');
  const [analysisData, setAnalysisData] = useState(null);
  const [processingActions, setProcessingActions] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedAction, setSelectedAction] = useState('');
  const [actionParams, setActionParams] = useState({});

  const actionTypes = [
    { id: 'resize', name: 'Resize', params: ['width', 'height'] },
    { id: 'grayscale', name: 'Convert to Grayscale', params: [] },
    { id: 'blur', name: 'Blur', params: ['radius'] },
    { id: 'sharpen', name: 'Sharpen', params: [] },
    { id: 'brightness', name: 'Adjust Brightness', params: ['factor'] },
    { id: 'contrast', name: 'Adjust Contrast', params: ['factor'] },
  ];

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file || !file.name.toLowerCase().endsWith('.zip')) {
      setError('Please upload a ZIP file containing images');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_URL}/images/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to analyze image dataset');
      }

      const data = await response.json();
      setAnalysisData(data);
      setCurrentStep('configure');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/zip': ['.zip']
    },
    multiple: false
  });

  const addProcessingAction = (action, params = {}) => {
    setProcessingActions(prev => [...prev, { action, params }]);
  };

  const removeProcessingAction = (index) => {
    setProcessingActions(prev => prev.filter((_, i) => i !== index));
  };

  const checkJobStatus = useCallback(async (jobId) => {
    if (!jobId || !token) return;
  
    try {
      const response = await fetch(`${API_URL}/images/jobs/${jobId}/status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
  
      if (!response.ok) {
        throw new Error('Failed to check job status');
      }
  
      const status = await response.json();
      setJobStatus(status);
  
      if (status.status === 'processing') {
        setTimeout(() => checkJobStatus(jobId), 3000);
      } else if (status.status === 'completed') {
        setCurrentStep('completed');
      } else if (status.status === 'failed') {
        setError(status.error || 'Processing failed');
      }
    } catch (err) {
      setError(err.message);
    }
  }, [token]);

  const startProcessing = async () => {
    if (processingActions.length === 0) {
      setError('Please add at least one processing action');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/images/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          job_id: analysisData.job_id,
          actions: processingActions
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start processing');
      }

      const data = await response.json();
      setCurrentStep('processing');
      checkJobStatus(data.job_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadProcessedDataset = async () => {
    try {
      const response = await fetch(`${API_URL}/images/jobs/${analysisData.job_id}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to download processed dataset');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      const disposition = response.headers.get('content-disposition');
      let downloadFilename = `processed_${analysisData.filename}`;
      if (disposition) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches?.[1]) {
          downloadFilename = matches[1].replace(/['"]/g, '');
        }
      }
      a.download = downloadFilename;

      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const resetProcess = () => {
    setCurrentStep('upload');
    setAnalysisData(null);
    setProcessingActions([]);
    setJobStatus(null);
    setError('');
  };

  const handleAddAction = () => {
    if (!selectedAction) return;

    const actionType = actionTypes.find(a => a.id === selectedAction);
    const params = {};

    actionType.params.forEach(param => {
      if (actionParams[param]) {
        if (param === 'width' || param === 'height' || param === 'radius') {
          params[param] = parseInt(actionParams[param]);
        } else if (param === 'factor') {
          params[param] = parseFloat(actionParams[param]);
        } else {
          params[param] = actionParams[param];
        }
      }
    });

    addProcessingAction(selectedAction, params);
    setSelectedAction('');
    setActionParams({});
    setShowAddForm(false);
  };

  const renderParamInput = (param) => {
    const value = actionParams[param] || '';
    
    switch (param) {
      case 'width':
      case 'height':
      case 'radius':
        return (
          <input
            type="number"
            placeholder={param === 'radius' ? '2' : '256'}
            value={value}
            onChange={(e) => setActionParams(prev => ({ ...prev, [param]: e.target.value }))}
            className="form-input"
            min="1"
          />
        );
      case 'factor':
        return (
          <input
            type="number"
            step="0.1"
            placeholder="1.0"
            value={value}
            onChange={(e) => setActionParams(prev => ({ ...prev, [param]: e.target.value }))}
            className="form-input"
            min="0.1"
            max="3.0"
          />
        );
      default:
        return (
          <input
            type="text"
            placeholder={param}
            value={value}
            onChange={(e) => setActionParams(prev => ({ ...prev, [param]: e.target.value }))}
            className="form-input"
          />
        );
    }
  };

  return (
    <div className="upload-page">
      <div className="upload-container">
        <div className="upload-header">
          <h1 className="main-title">Image Processing</h1>
          <p className="subtitle">
            Transform your image datasets with AI-powered processing capabilities
          </p>
        </div>

        {error && (
          <div className="error-message">
            <AlertTriangle size={20} />
            <span>{error}</span>
          </div>
        )}

        {/* Upload Step */}
        {currentStep === 'upload' && (
          <div className="processing-card">
            <div className="processing-header">
              <h2>Upload Image Dataset</h2>
              <p>Upload a ZIP file containing your images for processing</p>
            </div>
            
            <div
              {...getRootProps()}
              className={`dropzone ${isDragActive ? 'dragover' : ''}`}
            >
              <input {...getInputProps()} />
              <div className="dropzone-content">
                <Image size={48} className="dropzone-icon" />
                {isDragActive ? (
                  <div className="dropzone-text">
                    <h3>Drop your ZIP file here</h3>
                    <p>Release to start processing</p>
                  </div>
                ) : (
                  <div className="dropzone-text">
                    <h3>Drag & drop your ZIP file here</h3>
                    <p>or click to browse your files</p>
                    <small>Supported formats: PNG, JPG, JPEG inside a ZIP</small>
                  </div>
                )}
              </div>
            </div>
            
            {loading && (
              <div className="processing-status">
                <Loader className="spinner" size={20} />
                <span>Analyzing dataset...</span>
              </div>
            )}
          </div>
        )}

        {/* Configure Step */}
        {currentStep === 'configure' && analysisData && (
          <div className="processing-card">
            <div className="processing-header">
              <h2>Dataset Analysis</h2>
              <p>Configure your image processing actions</p>
            </div>

            <div className="analysis-summary">
              <div className="stats-grid">
                <div className="stat-item">
                  <div className="stat-value">{analysisData.image_count}</div>
                  <div className="stat-label">Total Images</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{Object.keys(analysisData.formats).length}</div>
                  <div className="stat-label">Formats</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{Object.keys(analysisData.modes).length}</div>
                  <div className="stat-label">Color Modes</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{Object.keys(analysisData.dimensions).length}</div>
                  <div className="stat-label">Dimensions</div>
                </div>
              </div>

              <div className="format-details">
                <div className="detail-section">
                  <h4>Image Formats</h4>
                  {Object.entries(analysisData.formats).map(([format, count]) => (
                    <div key={format} className="detail-item">
                      <span>{format}</span>
                      <span>{count}</span>
                    </div>
                  ))}
                </div>
                <div className="detail-section">
                  <h4>Color Modes</h4>
                  {Object.entries(analysisData.modes).map(([mode, count]) => (
                    <div key={mode} className="detail-item">
                      <span>{mode}</span>
                      <span>{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="actions-section">
              <h3>Processing Actions</h3>
              
              {processingActions.length > 0 && (
                <div className="current-actions">
                  <h4>Configured Actions:</h4>
                  {processingActions.map((action, index) => {
                    const actionType = actionTypes.find(a => a.id === action.action);
                    return (
                      <div key={index} className="action-item">
                        <div className="action-info">
                          <span className="action-name">{actionType?.name}</span>
                          {Object.keys(action.params).length > 0 && (
                            <span className="action-params">
                              ({Object.entries(action.params).map(([key, value]) => `${key}: ${value}`).join(', ')})
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => removeProcessingAction(index)}
                          className="remove-action-btn"
                        >
                          <X size={16} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {showAddForm ? (
                <div className="add-action-form">
                  <div className="form-group">
                    <label className="form-label">Action Type</label>
                    <select
                      value={selectedAction}
                      onChange={(e) => setSelectedAction(e.target.value)}
                      className="form-input"
                    >
                      <option value="">Select an action</option>
                      {actionTypes.map(action => (
                        <option key={action.id} value={action.id}>{action.name}</option>
                      ))}
                    </select>
                  </div>

                  {selectedAction && (
                    <div>
                      {actionTypes.find(a => a.id === selectedAction)?.params.map(param => (
                        <div key={param} className="form-group">
                          <label className="form-label">{param.charAt(0).toUpperCase() + param.slice(1)}</label>
                          {renderParamInput(param)}
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="form-actions">
                    <button
                      onClick={() => {
                        setShowAddForm(false);
                        setSelectedAction('');
                        setActionParams({});
                      }}
                      className="btn btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleAddAction}
                      disabled={!selectedAction}
                      className="btn btn-primary"
                    >
                      Add Action
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="add-action-btn"
                >
                  <Upload size={20} />
                  Add Processing Action
                </button>
              )}
            </div>

            <div className="form-actions">
              <button onClick={resetProcess} className="btn btn-secondary">
                Start Over
              </button>
              <button
                onClick={startProcessing}
                disabled={loading || processingActions.length === 0}
                className="btn btn-primary"
              >
                {loading ? 'Starting...' : 'Start Processing'}
              </button>
            </div>
          </div>
        )}

        {/* Processing Step */}
        {currentStep === 'processing' && (
          <div className="processing-card">
            <div className="processing-status-center">
              <Loader className="spinner large" size={48} />
              <h2>Processing Images</h2>
              <p>Please wait while we process your images...</p>
              {jobStatus && (
                <small>Status: {jobStatus.status}</small>
              )}
            </div>
          </div>
        )}

        {/* Completed Step */}
        {currentStep === 'completed' && (
          <div className="processing-card">
            <div className="processing-status-center">
              <CheckCircle size={48} className="success-icon" />
              <h2>Processing Complete!</h2>
              <p>Your processed images are ready for download.</p>
              
              <div className="form-actions">
                <button
                  onClick={downloadProcessedDataset}
                  className="btn btn-primary"
                >
                  <Download size={20} />
                  Download Processed Dataset
                </button>
                <button
                  onClick={resetProcess}
                  className="btn btn-secondary"
                >
                  Process Another Dataset
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageProcessing;
