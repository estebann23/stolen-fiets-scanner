# Apify Ingestion Engine Integration Guide (`apify-integration.md`)

This guide details the integration of **Apify** into the Velox Maastricht Next.js architecture. It covers client configuration, Route Handlers, schema normalization, and stage-resilient failover mechanisms.

---

## 1. Overview & Architectural Role

Within the Velox forensic pipeline, Apify operates as the **external perimeter crawler** across second-hand classified platforms (*Marktplaats*, *2ememain*, *Kleinanzeigen*).

To prevent live presentation latency (scraping runs taking 20–45s) from interrupting the 2-minute pitch:

* **Production Mode:** Apify runs on a recurring schedule (or webhook trigger), persisting scraped marketplace data into an Apify Dataset.
* **Stage / Demo Mode:** The Next.js Route Handler reads directly from the pre-populated Apify Dataset (or falls back deterministically to in-memory mocks if the network drops).

```
┌──────────────────────────────────────────────────────────┐
│              Euregio Classifieds Platforms               │
│      (Marktplaats.nl, 2ememain.be, Kleinanzeigen.de)      │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Apify Actor Network                    │
│      - Scheduled / On-Demand Crawlers                    │
│      - Proxy Rotation & Anti-Scraping Bypass             │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Apify Dataset Store                    │
│          (Raw JSON payloads of scraped listings)         │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼  GET /api/scrape (or via /api/scan)
┌──────────────────────────────────────────────────────────┐
│              Velox Next.js 16 API Layer                  │
│   1. Fetch from Dataset via apify-client                 │
│   2. Map to canonical MarketplaceListing contract        │
│   3. Pass to Euregio Language Agent & Data Fusion Engine │
└──────────────────────────────────────────────────────────┘

```

---

## 2. Package Installation & Credentials

Install the official Node.js client:

```bash
npm install apify-client

```

Add your credentials to `.env.local` (**never** expose these with `NEXT_PUBLIC_`):

```env
# Apify Personal API Token (found in Apify Console -> Settings -> Integrations)
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Default Dataset ID populated by scheduled actor runs
APIFY_DATASET_ID=your_dataset_id_here

# Optional: Target Actor ID for on-demand trigger runs
APIFY_ACTOR_ID=your_actor_id_here

```

Ensure `.env.local` is listed in your `.gitignore`.

---

## 3. Client Singleton (`src/lib/apify.ts`)

Create a singleton client instance to reuse across Route Handlers:

```typescript
import { ApifyClient } from 'apify-client';

const token = process.env.APIFY_API_TOKEN;

if (!token && process.env.NODE_ENV !== 'production') {
  console.warn('[Velox] Warning: APIFY_API_TOKEN is not defined in environment variables.');
}

export const apify = new ApifyClient({
  token: token || '',
});

```

---

## 4. Route Handler: Ingestion & Live Scrape Trigger

Create `src/app/api/scrape/route.ts` to manage fetching and executing tasks.

```typescript
import { NextResponse } from 'next/server';
import { apify } from '@/lib/apify';
import { mapApifyItemToListing } from '@/lib/apify-mapper';
import { FALLBACK_MARKETPLACE_LISTINGS } from '@/lib/mock-data';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const datasetId = process.env.APIFY_DATASET_ID;

  // Fallback immediately if dataset is unconfigured
  if (!datasetId) {
    return NextResponse.json({
      success: true,
      source: 'deterministic-mock',
      items: FALLBACK_MARKETPLACE_LISTINGS,
    });
  }

  try {
    // 1. Ingest latest 20 items from persistent Apify dataset
    const dataset = await apify.dataset(datasetId).listItems({
      limit: 20,
      desc: true,
    });

    if (!dataset.items || dataset.items.length === 0) {
      throw new Error('Dataset returned 0 items');
    }

    // 2. Map raw scraped payloads to canonical Velox schema
    const listings = dataset.items.map(mapApifyItemToListing);

    return NextResponse.json({
      success: true,
      source: 'apify-dataset',
      count: listings.length,
      items: listings,
    });
  } catch (error: any) {
    console.error('[Velox Ingestion] Apify fetch failed, engaging fallback:', error.message);
    
    // Stage-resilient fallback
    return NextResponse.json({
      success: true,
      source: 'deterministic-fallback',
      items: FALLBACK_MARKETPLACE_LISTINGS,
    });
  }
}

export async function POST(req: Request) {
  const actorId = process.env.APIFY_ACTOR_ID;

  if (!actorId) {
    return NextResponse.json(
      { success: false, error: 'APIFY_ACTOR_ID not configured' },
      { status: 400 }
    );
  }

  try {
    const { query = 'Gazelle', location = 'Maastricht', maxResults = 5 } = await req.json();

    // Trigger on-demand Actor run with a strict execution cap
    const run = await apify.actor(actorId).call(
      {
        searchQuery: query,
        location,
        maxItems: maxResults,
      },
      {
        timeoutSecs: 25,
      }
    );

    const { items } = await apify.dataset(run.defaultDatasetId).listItems();
    const listings = items.map(mapApifyItemToListing);

    return NextResponse.json({
      success: true,
      source: 'live-apify-run',
      count: listings.length,
      items: listings,
    });
  } catch (error: any) {
    console.error('[Velox Scraper] On-demand run error:', error.message);
    return NextResponse.json({
      success: false,
      error: error.message || 'Apify run failed',
      fallback: FALLBACK_MARKETPLACE_LISTINGS,
    }, { status: 500 });
  }
}

```

