import { useState, useEffect, useCallback } from 'react';
import { postJson, API } from '../../shared/api';

const STORAGE_KEY = 'yoko_auth';
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 días

function now() { return Date.now(); }

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Sesión vencida → ignorar y limpiar
    if (!parsed?.expiresAt || parsed.expiresAt < now()) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function saveAuth(user) {
  // Refrescamos `expiresAt` a now + 30 días en cada guardado,
  // de modo que cada vez que el user abra la app, extiende la sesión.
  const payload = { ...user, expiresAt: now() + SESSION_TTL_MS };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  return payload;
}

export function useAuth() {
  const [user, setUser] = useState(() => loadStoredAuth());
  const [error, setError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  // Refresca TTL cada vez que la app se monta con un user activo.
  useEffect(() => {
    if (user) {
      const refreshed = saveAuth(user);
      // Solo actualiza el estado si cambió (evita loop infinito)
      if (refreshed.expiresAt !== user.expiresAt) {
        setUser(refreshed);
      }
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mantén localStorage sincronizado con cambios manuales de user.
  useEffect(() => {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
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
        const fresh = saveAuth({
          dni,
          nombre: data.nombre || '',
          cargo: data.cargo || '',
          record_id: data.record_id || '',
          sessionId: `${dni}-${now()}`,
        });
        setUser(fresh);
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
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return { user, error, isAuthenticating, login, logout, clearError };
}
