/**
 * AI Pick Vault — multi-retailer price API (Cloudflare Worker)
 *
 * eBay Browse API (live + daily snapshot):
 *   NEW + free US shipping + Buy It Now + US location
 *
 * Amazon (optional, daily snapshot via PA-API 5.0):
 *   Set AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG
 *
 * Secrets:
 *   EBAY_CLIENT_ID, EBAY_CLIENT_SECRET
 *   EBAY_CAMPID (optional)
 *   AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_PARTNER_TAG (optional)
 *
 * Endpoints:
 *   GET  /health
 *   GET  /v1/snapshot          daily JSON for the whole catalog
 *   POST /v1/refresh           run refresh now (optional header X-Refresh-Token)
 *   GET  /v1/price?q=&id=
 *   POST /v1/prices           { items: [{ id, q }, ...] }
 *
 * Cron: daily full catalog refresh → KV key "daily"
 */

import catalog from "./catalog.json";

const EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token";
const EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search";
const OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope";
const CACHE_TTL_SECONDS = 6 * 60 * 60;
const MAX_BATCH = 40;
const SEARCH_LIMIT = 20;
const KV_KEY = "daily";
const CONCURRENCY = 3;

let tokenCache = { accessToken: null, expiresAt: 0 };

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }));
    }

    try {
      const url = new URL(request.url);
      const path = url.pathname.replace(/\/+$/, "") || "/";

      if (path === "/health" || path === "/") {
        const snap = env.PRICES ? await env.PRICES.get(KV_KEY, "json") : null;
        return json({
          ok: true,
          service: "aipickvault-ebay",
          filters: "NEW + free shipping + US location + Buy It Now",
          ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
          amazonConfigured: amazonConfigured(env),
          catalogSize: Array.isArray(catalog) ? catalog.length : 0,
          lastSnapshotAt: snap?.updatedAt || null,
          snapshotCount: snap?.count || 0,
        });
      }

      if (path === "/v1/snapshot" && request.method === "GET") {
        if (!env.PRICES) {
          return json({ error: "kv_not_bound", message: "PRICES KV not configured" }, 503);
        }
        const snap = await env.PRICES.get(KV_KEY, "json");
        if (!snap) {
          // First visit before cron: kick off refresh in background
          ctx.waitUntil(refreshCatalog(env, ctx));
          return json({
            ok: false,
            error: "snapshot_empty",
            message: "Daily snapshot not ready yet — refresh started",
          }, 503);
        }
        return withCors(
          new Response(JSON.stringify(snap), {
            status: 200,
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "Cache-Control": "public, max-age=300",
            },
          })
        );
      }

      if (path === "/v1/refresh" && (request.method === "POST" || request.method === "GET")) {
        const required = (env.REFRESH_TOKEN || "").trim();
        if (required) {
          const got = request.headers.get("X-Refresh-Token") || url.searchParams.get("token") || "";
          if (got !== required) return json({ error: "unauthorized" }, 401);
        }
        const result = await refreshCatalog(env, ctx);
        return json(result);
      }

      if (!env.EBAY_CLIENT_ID || !env.EBAY_CLIENT_SECRET) {
        return json(
          {
            error: "missing_credentials",
            message: "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET with wrangler secret put",
          },
          503
        );
      }

      if (path === "/v1/price" && request.method === "GET") {
        const q = (url.searchParams.get("q") || "").trim();
        const id = (url.searchParams.get("id") || q).trim();
        if (!q) return json({ error: "missing_q" }, 400);
        const result = await getLowestPrice(q, id, env, ctx);
        return json(result);
      }

      if (path === "/v1/prices" && request.method === "POST") {
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "invalid_json" }, 400);
        }
        const raw = Array.isArray(body?.items) ? body.items : [];
        if (!raw.length) return json({ error: "empty_items" }, 400);
        if (raw.length > MAX_BATCH) {
          return json({ error: "too_many_items", max: MAX_BATCH }, 400);
        }

        const items = [];
        const seen = new Set();
        for (const it of raw) {
          const q = String(it?.q || it?.name || "").trim();
          const id = String(it?.id || it?.asin || q).trim();
          if (!q || !id || seen.has(id)) continue;
          seen.add(id);
          items.push({ id, q });
        }

        const prices = {};
        let idx = 0;
        async function worker() {
          while (idx < items.length) {
            const i = idx++;
            const { id, q } = items[i];
            try {
              prices[id] = await getLowestPrice(q, id, env, ctx);
            } catch (err) {
              prices[id] = { ok: false, id, q, error: String(err?.message || err) };
            }
          }
        }
        await Promise.all(
          Array.from({ length: Math.min(CONCURRENCY, items.length) }, () => worker())
        );

        return json({
          ok: true,
          count: Object.keys(prices).length,
          filters: "NEW + free shipping + US + Buy It Now",
          cacheTtlSeconds: CACHE_TTL_SECONDS,
          prices,
        });
      }

      return json({ error: "not_found" }, 404);
    } catch (err) {
      return json({ error: "server_error", message: String(err?.message || err) }, 500);
    }
  },

  /** Cloudflare Cron Trigger — daily full refresh */
  async scheduled(event, env, ctx) {
    ctx.waitUntil(refreshCatalog(env, ctx));
  },
};

