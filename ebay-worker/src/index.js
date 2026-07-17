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
const SEARCH_LIMIT = 50;
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
        const id = (url.searchParams.get("id") || "").trim();
        const cat = findCatalogEntry(id);
        const q = (url.searchParams.get("q") || cat?.q || "").trim();
        const resolvedId = (id || q).trim();
        if (!q) return json({ error: "missing_q" }, 400);
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
        return json(result);
      }

      // Debug / compare: resolve a single eBay item id (legacy or RESTful)
      if (path === "/v1/item" && request.method === "GET") {
        const itemId = (url.searchParams.get("id") || "").trim();
        if (!itemId) return json({ error: "missing_id" }, 400);
        const result = await getItemById(itemId, env);
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
          });
        }

        const prices = {};
        let idx = 0;
        async function worker() {
          while (idx < items.length) {
            const i = idx++;
            const { id, q, ebayPreferItemId, requireTokens } = items[i];
            try {
              prices[id] = await getLowestPrice(q, id, env, ctx, {
                ebayPreferItemId,
                requireTokens,
              });
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
        const entry = items[i] || {};
        const id = entry.id;
        const q = entry.q;
        try {
          const row = await getLowestPrice(q, id, env, ctx, {
            skipCacheRead: true,
            ebayPreferItemId: entry.ebayPreferItemId || null,
            requireTokens: entry.requireTokens || null,
          });
          if (!prices[id]) prices[id] = { id, q };
          if (row?.ok && isFinite(Number(row.price))) {
            prices[id].ebay = Number(row.price);
            prices[id].ebayOk = true;
            prices[id].ebayTitle = row.title || null;
            prices[id].ebayItemId = row.itemId || null;
            prices[id].ebayItemWebUrl = row.itemWebUrl || null;
            prices[id].ebaySource = row.matchSource || row.source || "live";
            prices[id].ebayRejects = Array.isArray(row.rejected) ? row.rejected.slice(0, 3) : [];
          } else {
            // Explicit no-match: do not leave a stale price in the snapshot
            prices[id].ebay = null;
            prices[id].ebayOk = false;
            prices[id].ebayError = row?.error || "no_price";
            prices[id].ebayMessage = row?.message || null;
            prices[id].ebayRejects = Array.isArray(row?.rejected) ? row.rejected.slice(0, 5) : [];
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

  // v4: pins + reject logging + requireTokens
  const cacheKeyUrl = `https://aipickvault-ebay-cache.internal/v4/${hashKey(
    searchQ + "|" + pinId + "|" + JSON.stringify(requireTokens || [])
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
    const pinned = await tryPinnedListing(pinId, searchQ, requireTokens, env);
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
        shippingCost: 0,
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
  const filter = [
    "conditions:{NEW}",
    "maxDeliveryCost:0",
    "buyingOptions:{FIXED_PRICE}",
    "itemLocationCountry:US",
    "priceCurrency:USD",
  ].join(",");

  const search = new URL(EBAY_SEARCH_URL);
  search.searchParams.set("q", searchQ);
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
      q: searchQ,
      error: "ebay_search_failed",
      status: res.status,
      detail: text.slice(0, 400),
      rejected: rejected.slice(0, 5),
    };
  }

  const data = await res.json();
  const summaries = Array.isArray(data.itemSummaries) ? data.itemSummaries : [];
  const { ranked, rejected: rankRejected } = rankCandidates(summaries, searchQ, {
    requireTokens,
  });
  for (const r of rankRejected.slice(0, 8)) rejected.push(r);

  let best = null;
  for (const cand of ranked.slice(0, 10)) {
    const verified = await verifyFreeShipping(cand, env);
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
      message:
        "No New + free-shipping US Buy It Now listings found (or only accessory/false matches)",
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

/** Try a human-pinned eBay item id; must still be New + free ship + title rules. */
async function tryPinnedListing(pinId, q, requireTokens, env) {
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
    if (!detail.freeShipping) {
      return { ok: false, reason: "pin_not_free_ship", title, price: detail.price };
    }
    const price = Number(detail.price);
    if (!isFinite(price) || price <= 0) {
      return { ok: false, reason: "pin_bad_price", title, price: detail.price };
    }
    const opts = detail.buyingOptions || [];
    if (opts.length && !opts.includes("FIXED_PRICE")) {
      return { ok: false, reason: "pin_not_bin", title, price };
    }
    return {
      ok: true,
      price: Math.round(price * 100) / 100,
      currency: detail.currency || "USD",
      title,
      condition: detail.condition || "New",
      itemId: detail.itemId,
      itemWebUrl: detail.itemWebUrl,
      itemAffiliateWebUrl: null,
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
    /\b(replacement|refill|spare\s*part|parts?\s*only|bit\s*only|tips?\s*only|for\s+parts|as[\s-]?is|broken|damaged|housing\s*only|battery\s*only|charger\s*only|case\s*only|cover\s*only|hose\s*only|blade\s*only|bit\s*set\s*for|compatible\s+with\s+klein|carrying\s*case|case\s*bag|bag\s*\(|bag\s+for|storage\s*bag|protective\s*(case|cover|bag)|charging\s*cable|dc\s*(charging\s*)?cable|cable\s+for|adapter\s+only|mount\s+only|bracket\s+only|hardwire\s*kit|cpl\s*filter|power\s*charging\s*(data\s*)?cord|wall\s*plug\s+to)\b/i;
  if (accessoryRe.test(t)) return true;

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

/** Confirm free US shipping via item detail API (more reliable than search). */
async function verifyFreeShipping(cand, env) {
  if (!cand?.itemId) return { ok: false, reason: "no_item_id" };
  try {
    const detail = await getItemById(cand.itemId, env);
    if (!detail?.ok) return { ok: false, reason: "item_fetch_failed" };
    if (!detail.freeShipping) return { ok: false, reason: "not_free_ship" };
    const price = Number(detail.price);
    if (!isFinite(price) || price <= 0) return { ok: false, reason: "bad_detail_price" };
    const cond = String(detail.condition || "").toLowerCase();
    if (cond && !/\bnew\b/.test(cond)) return { ok: false, reason: "detail_not_new" };
    if (/\b(open\s*box|refurbished|pre[\s-]?owned|used)\b/.test(String(detail.title || "").toLowerCase())) {
      return { ok: false, reason: "detail_open_box_title" };
    }
    const opts = detail.buyingOptions || [];
    if (opts.length && !opts.includes("FIXED_PRICE")) {
      return { ok: false, reason: "not_buy_it_now" };
    }
    return {
      ok: true,
      listing: {
        price: Math.round(price * 100) / 100,
        currency: detail.currency || cand.currency || "USD",
        title: detail.title || cand.title,
        condition: detail.condition || cand.condition,
        itemId: detail.itemId || cand.itemId,
        itemWebUrl: detail.itemWebUrl || cand.itemWebUrl,
        itemAffiliateWebUrl: cand.itemAffiliateWebUrl || null,
        shippingCost: 0,
        seller: detail.seller || cand.seller,
      },
    };
  } catch (err) {
    return { ok: false, reason: "verify_error:" + String(err?.message || err) };
  }
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
