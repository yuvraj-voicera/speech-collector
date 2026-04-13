/** API origin (empty = same origin; dev uses CRA proxy to :8000). */
export const API_BASE = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');
