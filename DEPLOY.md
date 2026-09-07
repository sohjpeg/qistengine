# Deploying QistEngine for free

Two free hosts, no credit card:

| Piece | Host | Notes |
|---|---|---|
| Backend (FastAPI + model) | **Render** free web service | Sleeps after 15 min idle → ~50 s cold start. Warm it before you present. |
| Frontend (Next.js) | **Vercel** Hobby | Always on |

The demo link you submit is the **Vercel URL**.

> Hugging Face Spaces used to be an option but moved Docker/Gradio Spaces to a paid
> plan. Render is the free replacement.

---

## Step 1 — Backend on Render (~10 min, mostly waiting)

1. Sign up at <https://render.com> → **Get Started** → **GitHub** (free, no card).
   Authorise Render to see the `qistengine` repo.
2. Dashboard → **Add new… → Web Service** → pick `sohjpeg/qistengine` → **Connect**.
3. Fill in the form:

   | Field | Value |
   |---|---|
   | **Name** | `qistengine-api` |
   | **Language** | `Python 3` |
   | **Branch** | `main` |
   | **Root Directory** | `backend` |
   | **Build Command** | *(paste the one line below)* |
   | **Start Command** | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | **Free** |

   Build Command (one line, paste exactly):

   ```
   pip install -r requirements.txt && python scripts/generate_synthetic_data.py --n 5000 --seed 42 && python scripts/train_model.py && python scripts/make_sample_files.py && python -m app.seed
   ```

4. Expand **Environment Variables** → add:

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.11.9` |
   | `QIST_ENV` | `production` |
   | `QIST_CORS_ORIGINS` | `http://localhost:3000` *(you'll update this in Step 3)* |
   | `QIST_PII_KEY` | a long random string — see below |

   `QIST_PII_KEY` encrypts applicant names, CNIC/phone, bill fields and officer
   notes at rest. **It is required** because `QIST_ENV=production` is set, and
   Render applies environment variables to the build command too — which ends in
   `python -m app.seed`. Without the key the build fails, by design. Generate one
   with:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Keep it somewhere safe. Changing it makes an existing database unreadable —
   harmless here, since Render rebuilds and reseeds the database on every deploy,
   but it would matter with real data.

5. **Create Web Service.** First build runs `pip install` + model training — ~6–9 min.
   Watch the log. When it says **"Your service is live"** and the status is green:
   - Open `<your-service-url>/health` → should return `{"status":"ok","model_loaded":true,...}`
   - `<your-service-url>/docs` → Swagger UI
6. **Copy the service URL.** It looks like `https://qistengine-api.onrender.com`.

If the build fails with an out-of-memory error during training, see
**Troubleshooting** at the bottom.

---

## Step 2 — Frontend on Vercel (~3 min)

1. Sign up at <https://vercel.com/signup> → **Continue with GitHub** (free Hobby plan).
2. **Add New… → Project** → find `sohjpeg/qistengine` → **Import**.
3. **Root Directory:** click **Edit** → choose `frontend`.
4. **Framework Preset:** Next.js (auto-detected — leave it).
5. Expand **Environment Variables** and add two:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | your Render URL from Step 1 (no trailing `/`) |
   | `NEXT_PUBLIC_DEMO_MODE` | `true` |

6. **Deploy.** ~2 min. You'll get a URL like `https://qistengine-xxxx.vercel.app`.
   - Cleaner URL: **Project → Settings → Domains**, or rename the project to `qistengine`.
7. **Copy the final Vercel URL.**

---

## Step 3 — Let the backend trust the frontend

1. Back in Render → your service → **Environment** → edit `QIST_CORS_ORIGINS`:
   - Value: your exact Vercel URL, e.g. `https://qistengine.vercel.app` (no trailing `/`)
2. **Save Changes** → Render redeploys (~1 min, no rebuild of the model).

Until this is set, the frontend loads but every API call is blocked by the browser
(CORS) and pages fall back to the cached-demo banner.

---

## Step 4 — Verify

Open the Vercel URL and check:

- [ ] Landing page renders
- [ ] **/apply** → click *Quick Demo → Bilal* → **Submit application** → lands on a
      decision page with a real score (not the offline banner)
- [ ] Drag a **What-if** slider → the score re-computes (proves the backend is live)
- [ ] **/dashboard** → the underwriting queue lists applicants
- [ ] **/analytics** → model card (AUC 0.819, KS 0.488…) and the fairness table

An orange *"backend offline — showing cached demo"* banner means the Render service
is asleep or still deploying. Reload after ~50 s.

---

## Maintenance

Nothing day-to-day. It runs on Render's and Vercel's servers whether your laptop is
on or off.

**The one thing that matters:** Render's free service sleeps after 15 minutes of no
traffic. **Open `<render-url>/health` about 2 minutes before you present** so it's
awake when a judge clicks. `NEXT_PUBLIC_DEMO_MODE=true` means even a cold backend
still shows cached scores with a small banner rather than a broken page — but a live
backend is obviously better.

Vercel auto-redeploys on every push to `main`. Render also auto-redeploys on push
(and re-trains the model each time — that's fine, it's deterministic).

---

## Troubleshooting

**Render build OOMs during `train_model.py`** — the free build container is 512 MB.
Reduce the synthetic sample in the build command from `--n 5000` to `--n 2000`
(metrics shift by <0.01, still a valid demo). If it still fails, drop the
`generate_synthetic_data.py` + `train_model.py` steps from the build command and
instead commit the three files in `backend/app/ml/artifacts/` (`model.pkl`,
`explainer.pkl`, `scaler.pkl`) plus `metadata.json` to the repo with
`git add -f`, so Render serves the pre-trained model without training.

**Runtime OOM / service restarts** — same fix: pre-commit the artifacts and use a
build command of just
`pip install -r requirements.txt && python scripts/make_sample_files.py && python -m app.seed`.

**"model_loaded": false at /health** — the training step didn't run or didn't write
to `QIST_MODEL_DIR`. Check the build log for the "Training the scorecard" output.

---

## Deploying a branch without touching `main`

The live demo builds from `main`. To put a feature branch online for review
while leaving the current deployment exactly as it is:

- **Frontend** — Vercel builds a preview URL for every branch push automatically.
  Nothing to configure.
- **Backend** — Render's free plan tracks one branch per service, so create a
  *second* web service pointed at the branch. Same settings as Step 1 (root
  directory `backend`, same build and start commands), with its own
  `QIST_PII_KEY`. Then set the preview frontend's `NEXT_PUBLIC_API_BASE_URL` to
  that second service's URL, and add the preview origin to its
  `QIST_CORS_ORIGINS`.

A frontend preview alone is not enough to test a backend change — encryption and
statement parsing both live server-side.