async function refreshCatalog(env, ctx) {
  const started = Date.now();
  const items = Array.isArray(catalog) ? catalog : [];
  const prices = {};
  const errors = [];

  // eBay
  if (env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET) {
    let idx = 0;
    async function ebayWorker() {
      while (idx < items.length) {
        const i = idx++;
        const { id, q } = items[i];
        try {
          const row = await getLowestPrice(q, id, env, ctx, { skipCacheRead: true });
          if (!prices[id]) prices[id] = { id, q };
          if (row?.ok && isFinite(Number(row.price))) {
            prices[id].ebay = Number(row.price);
            prices[id].ebayOk = true;
            prices[id].ebayTitle = row.title || null;
          } else {
            prices[id].ebayOk = false;
            prices[id].ebayError = row?.error || "no_price";
          }
        } catch (err) {
          if (!prices[id]) prices[id] = { id, q };
          prices[id].ebayOk = false;
          prices[id].ebayError = String(err?.message || err);
          errors.push({ id, retailer: "ebay", error: String(err?.message || err) });
        }
      }
    }
    await Promise.all(
      Array.from({ length: Math.min(CONCURRENCY, items.length || 1) }, () => ebayWorker())
    );
  }

  // Amazon PA-API (optional)
  if (amazonConfigured(env)) {
    try {
      const amazonMap = await fetchAmazonPrices(
        items.map((x) => x.id),
        env
      );
      for (const id of Object.keys(amazonMap)) {
        if (!prices[id]) {
          const cat = items.find((x) => x.id === id);
          prices[id] = { id, q: cat?.q || id };
        }
        const a = amazonMap[id];
        if (a?.ok) {
          prices[id].amazon = a.price;
          prices[id].amazonOk = true;
          prices[id].amazonList = a.list || null;
          prices[id].amazonTitle = a.title || null;
        } else {
          prices[id].amazonOk = false;
          prices[id].amazonError = a?.error || "no_price";
        }
      }
    } catch (err) {
      errors.push({ retailer: "amazon", error: String(err?.message || err) });
    }
  }

  const snapshot = {
    ok: true,
    updatedAt: new Date().toISOString(),
    count: Object.keys(prices).length,
    amazonConfigured: amazonConfigured(env),
    ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
    durationMs: Date.now() - started,
    prices,
    errors: errors.slice(0, 20),
  };

  if (env.PRICES) {
    await env.PRICES.put(KV_KEY, JSON.stringify(snapshot));
  }

  return {
    ok: true,
    updatedAt: snapshot.updatedAt,
    count: snapshot.count,
    amazonConfigured: snapshot.amazonConfigured,
    durationMs: snapshot.durationMs,
    errorCount: errors.length,
  };
}

