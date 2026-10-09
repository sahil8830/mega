/**
 * Redis Search Cache Service
 *
 * Two-level cache for the search pipeline:
 *
 *   Level 1 — GQE cache  (key: gqe:v1:{queryHash})
 *     Stores flan-t5 expansion results + CLIP representative embeddings.
 *     TTL: 7 days.  GQE is pure query → no user dependency.
 *     Savings: 5–30 s → <5 ms on cache hit.
 *
 *   Level 2 — Full search result cache  (key: search:v1:{userId}:{queryHash})
 *     Stores the complete ranked ML result array.
 *     TTL: 30 min.  Scoped per user (FAISS namespace is per-user).
 *     Savings: 200–500 ms → <5 ms on cache hit.
 *
 * Cache is invalidated automatically by TTL.
 * When a video is re-indexed we also flush the user's search result cache.
 */
import IORedis from "ioredis";
import crypto   from "crypto";

// ─── Connection ───────────────────────────────────────────────────────────────
// Separate client from the BullMQ connection (different maxRetriesPerRequest)
let _redis = null;

function getRedis() {
  if (_redis) return _redis;
  _redis = new IORedis({
    host:     process.env.REDIS_HOST     || "localhost",
    port:     parseInt(process.env.REDIS_PORT) || 6379,
    password: process.env.REDIS_PASSWORD || undefined,
    lazyConnect: true,
    enableOfflineQueue: false,          // don't queue if Redis is down
    retryStrategy: (times) => {
      if (times > 3) return null;       // give up after 3 retries → fallback to no-cache
      return Math.min(times * 200, 2000);
    },
  });

  _redis.on("error", (err) => {
    // Log once, don't crash the server
    console.warn("[SearchCache] Redis error (search caching disabled):", err.message);
  });

  return _redis;
}

// ─── Key Helpers ──────────────────────────────────────────────────────────────
const CACHE_VERSION = "v1";

export function queryHash(query) {
  return crypto.createHash("sha256").update(query.trim().toLowerCase()).digest("hex");
}

export function gqeKey(query) {
  return `gqe:${CACHE_VERSION}:${queryHash(query)}`;
}

export function searchKey(userId, query) {
  return `search:${CACHE_VERSION}:${userId}:${queryHash(query)}`;
}

export function userSearchPattern(userId) {
  return `search:${CACHE_VERSION}:${userId}:*`;
}

// ─── TTLs ────────────────────────────────────────────────────────────────────
const GQE_TTL_S    = 7 * 24 * 60 * 60;  // 7 days
const SEARCH_TTL_S = 30 * 60;            // 30 minutes

// ─── GQE Cache ────────────────────────────────────────────────────────────────

/**
 * Try to get a cached GQE result.
 * Returns parsed object or null if miss / Redis unavailable.
 */
export async function getGqeCache(query) {
  try {
    const r = getRedis();
    const raw = await r.get(gqeKey(query));
    if (!raw) return null;
    const data = JSON.parse(raw);
    console.log(`[SearchCache] GQE cache HIT for: "${query}"`);
    return data;
  } catch {
    return null;   // Redis down or parse error — treat as miss
  }
}

/**
 * Store a GQE result in Redis.
 */
export async function setGqeCache(query, gqeData) {
  try {
    const r = getRedis();
    await r.set(gqeKey(query), JSON.stringify(gqeData), "EX", GQE_TTL_S);
    console.log(`[SearchCache] GQE cached (${GQE_TTL_S}s): "${query}"`);
  } catch {
    /* non-fatal */
  }
}

// ─── Search Result Cache ──────────────────────────────────────────────────────

/**
 * Try to get a cached full search result.
 * Returns parsed object or null if miss / Redis unavailable.
 */
export async function getSearchCache(userId, query) {
  try {
    const r = getRedis();
    const raw = await r.get(searchKey(userId, query));
    if (!raw) return null;
    const data = JSON.parse(raw);
    console.log(`[SearchCache] Search cache HIT for user=${userId} query="${query}"`);
    return data;
  } catch {
    return null;
  }
}

/**
 * Store a full search result in Redis.
 */
export async function setSearchCache(userId, query, resultData) {
  try {
    const r = getRedis();
    await r.set(searchKey(userId, query), JSON.stringify(resultData), "EX", SEARCH_TTL_S);
    console.log(`[SearchCache] Search result cached (${SEARCH_TTL_S}s): user=${userId} "${query}"`);
  } catch {
    /* non-fatal */
  }
}

/**
 * Invalidate ALL cached search results for a user.
 * Call this when a video is re-indexed so stale results don't surface.
 */
export async function invalidateUserSearchCache(userId) {
  try {
    const r = getRedis();
    const pattern = userSearchPattern(userId);
    // Use SCAN to avoid blocking Redis with KEYS on large datasets
    let cursor = "0";
    let deleted = 0;
    do {
      const [nextCursor, keys] = await r.scan(cursor, "MATCH", pattern, "COUNT", 100);
      cursor = nextCursor;
      if (keys.length > 0) {
        await r.del(...keys);
        deleted += keys.length;
      }
    } while (cursor !== "0");

    if (deleted > 0) {
      console.log(`[SearchCache] Invalidated ${deleted} cached search results for user ${userId}`);
    }
  } catch {
    /* non-fatal */
  }
}

/**
 * Return basic Redis stats for health monitoring.
 */
export async function getCacheStats() {
  try {
    const r = getRedis();
    const info = await r.info("stats");
    const hits   = info.match(/keyspace_hits:(\d+)/)?.[1]   ?? "?";
    const misses = info.match(/keyspace_misses:(\d+)/)?.[1] ?? "?";
    return { hits, misses, connected: true };
  } catch {
    return { connected: false };
  }
}
