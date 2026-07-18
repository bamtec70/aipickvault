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
 *   GET  /v1/tiktok           latest @aipickvault videos (cached in KV)
 *   POST /v1/tiktok/refresh   force TikTok list refresh (optional X-Refresh-Token)
 *
 * Cron: daily full catalog refresh → KV key "daily"
 */

import catalog from "./catalog.json";

const EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token";
const EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search";
const OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope";
const CACHE_TTL_SECONDS = 6 * 60 * 60;
/**
 * Soft guidance for clients (site chunks around this). Not a hard fail.
 * Keep small: each product can use multiple eBay subrequests (search + item
 * detail). Too large a single POST hits Workers subrequest limits mid-batch.
 */
const PREFERRED_BATCH = 15;
/**
 * Absolute abuse ceiling for POST /v1/prices.
 * Catalog growth must never hit this in normal use — site always chunks.
 * Full-catalog daily refresh uses refreshCatalog() (cron) separately.
 */
const ABSOLUTE_MAX_BATCH = 250;
/**
 * Full-catalog refresh chunk size. Each product can use many subrequests
 * (search + up to N item-detail verifies). Chunks must stay small enough
 * that one Worker invocation stays under the platform subrequest ceiling.
 * Full refresh orchestrates one HTTP invocation per chunk (fresh budget).
 */
const REFRESH_CHUNK_SIZE = 6;
/** Concurrent eBay product lookups inside a single refresh chunk. */
const REFRESH_CONCURRENCY = 2;
/** Max free-ship detail verifies per product during catalog refresh. */
const REFRESH_MAX_VERIFY = 5;
const SEARCH_LIMIT = 50;
const KV_KEY = "daily";
const TIKTOK_KV_KEY = "tiktok_videos";
const TIKTOK_USERNAME = "aipickvault";
const TIKTOK_CACHE_SECONDS = 3 * 60 * 60; // 3 hours
const TIKTOK_MAX = 6;
const CONCURRENCY = 3;
const DEFAULT_PUBLIC_BASE_URL = "https://ebay-api.aipickvault.com";

/** Public sites allowed to call the Worker from a browser (CORS). */
const DEFAULT_ALLOWED_ORIGINS = [
  "https://aipickvault.com",
  "https://www.aipickvault.com",
  "https://bamtec70.github.io",
];

/**
 * Per-IP rate limits (fixed window via KV). Tuned for normal site traffic
 * while stopping cheap scrapers from burning eBay quota.
 * key → { limit, windowSec }
 */
const RATE_LIMITS = {
  global: { limit: 120, windowSec: 60 },
  snapshot: { limit: 60, windowSec: 60 },
  tiktok: { limit: 40, windowSec: 60 },
  price: { limit: 40, windowSec: 60 },
  prices: { limit: 24, windowSec: 60 }, // expensive batch eBay lookups
  item: { limit: 20, windowSec: 60 },
  // Full + chunked refreshes (GHA may call once per chunk). Auth still required.
  refresh: { limit: 60, windowSec: 3600 },
};

