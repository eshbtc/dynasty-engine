// lp-portal/pages/_app.tsx
import '../styles/globals.css'; // Import Tailwind base styles
import type { AppProps } from 'next/app';
import React from 'react'; // Import React

function MyApp({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}

export default MyApp;
