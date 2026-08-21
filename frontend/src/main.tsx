// This is the ENTRY POINT of the whole app — the very first piece of
// JavaScript that runs in the browser. `index.html` has a script tag
// (`<script type="module" src="/src/main.tsx">`) that loads this file, and
// everything else in the app starts from here.
//
// Forsyt is a "single-page app" (SPA): the browser only ever loads ONE real
// HTML page (`index.html`, which contains just an empty `<div id="root">`).
// React then takes over and swaps content in and out of that div as the user
// clicks around — there is never a full page reload when navigating between
// News / Markets / Corridors / etc. This file is where that handoff from
// "plain HTML page" to "React-controlled app" happens.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { queryClient } from './lib/queryClient.ts'

// `createRoot(...).render(...)` is React's instruction to "start rendering my
// component tree inside this DOM element". `document.getElementById('root')!`
// finds the empty `<div id="root">` from index.html — the trailing `!` just
// tells TypeScript "trust me, this element definitely exists on the page".
createRoot(document.getElementById('root')!).render(
  // <StrictMode> is a React development-time helper — it renders nothing
  // itself, it just makes React double-check components for common mistakes
  // (e.g. side effects that aren't cleaned up) and logs warnings to the
  // browser console. It has no effect on the production build users see.
  <StrictMode>
    {/* QueryClientProvider makes the single shared `queryClient` (defined in
        lib/queryClient.ts) available to every component below it via React
        Context. This is the plumbing that lets any page call `useQuery(...)`
        to fetch data from the API and have it automatically cached/refreshed —
        see lib/queryClient.ts for what react-query actually does. */}
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