let tokenCache = { accessToken: null, expiresAt: 0 };

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }), request, env);
    }

    try {
      const url = new URL(request.url);
      const path = url.pathname.replace(/\/+$/, "") || "/";
      const clientIp = clientIpFrom(request);

      // Global soft cap (all routes except health)
      if (path !== "/health" && path !== "/") {
        const limited = await enforceRateLimit(env, "global", clientIp, RATE_LIMITS.global, request);
        if (limited) return limited;
      }

      if (path === "/health" || path === "/") {
        const snap = env.PRICES ? await env.PRICES.get(KV_KEY, "json") : null;
        return json(
          {
            ok: true,
            service: "aipickvault-ebay",
            filters: "NEW + free shipping + US location + Buy It Now",
            ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
            amazonConfigured: amazonConfigured(env),
            catalogSize: Array.isArray(catalog) ? catalog.length : 0,
            preferredBatch: PREFERRED_BATCH,
            absoluteMaxBatch: ABSOLUTE_MAX_BATCH,
            lastSnapshotAt: snap?.updatedAt || null,
            snapshotCount: snap?.count || 0,
            refreshAuthRequired: true,
            rateLimited: true,
          },
          200,
          request,
          env
        );
      }

      if (path === "/v1/snapshot" && request.method === "GET") {
        const limited = await enforceRateLimit(env, "snapshot", clientIp, RATE_LIMITS.snapshot, request);
        if (limited) return limited;
        if (!env.PRICES) {
          return json({ error: "kv_not_bound", message: "PRICES KV not configured" }, 503, request, env);
        }
        const snap = await env.PRICES.get(KV_KEY, "json");
        if (!snap) {
          // Do NOT auto-trigger a full eBay refresh from public traffic (abuse vector).
          return json(
            {
              ok: false,
              error: "snapshot_empty",
              message:
                "Daily snapshot not ready. Authorized refresh required (POST /v1/refresh with X-Refresh-Token).",
            },
            503,
            request,
            env
          );
        }
        return withCors(
          new Response(JSON.stringify(snap), {
            status: 200,
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "Cache-Control": "public, max-age=300",
            },
          }),
          request,
          env
        );
      }

      if (path === "/v1/refresh" && (request.method === "POST" || request.method === "GET")) {
        const authErr = assertRefreshAuth(request, env);
        if (authErr) return authErr;
        const limited = await enforceRateLimit(env, "refresh", clientIp, RATE_LIMITS.refresh, request);
        if (limited) return limited;

        const refreshOpts = await parseRefreshOptions(request, url);
        refreshOpts.baseUrl =
          refreshOpts.baseUrl || url.origin || env.PUBLIC_BASE_URL || DEFAULT_PUBLIC_BASE_URL;

        const result = await refreshCatalog(env, ctx, refreshOpts);
        // Full refreshes only — chunk calls must not each hit TikTok.
        if (!refreshOpts.partial) {
          ctx.waitUntil(refreshTikTokVideos(env).catch(() => null));
        }
        const status = result?.ok === false ? 500 : 200;
        return json(result, status, request, env);
      }

      if (path === "/v1/tiktok" && request.method === "GET") {
        const limited = await enforceRateLimit(env, "tiktok", clientIp, RATE_LIMITS.tiktok, request);
        if (limited) return limited;
        // Public GET is cache-only. Force refresh requires auth (no free ?refresh=1).
        const forceRequested = url.searchParams.get("refresh") === "1";
        if (forceRequested) {
          const authErr = assertRefreshAuth(request, env);
          if (authErr) return authErr;
        }
        const payload = await getTikTokVideos(env, ctx, forceRequested);
        return withCors(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "Cache-Control": "public, max-age=300",
            },
          }),
          request,
          env
        );
      }

      if (path === "/v1/tiktok/refresh" && (request.method === "POST" || request.method === "GET")) {
        const authErr = assertRefreshAuth(request, env);
        if (authErr) return authErr;
        const limited = await enforceRateLimit(env, "refresh", clientIp, RATE_LIMITS.refresh, request);
        if (limited) return limited;
        const payload = await refreshTikTokVideos(env);
        return json(payload, 200, request, env);
      }

      if (!env.EBAY_CLIENT_ID || !env.EBAY_CLIENT_SECRET) {
        return json(
          {
            error: "missing_credentials",
            message: "Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET with wrangler secret put",
          },
          503,
          request,
          env
        );
      }

      if (path === "/v1/price" && request.method === "GET") {
        const limited = await enforceRateLimit(env, "price", clientIp, RATE_LIMITS.price, request);
        if (limited) return limited;
        const id = (url.searchParams.get("id") || "").trim();
        const cat = findCatalogEntry(id);
        const q = (url.searchParams.get("q") || cat?.q || "").trim();
        const resolvedId = (id || q).trim();
        if (!q) return json({ error: "missing_q" }, 400, request, env);
        // ?fresh=1 skips cache — treat as more expensive; still rate-limited above
        const skipCache = url.searchParams.get("fresh") === "1";
        const pin =
          (url.searchParams.get("pin") || "").trim() ||
          cat?.ebayPreferItemId ||
          null;
        const result = await getLowestPrice(q, resolvedId, env, ctx, {
          skipCacheRead: skipCache,
          ebayPreferItemId: pin,
          requireTokens: cat?.requireTokens || null,
        });
        return json(result, 200, request, env);
      }

      // Debug / compare: resolve a single eBay item id (legacy or RESTful)
      if (path === "/v1/item" && request.method === "GET") {
        const limited = await enforceRateLimit(env, "item", clientIp, RATE_LIMITS.item, request);
        if (limited) return limited;
        const itemId = (url.searchParams.get("id") || "").trim();
        if (!itemId) return json({ error: "missing_id" }, 400, request, env);
        const result = await getItemById(itemId, env);
        return json(result, 200, request, env);
      }

      if (path === "/v1/prices" && request.method === "POST") {
        const limited = await enforceRateLimit(env, "prices", clientIp, RATE_LIMITS.prices, request);
        if (limited) return limited;
        let body;
        try {
          body = await request.json();
        } catch {
          return json({ error: "invalid_json" }, 400, request, env);
        }
        const raw = Array.isArray(body?.items) ? body.items : [];
        if (!raw.length) return json({ error: "empty_items" }, 400, request, env);
        // Only hard-reject pathological abuse sizes — never normal catalog growth.
        if (raw.length > ABSOLUTE_MAX_BATCH) {
          return json(
            {
              error: "too_many_items",
              max: ABSOLUTE_MAX_BATCH,
              preferredBatch: PREFERRED_BATCH,
              message:
                "Split into smaller POSTs (site auto-chunks). Absolute max is for abuse protection only.",
            },
            400,
            request,
            env
          );
        }

        const items = [];
        const seen = new Set();
        for (const it of raw) {
          const id = String(it?.id || it?.asin || "").trim();
          const cat = findCatalogEntry(id);
          const q = String(it?.q || it?.name || cat?.q || "").trim();
          if (!q || !id || seen.has(id)) continue;
          seen.add(id);
          items.push({
            id,
            q,
            ebayPreferItemId: it?.ebayPreferItemId || cat?.ebayPreferItemId || null,
            requireTokens: it?.requireTokens || cat?.requireTokens || null,
            ebayAllowPaidShip: Boolean(
              it?.ebayAllowPaidShip || cat?.ebayAllowPaidShip || cat?.allowPaidShip
            ),
          });
        }

        const prices = {};
        let idx = 0;
        async function worker() {
          while (idx < items.length) {
            const i = idx++;
            const { id, q, ebayPreferItemId, requireTokens, ebayAllowPaidShip } = items[i];
            try {
              prices[id] = await getLowestPrice(q, id, env, ctx, {
                ebayPreferItemId,
                requireTokens,
                ebayAllowPaidShip,
              });
            } catch (err) {
              prices[id] = { ok: false, id, q, error: String(err?.message || err) };
            }
          }
        }
        await Promise.all(
          Array.from({ length: Math.min(CONCURRENCY, items.length) }, () => worker())
        );

        return json(
          {
            ok: true,
            count: Object.keys(prices).length,
            filters: "NEW + free shipping + US + Buy It Now",
            cacheTtlSeconds: CACHE_TTL_SECONDS,
            preferredBatch: PREFERRED_BATCH,
            absoluteMaxBatch: ABSOLUTE_MAX_BATCH,
            prices,
          },
          200,
          request,
          env
        );
      }

      return json({ error: "not_found" }, 404, request, env);
    } catch (err) {
      return json(
        { error: "server_error", message: String(err?.message || err) },
        500,
        request,
        env
      );
    }
  },

  /** Cloudflare Cron Trigger — daily full refresh (chunk-orchestrated) */
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      refreshCatalog(env, ctx, {
        baseUrl: env.PUBLIC_BASE_URL || DEFAULT_PUBLIC_BASE_URL,
      })
    );
  },
};

/**
 * Parse full vs partial refresh options from query string and/or JSON body.
 * Partial: { partial:true, offset, limit, reset } — one catalog slice, merge into KV.
 * Full (default): orchestrate one Worker invocation per slice (fresh subrequest budget).
 */
async function parseRefreshOptions(request, url) {
  const opts = {
    partial: false,
    offset: 0,
    limit: REFRESH_CHUNK_SIZE,
    reset: false,
    baseUrl: null,
  };

  const qOffset = url.searchParams.get("offset");
  const qLimit = url.searchParams.get("limit");
  const qPartial = url.searchParams.get("partial");
  const qReset = url.searchParams.get("reset");
  if (qOffset != null && qOffset !== "") {
    opts.partial = true;
    opts.offset = Math.max(0, parseInt(qOffset, 10) || 0);
  }
  if (qLimit != null && qLimit !== "") {
    opts.limit = Math.max(1, Math.min(REFRESH_CHUNK_SIZE, parseInt(qLimit, 10) || REFRESH_CHUNK_SIZE));
  }
  if (qPartial === "1" || qPartial === "true") opts.partial = true;
  if (qReset === "1" || qReset === "true") opts.reset = true;

  if (request.method === "POST") {
    try {
      const text = await request.clone().text();
      if (text && text.trim()) {
        const body = JSON.parse(text);
        if (body && typeof body === "object") {
          if (body.partial === true || body.offset != null) opts.partial = true;
          if (body.offset != null) opts.offset = Math.max(0, parseInt(body.offset, 10) || 0);
          if (body.limit != null) {
            opts.limit = Math.max(
              1,
              Math.min(REFRESH_CHUNK_SIZE, parseInt(body.limit, 10) || REFRESH_CHUNK_SIZE)
            );
          }
          if (body.reset === true) opts.reset = true;
          if (typeof body.baseUrl === "string" && body.baseUrl.trim()) {
            opts.baseUrl = body.baseUrl.trim().replace(/\/+$/, "");
          }
        }
      }
    } catch {
      // ignore bad/missing body — query params still apply
    }
  }

  // Chunk marker header always means partial (used by orchestrator + GHA)
  if (request.headers.get("X-Refresh-Chunk") === "1") {
    opts.partial = true;
  }

  return opts;
}

