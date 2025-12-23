import { useAuth } from '../hooks/useAuth';
import './Unauthorized.css';

export function Unauthorized() {
  const { user, logout } = useAuth();

  return (
    <div className="unauthorized-container">
      <div className="unauthorized-card">
        <div className="unauthorized-icon">🔒</div>
        <h1>Access Denied</h1>
        <p>You don't have permission to access this dashboard.</p>
        <p className="user-email">Logged in as: {user?.email}</p>
        <button onClick={logout} className="logout-button">
          Sign Out
        </button>
      </div>
    </div>
  );
}
