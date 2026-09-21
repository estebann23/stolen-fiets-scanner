Apify Ingestion Engine Integration Guide (apify-integration.md)
This guide details the integration of Apify into the Velox Maastricht Next.js architecture. It covers client configuration, Route Handlers, schema normalization, targeted border actors, and stage-resilient failover mechanisms.
1. Overview & Architectural Role
Within the Velox forensic pipeline, Apify operates as the external perimeter crawler across second-hand classified platforms (Marktplaats, 2ememain, Kleinanzeigen).
To prevent live presentation latency (scraping runs taking 20–45s) from interrupting the 2-minute pitch:
Production Mode: Apify runs on a recurring schedule, persisting scraped marketplace data into an Apify Dataset.
Stage / Demo Mode: The Next.js Route Handler reads directly from a pre-populated Apify Dataset (or falls back deterministically to in-memory mocks if the network drops).
┌──────────────────────────────────────────────────────────┐
│              Euregio Classifieds Platforms               │
│      (Marktplaats.nl, 2ememain.be, Kleinanzeigen.de)     │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│                   Apify Actor Network                    │
│      - haketa/marktplaats-scraper (NL / BE)              │
│      - beatanalytics/kleinanzeigen-scraper (DE)          │
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
2. Selected Apify Actors & Store Links
Territory / Platform	Selected Actor & Store Link	Execution Method	Key Search Parameters
Netherlands & Belgium


(Marktplaats.nl, 2ememain.be, 2dehands.be)

haketa/marktplaats-scraper	Direct internal JSON API (/lrp/api/search)	searchQuery: "Gazelle", postcode: "6211", distanceMeters: 30000
Germany (Aachen Border)


(Kleinanzeigen.de)

beatanalytics/kleinanzeigen-scraper	HTTP search endpoints with radius	searchKeywords: ["Fahrrad"], searchLocations: ["52062"], searchRadius: 30
3. Package Installation & Credentials
Install the official Node.js client:
Bash
npm install apify-client
Add your credentials to .env.local (never expose these with NEXT_PUBLIC_):
Code-Snippet
# Apify Personal API Token (Console -> Settings -> Integrations)
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Default Dataset ID pre-populated by your preparation run
APIFY_DATASET_ID=your_dataset_id_here

# Selected Actor IDs
APIFY_MARKTPLAATS_ACTOR_ID=haketa/marktplaats-scraper
APIFY_KLEINANZEIGEN_ACTOR_ID=beatanalytics/kleinanzeigen-scraper
Ensure .env.local is listed in your .gitignore.
4. Client Singleton (src/lib/apify.ts)
Create a singleton client instance to reuse across Route Handlers:
TypeScript
import { ApifyClient } from 'apify-client';

const token = process.env.APIFY_API_TOKEN;

if (!token && process.env.NODE_ENV !== 'production') {
  console.warn('[Velox] Warning: APIFY_API_TOKEN is not defined in environment variables.');
}

export const apify = new ApifyClient({
  token: token || '',
});
5. Route Handler: Ingestion & Live Scrape Trigger
Create src/app/api/scrape/route.ts to manage fetching and executing tasks.
TypeScript
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
  const marktplaatsActorId = process.env.APIFY_MARKTPLAATS_ACTOR_ID || 'haketa/marktplaats-scraper';

  try {
    const { query = 'fiets', location = '6211', maxResults = 5 } = await req.json();

    // Trigger haketa/marktplaats-scraper with internal JSON API speed
    const run = await apify.actor(marktplaatsActorId).call(
      {
        searchQuery: query,
        postcode: location,
        distanceMeters: 30000,
        maxResults: maxResults,
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
6. Schema Normalization Mapper (src/lib/apify-mapper.ts)
Converts scraper outputs into Velox’s strict MarketplaceListing contract:
TypeScript
import { MarketplaceListing } from '@/lib/scan-types';

export function mapApifyItemToListing(raw: any): MarketplaceListing {
  // Infer origin platform & country
  const platform = raw.platform || 
    (raw.url?.includes('2ememain') ? '2ememain' :
     raw.url?.includes('kleinanzeigen') ? 'Kleinanzeigen' : 'Marktplaats');

  const originCountry = 
    platform === '2ememain' ? 'BE' :
    platform === 'Kleinanzeigen' ? 'DE' : 'NL';

  // Distance estimation relative to Maastricht center (Vrijthof)
  const distanceKm = typeof raw.distanceKm === 'number' 
    ? raw.distanceKm 
    : (originCountry === 'BE' ? 28 : originCountry === 'DE' ? 32 : 4);

  // Compass bearing (Liège = ~205°, Aachen = ~115°, Maastricht = ~45°)
  const bearingDeg = typeof raw.bearingDeg === 'number'
    ? raw.bearingDeg
    : (originCountry === 'BE' ? 205 : originCountry === 'DE' ? 115 : 45);

  // Parse EUR price (handles integer cents from haketa or formatted strings)
  let price = 0;
  if (typeof raw.priceCents === 'number') {
    price = raw.priceCents / 100;
  } else if (raw.price) {
    price = parseFloat(String(raw.price).replace(/[^0-9.]/g, '')) || 0;
  }

  return {
    id: raw.id || raw.itemId || String(raw.url ? Buffer.from(raw.url).toString('base64').slice(0, 16) : Math.random()),
    platform,
    originCountry,
    title: raw.title || 'Unknown Bike Listing',
    rawDescription: raw.description || raw.categorySpecificDescription || '',
    normalizedTokens: [], // Populated downstream by Euregio Language Agent
    priceEur: price,
    location: {
      city: raw.location?.city || raw.city || (originCountry === 'BE' ? 'Liège' : originCountry === 'DE' ? 'Aachen' : 'Maastricht'),
      distanceKm,
      bearingDeg,
    },
    postedTimestamp: raw.date || raw.publishedAt || new Date().toISOString(),
    sellerAccountAgeDays: parseInt(raw.sellerAccountAgeDays, 10) || 12,
    imageUrl: raw.imageUrls?.[0] || raw.imageUrl || raw.images?.[0] || '/demo-peugeot.jpg',
    markers: [],
  };
}
7. Jury Defense & Architecture Alignment
When demonstrating or explaining the Apify integration to the panel:
For Prof. Dr. Anna Wilbik (Data Fusion & Systems):
"Live scraping in production introduces external network variance and varying schema densities. Our ingestion layer uses Apify for continuous web polling, but decouples ingestion from decision logic: raw crawled payloads are normalized via our canonical taxonomy mapper into uniform feature vectors before entering the multi-source fusion engine."

For Jean-Maurice Henkel (Unit Economics & Feasibility):
"Real-time scraping of thousands of high-resolution images during an active user query is computationally inefficient. We utilize a tiered model: Apify continuously ingests low-bandwidth metadata into an indexed dataset cache, and heavy visual forensic inference is triggered exclusively when high-probability candidates pass initial price and geographic filters."