function isInfraSubrequestError(msg) {
  return /too many subrequests/i.test(String(msg || ""));
}

/** True if a getLowestPrice row failed because the Worker hit platform limits. */
function rowHasInfraFailure(row) {
  if (!row || typeof row !== "object") return false;
  if (
    isInfraSubrequestError(row.error) ||
    isInfraSubrequestError(row.detail) ||
    isInfraSubrequestError(row.message) ||
    isInfraSubrequestError(row.ebayError)
  ) {
    return true;
  }
  for (const r of row.rejected || row.ebayRejects || []) {
    if (typeof r === "string" && isInfraSubrequestError(r)) return true;
    if (r && isInfraSubrequestError(r.reason)) return true;
  }
  return false;
}

function snapshotQuality(prices, catalogSize, errors) {
  const rows = Object.values(prices || {});
  const ebayOkCount = rows.filter((p) => p && p.ebayOk === true).length;
  const ebayFailCount = rows.filter((p) => p && p.ebayOk === false).length;
  const infraErrors = (errors || []).filter((e) => isInfraSubrequestError(e?.error));
  const hasInfraFailure =
    infraErrors.length > 0 || rows.some((p) => rowHasInfraFailure(p));
  return {
    ebayOkCount,
    ebayFailCount,
    catalogSize,
    infraErrorCount: infraErrors.length,
    hasInfraFailure,
  };
}

/**
 * Full catalog refresh or a single mergeable chunk.
 * Full mode fans out to partial self-fetches so each chunk gets its own
 * Worker subrequest budget (in-process batching alone does not reset the cap).
 */
async function refreshCatalog(env, ctx, opts = {}) {
  const items = Array.isArray(catalog) ? catalog : [];

  if (opts.partial) {
    return refreshCatalogPartial(env, ctx, {
      offset: opts.offset || 0,
      limit: opts.limit || REFRESH_CHUNK_SIZE,
      reset: Boolean(opts.reset),
    });
  }

  return refreshCatalogFull(env, ctx, opts);
}

/**
 * Full-catalog refresh cannot safely run in one Worker invocation: each product
 * may use many eBay subrequests, and self-fetch orchestration against the custom
 * domain often fails with 522. Callers (GitHub Actions / scripts) must POST
 * partial chunks with a fresh invocation each time:
 *
 *   POST /v1/refresh?partial=1&offset=0&limit=6&reset=1
 *   POST /v1/refresh?partial=1&offset=6&limit=6&reset=0
 *   ...
 *
 * Small catalogs that fit in one chunk are refreshed here directly.
 */
async function refreshCatalogFull(env, ctx, opts = {}) {
  const started = Date.now();
  const items = Array.isArray(catalog) ? catalog : [];
  const chunkSize = REFRESH_CHUNK_SIZE;

  if (!items.length) {
    const empty = {
      ok: true,
      updatedAt: new Date().toISOString(),
      count: 0,
      ebayOkCount: 0,
      catalogSize: 0,
      amazonConfigured: amazonConfigured(env),
      ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
      durationMs: Date.now() - started,
      errorCount: 0,
      chunks: 0,
      mode: "full",
    };
    if (env.PRICES) await env.PRICES.put(KV_KEY, JSON.stringify({ ...empty, prices: {}, errors: [] }));
    return empty;
  }

  if (items.length <= chunkSize) {
    const one = await refreshCatalogPartial(env, ctx, {
      offset: 0,
      limit: items.length,
      reset: true,
    });
    if (amazonConfigured(env) && env.PRICES) {
      await applyAmazonToSnapshot(env, items, started);
    }
    return { ...one, mode: "full_single_chunk", durationMs: Date.now() - started };
  }

  return {
    ok: false,
    error: "use_chunked_refresh",
    message:
      "Full catalog exceeds one Worker subrequest budget. POST partial chunks " +
      "(query params work best): /v1/refresh?partial=1&offset=0&limit=" +
      chunkSize +
      "&reset=1 then offset+=limit with reset=0. GitHub Action daily-price-refresh.yml does this.",
    catalogSize: items.length,
    recommendedChunk: chunkSize,
    durationMs: Date.now() - started,
    mode: "full_rejected",
  };
}

async function applyAmazonToSnapshot(env, items, started) {
  try {
    const prev = (await env.PRICES.get(KV_KEY, "json")) || {};
    const prices = { ...(prev.prices || {}) };
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
    const quality = snapshotQuality(prices, items.length, prev.errors || []);
    const snapshot = {
      ...prev,
      ok: !quality.hasInfraFailure,
      updatedAt: new Date().toISOString(),
      count: Object.keys(prices).length,
      ebayOkCount: quality.ebayOkCount,
      ebayFailCount: quality.ebayFailCount,
      catalogSize: items.length,
      amazonConfigured: true,
      ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
      durationMs: Date.now() - started,
      prices,
      errors: Array.isArray(prev.errors) ? prev.errors.slice(0, 30) : [],
      mode: prev.mode || "partial",
    };
    await env.PRICES.put(KV_KEY, JSON.stringify(snapshot));
  } catch {
    // Amazon is optional; leave eBay snapshot as-is
  }
}

