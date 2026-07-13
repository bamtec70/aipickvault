/**
 * AI Pick Vault — eBay price API (Cloudflare Worker)
 *
 * Uses eBay Browse API to find the lowest Buy It Now price for:
 *   - Condition: NEW
 *   - Free shipping (maxDeliveryCost:0)
 *   - Item location: US
 *   - Fixed price only (no auctions)
 *
 * Secrets (wrangler secret put):
 *   EBAY_CLIENT_ID, EBAY_CLIENT_SECRET
 * Optional:
 *   EBAY_CAMPID  (EPN campaign → affiliate item URLs when available)
 *
 * Endpoints:
 *   GET  /health
 *   GET  /v1/price?q=Product+Name&id=ASIN
 *   POST /v1/prices  { "items": [ { "id": "ASIN", "q": "Product Name" }, ... ] }
 */

const EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token";
const EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search";
const OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope";
const CACHE_TTL_SECONDS = 6 * 60 * 60; // 6 hours
const MAX_BATCH = 40;
const SEARCH_LIMIT = 20;

/** In-isolate OAuth cache (survives warm isolates). */
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
        return json({
          ok: true,
          service: "aipickvault-ebay",
          filters: "NEW + free shipping + US location + Buy It Now",
          configured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
        });
      }

      if (!env.EBAY_CLIENT_ID || !env.EBAY_CLIENT_SECRET) {
        return json(
          {
            error: "missing_credentials",
            message:
              "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET with wrangler secret put",
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
        // Modest concurrency so we stay friendly to eBay rate limits
        const concurrency = 3;
        let idx = 0;
        async function worker() {
          while (idx < items.length) {
            const i = idx++;
            const { id, q } = items[i];
            try {
              prices[id] = await getLowestPrice(q, id, env, ctx);
            } catch (err) {
              prices[id] = {
                ok: false,
                id,
                q,
                error: String(err?.message || err),
              };
            }
          }
        }
        await Promise.all(
          Array.from({ length: Math.min(concurrency, items.length) }, () =>
            worker()
          )
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
      return json(
        { error: "server_error", message: String(err?.message || err) },
        500
      );
    }
  },
};

async function getLowestPrice(q, id, env, ctx) {
  const cacheKeyUrl = `https://aipickvault-ebay-cache.internal/v1/${hashKey(q)}`;
  const cache = caches.default;
  const cacheReq = new Request(cacheKeyUrl, { method: "GET" });

  const hit = await cache.match(cacheReq);
  if (hit) {
    const data = await hit.json();
    return { ...data, source: "cache", id, q };
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
    // Enables itemAffiliateWebUrl when the app is linked to EPN
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
  const best = pickLowest(summaries);

  if (!best) {
    const empty = {
      ok: false,
      id,
      q,
      error: "no_matching_listings",
      message: "No New + free-shipping US Buy It Now listings found",
      total: data.total || 0,
    };
    // Cache misses briefly to avoid hammering eBay
    ctx.waitUntil(
      cache.put(
        cacheReq,
        jsonResponse({ ...empty, source: "live" }, 900)
      )
    );
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

  ctx.waitUntil(
    cache.put(cacheReq, jsonResponse({ ...result, source: "live" }, CACHE_TTL_SECONDS))
  );

  return { ...result, source: "live" };
}

function pickLowest(summaries) {
  let best = null;
  for (const item of summaries) {
    const value = Number(item?.price?.value);
    if (!isFinite(value) || value <= 0) continue;

    // Prefer free shipping; maxDeliveryCost:0 should already enforce this
    let ship = 0;
    const opts = item.shippingOptions || [];
    if (opts.length) {
      const sc = Number(opts[0]?.shippingCost?.value);
      if (isFinite(sc)) ship = sc;
    }
    // Skip if shipping isn't free when we can tell
    if (ship > 0.009) continue;

    const total = value + ship;
    if (!best || total < best.total) {
      best = {
        total,
        price: Math.round(value * 100) / 100,
        currency: item.price?.currency || "USD",
        title: item.title || "",
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
    body:
      "grant_type=client_credentials&scope=" + encodeURIComponent(OAUTH_SCOPE),
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

function hashKey(q) {
  // Simple stable key for Cache API (not crypto-secure; just for caching)
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
  headers.set("Access-Control-Allow-Headers", "Content-Type");
  headers.set("Access-Control-Max-Age", "86400");
  return new Response(res.body, { status: res.status, headers });
}