async function getLowestPrice(q, id, env, ctx, opts = {}) {
  const cacheKeyUrl = `https://aipickvault-ebay-cache.internal/v1/${hashKey(q)}`;
  const cache = caches.default;
  const cacheReq = new Request(cacheKeyUrl, { method: "GET" });

  if (!opts.skipCacheRead) {
    const hit = await cache.match(cacheReq);
    if (hit) {
      const data = await hit.json();
      return { ...data, source: "cache", id, q };
    }
  }

  const token = await getAccessToken(env);
  const filter = [
    "conditions:{NEW}",
    "maxDeliveryCost:0",
    "buyingOptions:{FIXED_PRICE}",
    "itemLocationCountry:US",
    "priceCurrency:USD",
  ].join(",");

  const search = new URL(EBAY_SEARCH_URL);
  search.searchParams.set("q", q);
  search.searchParams.set("limit", String(SEARCH_LIMIT));
  search.searchParams.set("sort", "price");
  search.searchParams.set("filter", filter);

  const headers = {
    Authorization: "Bearer " + token,
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    Accept: "application/json",
  };

  const campid = (env.EBAY_CAMPID || "").trim();
  if (campid) {
    headers["X-EBAY-C-ENDUSERCTX"] =
      "affiliateCampaignId=" +
      campid +
      ",affiliateReferenceId=" +
      encodeURIComponent(String(id).slice(0, 256));
  }

  const res = await fetch(search.toString(), { headers });
  if (!res.ok) {
    const text = await res.text();
    return {
      ok: false,
      id,
      q,
      error: "ebay_search_failed",
      status: res.status,
      detail: text.slice(0, 400),
    };
  }

  const data = await res.json();
  const summaries = Array.isArray(data.itemSummaries) ? data.itemSummaries : [];
  const best = pickLowest(summaries, q);

  if (!best) {
    const empty = {
      ok: false,
      id,
      q,
      error: "no_matching_listings",
      message: "No New + free-shipping US Buy It Now listings found (or only accessory/false matches)",
      total: data.total || 0,
    };
    if (ctx?.waitUntil) {
      ctx.waitUntil(cache.put(cacheReq, jsonResponse({ ...empty, source: "live" }, 900)));
    }
    return { ...empty, source: "live" };
  }

  const result = {
    ok: true,
    id,
    q,
    price: best.price,
    currency: best.currency,
    title: best.title,
    condition: best.condition,
    itemId: best.itemId,
    itemWebUrl: best.itemWebUrl,
    itemAffiliateWebUrl: best.itemAffiliateWebUrl || null,
    shippingCost: best.shippingCost,
    seller: best.seller,
    fetchedAt: new Date().toISOString(),
  };

  if (ctx?.waitUntil) {
    ctx.waitUntil(
      cache.put(cacheReq, jsonResponse({ ...result, source: "live" }, CACHE_TTL_SECONDS))
    );
  }

  return { ...result, source: "live" };
}

/**
 * Reject accessory / replacement / partial listings that match brand keywords
 * but not the full product (e.g. Klein tip instead of 11-in-1 set).
 */
function isLikelyAccessoryTitle(title, q) {
  const t = String(title || "").toLowerCase();
  if (!t) return true;

  const accessoryRe =
    /\b(replacement|refill|spare\s*part|parts?\s*only|bit\s*only|tips?\s*only|for\s+parts|as[\s-]?is|broken|damaged|housing\s*only|battery\s*only|charger\s*only|case\s*only|cover\s*only|hose\s*only|blade\s*only|bit\s*set\s*for|compatible\s+with\s+klein)\b/i;
  if (accessoryRe.test(t)) return true;

  // Single tip / driver bit sold as "Klein" — very short titles with tip sizes
  if (/\b(ph[012]|slotted|torx|t[0-9]{1,2})\b/.test(t) && !/\b(11[\s-]?in[\s-]?1|multi[\s-]?bit|set|combo|kit)\b/.test(t)) {
    if (/\b(klein|32500)\b/.test(t) && t.length < 55) return true;
  }

  return false;
}

/** Significant query tokens that should appear in a good title match. */
function queryTokens(q) {
  return String(q || "")
    .toLowerCase()
    .replace(/[^a-z0-9.\-+/]+/g, " ")
    .split(/\s+/)
    .filter((w) => w.length >= 3)
    .filter((w) => !["with", "and", "the", "for", "max", "set", "pack"].includes(w));
}