async function refreshCatalogPartial(env, ctx, { offset = 0, limit = REFRESH_CHUNK_SIZE, reset = false } = {}) {
  const started = Date.now();
  const items = Array.isArray(catalog) ? catalog : [];
  const safeOffset = Math.max(0, offset | 0);
  const safeLimit = Math.max(1, Math.min(REFRESH_CHUNK_SIZE, limit | 0 || REFRESH_CHUNK_SIZE));
  const slice = items.slice(safeOffset, safeOffset + safeLimit);

  let prices = {};
  let priorErrors = [];
  if (!reset && env.PRICES) {
    const prev = await env.PRICES.get(KV_KEY, "json");
    if (prev?.prices && typeof prev.prices === "object") {
      prices = { ...prev.prices };
    }
    if (Array.isArray(prev?.errors)) {
      // Drop errors for ids we are about to reprocess
      const reprocess = new Set(slice.map((e) => e?.id).filter(Boolean));
      priorErrors = prev.errors.filter((e) => e?.id && !reprocess.has(e.id));
    }
  }

  const errors = [];

  if (env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET && slice.length) {
    let idx = 0;
    async function ebayWorker() {
      while (idx < slice.length) {
        const i = idx++;
        const entry = slice[i] || {};
        const id = entry.id;
        const q = entry.q;
        try {
          const row = await getLowestPrice(q, id, env, ctx, {
            skipCacheRead: true,
            ebayPreferItemId: entry.ebayPreferItemId || null,
            requireTokens: entry.requireTokens || null,
            ebayAllowPaidShip: entry.ebayAllowPaidShip || entry.allowPaidShip || false,
            maxVerify: REFRESH_MAX_VERIFY,
          });
          if (!prices[id]) prices[id] = { id, q };
          if (row?.ok && isFinite(Number(row.price))) {
            prices[id].ebay = Number(row.price);
            prices[id].ebayOk = true;
            prices[id].ebayTitle = row.title || null;
            prices[id].ebayItemId = row.itemId || null;
            prices[id].ebayItemWebUrl = row.itemWebUrl || null;
            prices[id].ebaySource = row.matchSource || row.source || "live";
            prices[id].ebayShipping = Number(row.shippingCost) || 0;
            prices[id].ebayPaidShip = Boolean(row.allowPaidShip && Number(row.shippingCost) > 0);
            prices[id].ebayRejects = Array.isArray(row.rejected) ? row.rejected.slice(0, 3) : [];
            delete prices[id].ebayError;
            delete prices[id].ebayMessage;
          } else {
            // Explicit no-match: do not leave a stale price in the snapshot
            prices[id].ebay = null;
            prices[id].ebayOk = false;
            prices[id].ebayError = row?.error || "no_price";
            prices[id].ebayMessage = row?.message || null;
            prices[id].ebayRejects = Array.isArray(row?.rejected) ? row.rejected.slice(0, 5) : [];
            if (rowHasInfraFailure(row)) {
              const infraMsg =
                String(row?.error || "") +
                " " +
                String(row?.detail || "") +
                " " +
                JSON.stringify(row?.rejected || []).slice(0, 200);
              errors.push({
                id,
                retailer: "ebay",
                error: isInfraSubrequestError(infraMsg)
                  ? "Too many subrequests by single Worker invocation"
                  : String(row?.error || "infra_failure"),
              });
            }
          }
        } catch (err) {
          if (!prices[id]) prices[id] = { id, q };
          prices[id].ebay = null;
          prices[id].ebayOk = false;
          prices[id].ebayError = String(err?.message || err);
          errors.push({ id, retailer: "ebay", error: String(err?.message || err) });
        }
      }
    }
    await Promise.all(
      Array.from(
        { length: Math.min(REFRESH_CONCURRENCY, slice.length || 1) },
        () => ebayWorker()
      )
    );
  } else if (slice.length) {
    for (const entry of slice) {
      const id = entry.id;
      const q = entry.q;
      prices[id] = {
        id,
        q,
        ebay: null,
        ebayOk: false,
        ebayError: "ebay_not_configured",
      };
      errors.push({ id, retailer: "ebay", error: "ebay_not_configured" });
    }
  }

  const mergedErrors = [...priorErrors, ...errors].slice(0, 40);
  const quality = snapshotQuality(prices, items.length, mergedErrors);
  const nextOffset = safeOffset + safeLimit < items.length ? safeOffset + safeLimit : null;
  const chunkOk = !slice.some((e) => rowHasInfraFailure(prices[e?.id]));

  const snapshot = {
    ok: chunkOk && !quality.hasInfraFailure,
    updatedAt: new Date().toISOString(),
    count: Object.keys(prices).length,
    ebayOkCount: quality.ebayOkCount,
    ebayFailCount: quality.ebayFailCount,
    catalogSize: items.length,
    amazonConfigured: amazonConfigured(env),
    ebayConfigured: Boolean(env.EBAY_CLIENT_ID && env.EBAY_CLIENT_SECRET),
    durationMs: Date.now() - started,
    prices,
    errors: mergedErrors,
    mode: "partial",
    offset: safeOffset,
    limit: safeLimit,
    processedInChunk: slice.length,
    nextOffset,
  };

  if (env.PRICES) {
    await env.PRICES.put(KV_KEY, JSON.stringify(snapshot));
  }

  return {
    ok: chunkOk && !quality.hasInfraFailure,
    updatedAt: snapshot.updatedAt,
    count: snapshot.count,
    ebayOkCount: quality.ebayOkCount,
    ebayFailCount: quality.ebayFailCount,
    catalogSize: items.length,
    amazonConfigured: snapshot.amazonConfigured,
    ebayConfigured: snapshot.ebayConfigured,
    durationMs: snapshot.durationMs,
    errorCount: errors.length,
    hasInfraFailure: quality.hasInfraFailure || !chunkOk,
    processedInChunk: slice.length,
    offset: safeOffset,
    limit: safeLimit,
    nextOffset,
    mode: "partial",
  };
}

function findCatalogEntry(id) {
  if (!id || !Array.isArray(catalog)) return null;
  return catalog.find((x) => x && String(x.id) === String(id)) || null;
}

