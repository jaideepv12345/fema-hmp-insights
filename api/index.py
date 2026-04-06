"""
FEMA HMP Deep Analyzer — Vercel Serverless Function
====================================================
Analyzes county Hazard Mitigation Plans against FEMA requirements,
BRIC funding criteria, and produces 4 depth layers of intelligence.

Environment Variables (set in Vercel Dashboard → Settings → Environment):
  OPENAI_API_KEY  — Required for deep analysis (Operational/Strategic/Wisdom/Insights)
  CENSUS_API_KEY  — Optional; enhances county demographic data
"""

import os
import re
import json
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# ---------------------------------------------------------------------------
# FEMA COMPLIANCE KNOWLEDGE BASE
# ---------------------------------------------------------------------------

FEMA_COMPLIANCE_CHECKLIST = [
    {
        "id": "plan_process_doc",
        "category": "Planning Process",
        "requirement": "44 CFR §201.6(b)(1) — Planning process must be documented",
        "keywords": ["planning process", "planning team", "mitigation planning",
                      "stakeholder", "public meeting", "public comment",
                      "outreach", "engagement process"],
        "weight": 8,
    },
    {
        "id": "public_participation",
        "category": "Planning Process",
        "requirement": "44 CFR §201.6(b)(2) — Opportunity for public comment must be provided",
        "keywords": ["public comment", "public hearing", "public meeting",
                      "public input", "stakeholder input", "community input",
                      "survey", "public notice", "comment period"],
        "weight": 10,
    },
    {
        "id": "jurisdiction_coord",
        "category": "Planning Process",
        "requirement": "44 CFR §201.6(b)(3) — Coordination with affected jurisdictions and agencies",
        "keywords": ["coordination", "partner", "jurisdiction", "neighboring",
                      "agency", "interagency", "regional", "collaboration",
                      "memorandum", "mou", "working group"],
        "weight": 9,
    },
    {
        "id": "existing_studies",
        "category": "Planning Process",
        "requirement": "44 CFR §201.6(b)(4) — Review and incorporation of existing studies",
        "keywords": ["existing study", "previous study", "prior assessment",
                      "incorporated", "reviewed", "literature review",
                      "data source", "reference", "bibliography"],
        "weight": 6,
    },
    {
        "id": "hazard_id",
        "category": "Risk Assessment",
        "requirement": "44 CFR §201.6(c)(2)(i) — Identification of all natural hazards",
        "keywords": ["hazard identification", "natural hazard", "flood", "earthquake",
                      "hurricane", "tornado", "wildfire", "landslide", "drought",
                      "winter storm", "tsunami", "coastal", "hazard profile",
                      "threat", "peril"],
        "weight": 10,
    },
    {
        "id": "hazard_profile",
        "category": "Risk Assessment",
        "requirement": "44 CFR §201.6(c)(2)(ii) — Hazard profiles (location, extent, magnitude, probability)",
        "keywords": ["probability", "frequency", "magnitude", "extent",
                      "location", "return period", "recurrence interval",
                      "likelihood", "intensity", "severity", "hazard profile",
                      "exposure"],
        "weight": 9,
    },
    {
        "id": "vulnerability",
        "category": "Risk Assessment",
        "requirement": "44 CFR §201.6(c)(2)(iii) — Vulnerability assessment identifying assets at risk",
        "keywords": ["vulnerability", "at risk", "exposed", "asset",
                      "critical facility", "infrastructure", "building",
                      "population at risk", "social vulnerability",
                      "lifeline", "essential facility"],
        "weight": 10,
    },
    {
        "id": "loss_estimation",
        "category": "Risk Assessment",
        "requirement": "44 CFR §201.6(c)(2)(iv) — Estimation of potential losses",
        "keywords": ["loss estimation", "potential loss", "economic loss",
                      "damage estimate", "annualized loss", "expected loss",
                      "haza", "cost estimate", "replacement value",
                      "dollars", "financial impact"],
        "weight": 8,
    },
    {
        "id": "future_conditions",
        "category": "Risk Assessment",
        "requirement": "44 CFR §201.6(c)(2)(ii)(C) — Incorporation of future conditions / climate change",
        "keywords": ["future condition", "climate change", "climate projection",
                      "future risk", "sea level rise", "temperature increase",
                      "precipitation change", "future development",
                      "population growth", "scenario"],
        "weight": 10,
    },
    {
        "id": "mitigation_actions",
        "category": "Mitigation Strategy",
        "requirement": "44 CFR §201.6(c)(3)(i) — Identification and analysis of mitigation actions",
        "keywords": ["mitigation action", "mitigation measure", "mitigation strategy",
                      "action item", "project", "initiative", "program",
                      "policy", "regulation", "code", "ordinance"],
        "weight": 10,
    },
    {
        "id": "staplee",
        "category": "Mitigation Strategy",
        "requirement": "STAPLEE evaluation — Social, Technical, Administrative, Political, Legal, Economic, Environmental",
        "keywords": ["staplee", "social", "technical", "administrative",
                      "political", "legal", "economic", "environmental",
                      "feasibility", "cost-benefit", "benefit-cost"],
        "weight": 9,
    },
    {
        "id": "implementation_plan",
        "category": "Mitigation Strategy",
        "requirement": "44 CFR §201.6(c)(3)(ii) — Action plan with timeline, responsible parties, funding",
        "keywords": ["timeline", "responsible", "funding source", "budget",
                      "implementation", "priority", "schedule", "milestone",
                      "cost estimate", "lead agency", "implementation plan",
                      "action plan"],
        "weight": 10,
    },
    {
        "id": "monitoring",
        "category": "Plan Maintenance",
        "requirement": "44 CFR §201.6(c)(4)(i) — Method and schedule for monitoring plan implementation",
        "keywords": ["monitor", "monitoring", "track", "tracking",
                      "progress", "metric", "indicator", "performance",
                      "evaluation criteria"],
        "weight": 8,
    },
    {
        "id": "plan_update",
        "category": "Plan Maintenance",
        "requirement": "44 CFR §201.6(c)(4)(ii) — Process for updating the plan (5-year cycle)",
        "keywords": ["update", "5-year", "five year", "revision",
                      "plan maintenance", "annual review", "cycle",
                      "update cycle", "review schedule"],
        "weight": 9,
    },
    {
        "id": "post_disaster",
        "category": "Plan Maintenance",
        "requirement": "44 CFR §201.6(c)(4)(iii) — Incorporation of post-disaster findings within 6 months",
        "keywords": ["post-disaster", "after action", "lessons learned",
                      "disaster event", "recovery", "incorporate",
                      "6 month", "six month", "post event"],
        "weight": 8,
    },
    {
        "id": "formal_adoption",
        "category": "Documentation",
        "requirement": "44 CFR §201.6(c)(5) — Formal adoption by the governing body",
        "keywords": ["adopt", "adoption", "resolution", "ordinance",
                      "governing body", "county commission", "city council",
                      "board of supervisors", "formal adoption"],
        "weight": 10,
    },
]

BRIC_CHECKLIST = [
    {
        "id": "bric_capability",
        "category": "BRIC Capability",
        "requirement": "Demonstrates existing mitigation capability and capacity",
        "keywords": ["capability", "capacity", "existing program", "staff",
                      "dedicated", "mitigation staff", "program manager",
                      "organizational capacity", "institutional capacity"],
        "weight": 10,
    },
    {
        "id": "bric_future_conditions",
        "category": "BRIC Future Conditions",
        "requirement": "Addresses risks from future conditions including climate change",
        "keywords": ["future condition", "climate change", "resilience",
                      "adaptation", "future risk", "projection",
                      "rcpm", "resilient", "climate projection"],
        "weight": 10,
    },
    {
        "id": "bric_nature_based",
        "category": "BRIC Nature-Based Solutions",
        "requirement": "Incorporates nature-based solutions where applicable",
        "keywords": ["nature-based", "green infrastructure", "wetland",
                      "floodplain", "restoration", "green space",
                      "natural system", "ecosystem", "biomimicry",
                      "living shoreline", "riparian", "conservation"],
        "weight": 8,
    },
    {
        "id": "bric_underserved",
        "category": "BRIC Equity",
        "requirement": "Addresses underserved communities and equity considerations",
        "keywords": ["underserved", "equity", "environmental justice",
                      "disadvantaged", "vulnerable population", "low-income",
                      "minority", "access and functional needs",
                      "social vulnerability", "justice40", "cdp"],
        "weight": 10,
    },
    {
        "id": "bric_integration",
        "category": "BRIC Integration",
        "requirement": "Demonstrates integration with other planning efforts",
        "keywords": ["integration", "comprehensive plan", "capital improvement",
                      "land use plan", "zoning", "housing strategy",
                      "transportation plan", "climate action plan",
                      "consistency", "aligned with"],
        "weight": 8,
    },
    {
        "id": "bric_bca",
        "category": "BRIC Benefit-Cost",
        "requirement": "Demonstrates benefit-cost analysis capability for proposed projects",
        "keywords": ["benefit-cost", "bca", "cost-benefit", "ratio",
                      "fema bca toolkit", "return on investment", "roi",
                      "benefit", "avoided damage"],
        "weight": 9,
    },
]

# ---------------------------------------------------------------------------
# STATE FIPS CODES
# ---------------------------------------------------------------------------

STATE_FIPS = {
    "Alabama": "01", "Alaska": "02", "Arizona": "04", "Arkansas": "05",
    "California": "06", "Colorado": "08", "Connecticut": "09", "Delaware": "10",
    "District of Columbia": "11", "Florida": "12", "Georgia": "13", "Hawaii": "15",
    "Idaho": "16", "Illinois": "17", "Indiana": "18", "Iowa": "19",
    "Kansas": "20", "Kentucky": "21", "Louisiana": "22", "Maine": "23",
    "Maryland": "24", "Massachusetts": "25", "Michigan": "26", "Minnesota": "27",
    "Mississippi": "28", "Missouri": "29", "Montana": "30", "Nebraska": "31",
    "Nevada": "32", "New Hampshire": "33", "New Jersey": "34", "New Mexico": "35",
    "New York": "36", "North Carolina": "37", "North Dakota": "38", "Ohio": "39",
    "Oklahoma": "40", "Oregon": "41", "Pennsylvania": "42", "Rhode Island": "44",
    "South Carolina": "45", "South Dakota": "46", "Tennessee": "47", "Texas": "48",
    "Utah": "49", "Vermont": "50", "Virginia": "51", "Washington": "53",
    "West Virginia": "54", "Wisconsin": "55", "Wyoming": "56",
}


# ---------------------------------------------------------------------------
# RULES-BASED COMPLIANCE ENGINE
# ---------------------------------------------------------------------------

def scan_compliance(text: str) -> dict:
    """Run FEMA compliance checklist against document text."""
    text_lower = text.lower()
    results = []
    total_weight = 0
    earned_weight = 0

    for item in FEMA_COMPLIANCE_CHECKLIST:
        hits = [kw for kw in item["keywords"] if kw in text_lower]
        hit_ratio = len(hits) / max(len(item["keywords"]), 1)

        if hit_ratio >= 0.35:
            status = "present"
            earned_weight += item["weight"]
        elif hit_ratio >= 0.15:
            status = "weak"
            earned_weight += item["weight"] * 0.5
        else:
            status = "missing"

        total_weight += item["weight"]
        results.append({
            "id": item["id"],
            "category": item["category"],
            "requirement": item["requirement"],
            "status": status,
            "keywords_found": hits[:5],
            "keywords_total": len(item["keywords"]),
            "weight": item["weight"],
        })

    score = round((earned_weight / total_weight) * 100) if total_weight else 0
    return {"score": score, "items": results}


def scan_bric(text: str) -> dict:
    """Run BRIC funding readiness checklist."""
    text_lower = text.lower()
    results = []
    total_weight = 0
    earned_weight = 0

    for item in BRIC_CHECKLIST:
        hits = [kw for kw in item["keywords"] if kw in text_lower]
        hit_ratio = len(hits) / max(len(item["keywords"]), 1)

        if hit_ratio >= 0.35:
            status = "present"
            earned_weight += item["weight"]
        elif hit_ratio >= 0.15:
            status = "weak"
            earned_weight += item["weight"] * 0.5
        else:
            status = "missing"

        total_weight += item["weight"]
        results.append({
            "id": item["id"],
            "category": item["category"],
            "requirement": item["requirement"],
            "status": status,
            "keywords_found": hits[:5],
            "weight": item["weight"],
        })

    score = round((earned_weight / total_weight) * 100) if total_weight else 0
    return {"score": score, "items": results}


def extract_plan_metadata(text: str) -> dict:
    """Extract structural metadata from the HMP."""
    lines = text.split("\n")
    headings = re.findall(r"^#+\s+(.+)", text, re.MULTILINE)
    sections = re.findall(r"^[A-Z][A-Z\s]{4,}$", text, re.MULTILINE)
    all_headings = headings + sections

    words = re.findall(r"\b[a-zA-Z]+\b", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    tables = re.findall(r"\|.+\|", text)
    numbers = re.findall(r"\b\d+[\.,]?\d*%?\b", text)
    dollar_amounts = re.findall(r"\$[\d,]+(?:\.\d{2})?(?:\s*[mMbBkK])?", text)

    # Detect plan year
    year_match = re.search(r"(?:20\d{2})(?:\s*[-–]\s*(?:20\d{2}))?", text[:1000])
    plan_years = year_match.group(0) if year_match else "Unknown"

    # Detect jurisdiction name
    first_500 = text[:500]
    county_match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+County", first_500)
    jurisdiction = county_match.group(0) if county_match else "Not detected"

    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "heading_count": len(all_headings),
        "headings": all_headings[:30],
        "table_count": len(tables),
        "number_count": len(numbers),
        "dollar_amounts": dollar_amounts[:10],
        "plan_years": plan_years,
        "detected_jurisdiction": jurisdiction,
    }


