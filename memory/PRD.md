# CreatorOS — Product Requirements (MVP v1)

## Vision
An AI-native business operating system for digital creators, solopreneurs, and personal brands. CreatorOS is the always-on CEO + CFO + growth strategist in your pocket.

## MVP scope (this release)
- **Smart AI Dashboard** with hero Business Health score (87/100), sub-scores (Growth, Financial, Content, Brand), top-of-funnel metric grid (Revenue MTD, Profit, Margin, Audience), live alerts (viral content, opportunity unlock), and a horizontally-scrolling AI Recommendation carousel.
- **Portfolio Management** across 6 platforms (YouTube, Instagram, TikTok, Course, Newsletter, Podcast) with revenue, AI score, follower reach, sparkline trend.
- **Financial Intelligence** with 30-day revenue line chart (gold gradient area), profit/expense/forecast/runway cards, and recent transactions.
- **AI Coach** — streaming chat powered by Claude Sonnet 4.5 via Emergent Universal Key. System prompt is rich with Maya's business context so suggestions are quantified and concrete.
- **Profile** with active goal tracking (revenue, subscribers, launch, content), top viral content this month, and account settings.

## Tech stack
- Frontend: Expo SDK 54, expo-router file-based routing, react-native-svg (charts/sparklines), expo-blur (glass tab bar), expo-linear-gradient.
- Backend: FastAPI + Motor + MongoDB. Endpoints prefixed `/api`. SSE streaming for AI chat.
- AI: `emergentintegrations` LlmChat with `anthropic/claude-sonnet-4-5-20250929`.
- Theme: "Dark-First Utility" — obsidian (#050505), warm amber accent (#E3A72F). No blue/purple/indigo. Phosphor-style outline icons.

## Demo data
Seeded persona: **Maya Chen** — creator with $56k MTD revenue, 184k YouTube subs, 92k IG, Ship It course ($24k/cohort), newsletter, podcast, TikTok. Realistic numbers so the dashboard feels alive on first open.

## What's NOT in MVP (next iteration candidates)
- Live integrations (YouTube/IG/Stripe APIs) — currently uses curated seed data
- Auth (single demo user for now)
- Light theme toggle, push notifications, competitor benchmarking, strategy planner

## Smart business enhancement
The AI Coach context window includes the user's full business data so recommendations are concrete ($-quantified, action-tied). This is the moat — the Coach answers like a co-founder who already read your books, not a generic chatbot.
