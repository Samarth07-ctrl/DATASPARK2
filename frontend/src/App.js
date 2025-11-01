// File: frontend/src/App.js

import React, { useState, useCallback, useMemo, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useNavigate, Navigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import {
  UploadCloud, FileText, BarChart2, Zap, Download, Loader, X, ChevronDown,
  AlertTriangle, Menu, Home, Upload, Brain, Shield, Cpu, Database,
  ArrowRight, CheckCircle, TrendingUp, Users, Star, User, LogOut, LogIn,
  UserPlus, Eye, EyeOff, Image
} from 'lucide-react';
import './App.css';

const API_URL = 'http://127.0.0.1:8000';

// Authentication Context
const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('session_token'));

  useEffect(() => {
    if (token) {
      fetchUserInfo();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUserInfo = async () => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        logout();
      }
    } catch (error) {
      console.error('Error fetching user info:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (credentials) => {
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(credentials)
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
        setToken(data.session_token);
        localStorage.setItem('session_token', data.session_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        return { success: true };
      } else {
        const error = await response.json();
        return { success: false, error: error.detail };
      }
    } catch (error) {
      return { success: false, error: 'Network error' };
    }
  };

  const register = async (userData) => {
    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(userData)
      });

      if (response.ok) {
        return { success: true };
      } else {
        const error = await response.json();
        return { success: false, error: error.detail };
      }
    } catch (error) {
      return { success: false, error: 'Network error' };
    }
  };

  const logout = async () => {
    try {
      if (token) {
        await fetch(`${API_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem('session_token');
      localStorage.removeItem('refresh_token');
    }
  };

  const value = {
    user,
    token,
    login,
    register,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-animation">
          <div className="loading-spinner"></div>
          <div className="loading-dots">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        </div>
        <h2 className="loading-title">Loading...</h2>
        <p className="loading-subtitle">Please wait while we verify your session</p>
      </div>
    );
  }

  return user ? children : <Navigate to="/login" />;
};

// Navbar Component
const Navbar = () => {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/" className="nav-logo">
          <Brain className="nav-logo-icon" size={28} />
          DataSpark
        </Link>

        <div className="nav-menu">
          {user ? (
            <>
              <Link to="/dashboard" className="nav-link">
                <Home size={18} />
                Dashboard
              </Link>
              <Link to="/upload" className="nav-link">
                <Upload size={18} />
                Upload
              </Link>
              <Link to="/image-processing" className="nav-link">
                <Image size={18} />
                Image Processing
              </Link>
              <div className="nav-user-menu">
                <div className="nav-user-info">
                  <User size={18} />
                  {user.username}
                </div>
                <button onClick={logout} className="nav-logout-btn">
                  <LogOut size={16} />
                  Logout
                </button>
              </div>
            </>
          ) : (
            <>
              <Link to="/login" className="nav-link">
                <LogIn size={18} />
                Login
              </Link>
              <Link to="/register" className="nav-register">
                <UserPlus size={18} />
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

// Home Page Component
const HomePage = () => {
  const { user } = useAuth();

  const features = [
    {
      icon: <Brain size={32} />,
      title: "AI-Powered Analysis",
      description: "Advanced machine learning algorithms automatically detect data quality issues and recommend optimal cleaning strategies."
    },
    {
      icon: <Zap size={32} />,
      title: "Lightning Fast Processing",
      description: "Process datasets of any size in seconds, not hours. Our optimized engine handles millions of rows effortlessly."
    },
    {
      icon: <Shield size={32} />,
      title: "Enterprise Security",
      description: "Bank-grade encryption and privacy protection ensure your sensitive data remains secure throughout the cleaning process."
    },
    {
      icon: <Cpu size={32} />,
      title: "Smart Automation",
      description: "Intelligent automation reduces manual work by 90%, allowing you to focus on insights rather than data preparation."
    },
    {
      icon: <Database size={32} />,
      title: "Format Flexibility",
      description: "Support for CSV, Excel, JSON, and more. Import from databases, APIs, or file uploads with seamless compatibility."
    },
    {
      icon: <BarChart2 size={32} />,
      title: "Quality Insights",
      description: "Comprehensive data quality reports with actionable insights and visualizations to understand your data better."
    }
  ];

  return (
    <div className="home-page">
      <section className="hero-section">
        <div className="app-container">
          <div className="hero-container">
            <div className="hero-content">
              <div className="hero-badge">
                <Star size={16} />
                Trusted by 10,000+ Data Professionals
              </div>
              
              <h1 className="hero-title">
                Clean Your Data with{' '}
                <span className="hero-title-gradient">AI Intelligence</span>
              </h1>
              
              <p className="hero-description">
                DataSpark revolutionizes data cleaning with intelligent automation. Upload your messy datasets and watch our AI transform them into analysis-ready, high-quality data in minutes, not hours.
              </p>
              
              <div className="hero-buttons">
                <Link to={user ? "/dashboard" : "/register"} className="hero-btn-primary">
                  {user ? "Go to Dashboard" : "Start Free Trial"}
                  <ArrowRight size={20} />
                </Link>
                <Link to="/upload" className="hero-btn-secondary">
                  <Upload size={20} />
                  Try Demo
                </Link>
              </div>
              
              <div className="hero-stats">
                <div className="hero-stat">
                  <div className="hero-stat-number">10M+</div>
                  <div className="hero-stat-label">Rows Cleaned</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">99.9%</div>
                  <div className="hero-stat-label">Accuracy Rate</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">5 Min</div>
                  <div className="hero-stat-label">Avg Process Time</div>
                </div>
                <div className="hero-stat">
                  <div className="hero-stat-number">24/7</div>
                  <div className="hero-stat-label">Support</div>
                </div>
              </div>
            </div>
            
            <div className="hero-visual">
              <div className="floating-dashboard">
                <div className="dashboard-header-preview">
                  <div className="preview-dots">
                    <div className="dot red"></div>
                    <div className="dot yellow"></div>
                    <div className="dot green"></div>
                  </div>
                  <div className="preview-title">Data Cleaning Dashboard</div>
                </div>
                <div className="dashboard-content-preview">
                  <div className="preview-chart">
                    <div className="chart-bars">
                      <div className="bar" style={{height: '60%'}}></div>
                      <div className="bar" style={{height: '80%'}}></div>
                      <div className="bar" style={{height: '100%'}}></div>
                      <div className="bar" style={{height: '45%'}}></div>
                      <div className="bar" style={{height: '75%'}}></div>
                    </div>
                  </div>
                  <div className="preview-metrics">
                    <div className="metric">
                      <div className="metric-value">95%</div>
                      <div className="metric-label">Clean Rate</div>
                    </div>
                    <div className="metric">
                      <div className="metric-value">1.2M</div>
                      <div className="metric-label">Rows</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="features-section">
        <div className="container">
          <div className="section-header">
            <h2 className="section-title">Why Choose DataSpark?</h2>
            <p className="section-subtitle">
              Cutting-edge technology meets intuitive design to deliver unparalleled data cleaning capabilities
            </p>
          </div>
          
          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card">
                <div className="feature-icon">
                  {feature.icon}
                </div>
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-description">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-section">
        <div className="container">
          <div className="cta-content">
            <h2 className="cta-title">Ready to Transform Your Data?</h2>
            <p className="cta-description">
              Join thousands of data professionals who trust DataSpark for their critical data cleaning workflows.
            </p>
            <Link to={user ? "/dashboard" : "/register"} className="cta-button">
              <ArrowRight size={20} />
              {user ? "Go to Dashboard" : "Start Your Free Trial"}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

// Login Page Component
const LoginPage = () => {
  const [formData, setFormData] = useState({
    username_or_email: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const result = await login(formData);
    
    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }
    
    setLoading(false);
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <Brain className="auth-logo" size={48} />
          <h1 className="auth-title">Welcome Back</h1>
          <p className="auth-subtitle">Sign in to your DataSpark account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label">Email or Username</label>
            <input
              type="text"
              name="username_or_email"
              value={formData.username_or_email}
              onChange={handleChange}
              className="form-input"
              placeholder="Enter your email or username"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="form-input"
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="password-toggle"
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="auth-error">
              <AlertTriangle size={20} />
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="auth-submit-btn">
            {loading ? <Loader size={20} className="spinner" /> : <LogIn size={20} />}
            {loading ? 'Signing In...' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          Don't have an account?{' '}
          <Link to="/register" className="auth-link">Sign up here</Link>
        </div>
      </div>
    </div>
  );
};

// Register Page Component
const RegisterPage = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { register } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const result = await register(formData);
    
    if (result.success) {
      setSuccess(true);
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    } else {
      setError(result.error);
    }
    
    setLoading(false);
  };

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-container">
          <div className="success-message">
            <CheckCircle className="success-icon" size={64} />
            <h2>Registration Successful!</h2>
            <p>Your account has been created. Redirecting to login...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-header">
          <Brain className="auth-logo" size={48} />
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Join DataSpark and start cleaning your data</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">First Name</label>
              <input
                type="text"
                name="first_name"
                value={formData.first_name}
                onChange={handleChange}
                className="form-input"
                placeholder="John"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Last Name</label>
              <input
                type="text"
                name="last_name"
                value={formData.last_name}
                onChange={handleChange}
                className="form-input"
                placeholder="Doe"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className="form-input"
              placeholder="johndoe"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="form-input"
              placeholder="john@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="form-input"
                placeholder="Create a secure password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="password-toggle"
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="auth-error">
              <AlertTriangle size={20} />
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="auth-submit-btn">
            {loading ? <Loader size={20} className="spinner" /> : <UserPlus size={20} />}
            {loading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login" className="auth-link">Sign in here</Link>
        </div>
      </div>
    </div>
  );
};

// Dashboard Component
const Dashboard = () => {
  const { user } = useAuth();
  const [uploadHistory, setUploadHistory] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const token = localStorage.getItem('session_token');
      
      // Fetch upload history
      const historyResponse = await fetch(`${API_URL}/history`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        setUploadHistory(historyData.uploads || []);
      }

      // Fetch analytics
      const analyticsResponse = await fetch(`${API_URL}/analytics`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (analyticsResponse.ok) {
        const analyticsData = await analyticsResponse.json();
        setAnalytics(analyticsData);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-animation">
          <div className="loading-spinner"></div>
          <div className="loading-dots">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        </div>
        <h2 className="loading-title">Fetching your data insights...</h2>
        <p className="loading-subtitle">Loading dashboard</p>
      </div>
    );
  }

  const StatCard = ({ icon, title, value }) => (
    <div className="stat-card">
      <div className="stat-icon">
        {icon}
      </div>
      <div>
        <div className="stat-title">{title}</div>
        <div className="stat-value">{value}</div>
      </div>
    </div>
  );

  return (
    <div className="dashboard-page">
      <div className="app-container">
        <div className="dashboard-header">
          <div>
            <h1 className="dashboard-title">Welcome back, {user.first_name || user.username}!</h1>
            <p className="dashboard-subtitle">Here's your data cleaning activity</p>
          </div>
          <Link to="/upload" className="dashboard-upload-btn">
            <Upload size={20} />
            Upload New File
          </Link>
        </div>

        <div className="stats-grid">
          <StatCard
            icon={<FileText size={24} />}
            title="Total Uploads"
            value={uploadHistory.length}
          />
          <StatCard
            icon={<TrendingUp size={24} />}
            title="Success Rate"
            value={`${analytics.success_rate || 0}%`}
          />
          <StatCard
            icon={<Zap size={24} />}
            title="Processing Jobs"
            value={analytics.total_processing_jobs || 0}
          />
          <StatCard
            icon={<Users size={24} />}
            title="Data Quality"
            value="Excellent"
          />
        </div>

        <div className="dashboard-content">
          <div className="upload-history">
            <h2>Recent Uploads</h2>
            {uploadHistory.length > 0 ? (
              <div className="history-list">
                {uploadHistory.slice(0, 5).map((upload) => (
                  <div key={upload.id} className="history-item">
                    <div className="history-item-info">
                      <h3>{upload.filename}</h3>
                      <p>{upload.row_count} rows, {upload.column_count} columns</p>
                      <div className="history-item-date">
                        {new Date(upload.upload_timestamp).toLocaleDateString()}
                      </div>
                    </div>
                    <div className={`history-item-status ${upload.status}`}>
                      {upload.status}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">
                <FileText size={48} />
                <h3>No uploads yet</h3>
                <p>Start by uploading your first CSV file to begin data cleaning!</p>
                <Link to="/upload" className="dashboard-upload-btn">
                  <Upload size={20} />
                  Upload File
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Upload Page Component
const UploadPage = () => {
  const [analysisData, setAnalysisData] = useState(null);
  const [processingActions, setProcessingActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // File upload handling
  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = localStorage.getItem('session_token');
      const response = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to analyze file');
      }

      const data = await response.json();
      setAnalysisData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv']
    },
    multiple: false
  });

  const addAction = (column, action) => {
    const newAction = { column, action };
    setProcessingActions(prev => [...prev, newAction]);
  };

  const removeAction = (index) => {
    setProcessingActions(prev => prev.filter((_, i) => i !== index));
  };

  const processData = async () => {
    if (processingActions.length === 0) {
      setError('Please select at least one action to perform');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('session_token');
      const response = await fetch(`${API_URL}/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          data: [], // This would be populated with actual data
          actions: processingActions,
          file_id: analysisData.file_id
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to process data');
      }

      // Handle file download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `cleaned_${analysisData.filename}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
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
        <div className="upload-header">
          <h1 className="main-title">Upload & Clean Your Data</h1>
          <p className="subtitle">
            Transform your raw data into clean, analysis-ready datasets with AI-powered intelligence.
          </p>
        </div>

        {!analysisData ? (
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
                {loading ? (
                  <div className="upload-status">
                    <Loader className="spinner" size={24} />
                    <h3 className="dropzone-text-main">Analyzing your data...</h3>
                    <p className="dropzone-text-sub">Our AI is processing your dataset</p>
                  </div>
                ) : isDragActive ? (
                  <div className="dropzone-text">
                    <h3 className="dropzone-text-main">Drop your file here</h3>
                    <p className="dropzone-text-sub">Release to start processing</p>
                  </div>
                ) : (
                  <div className="dropzone-text">
                    <h3 className="dropzone-text-main">Drag &amp; drop your CSV file here</h3>
                    <p className="dropzone-text-sub">or click to browse your files</p>
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
        ) : (
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
                  <h3>Column Analysis</h3>
                  <button onClick={resetUpload} className="reset-button">
                    <X size={16} />
                    Reset
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
                          </td>
                          <td>
                            <span className={`missing-percentage ${col.missing_percentage > 50 ? 'high' : col.missing_percentage > 20 ? 'medium' : 'low'}`}>
                              {col.missing_percentage}%
                            </span>
                          </td>
                          <td>
                            {col.suggestions.length > 0 ? (
                              <select
                                onChange={(e) => e.target.value && addAction(col.column_name, e.target.value)}
                                defaultValue=""
                              >
                                <option value="">Select action...</option>
                                {col.suggestions.map((suggestion, i) => (
                                  <option key={i} value={suggestion}>
                                    {suggestion.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
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

              {processingActions.length > 0 && (
                <div className="processing-actions-panel">
                  <div className="panel-header">
                    <h3>Selected Actions ({processingActions.length})</h3>
                  </div>
                  <div className="actions-list">
                    {processingActions.map((action, index) => (
                      <div key={index} className="action-item">
                        <span>
                          <strong>{action.column}</strong>: {action.action.replace(/_/g, ' ')}
                        </span>
                        <button onClick={() => removeAction(index)} className="remove-action">
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
                        Process Data
                      </>
                    )}
                  </button>
                </div>
              )}

              {processingActions.length === 0 && (
                <div className="no-actions">
                  <Zap size={48} />
                  <h3>Select actions to get started.</h3>
                  <p>Choose cleaning actions from the dropdown menus above to prepare your data.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="error-container">
            <AlertTriangle size={24} />
            <p>{error}</p>
          </div>
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
            <h2 className="loading-title">Our AI is examining your dataset for quality issues</h2>
            <p className="loading-subtitle">This usually takes a few seconds</p>
          </div>
        )}

        {error && (
          <div className="error-container">
            <AlertTriangle size={48} />
            <div>
              <h3>**Analysis Error:** {error}</h3>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Image Processing Component
const ImageProcessing = () => {
  const { user, token } = useAuth();
  const [currentStep, setCurrentStep] = useState('upload');
  const [analysisData, setAnalysisData] = useState(null);
  const [processingActions, setProcessingActions] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
        throw new Error('Failed to analyze image dataset');
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

      setCurrentStep('processing');
      checkJobStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const checkJobStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/images/jobs/${analysisData.job_id}/status`, {
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
        setTimeout(checkJobStatus, 2000);
      } else if (status.status === 'completed') {
        setCurrentStep('completed');
      } else if (status.status === 'failed') {
        setError(status.error || 'Processing failed');
      }
    } catch (err) {
      setError(err.message);
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
      a.download = `processed_${analysisData.filename}`;
      document.body.appendChild(a);
      a.click();
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

  const actionTypes = [
    { id: 'resize', name: 'Resize', params: ['width', 'height'] },
    { id: 'grayscale', name: 'Convert to Grayscale', params: [] },
    { id: 'blur', name: 'Blur', params: ['radius'] },
    { id: 'sharpen', name: 'Sharpen', params: [] },
    { id: 'brightness', name: 'Adjust Brightness', params: ['factor'] },
    { id: 'contrast', name: 'Adjust Contrast', params: ['factor'] },
  ];

  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedAction, setSelectedAction] = useState('');
  const [actionParams, setActionParams] = useState({});

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
            placeholder={param === 'radius' ? '2' : '800'}
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
                    <small>Supported formats: PNG, JPG, JPEG</small>
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

            {/* Analysis Summary */}
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

            {/* Processing Actions */}
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

// Main App Component
const App = () => {
  return (
    <AuthProvider>
      <Router>
        <div className="app">
          <Navbar />
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/upload" element={<ProtectedRoute><UploadPage /></ProtectedRoute>} />
            <Route path="/image-processing" element={<ProtectedRoute><ImageProcessing /></ProtectedRoute>} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
};

export default App;
