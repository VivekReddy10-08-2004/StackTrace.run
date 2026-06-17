// api/og-image.js — production "zero-cost image strategy" (MEMO 1.2 §3).
//
// Vercel Edge Function using @vercel/og. It reads the raw URL params passed from
// the OG meta tag (?user=&rank=&solved=&badge=) and renders them into a clean,
// dark-mode card that Vercel converts to a static PNG on-the-fly when crawled —
// no server-side raster libraries, no traditional backend processing.
//
// The Flask /api/og-image endpoint (backend/routes_profile.py) is the local/dev
// equivalent (SVG). In production, point og:image at this function instead.
//
// Deps:  npm i @vercel/og    (deploy this repo's frontend to Vercel)

import { ImageResponse } from '@vercel/og';

export const config = { runtime: 'edge' };

export default function handler(req) {
  const { searchParams } = new URL(req.url);
  const user = searchParams.get('user') || 'anonymous';
  const rank = searchParams.get('rank') || '1200';
  const solved = searchParams.get('solved') || '0';
  const badge = searchParams.get('badge') || 'Operator';

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#0a0e14',
          fontFamily: 'monospace',
          padding: '60px',
          color: '#c5d1de',
        }}
      >
        <div style={{ color: '#36d399', fontSize: 34, fontWeight: 700 }}>
          StackTrace.run // verification profile
        </div>
        <div style={{ color: '#ffffff', fontSize: 76, fontWeight: 700, marginTop: 16 }}>
          @{user}
        </div>
        <div style={{ height: 2, backgroundColor: '#1f2a37', margin: '28px 0' }} />
        <div style={{ display: 'flex', gap: 80, marginTop: 20 }}>
          <Stat value={rank} label="ELO RANKING" color="#36d399" />
          <Stat value={solved} label="INCIDENTS SOLVED" color="#4fd6e0" />
          <Stat value={badge} label="TOP BADGE" color="#f5c451" size={46} />
        </div>
        <div style={{ marginTop: 'auto', color: '#6b7c8f', fontSize: 26 }}>
          🔥 Live incident-response credentials · stacktrace.run
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}

function Stat({ value, label, color, size = 96 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ color, fontSize: size, fontWeight: 700 }}>{value}</div>
      <div style={{ color: '#6b7c8f', fontSize: 28, marginTop: 8 }}>{label}</div>
    </div>
  );
}