function titleRelevance(title, q) {
  const t = String(title || "").toLowerCase();
  const tokens = queryTokens(q);
  if (!tokens.length) return 1;
  let hit = 0;
  for (const tok of tokens) {
    if (t.includes(tok)) hit += 1;
  }
  return hit / tokens.length;
}

function pickLowest(summaries, q) {
  let best = null;
  for (const item of summaries) {
    const value = Number(item?.price?.value);
    if (!isFinite(value) || value <= 0) continue;

    const title = item.title || "";
    if (isLikelyAccessoryTitle(title, q)) continue;

    // Require at least ~40% of meaningful query tokens in the listing title
    const rel = titleRelevance(title, q);
    if (rel < 0.4) continue;

    let ship = 0;
    const opts = item.shippingOptions || [];
    if (opts.length) {
      const sc = Number(opts[0]?.shippingCost?.value);
      if (isFinite(sc)) ship = sc;
    }
    if (ship > 0.009) continue;

    const total = value + ship;
    // Prefer higher relevance, then lower price
    const score = total - rel * 2; // slight boost for better title match
    if (
      !best ||
      score < best.score ||
      (Math.abs(score - best.score) < 0.01 && total < best.total)
    ) {
      best = {
        score,
        total,
        price: Math.round(value * 100) / 100,
        currency: item.price?.currency || "USD",
        title,
        condition: item.condition || "New",
        itemId: item.itemId || "",
        itemWebUrl: item.itemWebUrl || "",
        itemAffiliateWebUrl: item.itemAffiliateWebUrl || "",
        shippingCost: ship,
        seller: item.seller?.username || "",
      };
    }
  }
  return best;
}

async function getAccessToken(env) {
  const now = Date.now();
  if (tokenCache.accessToken && now < tokenCache.expiresAt - 60_000) {
    return tokenCache.accessToken;
  }

  const basic = btoa(env.EBAY_CLIENT_ID + ":" + env.EBAY_CLIENT_SECRET);
  const res = await fetch(EBAY_TOKEN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: "Basic " + basic,
    },
    body: "grant_type=client_credentials&scope=" + encodeURIComponent(OAUTH_SCOPE),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error("oauth_failed " + res.status + ": " + text.slice(0, 200));
  }

  const data = await res.json();
  tokenCache = {
    accessToken: data.access_token,
    expiresAt: now + (Number(data.expires_in) || 7200) * 1000,
  };
  return tokenCache.accessToken;
}

function amazonConfigured(env) {
  return Boolean(
    env.AMAZON_ACCESS_KEY && env.AMAZON_SECRET_KEY && env.AMAZON_PARTNER_TAG
  );
}

/**
 * Amazon Product Advertising API 5.0 GetItems (batches of 10).
 * Requires Associates PA-API access keys.
 */
async function fetchAmazonPrices(asins, env) {
  const out = {};
  const clean = [...new Set(asins.map((a) => String(a || "").trim()).filter(Boolean))];
  for (let i = 0; i < clean.length; i += 10) {
    const batch = clean.slice(i, i + 10);
    try {
      const payload = {
        ItemIds: batch,
        ItemIdType: "ASIN",
        Resources: [
          "ItemInfo.Title",
          "Offers.Listings.Price",
          "Offers.Listings.SavingBasis",
        ],
        PartnerTag: env.AMAZON_PARTNER_TAG,
        PartnerType: "Associates",
        Marketplace: "www.amazon.com",
      };
      const body = JSON.stringify(payload);
      const headers = await signPaapiHeaders(env, body);
      const res = await fetch("https://webservices.amazon.com/paapi5/getitems", {
        method: "POST",
        headers,
        body,
      });
      if (!res.ok) {
        const text = await res.text();
        for (const id of batch) {
          out[id] = { ok: false, error: "paapi_" + res.status, detail: text.slice(0, 200) };
        }
        continue;
      }
      const data = await res.json();
      const results = data?.ItemsResult?.Items || [];
      const byAsin = {};
      for (const item of results) {
        const asin = item?.ASIN;
        if (!asin) continue;
        const listing = item?.Offers?.Listings?.[0];
        const amount = Number(listing?.Price?.Amount);
        const listAmt = Number(listing?.SavingBasis?.Amount);
        byAsin[asin] = {
          ok: isFinite(amount) && amount > 0,
          price: isFinite(amount) ? Math.round(amount * 100) / 100 : null,
          list: isFinite(listAmt) && listAmt > amount ? Math.round(listAmt * 100) / 100 : null,
          title: item?.ItemInfo?.Title?.DisplayValue || null,
        };
      }
      for (const id of batch) {
        out[id] = byAsin[id] || { ok: false, error: "not_returned" };
      }
    } catch (err) {
      for (const id of batch) {
        out[id] = { ok: false, error: String(err?.message || err) };
      }
    }
  }
  return out;
}

