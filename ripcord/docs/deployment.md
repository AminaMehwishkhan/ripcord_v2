# Deployment Guide

lablab.ai's submission requirements include a **publicly accessible demo URL**. Ripcord splits across two hosts because the backend needs a persistent WebSocket connection, which rules out plain serverless functions:

- **Backend** (FastAPI + WebSockets) → Render, Railway, or Fly.io
- **Frontend** (static Vite build) → Vercel, Netlify, or any static host

This guide uses Render + Vercel since both have generous free tiers and a simple Git-push deploy flow.

## Simplest option: one service

The backend also serves the built dashboard (`frontend/dist`) from the same address, so one host is enough and there is no CORS or WebSocket-proxy setup:

```bash
cd frontend && npm ci && npm run build && cd ..
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000     # open http://localhost:8000
```

On a host that has both Python and Node in its build step, use `pip install -r requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build` as the build command (check that your host's build image includes Node; if it does not, use the two-host setup below). This single-service path was run and checked locally, not on Render.


## 1. Backend on Render

1. Push this repo to GitHub (public, per the hackathon rules).
2. On [render.com](https://render.com), **New → Web Service**, connect the repo.
3. Settings:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r ../requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance type**: the free tier works for a demo; note it spins down on inactivity, so hit the health endpoint a minute before your judges/video recording to warm it up.
4. Environment variables (Render dashboard → Environment):
   ```
   ASSEMBLYAI_API_KEY=<your key>
   MOCK_MODE=false
   CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
   ```
   Leave `MOCK_MODE=true` and skip the API key if you're demoing only the scripted scenarios — just say so in your video (see `docs/video-script.md`).
5. Deploy. Note the resulting URL, e.g. `https://ripcord-backend.onrender.com`.
6. Verify: `curl https://ripcord-backend.onrender.com/api/health` should return `{"status":"ok",...}`.

## 2. Frontend on Vercel

1. On [vercel.com](https://vercel.com), **New Project**, import the same repo.
2. Settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite (auto-detected)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. The frontend currently reads `/api` and `/ws` as relative paths (proxied to `localhost:8000` only in local dev via `vite.config.ts`). For production, either:
   - **Option A (simplest):** add a Vercel rewrite in `frontend/vercel.json` pointing `/api/*` and `/ws/*` at your Render backend URL, or
   - **Option B:** add a `VITE_BACKEND_URL` env var and update `src/services/api.ts` / `src/hooks/useRipcordSession.ts` to build absolute URLs from it instead of relative paths.

   Example `frontend/vercel.json` for Option A:
   ```json
   {
     "rewrites": [
       { "source": "/api/:path*", "destination": "https://ripcord-backend.onrender.com/api/:path*" }
     ]
   }
   ```
   Note: Vercel's rewrites don't proxy WebSocket upgrades reliably — Option B (absolute WS URL straight to the Render host) is the more robust choice for the `/ws/session` connection specifically. Keep `/api` on the rewrite and point the WebSocket hook directly at `wss://ripcord-backend.onrender.com/ws/session`.
4. Deploy. Note the resulting URL, e.g. `https://ripcord.vercel.app` — this is your **Demo Application URL** for the submission form.
5. Go back to Render and confirm `CORS_ORIGINS` matches this exact origin (scheme + host, no trailing slash).

## 3. Post-deploy verification checklist

- [ ] `GET https://<backend>/api/health` returns 200
- [ ] `GET https://<backend>/api/scenarios` returns the scenario list (recorded clips plus the 10 scripted ones)
- [ ] Opening the frontend URL connects the WebSocket (green "Live" status pill in the header)
- [ ] Running a mock scenario updates the dashboard end-to-end
- [ ] If using real mode: the mic button is enabled and a real session connects (check for `assemblyai_key_configured: true` at `/api/health`)
- [ ] No browser console errors about mixed content (http vs https) or CORS

## 4. Common failure modes

| Symptom | Likely cause |
|---|---|
| Frontend loads but WebSocket never connects | `/ws` not routed to the backend — see Option B above; check browser console for the actual URL it tried |
| `CORS` error in browser console | `CORS_ORIGINS` on Render doesn't exactly match the Vercel origin |
| Backend health check works but real mic mode is greyed out | `MOCK_MODE` still `true`, or `ASSEMBLYAI_API_KEY` unset on Render |
| First request after idle takes 30+ seconds | Render free tier cold start — hit `/api/health` a minute before demoing |
