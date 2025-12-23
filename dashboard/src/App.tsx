import { useState, useEffect } from 'react';
import { ref, onValue, off } from 'firebase/database';
import { database } from './firebase/config';
import { GlucoseData } from './types';
import { useAuth } from './hooks/useAuth';
import { Login } from './components/Login';
import './App.css';

function Dashboard() {
    const [glucoseData, setGlucoseData] = useState<GlucoseData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [userId, setUserId] = useState<string>('78347'); // Default user ID
    const { logout } = useAuth();

    useEffect(() => {
        const dataRef = ref(database, `users/${userId}/latest`);

        setLoading(true);
        setError(null);

        const unsubscribe = onValue(
            dataRef,
            (snapshot) => {
                const data = snapshot.val();
                if (data) {
                    setGlucoseData(data);
                    setLoading(false);
                } else {
                    setError('No data found for this user');
                    setLoading(false);
                }
            },
            (err) => {
                console.error('Error fetching data:', err);
                setError('Failed to fetch data from Firebase');
                setLoading(false);
            }
        );

        return () => {
            off(dataRef, 'value', unsubscribe);
        };
    }, [userId]);

    const formatDate = (timestamp: number | string) => {
        const date = typeof timestamp === 'string'
            ? new Date(timestamp)
            : new Date(timestamp * 1000);
        return date.toLocaleString();
    };

    const getGlucoseStatus = (glucose: number) => {
        if (glucose < 3.9) return { status: 'Low', color: '#ff6b6b' };
        if (glucose > 10.0) return { status: 'High', color: '#ffa500' };
        return { status: 'Normal', color: '#51cf66' };
    };

    return (
        <div className="app">
            <header className="app-header">
                <h1>Gluco Watch Dashboard</h1>
                <div className="header-right">
                    <div className="user-selector">
                        <label htmlFor="userId">User ID: </label>
                        <input
                            id="userId"
                            type="text"
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            placeholder="Enter user ID"
                        />
                    </div>
                    <button onClick={logout} className="logout-btn">
                        Sign Out
                    </button>
                </div>
            </header>

            <main className="app-main">
                {loading && <div className="loading">Loading...</div>}

                {error && (
                    <div className="error">
                        <p>{error}</p>
                    </div>
                )}

                {glucoseData && !loading && (
                    <div className="glucose-card">
                        <div className="glucose-value-container">
                            <div
                                className="glucose-value"
                                style={{
                                    color: getGlucoseStatus(glucoseData.main.glucose).color
                                }}
                            >
                                {glucoseData.main.glucose.toFixed(1)}
                            </div>
                            <div className="glucose-unit">mmol/L</div>
                        </div>

                        <div className="glucose-status">
                            <span
                                className="status-badge"
                                style={{
                                    backgroundColor: getGlucoseStatus(glucoseData.main.glucose).color
                                }}
                            >
                                {getGlucoseStatus(glucoseData.main.glucose).status}
                            </span>
                        </div>

                        <div className="glucose-details">
                            <div className="detail-item">
                                <span className="detail-label">Timestamp:</span>
                                <span className="detail-value">
                                    {formatDate(glucoseData.main.timestamp)}
                                </span>
                            </div>
                            <div className="detail-item">
                                <span className="detail-label">Time:</span>
                                <span className="detail-value">{glucoseData.main.time}</span>
                            </div>
                            <div className="detail-item">
                                <span className="detail-label">Fetched At:</span>
                                <span className="detail-value">
                                    {formatDate(glucoseData.fetched_at)}
                                </span>
                            </div>
                            <div className="detail-item">
                                <span className="detail-label">Fetched At (Unix):</span>
                                <span className="detail-value">
                                    {new Date(glucoseData.fetched_at_unix * 1000).toLocaleString()}
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

function App() {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="app">
                <div className="loading">Loading...</div>
            </div>
        );
    }

    if (!user) {
        return <Login />;
    }

    return <Dashboard />;
}

export default App;
