import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const OAuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { fetchUserInfo, setToken } = useAuth();

  useEffect(() => {
    const handleCallback = async () => {
      // 1. Parse token from URL
      const params = new URLSearchParams(location.search);
      const token = params.get('token');
      const refresh = params.get('refresh');

      if (token && refresh) {
        // 2. Save tokens to localStorage
        localStorage.setItem('session_token', token);
        localStorage.setItem('refresh_token', refresh);
        
        // Update context token immediately
        if (setToken) {
          setToken(token);
        }

        // 3. Trigger context update (this will fetch /auth/me and set user)
        if (fetchUserInfo) {
          await fetchUserInfo(token);
        } else {
          // Fallback if fetchUserInfo isn't exported: just reload the page and let context handle it
          window.location.href = '/dashboard';
          return;
        }

        // 4. Navigate to dashboard
        navigate('/dashboard');
      } else {
        console.error("Missing OAuth tokens");
        navigate('/login');
      }
    };

    handleCallback();
  }, [location, navigate, fetchUserInfo]);

  return (
    <div className="auth-page">
      <div className="auth-container" style={{ textAlign: 'center', padding: '40px' }}>
        <Loader size={48} className="spinner" style={{ margin: '0 auto 20px', display: 'block' }} />
        <h2>Authenticating...</h2>
        <p>Please wait while we log you in securely.</p>
      </div>
    </div>
  );
};

export default OAuthCallback;
