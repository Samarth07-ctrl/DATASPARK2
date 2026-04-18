// ==============================================================================
// File: frontend/src/App.js
// Purpose: Thin router shell — ONLY defines routes and wraps with providers.
//
// WHY THIS MATTERS:
// The original App.js was 1939 lines containing ALL components. This version
// is ~45 lines. Each component now lives in its own file, making it:
//   1. Searchable — find any component by filename
//   2. Testable — import and unit test individual components
//   3. Code-splittable — React.lazy() can now be used per-route
//   4. Team-friendly — no merge conflicts when 2 devs edit different pages
// ==============================================================================

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

// --- Context ---
import { AuthProvider } from './context/AuthContext';

// --- Components ---
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';

// --- Pages ---
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './pages/Dashboard';
import UploadPage from './pages/UploadPage';
import AnalysisDashboard from './pages/AnalysisDashboard';
import ImageProcessing from './pages/ImageProcessing';
import OAuthCallback from './pages/OAuthCallback'; // NEW

// --- Styles ---
import './App.css';

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
            <Route path="/oauth-callback" element={<OAuthCallback />} /> {/* NEW */}
            <Route path="/dashboard" element={
              <ProtectedRoute><Dashboard /></ProtectedRoute>
            } />
            <Route path="/upload" element={
              <ProtectedRoute><UploadPage /></ProtectedRoute>
            } />
            <Route path="/image-processing" element={
              <ProtectedRoute><ImageProcessing /></ProtectedRoute>
            } />
            <Route path="/dashboard/analysis" element={
              <ProtectedRoute><AnalysisDashboard /></ProtectedRoute>
            } />
            <Route path="/dashboard/analysis/:jobId" element={
              <ProtectedRoute><AnalysisDashboard /></ProtectedRoute>
            } />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
};

export default App;