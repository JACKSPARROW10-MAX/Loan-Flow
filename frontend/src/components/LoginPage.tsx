'use client';

import React, { useState } from 'react';
import { Landmark } from 'lucide-react';
import { login, registerUser, SessionUser } from '@/lib/api';

interface LoginPageProps {
  onLoggedIn: (user: SessionUser) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoggedIn }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'customer' | 'employee'>('customer');

  const switchMode = (m: 'login' | 'register') => {
    setMode(m);
    setError(null);
    setInfo(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === 'login') {
        const user = await login(username.trim(), password);
        onLoggedIn(user);
      } else {
        await registerUser({
          username: username.trim(),
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          role,
        });
        setInfo(
          role === 'customer'
            ? 'Registration submitted. A loan officer must approve your account before you can sign in.'
            : 'Registration submitted. A branch manager must approve your account before you can sign in.'
        );
        setMode('login');
        setPassword('');
      }
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  const input =
    'w-full px-3 py-2 rounded-lg border border-[#C3D9CE] bg-white text-sm text-[#14241e] focus:outline-none focus:ring-2 focus:ring-[#6D9773]';

  return (
    <div className="min-h-screen bg-[#F7F8F5] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center space-x-3 mb-6">
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-[#FFBA00] to-[#BB8A52] flex items-center justify-center shadow-md text-[#0C3B2E]">
            <Landmark className="w-6 h-6 stroke-[2.2]" />
          </div>
          <span className="text-2xl font-bold tracking-tight text-[#0C3B2E]">LoanFlow</span>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E9E1] shadow-sm p-6">
          <div className="flex bg-[#EBF3EF] p-1 rounded-xl mb-5">
            {(['login', 'register'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={`flex-1 py-1.5 text-sm rounded-lg transition-all ${
                  mode === m ? 'bg-[#0C3B2E] text-white font-semibold shadow' : 'text-[#3b5346]'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === 'register' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-[#3b5346] mb-1">Full name</label>
                  <input className={input} value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#3b5346] mb-1">Email</label>
                  <input
                    type="email"
                    className={input}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[#3b5346] mb-1">I am a</label>
                  <select
                    className={input}
                    value={role}
                    onChange={(e) => setRole(e.target.value as 'customer' | 'employee')}
                  >
                    <option value="customer">Customer (approved by a loan officer)</option>
                    <option value="employee">Loan officer (approved by a manager)</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-medium text-[#3b5346] mb-1">Username</label>
              <input
                className={input}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#3b5346] mb-1">Password</label>
              <input
                type="password"
                className={input}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={mode === 'register' ? 8 : undefined}
                required
              />
              {mode === 'register' && <p className="text-[11px] text-[#5e6d65] mt-1">At least 8 characters.</p>}
            </div>

            {error && (
              <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>
            )}
            {info && (
              <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                {info}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-2.5 rounded-lg bg-[#0C3B2E] text-white text-sm font-semibold hover:bg-[#165443] disabled:opacity-60 transition-colors"
            >
              {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          {busy && (
            <p className="text-[11px] text-[#5e6d65] mt-3 text-center">
              The server may take up to a minute to wake up on the first request.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