async function getLowestPrice(q, id, env, ctx, opts = {}) {
  const cat = findCatalogEntry(id);
  const searchQ = String(q || cat?.q || "").trim();
  const pinId = String(
    opts.ebayPreferItemId || cat?.ebayPreferItemId || cat?.ebayPinItemId || ""
  ).trim();
  const requireTokens = opts.requireTokens || cat?.requireTokens || null;
  // Rare opt-in: some new SKUs have zero free-ship New inventory on eBay.
  // When true, search without maxDeliveryCost:0 and accept paid US shipping.
  // Returned price is landed cost (item + shipping) for fair Amazon compare.
  const allowPaidShip = Boolean(
    opts.ebayAllowPaidShip ?? cat?.ebayAllowPaidShip ?? cat?.allowPaidShip
  );

  // v5: pins + reject logging + requireTokens + optional paid-ship
  const cacheKeyUrl = `https://aipickvault-ebay-cache.internal/v5/${hashKey(
    searchQ +
      "|" +
      pinId +
      "|" +
      JSON.stringify(requireTokens || []) +
      "|paid=" +
      (allowPaidShip ? "1" : "0")
  )}`;
  const cache = caches.default;
  const cacheReq = new Request(cacheKeyUrl, { method: "GET" });

  if (!opts.skipCacheRead) {
    const hit = await cache.match(cacheReq);
    if (hit) {
      const data = await hit.json();
      return { ...data, source: "cache", id, q: searchQ };
    }
  }

  const rejected = [];
  // 1) Prefer pinned item when still valid (human override for known-good listings)
  if (pinId) {
    const pinned = await tryPinnedListing(pinId, searchQ, requireTokens, env, {
      allowPaidShip,
    });
    if (pinned.ok) {
      const result = {
        ok: true,
        id,
        q: searchQ,
        price: pinned.price,
        currency: pinned.currency,
        title: pinned.title,
        condition: pinned.condition,
        itemId: pinned.itemId,
        itemWebUrl: pinned.itemWebUrl,
        itemAffiliateWebUrl: pinned.itemAffiliateWebUrl || null,
        shippingCost: pinned.shippingCost ?? 0,
        allowPaidShip: allowPaidShip || undefined,
        seller: pinned.seller,
        fetchedAt: new Date().toISOString(),
        matchSource: "pin",
        pinItemId: pinId,
        rejected: [],
      };
      if (ctx?.waitUntil) {
        ctx.waitUntil(
          cache.put(cacheReq, jsonResponse({ ...result, source: "live" }, CACHE_TTL_SECONDS))
        );
      }
      return { ...result, source: "live" };
    }
    rejected.push({
      itemId: pinId,
      title: pinned.title || null,
      price: pinned.price ?? null,
      reason: pinned.reason || "pin_invalid",
    });
  }

  const token = await getAccessToken(env);
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

  // Build filter set(s). Default: New + free ship + US + BIN.
  // allowPaidShip: drop free-ship filter; if still empty, also drop US location
  // (some new SKUs only appear from non-US sellers that ship to US).
  const filterAttempts = [];
  if (!allowPaidShip) {
    filterAttempts.push(
      [
        "conditions:{NEW}",
        "maxDeliveryCost:0",
        "buyingOptions:{FIXED_PRICE}",
        "itemLocationCountry:US",
        "priceCurrency:USD",
      ].join(",")
    );
  } else {
    filterAttempts.push(
      [
        "conditions:{NEW}",
        "buyingOptions:{FIXED_PRICE}",
        "itemLocationCountry:US",
        "priceCurrency:USD",
      ].join(",")
    );
    filterAttempts.push(
      ["conditions:{NEW}", "buyingOptions:{FIXED_PRICE}", "priceCurrency:USD"].join(",")
    );
  }

  let data = { itemSummaries: [], total: 0 };
  let lastSearchError = null;
  for (const filter of filterAttempts) {
    const search = new URL(EBAY_SEARCH_URL);
    search.searchParams.set("q", searchQ);
    search.searchParams.set("limit", String(SEARCH_LIMIT));
    search.searchParams.set("sort", "price");
    search.searchParams.set("filter", filter);
    const res = await fetch(search.toString(), { headers });
    if (!res.ok) {
      const text = await res.text();
      lastSearchError = { status: res.status, detail: text.slice(0, 400) };
      continue;
    }
    data = await res.json();
    const summariesTry = Array.isArray(data.itemSummaries) ? data.itemSummaries : [];
    if (summariesTry.length) break;
  }
  if (lastSearchError && !(Array.isArray(data.itemSummaries) && data.itemSummaries.length)) {
    return {
      ok: false,
      id,
      q: searchQ,
      error: "ebay_search_failed",
      status: lastSearchError.status,
      detail: lastSearchError.detail,
      rejected: rejected.slice(0, 5),
    };
  }

  const summaries = Array.isArray(data.itemSummaries) ? data.itemSummaries : [];
  const { ranked, rejected: rankRejected } = rankCandidates(summaries, searchQ, {
    requireTokens,
  });
  for (const r of rankRejected.slice(0, 8)) rejected.push(r);

  const maxVerify = Math.max(
    1,
    Math.min(10, Number(opts.maxVerify) > 0 ? Number(opts.maxVerify) : 10)
  );
  let best = null;
  for (const cand of ranked.slice(0, maxVerify)) {
    const verified = await verifyShipping(cand, env, { allowPaidShip });
    if (verified.ok) {
      best = verified.listing;
      break;
    }
    rejected.push({
      itemId: cand.itemId || null,
      title: (cand.title || "").slice(0, 90),
      price: cand.price,
      reason: verified.reason || "verify_failed",
    });
  }

  if (!best) {
    const empty = {
      ok: false,
      id,
      q: searchQ,
      error: "no_matching_listings",
      message: allowPaidShip
        ? "No New US Buy It Now listings found (free or paid ship) after filters"
        : "No New + free-shipping US Buy It Now listings found (or only accessory/false matches)",
      total: data.total || 0,
      rejected: rejected.slice(0, 8),
      matchSource: "search",
    };
    if (ctx?.waitUntil) {
      ctx.waitUntil(cache.put(cacheReq, jsonResponse({ ...empty, source: "live" }, 900)));
    }
    return { ...empty, source: "live" };
  }

  const result = {
    ok: true,
    id,
    q: searchQ,
    price: best.price,
    currency: best.currency,
    title: best.title,
    condition: best.condition,
    itemId: best.itemId,
    itemWebUrl: best.itemWebUrl,
    itemAffiliateWebUrl: best.itemAffiliateWebUrl || null,
    shippingCost: best.shippingCost,
    allowPaidShip: allowPaidShip || undefined,
    seller: best.seller,
    fetchedAt: new Date().toISOString(),
    matchSource: "search",
    rejected: rejected.slice(0, 5),
  };

  if (ctx?.waitUntil) {
    ctx.waitUntil(
      cache.put(cacheReq, jsonResponse({ ...result, source: "live" }, CACHE_TTL_SECONDS))
    );
  }

  return { ...result, source: "live" };
}

/** Try a human-pinned eBay item id; must still be New + title rules (+ free ship unless allowed). */
async function tryPinnedListing(pinId, q, requireTokens, env, opts = {}) {
  const allowPaidShip = Boolean(opts.allowPaidShip);
  try {
    const detail = await getItemById(pinId, env);
    if (!detail?.ok) {
      return { ok: false, reason: "pin_fetch_failed", title: null, price: null };
    }
    const title = detail.title || "";
    if (isLikelyAccessoryTitle(title, q)) {
      return { ok: false, reason: "pin_accessory_title", title, price: detail.price };
    }
    if (!passesRequireTokens(title, requireTokens)) {
      return { ok: false, reason: "pin_missing_require_tokens", title, price: detail.price };
    }
    const cond = String(detail.condition || "").toLowerCase();
    if (cond && !/\bnew\b/.test(cond)) {
      return { ok: false, reason: "pin_not_new", title, price: detail.price };
    }
    if (/\b(open\s*box|refurbished|pre[\s-]?owned|used)\b/.test(title.toLowerCase())) {
      return { ok: false, reason: "pin_open_box_title", title, price: detail.price };
    }
    const ship = Number(detail.shippingCost);
    const freeShip = Boolean(detail.freeShipping) || (isFinite(ship) && ship === 0);
    if (!freeShip && !allowPaidShip) {
      return { ok: false, reason: "pin_not_free_ship", title, price: detail.price };
    }
    const itemPrice = Number(detail.price);
    if (!isFinite(itemPrice) || itemPrice <= 0) {
      return { ok: false, reason: "pin_bad_price", title, price: detail.price };
    }
    const shipCost = freeShip ? 0 : isFinite(ship) && ship > 0 ? ship : 0;
    const price = Math.round((itemPrice + shipCost) * 100) / 100;
    const binOpts = detail.buyingOptions || [];
    if (binOpts.length && !binOpts.includes("FIXED_PRICE")) {
      return { ok: false, reason: "pin_not_bin", title, price };
    }
    return {
      ok: true,
      price,
      currency: detail.currency || "USD",
      title,
      condition: detail.condition || "New",
      itemId: detail.itemId,
      itemWebUrl: detail.itemWebUrl,
      itemAffiliateWebUrl: null,
      shippingCost: shipCost,
      seller: detail.seller,
    };
  } catch (err) {
    return { ok: false, reason: "pin_error:" + String(err?.message || err), title: null, price: null };
  }
}

function passesRequireTokens(title, requireTokens) {
  if (!Array.isArray(requireTokens) || !requireTokens.length) return true;
  const t = String(title || "").toLowerCase();
  return requireTokens.every((tok) => t.includes(String(tok || "").toLowerCase()));
}

