/*
 * fft.c — Complex FFT and real FFT forward.
 * Optimized: precomputed twiddle table + pre-allocated scratch.
 * Algorithm unchanged from verified recursive implementation.
 */
#include "encode.h"
#include "../seed.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

static const float smpl_pi = 3.1415926535897f;

typedef struct { float re, im; } cpx_t;

static cpx_t cpx_add(cpx_t a, cpx_t b) { return (cpx_t){a.re + b.re, a.im + b.im}; }
static cpx_t cpx_mul(cpx_t a, cpx_t b) {
    return (cpx_t){a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re};
}

/* ── Precomputed twiddle factors ────────────────────────────────────────────── */
/* tw_fwd[k] = e^{-i 2π k / N}, tw_inv[k] = e^{+i 2π k / N}, N=576 */
#define FFT_N 576
static cpx_t tw_fwd[FFT_N];
static cpx_t tw_inv[FFT_N];
static bool tw_built = false;

static void build_twiddles(void) {
    if (tw_built) return;
    for (int k = 0; k < FFT_N; k++) {
        float ang = 2.0f * smpl_pi * (float)k / (float)FFT_N;
        tw_fwd[k].re = mlow_cosf32(ang);
        tw_fwd[k].im = -mlow_sinf32(ang);
        tw_inv[k].re = mlow_cosf32(ang);
        tw_inv[k].im = mlow_sinf32(ang);
    }
    tw_built = true;
}

/* Get twiddle W_N^{k} = e^{sign * i 2π k/N} from lookup table */
static cpx_t get_twiddle(int k, int N, float sign) {
    /* k can be any integer; we need W_N^k = tw[(k * FFT_N / N) % FFT_N] */
    int idx = (int)((int64_t)k * FFT_N / N) % FFT_N;
    if (idx < 0) idx += FFT_N;
    return (sign < 0) ? tw_fwd[idx] : tw_inv[idx];
}

static int smallest_factor(int n) {
    if (n % 2 == 0) return 2;
    for (int p = 3; p * p <= n; p += 2) if (n % p == 0) return p;
    return n;
}

/* ── Pre-allocated scratch for recursive FFT (max N=576) ────────────────────── */
/* Each recursion level needs n elements for sub-FFT outputs.
   For 576 = 2^6 × 3^2, the recursion tree has depth 8.
   At each level, p sub-FFTs are called sequentially. Each sub-FFT writes
   to a disjoint slice of the output (sub[q*m..(q+1)*m-1]).
   But each sub-FFT also needs its own scratch for deeper levels.
   We allocate scratch per branch: child q uses offset child_offset + q*m.
   Total max offset = sum of n at each level = 576+288+144+72+36+18+9+3 = 1146.
   But branches at the same level need separate scratch, so we need
   to give each branch its own offset. With p=2, branch 0 uses
   child_offset, branch 1 uses child_offset + m. This doubles the space.
   Safe upper bound: 4 * FFT_N.
   Thread-local so concurrent encode calls from different threads don't
   race on the scratch buffer. */
static _Thread_local cpx_t fft_sub_buf[4 * FFT_N];

static void fft_rec(const cpx_t *x, int stride, int n, float sign, cpx_t *out,
                     cpx_t *sub, int sub_offset) {
    if (n == 1) { out[0] = x[0]; return; }
    int p = smallest_factor(n);
    int m = n / p;

    if (p == n) {
        /* Prime-size DFT using twiddle lookup */
        for (int k = 0; k < n; k++) {
            cpx_t acc = {0, 0};
            for (int j = 0; j < n; j++) {
                cpx_t w = get_twiddle(k * j, n, sign);
                acc = cpx_add(acc, cpx_mul(x[j * stride], w));
            }
            out[k] = acc;
        }
        return;
    }

    /* Recursive sub-FFTs — each branch gets its own scratch region */
    for (int q = 0; q < p; q++) {
        int child_off = sub_offset + n + q * m;
        fft_rec(&x[q * stride], stride * p, m, sign, &sub[q * m],
                &fft_sub_buf[child_off], child_off);
    }

    /* Combine using twiddle lookup */
    for (int k = 0; k < n; k++) {
        int kmod = k % m;
        cpx_t acc = {0, 0};
        for (int q = 0; q < p; q++) {
            cpx_t tw = get_twiddle(k * q, n, sign);
            acc = cpx_add(acc, cpx_mul(sub[q * m + kmod], tw));
        }
        out[k] = acc;
    }
}

static void cfft(const cpx_t *input, cpx_t *out, int n, float sign) {
    build_twiddles();
    fft_rec(input, 1, n, sign, out, fft_sub_buf, 0);
}

void rfft_forward_ordered(const float *time, int n, float *f) {
    build_twiddles();
    /* Use stack arrays (n=576, cpx_t=8 bytes → 4.5KB each) */
    cpx_t cin[FFT_N];
    cpx_t spec[FFT_N];
    for (int i = 0; i < n; i++) { cin[i].re = time[i]; cin[i].im = 0.0f; }
    cfft(cin, spec, n, -1.0f);
    f[0] = spec[0].re;
    f[1] = spec[n/2].re;
    for (int i = 1; i < n/2; i++) {
        f[2*i] = spec[i].re;
        f[2*i+1] = spec[i].im;
    }
}

/* rfft_backward_ordered: inverse of rfft_forward_ordered — converts ordered-real
 * FFT representation back to time domain (unnormalized). */
void rfft_backward_ordered(const float *f, int n, float *time) {
    build_twiddles();
    cpx_t spec[FFT_N];
    cpx_t tout[FFT_N];
    spec[0].re = f[0]; spec[0].im = 0.0f;
    spec[n/2].re = f[1]; spec[n/2].im = 0.0f;
    for (int i = 1; i < n/2; i++) {
        spec[i].re = f[2*i];
        spec[i].im = f[2*i+1];
        spec[n-i].re = f[2*i];
        spec[n-i].im = -f[2*i+1];
    }
    cfft(spec, tout, n, 1.0f);
    for (int i = 0; i < n; i++) time[i] = tout[i].re;
}