# ---------------------------------------------------------------------------
# COUNTY DATA FETCHING
# ---------------------------------------------------------------------------

def resolve_county_fips(state_name: str, county_name: str) -> str:
    """Resolve county name to FIPS code using Census API."""
    state_fips = STATE_FIPS.get(state_name, "")
    if not state_fips:
        return ""
    try:
        url = (
            f"https://api.census.gov/data/2020/dec/pl"
            f"?get=NAME,P1_001N&for=county:*&in=state:{state_fips}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return ""
        data = resp.json()
        county_lower = county_name.lower().strip()
        for row in data[1:]:
            name = row[0].lower()
            if county_lower in name or name in county_lower:
                return f"{state_fips}{row[2]}"
        return ""
    except Exception:
        return ""


def fetch_census_demographics(state_name: str, county_name: str) -> dict:
    """Fetch demographic data from Census ACS 5-year estimates."""
    state_fips = STATE_FIPS.get(state_name, "")
    fips = resolve_county_fips(state_name, county_name)

    result = {"source": "U.S. Census Bureau ACS 5-Year Estimates", "fips": fips}

    if not fips:
        result["error"] = "Could not resolve county FIPS code"
        return result

    county_fips = fips[2:] if len(fips) > 2 else fips
    api_key = os.environ.get("CENSUS_API_KEY", "")

    # ACS DP05 — Demographic and Housing Characteristics
    try:
        variables = [
            "NAME", "DP05_0001E",   # Total population
            "DP05_0002E",           # Male
            "DP05_0003E",           # Female
            "DP05_0037E",           # Median age
            "DP05_0071E",           # White alone
            "DP05_0072E",           # Black or African American
            "DP05_0073E",           # American Indian
            "DP05_0074E",           # Asian
            "DP05_0078E",           # Hispanic or Latino
            "DP05_0079E",           # White alone, not Hispanic
        ]
        key_param = f"&key={api_key}" if api_key else ""
        url = (
            f"https://api.census.gov/data/2022/acs/acs5/profile"
            f"?get={','.join(variables)}&for=county:{county_fips}"
            f"&in=state:{state_fips}{key_param}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1:
                row = data[1]
                result["name"] = row[0]
                result["total_population"] = int(row[1]) if row[1] != "-1" else None
                result["male"] = int(row[2]) if row[2] != "-1" else None
                result["female"] = int(row[3]) if row[3] != "-1" else None
                result["median_age"] = float(row[4]) if row[4] != "-1" else None
                result["white"] = int(row[5]) if row[5] != "-1" else None
                result["black"] = int(row[6]) if row[6] != "-1" else None
                result["native_american"] = int(row[7]) if row[7] != "-1" else None
                result["asian"] = int(row[8]) if row[8] != "-1" else None
                result["hispanic"] = int(row[9]) if row[9] != "-1" else None
                result["white_non_hispanic"] = int(row[10]) if row[10] != "-1" else None
    except Exception as e:
        result["census_error"] = str(e)

    # ACS S1903 — Median Income
    try:
        key_param = f"&key={api_key}" if api_key else ""
        url = (
            f"https://api.census.gov/data/2022/acs/acs5/subject"
            f"?get=NAME,S1903_C03_001E&for=county:{county_fips}"
            f"&in=state:{state_fips}{key_param}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1:
                val = data[1][1]
                result["median_household_income"] = int(val) if val != "-1" else None
    except Exception:
        pass

    # ACS S1701 — Poverty
    try:
        key_param = f"&key={api_key}" if api_key else ""
        url = (
            f"https://api.census.gov/data/2022/acs/acs5/subject"
            f"?get=NAME,S1701_C03_001E&for=county:{county_fips}"
            f"&in=state:{state_fips}{key_param}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1:
                val = data[1][1]
                result["poverty_rate_pct"] = float(val) if val != "-1" else None
    except Exception:
        pass

    return result


def fetch_fema_nri(fips: str) -> dict:
    """Fetch FEMA National Risk Index data for the county."""
    result = {"source": "FEMA National Risk Index (NRI)"}

    if not fips or len(fips) < 5:
        result["error"] = "Valid FIPS code required"
        return result

    try:
        state_fips = fips[:2]
        county_fips = fips[2:]
        geo_id = f"0500000US{fips}"

        # NRI County Boundaries with risk scores
        url = (
            "https://services.arcgis.com/ZzrwjT6KBLqz4n51/arcgis/rest/services/"
            "NRI_Boundaries/FeatureServer/0/query"
            f"?where=GEOID='{geo_id}'"
            "&outFields=CNTRYFIPS,CNTRYNAME,STATEFIPS,STATENAME,RISK_SCORE,"
            "RISK_RNKNG,ELP_RISK_SCORE,EAL_RISK_SCORE,SOVI_SCORE,"
            "EXPB,RISKVULN,EALRATNG,AVGREVX,AVGREVXB"
            "&returnGeometry=false&f=json"
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("features") and len(data["features"]) > 0:
                attrs = data["features"][0]["attributes"]
                result["county_name"] = attrs.get("CNTRYNAME")
                result["state_name"] = attrs.get("STATENAME")
                result["composite_risk_score"] = round(attrs.get("RISK_SCORE", 0), 2)
                result["risk_national_ranking"] = attrs.get("RISK_RNKNG")
                result["expected_annual_loss_score"] = round(attrs.get("EAL_RISK_SCORE", 0), 2)
                result["social_vulnerability_score"] = round(attrs.get("SOVI_SCORE", 0), 2)
                result["exposure_score"] = round(attrs.get("EXPB", 0), 2)
                result["risk_vulnerability"] = attrs.get("RISKVULN")
                result["annualized_building_loss"] = attrs.get("AVGREVX")
                result["annualized_building_loss_b"] = attrs.get("AVGREVXB")
            else:
                result["error"] = "County not found in FEMA NRI database"
    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_disaster_history(state_fips: str) -> dict:
    """Fetch FEMA disaster declaration summary for the state."""
    result = {"source": "FEMA Disaster Declarations"}
    try:
        url = (
            f"https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
            f"?$filter=stateCode%20eq%20%27{state_fips}%27"
            f"&$orderby=declarationDate%20desc&$top=20"
            f"&$select=disasterNumber,declarationDate,disasterType,"
            f"declarationTitle,incidentType,designatedArea"
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            declarations = data.get("DisasterDeclarationsSummaries", [])
            result["total_recent"] = len(declarations)
            result["recent_declarations"] = [
                {
                    "id": d.get("disasterNumber"),
                    "date": d.get("declarationDate"),
                    "type": d.get("incidentType"),
                    "title": d.get("declarationTitle"),
                    "area": d.get("designatedArea"),
                }
                for d in declarations[:10]
            ]
            # Count by type
            type_counts = {}
            for d in declarations:
                t = d.get("incidentType", "Unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            result["by_type"] = type_counts
    except Exception as e:
        result["error"] = str(e)

    return result


def build_county_profile(state_name: str, county_name: str) -> dict:
    """Build comprehensive county profile from multiple data sources."""
    state_fips = STATE_FIPS.get(state_name, "")
    fips = resolve_county_fips(state_name, county_name)

    demographics = fetch_census_demographics(state_name, county_name)
    nri = fetch_fema_nri(fips)
    disasters = fetch_disaster_history(state_fips) if state_fips else {}

    return {
        "state": state_name,
        "county": county_name,
        "fips": fips,
        "demographics": demographics,
        "risk_index": nri,
        "disaster_history": disasters,
    }


# ---------------------------------------------------------------------------
# DOCUMENT SUMMARIZATION (for long HMPs)
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = 14000) -> list:
    """Split text into chunks at paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current = current + "\n\n" + p if current else p
    if current.strip():
        chunks.append(current.strip())
    return chunks


def summarize_text(text: str) -> str:
    """Summarize text using OpenAI if available, otherwise truncate."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Fallback: return first 6000 chars
        return text[:6000] + ("\n\n[... truncated for length ...]" if len(text) > 6000 else "")

    try:
        client = OpenAI(api_key=api_key)
        if len(text) <= 12000:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Summarize this Hazard Mitigation Plan section, preserving ALL specific mitigation actions, hazard types, dollar amounts, timelines, responsible parties, and numerical data. Do not generalize — keep specifics."},
                    {"role": "user", "content": text[:12000]},
                ],
                max_tokens=2500,
                temperature=0.2,
            )
            return resp.choices[0].message.content
        else:
            chunks = chunk_text(text, 14000)
            summaries = []
            for chunk in chunks[:8]:  # Max 8 chunks to limit API calls
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Summarize this HMP section preserving ALL specific actions, hazards, dollar amounts, timelines, and responsible parties. Keep specifics."},
                        {"role": "user", "content": chunk},
                    ],
                    max_tokens=1500,
                    temperature=0.2,
                )
                summaries.append(resp.choices[0].message.content)

            # Combine summaries into a final summary
            combined = "\n\n".join(summaries)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Create a consolidated summary of this Hazard Mitigation Plan. Preserve ALL specific mitigation actions with their costs, timelines, responsible parties, and hazard types. This will be used for compliance analysis — do not lose details."},
                    {"role": "user", "content": combined},
                ],
                max_tokens=4000,
                temperature=0.2,
            )
            return resp.choices[0].message.content
    except Exception as e:
        return text[:6000] + f"\n\n[Summarization error: {str(e)} — using truncated text]"


