// ==============================================================================
// File: frontend/src/context/AuthContext.js
// Purpose: React Context + Provider for authentication state management.
// Why: Auth state (user, token, login/register/logout) is consumed by almost
//      every component. A dedicated context module keeps this cross-cutting
//      concern isolated and testable.
// ==============================================================================

import { useState, useCallback, useMemo, useEffect, createContext, useContext } from 'react';
import { API_URL } from '../config/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('session_token'));

  const logout = useCallback(async (isTokenInvalid = false) => {
    try {
      const currentToken = localStorage.getItem('session_token');
      if (currentToken && !isTokenInvalid) {
        await fetch(`${API_URL}/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${currentToken}`
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
  }, []);

  const fetchUserInfo = useCallback(async (authToken) => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        await logout(true);
      }
    } catch (error) {
      console.error('Error fetching user info:', error);
      await logout(true);
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    if (token) {
      fetchUserInfo(token);
    } else {
      setLoading(false);
    }
  }, [token, fetchUserInfo]);

  const login = useCallback(async (credentials) => {
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
        return { success: false, error: error.detail || 'Invalid credentials' };
      }
    } catch (error) {
      return { success: false, error: 'Network error. Please try again.' };
    }
  }, []);

  const register = useCallback(async (userData) => {
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
        return { success: false, error: error.detail || 'Registration failed.' };
      }
    } catch (error) {
      return { success: false, error: 'Network error. Please try again.' };
    }
  }, []);

  const value = useMemo(() => ({
    user,
    token,
    setToken,
    login,
    register,
    logout,
    loading,
    fetchUserInfo
  }), [user, token, loading, login, register, logout, fetchUserInfo]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
