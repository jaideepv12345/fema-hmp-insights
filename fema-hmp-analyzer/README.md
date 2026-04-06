# FEMA HMP Deep Analyzer

An AI-powered Hazard Mitigation Plan analysis platform that provides FEMA compliance scanning, BRIC funding gap analysis, and four depth layers of strategic intelligence for county emergency management directors.

## What It Does

1. **Contextual Intelligence** — Ingests HMP + fetches county data from Census Bureau, FEMA National Risk Index, and FEMA Disaster Declarations
2. **Compliance & Funding Engine** — Scans against 16 FEMA 44 CFR §201.6 requirements + 6 BRIC criteria; identifies funding gaps and opportunities
3. **Deep Reasoning (4 Layers)**:
   - **Deep Operational Rigor** — Are mitigation actions specific, implementable, and properly resourced?
   - **Deep Strategic Rigor** — Is risk prioritization aligned with actual county risk? Is funding strategy sound?
   - **Deep Wisdom** — Hidden patterns, systemic risks, assumptions to challenge, second-order effects
   - **Deep Insights** — Top actionable insights for the county director, funding opportunities, political levers, 6-month roadmap

## Tech Stack

- **Backend:** Python 3.9 + Flask (Vercel Serverless Functions)
- **AI:** OpenAI GPT-4o for deep analysis, GPT-4o-mini for summarization
- **Data:** U.S. Census Bureau ACS API, FEMA NRI ArcGIS API, FEMA Disaster Declarations API
- **Frontend:** Vanilla HTML/CSS/JS (no build step)
- **Hosting:** Vercel (free tier works with API key)

## Deploy to Vercel

### Prerequisites

1. An [OpenAI API key](https://platform.openai.com/api-keys) with GPT-4o access
2. (Optional) A [Census API key](https://api.census.gov/data/key_signup.html) for enhanced demographics

### Step 1: Create the Project

Create this exact folder structure:

