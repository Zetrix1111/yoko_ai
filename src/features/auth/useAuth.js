import { useState, useEffect, useCallback } from 'react';
import { postJson, API } from '../../shared/api';

const STORAGE_KEY = 'yoko_auth';

function loadStoredAuth() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState(() => loadStoredAuth());
  const [error, setError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  useEffect(() => {
    if (user) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, [user]);

  const login = useCallback(async (dni) => {
    if (dni.length !== 8) {
      setError('Ingresa tu DNI de 8 dígitos.');
      return false;
    }
    setIsAuthenticating(true);
    setError('');
    try {
      const data = await postJson(API.LOGIN, { dni });
      if (data.authorized) {
        setUser({
          dni,
          nombre: data.nombre || '',
          cargo: data.cargo || '',
          sessionId: `${dni}-${Date.now()}`,
        });
        return true;
      }
      setError('DNI no autorizado. Contacta al administrador.');
      return false;
    } catch {
      setError('Error al verificar. Intenta de nuevo.');
      return false;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return { user, error, isAuthenticating, login, logout, clearError };
}
