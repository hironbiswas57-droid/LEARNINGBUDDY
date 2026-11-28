# LearnMate AI

LearnMate AI pairs an illustrated, motion-rich public landing page with an authenticated learning workspace backed by a lightweight Python API.

## Open the app

- **Live prototype:** [learnmate-ai-w44n.onrender.com](https://learnmate-ai-w44n.onrender.com/)
- **Public landing page:** `/`
- **Learner workspace:** `/workspace`
- **API reference:** `/docs`
- **Health check:** `/api/v1/health`

The live prototype link above is the existing static deployment. The full-stack app described below needs to be deployed as a Render **Web Service**; it will receive its own Render URL.

## Features

### Public landing experience

- Responsive illustrated LearnMate homepage with pointer and scroll motion, reduced-motion support, learning subject showcases, communities, Skill Studio, Idea Lab, and a front-end buddy preview.
- Existing community join controls, practice progress, thought wall, and the original landing-page chat remain browser-side demonstrations.
- Sign-in and account-creation links open the connected workspace without removing the landing experience.

### Connected learner workspace

- Learner registration and sign-in with access and rotating refresh tokens.
- Personalized learner overview, course catalog, enrollment, lessons, and saved lesson progress.
- Daily goals, focus sessions, weekly activity summary, profile, and AI study buddy.
- Curiosity articles, saved/read events, recommendation preferences, question history and solution decks, teen-only room messages, and message reports stored in SQLite.
- A dedicated Curiosity tab in the signed-in workspace, with a research shelf, saved question history, solution deck, and teen study-circle chat connected to the API and SQLite records.
- Teen room posts, reports, contact-detail holds, and opt-in learner-scoped topic suggestions use the same backend; conversation content is not used to train a shared model.
- Local mock tutor works without API credentials. Answers are marked **unverified** unless a configured reviewer approves them.

The ESD package also describes live classes, careers, marketplace, parent/educator tools, and other integrations as future roadmap items. The new Curiosity rooms are active API features. There is no staffed real-time moderation console in this prototype: reported posts are hidden pending review, and posts containing detected email addresses or phone-like strings are held. Do not treat automated checks as complete moderation.

## Run locally

Python 3.9 or newer is sufficient; the backend uses the Python standard library.

```sh
python -m learnmate
```

Open <http://127.0.0.1:8000/>. Use `/workspace` for the account-based dashboard. In development, the seeded sample learner is:

- Email: `demo@learnmate.ai`
- Password: `LearnMate123!`

This sample account is only seeded in development. Register a learner account to use the production deployment.

## Deploy the full-stack version to Render

The root [`render.yaml`](render.yaml) defines a Python Web Service. It serves the existing landing page and its assets, the authenticated workspace, and the API from the same origin.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/hironbiswas57-droid/LEARNINGBUDDY)

In Render, create a **Blueprint** from this repository, or create a Python **Web Service** with:

- **Build command:** `python -m compileall -q learnmate`
- **Start command:** `python -m learnmate`
- **Health check:** `/api/v1/health`
- **Environment:** `HOST=0.0.0.0`, `LEARNMATE_ENV=production`, and a strong generated `JWT_SECRET`

Render free web services have an ephemeral filesystem and may spin down when idle. The SQLite database and demo user data can be lost when the service restarts or redeploys. Use a persistent datastore for data that must survive; this MVP currently uses SQLite and does not include a PostgreSQL adapter.

## Optional tutor and reviewer configuration

Set `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `REVIEWER_MODEL` in a protected environment to use the OpenAI-compatible adapter. Do not commit production credentials. Until a reviewer is configured and approves an answer, the API labels it unverified.

Curiosity questions and generated replies are retained in the learner's account. When an external compatible model is configured, the question is sent to that provider to generate a response. Reading and answer-feedback suggestions are off by default and can be enabled in the Curiosity section; the resulting topic summaries use only that learner's own article activity and do not update model weights or train a shared model. Curiosity rooms are restricted to teen accounts and posts are visible to signed-in teens. Avoid sharing identifying or sensitive information.

## Project structure

```text
LEARNINGBUDDY/
├── index.html                 Existing public landing page
├── assets/                    Optimized artwork used by the landing page
├── learnmate/                 Python API, security, database, and services
├── static/
│   ├── index.html             Account workspace served at /workspace
│   ├── app.js                 Workspace and API client
│   ├── curiosity-page.js      Signed-in Curiosity workspace interactions
│   └── curiosity-page.css     Dedicated Curiosity workspace design
│   └── styles.css             Workspace styles
├── docs/                      Architecture and delivery roadmap
├── tests/                     Supplied backend test suite
├── Dockerfile
├── .env.example
└── render.yaml
```

## Prototype boundaries

Authentication, learner records, courses, goals, focus sessions, tutor conversations, and the new Curiosity features use the backend API. The older homepage community controls, persistent thought saving, and its demo chat are still browser-only. The service is a single-node MVP using SQLite and in-memory rate limiting, not a horizontally scaled production system. Render's free service uses an ephemeral filesystem, so SQLite records may be lost on restart or redeploy; use persistent managed storage before collecting real learner data.

## Docker

The supplied Dockerfile runs the same combined frontend and API:

```sh
docker build -t learnmate-ai .
docker run --rm -p 8000:8000 -e HOST=0.0.0.0 -e LEARNMATE_ENV=production -e JWT_SECRET='replace-with-a-long-random-secret' -v learnmate-data:/app/data learnmate-ai
```