# ---------------------------------------------------------------------------
# LLM DEEP ANALYSIS ENGINE
# ---------------------------------------------------------------------------

DEEP_ANALYSIS_SYSTEM_PROMPT = """You are FEMA-HMP-EXPERT, an elite-level emergency management analyst AI with 30+ years of combined expertise across:

• FEMA Hazard Mitigation Plan requirements (44 CFR Part 201.6 — all subsections)
• FEMA BRIC (Building Resilient Infrastructure and Communities) program — FY2024 guidance
• FEMA Hazard Mitigation Grant Program (HMGP), Flood Mitigation Assistance (FMA), Pre-Disaster Mitigation (PDM)
• STAPLEE evaluation framework (Social, Technical, Administrative, Political, Legal, Economic, Environmental)
• FEMA National Risk Index (NRI) methodology and scoring
• Benefit-Cost Analysis (BCA) per OMB Circular A-94 and FEMA BCA Toolkit
• Climate adaptation, future conditions planning, and the Resilient Communities and Preparedness (RCPM) framework
• Community Rating System (CRS), NFIP coordination
• State and local emergency management operations, including EMAP standards
• Social vulnerability (CDC/ATSDR SVI), environmental justice (EJScreen), and equity frameworks
• Robert T. Stafford Disaster Relief and Emergency Assistance Act

YOU HAVE BEEN PROVIDED WITH:
1. A county's Hazard Mitigation Plan (possibly summarized for length)
2. The county's official risk profile (FEMA NRI scores, demographics, disaster history)
3. A rules-based compliance scan identifying which FEMA requirements are present/weak/missing

YOUR TASK: Produce FOUR distinct depth layers of analysis. Each layer must be specific, evidence-based, and actionable. Reference specific sections, data points, or gaps. NEVER produce generic platitudes.

CRITICAL RULES:
- Reference specific data from the county profile (population, risk scores, poverty rates, disaster history)
- Reference specific compliance gaps found in the scan
- Reference specific text or absence of text in the HMP
- Name specific FEMA programs, CFR sections, and BRIC categories
- If the plan is weak, say so directly with evidence
- Produce actionable items a county emergency management director can act on THIS WEEK
- Never say "the plan should consider" — say "the plan MUST include X because Y"
- Quantify wherever possible

You MUST respond in valid JSON with this exact structure:
{
  "operational_rigor": {
    "score": <number 0-100>,
    "verdict": "<one sentence overall assessment>",
    "findings": [
      {
        "area": "<specific area name>",
        "observation": "<what you found or didn't find in the plan>",
        "gap_analysis": "<why this matters operationally>",
        "recommendation": "<specific, actionable fix>"
      }
    ],
    "mitigation_action_quality": "<assessment of how specific/implementable the mitigation actions are>",
    "implementation_readiness": "<assessment of whether the plan can actually be executed>",
    "timeline_feasibility": "<assessment of proposed timelines>"
  },
  "strategic_rigor": {
    "score": <number 0-100>,
    "verdict": "<one sentence overall assessment>",
    "findings": [
      {
        "area": "<strategic area>",
        "observation": "<what you found>",
        "gap_analysis": "<strategic implication>",
        "recommendation": "<strategic action>"
      }
    ],
    "risk_prioritization": "<how well does the plan prioritize risks vs. the county's actual risk profile>",
    "funding_strategy": "<assessment of the plan's approach to securing mitigation funding>",
    "long_term_vision": "<assessment of 5-10 year strategic direction>",
    "integration_assessment": "<how well does this integrate with comprehensive plans, CIP, etc.>"
  },
  "wisdom": {
    "score": <number 0-100>,
    "verdict": "<one sentence overall assessment>",
    "hidden_patterns": [
      "<pattern observed across the plan that reveals deeper issues>"
    ],
    "systemic_risks": [
      {
        "risk": "<systemic risk name>",
        "explanation": "<why this is a systemic risk for this specific county>",
        "early_warning_signs": "<what indicators to watch>"
      }
    ],
    "assumptions_to_challenge": [
      {
        "assumption": "<assumption the plan makes>",
        "why_question_it": "<why this assumption may be flawed>",
        "alternative": "<what to consider instead>"
      }
    ],
    "second_order_effects": [
      {
        "action": "<mitigation action from plan>",
        "intended_effect": "<what the plan says it will do>",
        "unintended_consequence": "<what could go wrong>",
        "mitigation": "<how to prevent the unintended consequence>"
      }
    ],
    "what_an_expert_would_notice": [
      "<specific thing an experienced EM director would flag immediately>"
    ],
    "cross_jurisdictional_insights": "<insights about how this county's plan relates to neighboring counties or regional patterns>"
  },
  "insights": {
    "score": <number 0-100>,
    "verdict": "<one sentence overall assessment>",
    "top_insights": [
      {
        "insight": "<the insight in one clear sentence>",
        "why_it_matters": "<concrete impact if addressed or ignored>",
        "action_for_director": "<specific action the county director can take this week>",
        "funding_link": "<specific FEMA/BRIC/funding program this connects to, or null>"
      }
    ],
    "funding_opportunities": [
      {
        "program": "<specific FEMA or federal program name>",
        "category": "<BRIC/HMGP/FMA/PDM/other>",
        "what_county_can_pursue": "<specific project type this county could pursue>",
        "estimated_competitiveness": "<high/medium/low based on the county profile>",
        "what_plan_needs": "<what the HMP needs to include to be competitive>"
      }
    ],
    "political_levers": [
      {
        "lever": "<specific political/administrative action>",
        "who_to_engage": "<specific role/office>",
        "talking_point": "<specific argument to make>"
      }
    ],
    "quick_wins": [
      "<action that can be done in <30 days to improve the plan>"
    ],
    "six_month_roadmap": [
      "<month 1 action>",
      "<month 2-3 action>",
      "<month 4-6 action>"
    ]
  }
}"""


