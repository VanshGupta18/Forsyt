Great question. Let me think through this practically.

---

## The Core Problem with 15-Minute GPR

```
GDELT updates every 15 minutes
BUT
GPR is fundamentally a daily/monthly concept

Why?
  Single articles are noisy
  15-minute windows have very few articles
  Index will spike and crash randomly
  Signal-to-noise ratio is extremely poor
```

---

## What Happens at Different Frequencies

### 15-Minute GPR
```
Window: ~50-200 articles
Problem:
  One viral article about war → index spikes to 400
  Next 15 minutes calm news → index drops to 20
  This is noise, not geopolitical risk signal

Usable for: Nothing meaningful
```

### Hourly GPR
```
Window: ~200-800 articles
Still too small for stable signal
Major breaking news creates artificial spikes
Calms down too quickly after event

Usable for: Detecting breaking news only
            Not true GPR measurement
```

### Daily GPR
```
Window: ~50,000-200,000 articles
This is the correct granularity
Smooths intra-day noise
Captures genuine risk elevation
Matches Caldara and Iacoviello methodology exactly

Usable for: True GPR index
            Research applications
            Dashboard primary metric
```

### Weekly/Monthly GPR
```
Most stable signal
Used for macroeconomic analysis
Too slow for a dashboard

Usable for: Trend analysis
            Academic research
            Policy applications
```

---

## Recommended Architecture for Real-Time Dashboard

The answer is not either/or. Use a layered approach:

```
Layer 1: 15-minute raw feed
         → Article ingestion only
         → No index calculation
         → Just store scored articles

Layer 2: Hourly rolling window
         → Breaking news alert only
         → NOT presented as GPR index
         → Triggers notification if
           something major happens

Layer 3: Daily GPR index (PRIMARY)
         → Calculated once per day
         → This is your main dashboard metric
         → Updated at end of each day
         → What you show as the GPR index

Layer 4: 7-day and 30-day moving average
         → Trend lines on dashboard
         → Updated daily alongside Layer 3
```

---

## What Your Dashboard Should Show

```
┌─────────────────────────────────────────────────────┐
│              INDIA GPR DASHBOARD                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TODAY'S GPR INDEX: 142  ▲ +12 from yesterday      │
│  (Updated daily at 00:00 UTC)                       │
│                                                     │
├─────────────────────────────────────────────────────┤
│  30-day trend: [line chart]                         │
│  Acts vs Threats: [dual line]                       │
│  Country breakdown: [bar chart]                     │
├─────────────────────────────────────────────────────┤
│  ⚡ BREAKING NEWS ALERT (last 2 hours):             │
│  "India-Pakistan border tensions escalating"        │
│  Detected from 23 articles — GPR spike likely       │
│  (This is NOT the GPR index — alert only)           │
├─────────────────────────────────────────────────────┤
│  TOP GEOPOLITICAL ARTICLES TODAY: [list]            │
│  Article 1: score 0.87 — [headline] — [source]     │
│  Article 2: score 0.79 — [headline] — [source]     │
│  Article 3: score 0.74 — [headline] — [source]     │
└─────────────────────────────────────────────────────┘
```

---

## Breaking News Alert Logic

This is how you give users real-time feel without compromising index integrity:

```
Every 15 minutes:
  → Ingest new articles
  → Score each article
  → Check: are there 5+ articles with score > 0.70
           in the last 2 hours?
  → If YES: trigger breaking news alert
            show top articles
            flag "GPR spike likely tomorrow"
  → If NO:  continue normal ingestion
            no alert shown

This gives real-time responsiveness
without misrepresenting the GPR index frequency
```

---

## Pipeline Timing Design

```
Every 15 minutes:
  Scraper runs
  New articles fetched
  Articles scored
  Stored in database
  Breaking news check runs

Once per day (midnight UTC or 6am IST):
  Pull all articles from past 24 hours
  Compute daily GPR index
  Update all decompositions
    (country, event type, acts/threats)
  Update 7-day and 30-day moving averages
  Publish to dashboard
  Archive daily record

Once per week:
  Compute weekly summary statistics
  Update trend analysis
  Generate weekly GPR report
```

---

## Bottom Line

```
Real-time (15 min):  Article ingestion + scoring + breaking news alerts
Daily:               Actual GPR index calculation (primary metric)
Weekly/Monthly:      Trend analysis and summary

Never present 15-minute or hourly data as the GPR index
It will look broken and mislead users

The daily update IS real-time enough for a GPR index
Geopolitical risk does not change meaningfully
in 15-minute windows — it evolves over days
```

This also directly mirrors how GDELT itself publishes its own risk indicators — raw data every 15 minutes but meaningful indices at daily frequency.