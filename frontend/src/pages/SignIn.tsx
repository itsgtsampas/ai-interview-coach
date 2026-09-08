import { useState } from "react";

import { ErrorBox } from "../components/bits";
import { useAuth } from "../lib/auth";

export function SignIn() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("demo@example.com");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "in") await signIn(email, password);
      else await signUp(email, name, password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="centre">
      <div className="panel">
        <div className="brand__mark" style={{ fontSize: "1.5rem" }}>
          Interview Coach
        </div>
        <p className="prose mt" style={{ marginTop: "0.7rem" }}>
          Upload your CV and the job description. Get an honest, evidenced read on where
          you stand — every claim shows the sentence it came from.
        </p>

        <form onSubmit={submit} className="mt">
          <div className="field">
            <label className="label" htmlFor="email">Email</label>
            <input
              id="email" className="input" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} autoComplete="email"
            />
          </div>

          {mode === "up" ? (
            <div className="field">
              <label className="label" htmlFor="name">Full name</label>
              <input
                id="name" className="input" required value={name}
                onChange={(e) => setName(e.target.value)} autoComplete="name"
              />
            </div>
          ) : null}

          <div className="field">
            <label className="label" htmlFor="password">Password</label>
            <input
              id="password" className="input" type="password" required minLength={8}
              value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "in" ? "current-password" : "new-password"}
            />
            {mode === "up" ? (
              <span className="hint">At least 8 characters, with letters and numbers.</span>
            ) : null}
          </div>

          <ErrorBox error={error} />

          <button className="btn" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Working…" : mode === "in" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="hint mt">
          {mode === "in" ? "No account yet? " : "Already have an account? "}
          <button
            className="btn btn--link"
            onClick={() => { setMode(mode === "in" ? "up" : "in"); setError(null); }}
          >
            {mode === "in" ? "Create one" : "Sign in"}
          </button>
        </p>
      </div>
    </main>
  );
}
