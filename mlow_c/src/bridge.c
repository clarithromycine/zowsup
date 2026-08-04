/*
 * bridge.c — C ABI entry point.
 *
 * The Python ctypes loader calls these 8 functions.  Each one dispatches
 * to the internal decoder/encoder implementation.  The handle→instance
 * map uses a simple mutex-protected hash table.
 */

#include "mlow.h"
#include "mlow_internal.h"

#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* ── Handle registry ────────────────────────────────────────────────────────── */

typedef struct {
    uint64_t id;
    void *instance;  /* MlowDecoder* or MlowEncoder* */
} slot_t;

#define SLOTS_INIT_CAP 16

typedef struct {
    pthread_mutex_t mu;
    uint64_t next_id;
    slot_t *slots;
    size_t cap;
    size_t count;
    int mu_inited;
} registry_t;

static registry_t g_decoders;
static registry_t g_encoders;

static void registry_init(registry_t *r) {
    pthread_mutex_init(&r->mu, NULL);
    r->mu_inited = 1;
    r->next_id = 1;
    r->cap = SLOTS_INIT_CAP;
    r->count = 0;
    r->slots = (slot_t *)calloc(r->cap, sizeof(slot_t));
}

static uint64_t registry_add(registry_t *r, void *instance) {
    pthread_mutex_lock(&r->mu);
    uint64_t id = r->next_id++;
    if (r->count >= r->cap) {
        r->cap *= 2;
        r->slots = (slot_t *)realloc(r->slots, r->cap * sizeof(slot_t));
        memset(r->slots + r->count, 0, (r->cap - r->count) * sizeof(slot_t));
    }
    r->slots[r->count].id = id;
    r->slots[r->count].instance = instance;
    r->count++;
    pthread_mutex_unlock(&r->mu);
    return id;
}

static void *registry_get(registry_t *r, uint64_t id) {
    pthread_mutex_lock(&r->mu);
    void *inst = NULL;
    for (size_t i = 0; i < r->count; i++) {
        if (r->slots[i].id == id) {
            inst = r->slots[i].instance;
            break;
        }
    }
    pthread_mutex_unlock(&r->mu);
    return inst;
}

static void *registry_remove(registry_t *r, uint64_t id) {
    pthread_mutex_lock(&r->mu);
    void *inst = NULL;
    for (size_t i = 0; i < r->count; i++) {
        if (r->slots[i].id == id) {
            inst = r->slots[i].instance;
            r->slots[i] = r->slots[r->count - 1];
            r->count--;
            break;
        }
    }
    pthread_mutex_unlock(&r->mu);
    return inst;
}

/* ── One-time init (thread-safe via mutex) ───────────────────────────────────── */
static pthread_mutex_t g_init_mu = PTHREAD_MUTEX_INITIALIZER;
static int g_initialized = 0;

static void do_global_init(void) {
    registry_init(&g_decoders);
    registry_init(&g_encoders);
    mlow_tables_init();  /* load seed data, build runtime tables */
}

static inline void ensure_init(void) {
    if (g_initialized) return;
    pthread_mutex_lock(&g_init_mu);
    if (!g_initialized) {
        do_global_init();
        g_initialized = 1;
    }
    pthread_mutex_unlock(&g_init_mu);
}

/* ── Cleanup at process exit ────────────────────────────────────────────────── */
/* NOTE: We do NOT install a destructor for the shared library.
 * On macOS, __attribute__((destructor)) in a dylib loaded via dlopen/ctypes
 * runs during Python interpreter teardown, which can interact badly with
 * Python's GC and ctypes cleanup.  The OS will reclaim all memory at process
 * exit, so explicit cleanup is unnecessary.
 *
 * If you need deterministic cleanup, call an explicit mlow_cleanup() function
 * before unloading the library.
 */
#if 0
__attribute__((destructor))
static void bridge_cleanup(void) {
    fprintf(stderr, "[bridge] destructor start\n"); fflush(stderr);
    fprintf(stderr, "[bridge] decoders: count=%zu cap=%zu mu_inited=%d\n",
            g_decoders.count, g_decoders.cap, g_decoders.mu_inited); fflush(stderr);
    fprintf(stderr, "[bridge] encoders: count=%zu cap=%zu mu_inited=%d\n",
            g_encoders.count, g_encoders.cap, g_encoders.mu_inited); fflush(stderr);
    if (g_decoders.mu_inited) {
        fprintf(stderr, "[bridge] destroying decoders mutex\n"); fflush(stderr);
        pthread_mutex_destroy(&g_decoders.mu);
        g_decoders.mu_inited = 0;
    }
    if (g_encoders.mu_inited) {
        fprintf(stderr, "[bridge] destroying encoders mutex\n"); fflush(stderr);
        pthread_mutex_destroy(&g_encoders.mu);
        g_encoders.mu_inited = 0;
    }
    fprintf(stderr, "[bridge] destroying init mutex\n"); fflush(stderr);
    pthread_mutex_destroy(&g_init_mu);
    fprintf(stderr, "[bridge] destructor done\n"); fflush(stderr);
}
#endif

/* ── Decoder ABI ────────────────────────────────────────────────────────────── */

MLOW_API uint64_t mlow_decoder_create(void) {
    ensure_init();
    MlowDecoder *d = mlow_decoder_new();
    if (!d) return 0;
    return registry_add(&g_decoders, d);
}

MLOW_API void mlow_decoder_destroy(uint64_t handle) {
    ensure_init();
    MlowDecoder *d = (MlowDecoder *)registry_remove(&g_decoders, handle);
    if (d) mlow_decoder_free(d);
}

MLOW_API void mlow_decoder_reset(uint64_t handle) {
    ensure_init();
    MlowDecoder *d = (MlowDecoder *)registry_get(&g_decoders, handle);
    if (d) mlow_decoder_reset_impl(d);
}

MLOW_API void mlow_set_redundancy(uint64_t handle, int n) {
    ensure_init();
    MlowDecoder *d = (MlowDecoder *)registry_get(&g_decoders, handle);
    if (d) mlow_decoder_set_redundancy(d, n);
}

MLOW_API int mlow_decode(uint64_t handle,
                          const uint8_t *data,
                          int length,
                          float *pcm_out,
                          int max_samples) {
    ensure_init();
    MlowDecoder *d = (MlowDecoder *)registry_get(&g_decoders, handle);
    if (!d) return -1;
    return mlow_decoder_decode(d, data, length, pcm_out, max_samples);
}

/* ── Encoder ABI ────────────────────────────────────────────────────────────── */

MLOW_API uint64_t mlow_encoder_create(void) {
    ensure_init();
    MlowEncoder *e = mlow_encoder_new();
    if (!e) return 0;
    return registry_add(&g_encoders, e);
}

MLOW_API void mlow_encoder_destroy(uint64_t handle) {
    ensure_init();
    MlowEncoder *e = (MlowEncoder *)registry_remove(&g_encoders, handle);
    if (e) mlow_encoder_free(e);
}

MLOW_API void mlow_encoder_reset(uint64_t handle) {
    ensure_init();
    MlowEncoder *e = (MlowEncoder *)registry_get(&g_encoders, handle);
    if (e) mlow_encoder_reset_impl(e);
}

MLOW_API int mlow_encode(uint64_t handle,
                          const float *pcm_in,
                          int pcm_len,
                          uint8_t *enc_out,
                          int max_enc) {
    ensure_init();
    MlowEncoder *e = (MlowEncoder *)registry_get(&g_encoders, handle);
    if (!e) return -1;
    return mlow_encoder_encode(e, pcm_in, pcm_len, enc_out, max_enc);
}