// lp-portal/pages/_app.tsx
import '../styles/globals.css'; // Import Tailwind base styles
import type { AppProps } from 'next/app';
import React from 'react'; // Import React

import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { supa } from '../lib/supa';

function MyApp({ Component, pageProps }: AppProps) {
  const router = useRouter();

  useEffect(() => {
    // Only run client-side
    if (typeof window !== 'undefined') {
      const hash = window.location.hash;
      if (hash && hash.includes('access_token')) {
        const params = new URLSearchParams(hash.replace('#', ''));
        const access_token = params.get('access_token');
        const refresh_token = params.get('refresh_token');
        const expires_in = params.get('expires_in');
        const token_type = params.get('token_type');

        if (access_token && refresh_token && token_type) {
          supa.auth.setSession({
            access_token,
            refresh_token,
            expires_in: Number(expires_in),
            token_type,
          }).then(() => {
            // Clean up the URL and redirect to the main page
            window.location.replace('/');
          });
        }
      }
    }
  }, []);

  return <Component {...pageProps} />;
}

export default MyApp;
