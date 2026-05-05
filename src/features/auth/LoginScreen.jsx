import { useState } from 'react';
import { APP_NAME, APP_LOGO } from '../../shared/branding';

export default function LoginScreen({ onLogin, error, isAuthenticating, clearError }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    if (error) clearError();
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    if (error) clearError();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(email.trim().toLowerCase(), password);
  };

  const canSubmit = email.includes('@') && password.length > 0 && !isAuthenticating;

  return (
    <div className="app-container login-container">
      <div className="login-card glass-panel animate-fade-in">
        <div className="login-logo-wrapper yoko-avatar">
          <img src={APP_LOGO} alt={`${APP_NAME} Logo`} className="logo-image" />
        </div>
        <h1 className="login-title">{APP_NAME}</h1>
        <p className="login-subtitle">Automatización de procesos con IA</p>

        <form onSubmit={handleSubmit} className="login-form" noValidate>
          <label htmlFor="login-email" className="sr-only">Email</label>
          <input
            id="login-email"
            type="email"
            inputMode="email"
            autoComplete="username"
            value={email}
            onChange={handleEmailChange}
            placeholder="tu@correo.com"
            className="login-input"
            required
            autoFocus
          />

          <label htmlFor="login-password" className="sr-only">Contraseña</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={handlePasswordChange}
            placeholder="Contraseña"
            className="login-input"
            required
          />

          {error && <p className="login-error" role="alert">{error}</p>}

          <button
            type="submit"
            className="login-btn"
            disabled={!canSubmit}
          >
            {isAuthenticating ? (
              <span className="login-loading">
                <span /><span /><span />
              </span>
            ) : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  );
}