def run_deep_analysis(text: str, county_profile: dict,
                      compliance: dict, bric: dict,
                      metadata: dict) -> dict:
    """Run the 4-layer deep analysis using OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "error": "OPENAI_API_KEY environment variable not set on Vercel. "
                     "Deep analysis requires an OpenAI API key. "
                     "The compliance scan results are still available.",
            "operational_rigor": None,
            "strategic_rigor": None,
            "wisdom": None,
            "insights": None,
        }

    # Summarize the document if long
    doc_for_llm = summarize_text(text)

    # Build county context string
    cp = county_profile
    nri = cp.get("risk_index", {})
    demo = cp.get("demographics", {})
    disasters = cp.get("disaster_history", {})

    county_context = f"""COUNTY PROFILE: {cp.get('county', 'Unknown')}, {cp.get('state', 'Unknown')}
FIPS Code: {cp.get('fips', 'Unknown')}

DEMOGRAPHICS (Census ACS):
- Population: {demo.get('total_population', 'N/A')}
- Median Age: {demo.get('median_age', 'N/A')}
- Median Household Income: {demo.get('median_household_income', 'N/A')}
- Poverty Rate: {demo.get('poverty_rate_pct', 'N/A')}%
- White: {demo.get('white', 'N/A')}, Black: {demo.get('black', 'N/A')}, Hispanic: {demo.get('hispanic', 'N/A')}, Asian: {demo.get('asian', 'N/A')}, Native American: {demo.get('native_american', 'N/A')}