/**
 * Reject accessory / replacement / partial listings that match brand keywords
 * but not the full product (e.g. Klein tip instead of 11-in-1 set).
 */
function isLikelyAccessoryTitle(title, q) {
  const t = String(title || "").toLowerCase();
  if (!t) return true;

  const accessoryRe =
    /\b(replacement|refill|spare\s*part|parts?\s*only|bit\s*only|tips?\s*only|for\s+parts|as[\s-]?is|broken|damaged|housing\s*only|battery\s*only|charger\s*only|case\s*only|cover\s*only|hose\s*only|blade\s*only|bit\s*set\s*for|compatible\s+with\s+klein|carrying\s*case|case\s*bag|bag\s*\(|bag\s+for|storage\s*bag|protective\s*(case|cover|bag|eva)|hard\s*travel\s*case|eva\s*(case|bag)|travel\s*case|charging\s*cable|dc\s*(charging\s*)?cable|cable\s+for|cable\s+cord|usb\s*(charging\s*)?(power\s*)?(cable|cord)|adapter\s+only|mount\s+only|bracket\s+only|hardwire\s*kit|cpl\s*filter|power\s*charging\s*(data\s*)?cord|wall\s*plug\s+to)\b/i;
  if (accessoryRe.test(t)) return true;
  // Cases/cables sold for a brand/product (not the unit itself)
  if (
    /\b(case|bag|pouch|eva|cable|cord)\b/.test(t) &&
    /\b(for|fits|compatible|protective|to)\b/.test(t) &&
    /\b(noco|gb\d{2}|jump\s*starter|redtiger|jackery|dewalt)\b/.test(t)
  ) {
    return true;
  }
  // NOCO jump packs: reject cables/cases/wall chargers sold as accessories
  if (
    /\b(noco|gb40|gb20|gb70)\b/.test(t) &&
    /\b(cable|cord|case|bag|pouch|eva|adapter)\b/.test(t)
  ) {
    return true;
  }
  if (/\bcharger\b/.test(t) && /\b(for|to)\b/.test(t) && /\b(noco|gb40|gb20)\b/.test(t)) {
    return true;
  }

  // "FOR DEWALT ..." kits / third-party combo shells that are not the OEM product
  if (/^\s*for\s+(dewalt|makita|milwaukee|craftsman|bosch|ryobi)\b/i.test(t)) return true;
  // Accessories marketed "for Jackery/Anker/..." (bags, panels, cables)
  if (/\bfor\s+(jackery|anker|bluetti|ecoflow|solix|goal\s*zero|redtiger)\b/i.test(t)) return true;
  // Power-station search should not return solar panels / cases
  const qLower = String(q || "").toLowerCase();
  if (/\bpower\s*station\b/.test(qLower) && /\b(solar\s*panel|carrying\s*case|case\s*bag)\b/.test(t)) {
    return true;
  }
  // Dual dash-cam products: require "rear" when query asks for front+rear
  if (/\brear\b/.test(qLower) && !/\brear\b/.test(t)) {
    return true;
  }

  // Single tip / driver bit sold as "Klein" — title is mostly a tip size, not the full tool
  if (
    /\b(ph[012]|slotted|torx|t[0-9]{1,2})\b/.test(t) &&
    !/\b(11[\s-]?in[\s-]?1|multi[\s-]?bit|nut\s*driver|screwdriver)\b/.test(t)
  ) {
    if (/\b(klein|32500)\b/.test(t) && t.length < 70) return true;
  }

  // "Klein 32483 Bit 11 in 1" style — selling a bit, not the 32500 handle set
  if (/\bbit\b/.test(t) && !/\b(multi[\s-]?bit|11[\s-]?in[\s-]?1|nut\s*driver)\b/.test(t)) {
    if (/\b(klein|screwdriver)\b/.test(t)) return true;
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

/** Model numbers (e.g. 32500) — if present in query, require them in the title. */
function requiredModelTokens(q) {
  return String(q || "")
    .toLowerCase()
    .match(/\b[a-z]*\d{4,}[a-z0-9]*\b/g) || [];
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

function rankCandidates(summaries, q, opts = {}) {
  const out = [];
  const rejected = [];
  const models = requiredModelTokens(q);
  const requireTokens = opts.requireTokens || null;

  for (const item of summaries) {
    const value = Number(item?.price?.value);
    const title = item.title || "";
    const tLower = title.toLowerCase();
    const baseReject = {
      itemId: item.itemId || null,
      title: title.slice(0, 90),
      price: isFinite(value) ? Math.round(value * 100) / 100 : null,
    };

    if (!isFinite(value) || value <= 0) {
      rejected.push({ ...baseReject, reason: "bad_price" });
      continue;
    }
    if (isLikelyAccessoryTitle(title, q)) {
      rejected.push({ ...baseReject, reason: "accessory_title" });
      continue;
    }

    const cond = String(item.condition || "").toLowerCase();
    if (cond && !/\bnew\b/.test(cond)) {
      rejected.push({ ...baseReject, reason: "not_new:" + (item.condition || "unknown") });
      continue;
    }
    if (/\b(open\s*box|refurbished|pre[\s-]?owned|used)\b/.test(tLower)) {
      rejected.push({ ...baseReject, reason: "open_box_or_used_title" });
      continue;
    }

    if (models.length) {
      const hasModel = models.some((m) => tLower.includes(m));
      if (!hasModel) {
        rejected.push({ ...baseReject, reason: "missing_model_token" });
        continue;
      }
    }

    if (!passesRequireTokens(title, requireTokens)) {
      rejected.push({ ...baseReject, reason: "missing_require_tokens" });
      continue;
    }

    const rel = titleRelevance(title, q);
    if (rel < 0.4) {
      rejected.push({ ...baseReject, reason: "low_title_relevance:" + rel.toFixed(2) });
      continue;
    }

    const optsShip = item.shippingOptions || [];
    let shipHint = null;
    if (optsShip.length) {
      const sc = Number(optsShip[0]?.shippingCost?.value);
      if (isFinite(sc)) shipHint = sc;
    }

    const totalHint = value + (shipHint == null ? 0 : shipHint);
    out.push({
      score: totalHint - rel * 1.5 + (shipHint === 0 ? 0 : 0.5),
      totalHint,
      price: Math.round(value * 100) / 100,
      currency: item.price?.currency || "USD",
      title,
      condition: item.condition || "New",
      itemId: item.itemId || "",
      itemWebUrl: item.itemWebUrl || "",
      itemAffiliateWebUrl: item.itemAffiliateWebUrl || "",
      shippingHint: shipHint,
      seller: item.seller?.username || "",
      relevance: rel,
    });
  }
  out.sort((a, b) => a.score - b.score || a.price - b.price);
  // Keep cheapest rejected samples first for debugging
  rejected.sort((a, b) => (a.price ?? 1e12) - (b.price ?? 1e12));
  return { ranked: out, rejected: rejected.slice(0, 12) };
}

/** Confirm shipping via item detail API (free by default; paid allowed opt-in). */
async function verifyShipping(cand, env, opts = {}) {
  const allowPaidShip = Boolean(opts.allowPaidShip);
  if (!cand?.itemId) return { ok: false, reason: "no_item_id" };
  try {
    const detail = await getItemById(cand.itemId, env);
    if (!detail?.ok) return { ok: false, reason: "item_fetch_failed" };
    const ship = Number(detail.shippingCost);
    const freeShip = Boolean(detail.freeShipping) || (isFinite(ship) && ship === 0);
    if (!freeShip && !allowPaidShip) return { ok: false, reason: "not_free_ship" };
    const itemPrice = Number(detail.price);
    if (!isFinite(itemPrice) || itemPrice <= 0) return { ok: false, reason: "bad_detail_price" };
    const cond = String(detail.condition || "").toLowerCase();
    if (cond && !/\bnew\b/.test(cond)) return { ok: false, reason: "detail_not_new" };
    if (/\b(open\s*box|refurbished|pre[\s-]?owned|used)\b/.test(String(detail.title || "").toLowerCase())) {
      return { ok: false, reason: "detail_open_box_title" };
    }
    const binOpts = detail.buyingOptions || [];
    if (binOpts.length && !binOpts.includes("FIXED_PRICE")) {
      return { ok: false, reason: "not_buy_it_now" };
    }
    const shipCost = freeShip ? 0 : isFinite(ship) && ship > 0 ? ship : 0;
    // Landed cost when paid ship so Amazon vs eBay compare stays honest
    const price = Math.round((itemPrice + shipCost) * 100) / 100;
    return {
      ok: true,
      listing: {
        price,
        currency: detail.currency || cand.currency || "USD",
        title: detail.title || cand.title,
        condition: detail.condition || cand.condition,
        itemId: detail.itemId || cand.itemId,
        itemWebUrl: detail.itemWebUrl || cand.itemWebUrl,
        itemAffiliateWebUrl: cand.itemAffiliateWebUrl || null,
        shippingCost: shipCost,
        seller: detail.seller || cand.seller,
      },
    };
  } catch (err) {
    return { ok: false, reason: "verify_error:" + String(err?.message || err) };
  }
}

/** @deprecated name kept for greps — use verifyShipping */
async function verifyFreeShipping(cand, env) {
  return verifyShipping(cand, env, { allowPaidShip: false });
}

/** Look up one eBay listing (for debugging false matches / shipping). */
async function getItemById(rawId, env) {
  const token = await getAccessToken(env);
  // Accept plain legacy ids (147380418292) or REST ids (v1|147380418292|0)
  let itemPath = String(rawId).trim();
  if (/^\d+$/.test(itemPath)) {
    itemPath = "v1|" + itemPath + "|0";
  }
  const fetchUrl =
    "https://api.ebay.com/buy/browse/v1/item/" + encodeURIComponent(itemPath);

  const headers = {
    Authorization: "Bearer " + token,
    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    Accept: "application/json",
  };
  const res = await fetch(fetchUrl, { headers });
  if (!res.ok) {
    const text = await res.text();
    return {
      ok: false,
      error: "item_fetch_failed",
      status: res.status,
      itemPath,
      detail: text.slice(0, 500),
    };
  }
  const data = await res.json();
  const price = Number(data?.price?.value);
  let ship = null;
  const opts = data?.shippingOptions || [];
  if (opts.length) {
    const sc = Number(opts[0]?.shippingCost?.value);
    if (isFinite(sc)) ship = sc;
  }
  const freeShip =
    ship === 0 ||
    (Array.isArray(data?.shippingOptions) &&
      data.shippingOptions.some(
        (o) =>
          Number(o?.shippingCost?.value) === 0 ||
          String(o?.shippingCostType || "").toUpperCase() === "FREE"
      ));

  return {
    ok: true,
    itemId: data.itemId || itemPath,
    title: data.title || "",
    condition: data.condition || data.conditionId || null,
    price: isFinite(price) ? price : null,
    currency: data?.price?.currency || "USD",
    shippingCost: ship,
    freeShipping: freeShip,
    total:
      isFinite(price) && isFinite(ship)
        ? Math.round((price + ship) * 100) / 100
        : isFinite(price)
          ? price
          : null,
    buyingOptions: data.buyingOptions || [],
    itemWebUrl: data.itemWebUrl || null,
    itemLocation: data.itemLocation || null,
    seller: data?.seller?.username || null,
  };
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

/**
 * Cached TikTok creator feed for the site "From the Vault" section.
 * Source: public creator embed page (same approach as tiktok/sync_videos.py).
 */
async function getTikTokVideos(env, ctx, force) {
  // Authorized force refresh only (caller must have passed assertRefreshAuth).
  if (force) {
    try {
      return await refreshTikTokVideos(env);
    } catch (err) {
      if (env.PRICES) {
        const cached = await env.PRICES.get(TIKTOK_KV_KEY, "json");
        if (cached) return cached;
      }
      return {
        ok: false,
        error: "tiktok_fetch_failed",
        message: String(err && err.message ? err.message : err),
        username: TIKTOK_USERNAME,
        profileUrl: "https://www.tiktok.com/@" + TIKTOK_USERNAME,
        maxDisplay: TIKTOK_MAX,
        videos: [],
        updatedAt: new Date().toISOString(),
      };
    }
  }

  // Public path: serve KV cache only — never let anonymous traffic hit TikTok.
  if (env.PRICES) {
    const cached = await env.PRICES.get(TIKTOK_KV_KEY, "json");
    if (cached && Array.isArray(cached.videos) && cached.videos.length) {
      return cached;
    }
  }
  return {
    ok: false,
    error: "tiktok_cache_empty",
    message:
      "TikTok list not cached. Use authorized POST /v1/tiktok/refresh or wait for scheduled sync. Site falls back to tiktok/videos.json.",
    username: TIKTOK_USERNAME,
    profileUrl: "https://www.tiktok.com/@" + TIKTOK_USERNAME,
    maxDisplay: TIKTOK_MAX,
    videos: [],
    updatedAt: new Date().toISOString(),
  };
}

async function refreshTikTokVideos(env) {
  const username = TIKTOK_USERNAME;
  const embedUrl = "https://www.tiktok.com/embed/@" + username;
  const res = await fetch(embedUrl, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      Accept: "text/html,application/json,*/*",
      "Accept-Language": "en-US,en;q=0.9",
    },
  });
  if (!res.ok) {
    throw new Error("tiktok_embed_http_" + res.status);
  }
  const html = await res.text();
  const rawList = parseTikTokEmbedVideoList(html);
  if (!rawList.length) {
    throw new Error("tiktok_embed_empty");
  }

  const videos = rawList.slice(0, TIKTOK_MAX).map((item) => {
    const id = String(item.id || "").trim();
    const desc = String(item.desc || "");
    const cover =
      item.coverUrl || item.originCoverUrl || item.dynamicCoverUrl || "";
    return {
      id,
      title: titleFromTikTokDesc(desc, "TikTok · @" + username),
      url: "https://www.tiktok.com/@" + username + "/video/" + id,
      cover,
      desc: desc.slice(0, 280),
    };
  }).filter((v) => v.id);

  const payload = {
    ok: true,
    source: "tiktok_embed",
    username,
    profileUrl: "https://www.tiktok.com/@" + username,
    maxDisplay: TIKTOK_MAX,
    count: videos.length,
    updatedAt: new Date().toISOString(),
    videos,
  };

  if (env.PRICES) {
    await env.PRICES.put(TIKTOK_KV_KEY, JSON.stringify(payload), {
      expirationTtl: TIKTOK_CACHE_SECONDS * 4,
    });
  }
  return payload;
}

function parseTikTokEmbedVideoList(html) {
  const scripts = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi) || [];
  for (const tag of scripts) {
    const raw = tag.replace(/^<script[^>]*>/i, "").replace(/<\/script>$/i, "");
    if (!raw.includes("videoList")) continue;
    try {
      const data = JSON.parse(raw);
      const source = (data.source && data.source.data) || {};
      for (const key of Object.keys(source)) {
        const page = source[key];
        if (page && Array.isArray(page.videoList) && page.videoList.length) {
          return page.videoList;
        }
      }
    } catch (_) {
      /* try next script */
    }
  }
  // Fallback: bare ids
  const ids = [...html.matchAll(/\/@[\w.]+\/video\/(\d{15,})/g)].map((m) => m[1]);
  const unique = [...new Set(ids)];
  return unique.map((id) => ({ id, desc: "", coverUrl: "" }));
}

function titleFromTikTokDesc(desc, fallback) {
  if (!desc) return fallback;
  let text = String(desc)
    .replace(/[#@]\S+/g, " ")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const hook = text.match(/^(.{10,72}?)[!?]/);
  if (hook) {
    text = hook[1].trim();
  } else {
    for (const sep of [". ", " — ", " - ", "\n"]) {
      if (text.includes(sep)) {
        text = text.split(sep)[0].trim();
        break;
      }
    }
  }
  if (text.length > 68) {
    const cut = text.slice(0, 65).split(" ").slice(0, -1).join(" ");
    text = (cut || text.slice(0, 65)).replace(/[.,;:]+$/, "") + "…";
  }
  return text || fallback;
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

/**
 * Fail-closed refresh auth.
 * - REFRESH_TOKEN must be set as a Worker secret
 * - Client must send header X-Refresh-Token (query ?token= rejected to avoid log leaks)
 */
function assertRefreshAuth(request, env) {
  const required = String(env.REFRESH_TOKEN || "").trim();
  if (!required) {
    return json(
      {
        error: "refresh_locked",
        message:
          "Full catalog refresh is locked. Set Worker secret REFRESH_TOKEN and send header X-Refresh-Token. See docs/SECURITY.md",
      },
      503,
      request,
      env
    );
  }
  const got = String(request.headers.get("X-Refresh-Token") || "").trim();
  // Reject tokens passed in the query string (they end up in access logs / Referer).
  try {
    const u = new URL(request.url);
    if (u.searchParams.has("token")) {
      return json(
        {
          error: "unauthorized",
          message: "Pass refresh auth only via X-Refresh-Token header, not ?token=",
        },
        401,
        request,
        env
      );
    }
  } catch (_) {
    /* ignore */
  }
  if (!got || !timingSafeEqualString(got, required)) {
    return json({ error: "unauthorized" }, 401, request, env);
  }
  return null;
}

function timingSafeEqualString(a, b) {
  const enc = new TextEncoder();
  const ba = enc.encode(a);
  const bb = enc.encode(b);
  if (ba.length !== bb.length) {
    // Still walk the longer buffer to reduce length-oracle noise
    let diff = ba.length ^ bb.length;
    const n = Math.max(ba.length, bb.length);
    for (let i = 0; i < n; i++) {
      const x = i < ba.length ? ba[i] : 0;
      const y = i < bb.length ? bb[i] : 0;
      diff |= x ^ y;
    }
    return false;
  }
  let diff = 0;
  for (let i = 0; i < ba.length; i++) diff |= ba[i] ^ bb[i];
  return diff === 0;
}

function clientIpFrom(request) {
  return (
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("True-Client-IP") ||
    (request.headers.get("X-Forwarded-For") || "").split(",")[0].trim() ||
    "unknown"
  );
}

/**
 * Fixed-window rate limit stored in KV. Returns a 429 Response or null if allowed.
 */
async function enforceRateLimit(env, bucket, ip, cfg, request) {
  if (!env.PRICES || !cfg) return null;
  const windowSec = Math.max(10, Number(cfg.windowSec) || 60);
  const limit = Math.max(1, Number(cfg.limit) || 60);
  const windowId = Math.floor(Date.now() / (windowSec * 1000));
  // Hash-ish key keeps KV tidy; IP still unique per bucket
  const key = "rl:" + bucket + ":" + windowId + ":" + String(ip).slice(0, 64);
  let count = 0;
  try {
    count = parseInt((await env.PRICES.get(key)) || "0", 10) || 0;
  } catch (_) {
    return null; // fail open on KV read errors so the site keeps working
  }
  if (count >= limit) {
    return json(
      {
        error: "rate_limited",
        message: "Too many requests. Slow down and try again shortly.",
        bucket,
        retryAfterSeconds: windowSec,
      },
      429,
      request,
      env,
      { "Retry-After": String(windowSec) }
    );
  }
  try {
    await env.PRICES.put(key, String(count + 1), {
      expirationTtl: windowSec + 30,
    });
  } catch (_) {
    /* ignore write errors */
  }
  return null;
}

function allowedOrigins(env) {
  const fromEnv = String(env.ALLOWED_ORIGINS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return fromEnv.length ? fromEnv : DEFAULT_ALLOWED_ORIGINS;
}

function pickCorsOrigin(request, env) {
  if (!request) return DEFAULT_ALLOWED_ORIGINS[0];
  const origin = request.headers.get("Origin") || "";
  const allowed = allowedOrigins(env);
  if (origin && allowed.includes(origin)) return origin;
  // Non-browser clients (curl, GitHub Actions) — no Origin header
  if (!origin) return allowed[0];
  // Unknown browser origin: omit allow (browser will block). Still return a
  // safe default header only for same-site tools that ignore CORS.
  return null;
}

function json(obj, status, request, env, extraHeaders) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
  };
  if (extraHeaders) {
    for (const [k, v] of Object.entries(extraHeaders)) headers[k] = v;
  }
  return withCors(
    new Response(JSON.stringify(obj, null, 0), {
      status: status || 200,
      headers,
    }),
    request,
    env
  );
}

function withCors(res, request, env) {
  const headers = new Headers(res.headers);
  const origin = pickCorsOrigin(request, env || {});
  if (origin) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Vary", "Origin");
  }
  headers.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, X-Refresh-Token");
  headers.set("Access-Control-Max-Age", "86400");
  // Mild hardening headers on API responses
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("Referrer-Policy", "no-referrer");
  return new Response(res.body, { status: res.status, headers });
}
