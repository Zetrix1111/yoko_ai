import { useState } from 'react';
import { tenantConfig, appLogo } from '../../tenants';

export default function LoginScreen({ onLogin, error, isAuthenticating, clearError }) {
  const [dni, setDni] = useState('');

  const handleDniChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 8);
    setDni(value);
    if (error) clearError();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(dni);
  };

  return (
    <div className="app-container login-container">
      <div className="login-card glass-panel animate-fade-in">
        <div className="login-logo-wrapper yoko-avatar">
          <img src={appLogo} alt={`${tenantConfig.agent.name} Logo`} className="logo-image" />
        </div>
        <h1 className="login-title">{tenantConfig.agent.name}</h1>
        <p className="login-subtitle">Automatización de procesos con IA</p>
        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="text"
            inputMode="numeric"
            value={dni}
            onChange={handleDniChange}
            placeholder="Ingresa tu DNI"
            className="login-input"
            maxLength={8}
            autoFocus
          />
          {error && <p className="login-error">{error}</p>}
          <button
            type="submit"
            className="login-btn"
            disabled={isAuthenticating || dni.length !== 8}
          >
            {isAuthenticating ? (
              <span className="login-loading">
                <span /><span /><span />
              </span>
            ) : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
}