FEMA NATIONAL RISK INDEX:
- Composite Risk Score: {nri.get('composite_risk_score', 'N/A')} (National Percentile Rank: {nri.get('risk_national_ranking', 'N/A')})
- Expected Annual Loss Score: {nri.get('expected_annual_loss_score', 'N/A')}
- Social Vulnerability Score: {nri.get('social_vulnerability_score', 'N/A')}
- Exposure Score: {nri.get('exposure_score', 'N/A')}
- Annualized Building Loss: {nri.get('annualized_building_loss', 'N/A')}

RECENT DISASTER DECLARATIONS (last 20 for state):
- Total: {disasters.get('total_recent', 'N/A')}
- By Type: {json.dumps(disasters.get('by_type', {}), default=str)}
- Recent: {json.dumps(disasters.get('recent_declarations', [])[:5], default=str)}"""

    # Build compliance context
    missing_items = [item for item in compliance["items"] if item["status"] == "missing"]
    weak_items = [item for item in compliance["items"] if item["status"] == "weak"]
    bric_missing = [item for item in bric["items"] if item["status"] == "missing"]
    bric_weak = [item for item in bric["items"] if item["status"] == "weak"]

    compliance_context = f"""COMPLIANCE SCAN RESULTS:
FEMA 44 CFR Compliance Score: {compliance['score']}/100
MISSING FEMA Requirements ({len(missing_items)}):
{chr(10).join(f"  - [{m['category']}] {m['requirement']}" for m in missing_items)}
WEAK FEMA Requirements ({len(weak_items)}):
{chr(10).join(f"  - [{w['category']}] {w['requirement']}" for w in weak_items)}

