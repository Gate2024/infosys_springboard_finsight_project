import { useState } from "react";
import "./style.css";

/**
 * FinSight sliding sign-in / sign-up card.
 * Usage: import AuthCard from "./AuthCard"; then render <AuthCard />
 * Requires style.css (same folder) and the Fraunces / Inter / IBM Plex Mono
 * fonts loaded, e.g. via a <link> tag in index.html:
 *
 * <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
 */
export default function AuthCard() {
  const [active, setActive] = useState(false); // false = sign in, true = sign up
  const [mobilePanel, setMobilePanel] = useState("signin");
  const [showSiPassword, setShowSiPassword] = useState(false);
  const [showSuPassword, setShowSuPassword] = useState(false);

  const handleSignIn = (e) => {
    e.preventDefault();
    // Hook up to your auth endpoint here.
    console.log("sign in submitted");
  };

  const handleSignUp = (e) => {
    e.preventDefault();
    // Hook up to your auth endpoint here.
    console.log("sign up submitted");
  };

  return (
    <div className={`container${active ? " active" : ""}`} id="authContainer">
      {/* SIGN UP PANEL */}
      <div
        className={`form-panel sign-up-panel${
          mobilePanel === "signup" ? " mobile-active" : ""
        }`}
      >
        <div className="panel-inner">
          <span className="eyebrow">Create account</span>
          <h2 className="panel-title">Get started</h2>

          <div className="social-row">
            <button type="button" className="social-btn" aria-label="Continue with Google">G</button>
            <button type="button" className="social-btn" aria-label="Continue with Apple">&#63743;</button>
            <button type="button" className="social-btn" aria-label="Continue with LinkedIn">in</button>
          </div>
          <p className="divider-text">or use your email to register</p>

          <form onSubmit={handleSignUp}>
            <div className="field">
              <label htmlFor="su-name">Full name</label>
              <div className="field-line">
                <input type="text" id="su-name" placeholder="Jordan Reyes" required autoComplete="name" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="su-email">Email</label>
              <div className="field-line">
                <input type="email" id="su-email" placeholder="you@domain.com" required autoComplete="email" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="su-password">Password</label>
              <div className="field-line">
                <input
                  type={showSuPassword ? "text" : "password"}
                  id="su-password"
                  placeholder="••••••••••"
                  required
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="toggle-visibility"
                  onClick={() => setShowSuPassword((v) => !v)}
                >
                  {showSuPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>
            <button type="submit" className="submit-btn" style={{ marginTop: 8 }}>
              Create account
            </button>
          </form>

          <p className="mobile-switch">
            Already have an account?{" "}
            <a onClick={() => setMobilePanel("signin")}>Sign in</a>
          </p>
        </div>
      </div>

      {/* SIGN IN PANEL */}
      <div
        className={`form-panel sign-in-panel${
          mobilePanel === "signin" ? " mobile-active" : ""
        }`}
      >
        <div className="panel-inner">
          <span className="eyebrow">Sign in</span>
          <h2 className="panel-title">Welcome back</h2>

          <div className="social-row">
            <button type="button" className="social-btn" aria-label="Continue with Google">G</button>
            <button type="button" className="social-btn" aria-label="Continue with Apple">&#63743;</button>
            <button type="button" className="social-btn" aria-label="Continue with LinkedIn">in</button>
          </div>
          <p className="divider-text">or use your FinSight account</p>

          <form onSubmit={handleSignIn}>
            <div className="field">
              <label htmlFor="si-email">Email</label>
              <div className="field-line">
                <input type="email" id="si-email" placeholder="you@domain.com" required autoComplete="email" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="si-password">Password</label>
              <div className="field-line">
                <input
                  type={showSiPassword ? "text" : "password"}
                  id="si-password"
                  placeholder="••••••••••"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="toggle-visibility"
                  onClick={() => setShowSiPassword((v) => !v)}
                >
                  {showSiPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>
            <div className="forgot-row">
              <a href="#">Forgot your password?</a>
            </div>
            <button type="submit" className="submit-btn">Sign in</button>
          </form>

          <p className="mobile-switch">
            New to FinSight?{" "}
            <a onClick={() => setMobilePanel("signup")}>Create an account</a>
          </p>
        </div>
      </div>

      {/* SLIDING OVERLAY */}
      <div className="overlay-container">
        <div className="overlay">
          <div className="overlay-panel overlay-left">
            <div className="wordmark" style={{ marginBottom: 26 }}>
              Fin<span>Sight</span>
            </div>
            <span className="overlay-eyebrow">Already tracking?</span>
            <h3 className="overlay-title">Welcome back</h3>
            <p className="overlay-copy">
              Sign in to see your accounts, budgets, and goals exactly where you left them.
            </p>
            <button type="button" className="ghost-btn" onClick={() => setActive(false)}>
              Sign in
            </button>
            <div className="mini-ticker" aria-hidden="true">
              <span style={{ height: 8 }}></span>
              <span style={{ height: 14 }}></span>
              <span style={{ height: 10 }}></span>
              <span style={{ height: 18 }}></span>
              <span style={{ height: 12 }}></span>
              <span style={{ height: 22 }}></span>
              <span style={{ height: 16 }}></span>
            </div>
          </div>

          <div className="overlay-panel overlay-right">
            <div className="wordmark" style={{ marginBottom: 26 }}>
              Fin<span>Sight</span>
            </div>
            <span className="overlay-eyebrow">First time here?</span>
            <h3 className="overlay-title">Hello, friend</h3>
            <p className="overlay-copy">
              Create an account and start seeing your income, spending, and goals in one place.
            </p>
            <button type="button" className="ghost-btn" onClick={() => setActive(true)}>
              Sign up
            </button>
            <div className="mini-ticker" aria-hidden="true">
              <span style={{ height: 10 }}></span>
              <span style={{ height: 16 }}></span>
              <span style={{ height: 12 }}></span>
              <span style={{ height: 20 }}></span>
              <span style={{ height: 14 }}></span>
              <span style={{ height: 24 }}></span>
              <span style={{ height: 18 }}></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
