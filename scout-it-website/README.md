# scout-it Web

This directory contains the Vite, React, and TypeScript documentation site for scout-it.

## Structure

```text
web/
  public/                 static assets (favicon mark, sitemap, robots.txt)
  src/
    components/           Nav, Footer, Layout, DocsLayout, Terminal, etc.
    data/                 site metadata + all documented CLI flags/tables
    pages/                Home, NotFound
    pages/docs/           one file per docs route
    styles/global.css     design tokens + global styles (light/dark theme)
```

## Scripts

```sh
npm install
npm run dev         # local dev server
npm run typecheck   # tsc --noEmit
npm run build       # tsc -b && vite build -> dist/
npm run preview     # serve the production build locally
```

## Notes

- Client-side routing via react-router-dom; every `/docs/*` route renders through `DocsLayout`.
- Theme preference is stored in `localStorage` as `scout-it-theme`.
- All CLI flags, GitHub commands, social commands, and engine tables live in `src/data/` —
  update the data file and every page/table referencing it updates automatically.
- Production output is written to `web/dist/`. Deploys cleanly to Netlify/Vercel/any static host
  (SPA fallback already configured in `public/_redirects`).
