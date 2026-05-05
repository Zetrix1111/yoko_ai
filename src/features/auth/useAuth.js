import { useState, useEffect, useCallback } from 'react';
import { postJson, API } from '../../shared/api';

const STORAGE_KEY = 'yoko_auth';
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 días, matching JWT exp del backend

function now() { return Date.now(); }

/**
 * Forma del estado `user` que devuelve este hook (y que consumen App, useChat,
 * MessageBubble, etc.):
 *
 *   {
 *     token:     '<JWT>',
 *     id:        '<airtable record_id>',
 *     email:     'foo@bar.com',
 *     nombre:    'Foo',
 *     dni?:      '12345678',     // si el email matchea fila en Empleados
 *     cargo?:    'Residente',    // idem
 *     celular?:  '999...',       // idem
 *     empresa:   { id, razon_social, modulos: [...] },
 *     expiresAt: <unix ms>,
 *   }
 *
 * `dni`, `cargo`, `celular` se aplanan al top level (no van bajo user.user)
 * para que useChat.js siga mandando user.dni / user.nombre / user.cargo
 * al backend del chat sin cambios. La separación entre identidad personal
 * (top level) y empresa (sub-objeto) deja claro qué es del usuario y qué
 * del tenant.
 */

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Sesión vencida o sin token → ignorar y limpiar.
    if (!parsed?.token || !parsed?.expiresAt || parsed.expiresAt < now()) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function persist(authState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(authState));
}

/**
 * Aplana el response del backend (`{token, user, empresa}`) en la forma que
 * usan los consumidores del frontend. `dni` / `cargo` / `celular` solo
 * aparecen si el login los devolvió (existen en Empleados).
 */
function buildAuthState({ token, user, empresa }) {
  const state = {
    token,
    id:        user?.id || '',
    email:     user?.email || '',
    nombre:    user?.nombre || '',
    empresa: {
      id:           empresa?.id || '',
      razon_social: empresa?.razon_social || '',
      modulos:      Array.isArray(empresa?.modulos) ? empresa.modulos : [],
    },
    expiresAt: now() + SESSION_TTL_MS,
  };
  if (user?.dni)     state.dni     = user.dni;
  if (user?.cargo)   state.cargo   = user.cargo;
  if (user?.celular) state.celular = user.celular;
  return state;
}

export function useAuth() {
  const [user, setUser] = useState(() => loadStoredAuth());
  const [error, setError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  // Auto-logout cuando algún apiFetch reciba 401. apiFetch dispara
  // 'yoko:auth-expired'. Lo escuchamos a nivel global.
  useEffect(() => {
    const handleExpired = () => logout();
    window.addEventListener('yoko:auth-expired', handleExpired);
    return () => window.removeEventListener('yoko:auth-expired', handleExpired);
  }, [logout]);

  const login = useCallback(async (email, password) => {
    const cleanEmail = (email || '').trim().toLowerCase();
    if (!cleanEmail.includes('@')) {
      setError('Email inválido.');
      return false;
    }
    if (!password) {
      setError('Ingresa tu contraseña.');
      return false;
    }

    setIsAuthenticating(true);
    setError('');
    try {
      const data = await postJson(API.LOGIN, { email: cleanEmail, password });

      if (!data?.token || !data?.user || !data?.empresa) {
        setError('Respuesta inesperada del servidor.');
        return false;
      }

      const authState = buildAuthState(data);
      persist(authState);
      setUser(authState);
      return true;
    } catch (err) {
      // postJson tira `Error('HTTP <code>')` para no-OK responses. Para no
      // distinguir entre "credenciales malas" y "servidor caído" desde el
      // mensaje al user, usamos genéricos y solo para 5xx mostramos un texto
      // distinto. Mejorable cuando el backend devuelva el JSON de error.
      const msg = String(err?.message || '');
      if (msg.includes('HTTP 401') || msg.includes('HTTP 403')) {
        setError('Email o contraseña incorrectos.');
      } else if (msg.includes('HTTP 5')) {
        setError('Servidor no disponible. Intenta de nuevo en un momento.');
      } else {
        setError('Error al iniciar sesión. Intenta de nuevo.');
      }
      return false;
    } finally {
      setIsAuthenticating(false);
    }
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return { user, error, isAuthenticating, login, logout, clearError };
}