BRIC READINESS Score: {bric['score']}/100
MISSING BRIC Criteria ({len(bric_missing)}):
{chr(10).join(f"  - [{b['category']}] {b['requirement']}" for b in bric_missing)}
WEAK BRIC Criteria ({len(bric_weak)}):
{chr(10).join(f"  - [{b['category']}] {b['requirement']}" for b in bric_weak)}"""

    # Metadata context
    meta_context = f"""PLAN METADATA:
- Word Count: {metadata['word_count']}
- Headings Found: {metadata['heading_count']}
- Dollar Amounts Found: {metadata['dollar_amounts']}
- Plan Period: {metadata['plan_years']}
- Detected Jurisdiction: {metadata['detected_jurisdiction']}
- Sections: {', '.join(metadata['headings'][:15])}"""

    user_message = f"""Analyze the following Hazard Mitigation Plan with all four depth layers.

{county_context}

{compliance_context}

{meta_context}

HAZARD MITIGATION PLAN TEXT:
{doc_for_llm}

Produce the complete JSON analysis with all four depth layers: operational_rigor, strategic_rigor, wisdom, and insights. Be specific, evidence-based, and actionable. Reference the county data and compliance gaps directly."""

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": DEEP_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=6000,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        result = json.loads(raw)
        return result
    except json.JSONDecodeError as e:
        return {
            "error": f"LLM returned invalid JSON: {str(e)}",
            "raw_response": raw[:2000] if 'raw' in dir() else "unavailable",
            "operational_rigor": None,
            "strategic_rigor": None,
            "wisdom": None,
            "insights": None,
        }
    except Exception as e:
        return {
            "error": f"LLM analysis failed: {str(e)}",
            "operational_rigor": None,
            "strategic_rigor": None,
            "wisdom": None,
            "insights": None,
        }


# ---------------------------------------------------------------------------
# FLASK ROUTES
# ---------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def handle_analyze():
    """Main analysis endpoint — runs pre-scan + county data + deep LLM analysis."""
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        action = data.get("action", "full")

        # ── Action: states list ──
        if action == "states":
            return jsonify({"states": sorted(STATE_FIPS.keys())}), 200

        text = data.get("text", "").strip()
        state = data.get("state", "").strip()
        county = data.get("county", "").strip()

        if not text:
            return jsonify({"error": "No document text provided"}), 400
        if len(text) < 50:
            return jsonify({"error": "Text too short for analysis (min 50 characters)"}), 400

        # ── Step 1: Pre-scan (fast, rules-based) ──
        compliance = scan_compliance(text)
        bric = scan_bric(text)
        metadata = extract_plan_metadata(text)

        pre_scan = {
            "compliance": compliance,
            "bric": bric,
            "metadata": metadata,
        }

        # ── Action: preprocess only (no LLM, no county data) ──
        if action == "preprocess":
            return jsonify({"pre_scan": pre_scan}), 200

        # ── Step 2: County profile (if state/county provided) ──
        county_profile = {}
        if state and county:
            county_profile = build_county_profile(state, county)

        # ── Action: county-data only ──
        if action == "county-data":
            if not state or not county:
                return jsonify({"error": "State and county required for county data lookup"}), 400
            return jsonify({"county_profile": county_profile}), 200

        # ── Step 3: Deep LLM analysis ──
        if action == "deep":
            deep = run_deep_analysis(text, county_profile, compliance, bric, metadata)
            return jsonify({
                "pre_scan": pre_scan,
                "county_profile": county_profile,
                "deep_analysis": deep,
            }), 200

        # ── Default: full analysis ──
        deep = run_deep_analysis(text, county_profile, compliance, bric, metadata)

        # Calculate overall readiness
        combined_score = round(
            compliance["score"] * 0.35 +
            bric["score"] * 0.25 +
            (deep.get("operational_rigor", {}).get("score", 0) or 0) * 0.15 +
            (deep.get("strategic_rigor", {}).get("score", 0) or 0) * 0.15 +
            (deep.get("wisdom", {}).get("score", 0) or 0) * 0.05 +
            (deep.get("insights", {}).get("score", 0) or 0) * 0.05
        )

        if combined_score >= 75:
            readiness = "ready"
            label = "✅ READY — Plan meets most FEMA requirements and demonstrates strong mitigation capability"
        elif combined_score >= 50:
            readiness = "conditional"
            label = "⚠️ CONDITIONAL — Plan has significant gaps that should be addressed before FEMA review"
        else:
            readiness = "not-ready"
            label = "❌ NOT READY — Plan has critical deficiencies; major revision recommended before submission"

        return jsonify({
            "overall_score": combined_score,
            "readiness": readiness,
            "readiness_label": label,
            "pre_scan": pre_scan,
            "county_profile": county_profile,
            "deep_analysis": deep,
        }), 200

    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    return jsonify({
        "status": "ok",
        "service": "fema-hmp-analyzer",
        "openai_configured": has_key,
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
