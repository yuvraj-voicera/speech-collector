/**
 * Optional extra proxies. The app uses package.json "proxy" for the FastAPI backend.
 * Appwrite proxy removed — auth and API are served from the same FastAPI app.
 */
module.exports = function setupProxy(_app) {
  /* no-op — CRA proxy field targets FastAPI */
};