---

## 5. Schema Normalization Mapper (`src/lib/apify-mapper.ts`)

Converts diverse scraper outputs (different HTML structures, currencies, languages) into Velox’s strict `MarketplaceListing` contract:

```typescript
import { MarketplaceListing } from '@/lib/scan-types';

export function mapApifyItemToListing(raw: any): MarketplaceListing {
  // Infer origin platform & country
  const platform = raw.platform || 
    (raw.url?.includes('2ememain') ? '2ememain' :
     raw.url?.includes('kleinanzeigen') ? 'Kleinanzeigen' : 'Marktplaats');

  const originCountry = 
    platform === '2ememain' ? 'BE' :
    platform === 'Kleinanzeigen' ? 'DE' : 'NL';

  // Distance estimation fallback relative to Maastricht (Vrijthof center)
  const distanceKm = typeof raw.distanceKm === 'number' 
    ? raw.distanceKm 
    : (originCountry === 'BE' ? 28 : originCountry === 'DE' ? 32 : 4);

  // Compass bearing estimation (Liège = ~200°, Aachen = ~110°, Maastricht = ~0°)
  const bearingDeg = typeof raw.bearingDeg === 'number'
    ? raw.bearingDeg
    : (originCountry === 'BE' ? 205 : originCountry === 'DE' ? 115 : 45);

  return {
    id: raw.id || String(raw.url ? Buffer.from(raw.url).toString('base64').slice(0, 16) : Math.random()),
    platform,
    originCountry,
    title: raw.title || 'Unknown Listing',
    rawDescription: raw.description || raw.text || '',
    normalizedTokens: [], // Populated downstream by the Euregio Language Agent
    priceEur: parseFloat(String(raw.price).replace(/[^0-9.]/g, '')) || 0,
    location: {
      city: raw.city || (originCountry === 'BE' ? 'Liège' : originCountry === 'DE' ? 'Aachen' : 'Maastricht'),
      distanceKm,
      bearingDeg,
    },
    postedTimestamp: raw.publishedAt || raw.date || new Date().toISOString(),
    sellerAccountAgeDays: parseInt(raw.sellerAccountAgeDays, 10) || 12,
    imageUrl: raw.imageUrl || raw.image || raw.images?.[0] || '/demo-peugeot.jpg',
    markers: [],
  };
}

```

---

## 6. Jury Defense & Architecture Alignment

When demonstrating or explaining the Apify integration to the panel:

* **For Prof. Dr. Anna Wilbik (Data Fusion & Robustness):**
> *"Live scraping in production introduces external network variance and varying schema densities. Our ingestion layer uses Apify for continuous web polling, but decouples ingestion from decision logic: raw crawled payloads are normalized via our canonical taxonomy mapper into uniform feature vectors before entering the multi-source fusion engine."*


* **For Jean-Maurice Henkel (Unit Economics & Feasibility):**
> *"Real-time scraping of thousands of high-resolution images during an active user query is computationally inefficient. We utilize a tiered model: Apify continuously ingests low-bandwidth metadata into an indexed dataset cache, and heavy visual forensic inference is triggered exclusively when high-probability candidates pass initial price and geographic filters."*
