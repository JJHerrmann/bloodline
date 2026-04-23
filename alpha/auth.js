(() => {
  const STORAGE_KEY = "bloodline-alpha-session";
  const SESSION_HOURS = 12;

  const config = {
    // SHA-256 for the alpha-reader passphrase.
    passwordHash: "7e37e57da000ea1f196cb7d167fe571efad170316045029b71cf5bf4d336d4ed",
    sessionHours: SESSION_HOURS,
    storageKey: STORAGE_KEY,
  };

  async function sha256(value) {
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  function readSession() {
    try {
      const raw = localStorage.getItem(config.storageKey);
      if (!raw) return null;
      const session = JSON.parse(raw);
      if (!session || typeof session !== "object") return null;
      if (!session.expiresAt || Date.now() > session.expiresAt) {
        localStorage.removeItem(config.storageKey);
        return null;
      }
      if (session.passwordHash !== config.passwordHash) {
        localStorage.removeItem(config.storageKey);
        return null;
      }
      return session;
    } catch (error) {
      localStorage.removeItem(config.storageKey);
      return null;
    }
  }

  function isAuthenticated() {
    return Boolean(readSession());
  }

  function setSession() {
    const expiresAt = Date.now() + config.sessionHours * 60 * 60 * 1000;
    localStorage.setItem(
      config.storageKey,
      JSON.stringify({
        passwordHash: config.passwordHash,
        expiresAt,
      })
    );
  }

  function signOut() {
    localStorage.removeItem(config.storageKey);
  }

  async function signIn(password) {
    const submittedHash = await sha256(password.trim());
    const ok = submittedHash === config.passwordHash;
    if (ok) setSession();
    return ok;
  }

  function requireAuth({ redirectTo }) {
    if (isAuthenticated()) return true;
    const next = encodeURIComponent(window.location.pathname);
    window.location.replace(`${redirectTo}?next=${next}`);
    return false;
  }

  window.BloodlineAlphaAuth = {
    config,
    isAuthenticated,
    signIn,
    signOut,
    requireAuth,
  };
})();
