import { useState, type FormEvent } from "react";
import { ArrowUpRight, KeyRound, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { BrandMark, SectionKicker } from "./ui";

type Props = { onLogin: (username: string, password: string) => Promise<void>; notice?: string };

export function LoginPage({ onLogin, notice }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await onLogin(username, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="login-shell">
      <div className="login-glow" />
      <section className="login-card panel">
        <div className="login-brand">
          <BrandMark /><span>TOLLGATE</span><span className="login-brand-divider">/</span><span>ADMIN</span>
        </div>
        <div className="login-emblem"><ShieldCheck size={24} /></div>
        <SectionKicker rule>ADMINISTRATOR ACCESS</SectionKicker>
        <h1>Welcome <em>back.</em></h1>
        <p className="login-copy">Sign in to view gateway and per-token activity.</p>
        {notice && <div className="login-error"><ShieldAlert size={15} />{notice}</div>}
        <form className="login-form" onSubmit={(event) => void submit(event)}>
          <label>
            USERNAME
            <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Admin username" required />
          </label>
          <label>
            PASSWORD
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Admin password" required />
          </label>
          {error && <div className="login-error"><ShieldAlert size={15} />{error}</div>}
          <button className="login-submit" disabled={pending || !username || !password}>
            {pending ? <RefreshCw size={15} className="spin" /> : <KeyRound size={15} />}
            {pending ? "SIGNING IN" : "SIGN IN TO DASHBOARD"}
            <ArrowUpRight size={14} />
          </button>
        </form>
        <div className="login-foot"><i />CREDENTIALS ARE SENT SECURELY TO THE ADMIN LOGIN API</div>
      </section>
      <div className="login-caption">TOLLGATE <span>·</span> LIVE GATEWAY OBSERVABILITY</div>
    </main>
  );
}
