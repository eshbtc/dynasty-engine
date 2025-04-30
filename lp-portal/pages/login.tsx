import { useState } from 'react';
import { supa } from '../lib/supa';

export default function Login() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const { error } = await supa.auth.signInWithOtp({ email });
    if (error) setError(error.message);
    else setSent(true);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-indigo-50 to-white p-4">
      <div className="bg-white shadow-xl p-10 rounded-2xl w-full max-w-md border border-gray-100">
        {/* Logo or branding */}
        <div className="flex justify-center mb-6">
          <div className="h-12 w-12 rounded-full bg-indigo-100 flex items-center justify-center">
            {/* Replace below with your actual logo if available */}
            <span className="text-indigo-600 text-2xl font-extrabold">Λ</span>
          </div>
        </div>
        <h1 className="text-3xl font-extrabold mb-2 text-center text-gray-900 tracking-tight">Investor Portal</h1>
        <p className="text-center text-gray-500 mb-6">Sign in with your email to receive a secure magic link.</p>
        {sent ? (
          <div className="flex flex-col items-center">
            <svg className="h-12 w-12 text-green-500 mb-2" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
            <p className="text-green-700 text-lg font-semibold mb-2">Magic link sent!</p>
            <p className="text-gray-500 text-center">Check your inbox and follow the link to log in.</p>
          </div>
        ) : (
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
              <input
                id="email"
                type="email"
                placeholder="you@email.com"
                className="w-full border border-gray-300 p-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 text-gray-900"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="w-full bg-indigo-600 text-white p-3 rounded-lg font-semibold shadow hover:bg-indigo-700 transition-colors"
            >
              Send Magic Link
            </button>
            {error && <p className="text-red-600 text-sm text-center">{error}</p>}
          </form>
        )}
      </div>
      <footer className="mt-8 text-gray-400 text-xs text-center">
        &copy; {new Date().getFullYear()} Dynasty LP Portal. All rights reserved.
      </footer>
    </div>
  );
}