/** AWS Signature Version 4 for PA-API */
async function signPaapiHeaders(env, body) {
  const region = "us-east-1";
  const service = "ProductAdvertisingAPI";
  const host = "webservices.amazon.com";
  const method = "POST";
  const path = "/paapi5/getitems";
  const amzTarget = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems";

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const dateStamp = amzDate.slice(0, 8);

  const payloadHash = await sha256Hex(body);
  const canonicalHeaders =
    "content-encoding:amz-1.0\n" +
    "content-type:application/json; charset=utf-8\n" +
    "host:" +
    host +
    "\n" +
    "x-amz-date:" +
    amzDate +
    "\n" +
    "x-amz-target:" +
    amzTarget +
    "\n";
  const signedHeaders = "content-encoding;content-type;host;x-amz-date;x-amz-target";
  const canonicalRequest = [
    method,
    path,
    "",
    canonicalHeaders,
    signedHeaders,
    payloadHash,
  ].join("\n");

  const credentialScope = dateStamp + "/" + region + "/" + service + "/aws4_request";
  const stringToSign = [
    "AWS4-HMAC-SHA256",
    amzDate,
    credentialScope,
    await sha256Hex(canonicalRequest),
  ].join("\n");

  const signingKey = await getSignatureKey(env.AMAZON_SECRET_KEY, dateStamp, region, service);
  const signature = await hmacHex(signingKey, stringToSign);

  const authorization =
    "AWS4-HMAC-SHA256 Credential=" +
    env.AMAZON_ACCESS_KEY +
    "/" +
    credentialScope +
    ", SignedHeaders=" +
    signedHeaders +
    ", Signature=" +
    signature;

  return {
    "content-encoding": "amz-1.0",
    "content-type": "application/json; charset=utf-8",
    host,
    "x-amz-date": amzDate,
    "x-amz-target": amzTarget,
    Authorization: authorization,
  };
}

async function sha256Hex(message) {
  const data = new TextEncoder().encode(message);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function hmac(key, message) {
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    typeof key === "string" ? new TextEncoder().encode(key) : key,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, new TextEncoder().encode(message));
  return new Uint8Array(sig);
}

async function hmacHex(key, message) {
  const sig = await hmac(key, message);
  return [...sig].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function getSignatureKey(key, dateStamp, regionName, serviceName) {
  const kDate = await hmac("AWS4" + key, dateStamp);
  const kRegion = await hmac(kDate, regionName);
  const kService = await hmac(kRegion, serviceName);
  return hmac(kService, "aws4_request");
}

function hashKey(q) {
  let h = 2166136261;
  const s = String(q).toLowerCase().trim();
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16) + "-" + encodeURIComponent(s).slice(0, 80);
}

function jsonResponse(obj, maxAge) {
  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=" + String(maxAge),
    },
  });
}

function json(obj, status) {
  return withCors(
    new Response(JSON.stringify(obj, null, 0), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    })
  );
}

function withCors(res) {
  const headers = new Headers(res.headers);
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, X-Refresh-Token");
  headers.set("Access-Control-Max-Age", "86400");
  return new Response(res.body, { status: res.status, headers });
}
