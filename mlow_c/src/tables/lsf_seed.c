/*
 * lsf_seed.c �?LSF runtime table expansion from seed.
 *
 * The float op order is load-bearing (matmul accumulation, sqrt-then-reciprocal
 * in rotApplyWght, integer truncation in lsfDcmfToCmf, scalar unpack8) so the
 * rebuilt tables are bit-faithful.
 */

#include "lsf_seed.h"
#include "../seed.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "lsf_seed_data.h"

/* ── Global singletons ─────────────────────────────────────────────────────── */
lsf_cb_t            g_lsf_cb;
smpl_tables_t       g_smpl_tables;
smpl_synth_tables_t g_smpl_synth;

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const float lsf_cb_min[2]        = {-0.5873778f, -0.24721986f};
static const float lsf_cb_scale[2]       = {1.3145164e-5f, 7.226229e-6f};
static const float lsf_cinv_min[2]      = {-3.5960955e-5f, -2.778548e-5f};
static const float lsf_cinv_scale[2]    = {1.8589316e-9f, 1.2180106e-9f};
static const float lsf_rot_min[2]       = {-0.9124832f, -0.8455929f};
static const float lsf_rot_scale[2]     = {0.006554049f, 0.0069253775f};
static const float lsf_rot_cond_min[2]  = {-0.67291605f, -0.8248211f};
static const float lsf_rot_cond_scale[2]= {0.0052386564f, 0.0064186584f};

static const float lsf_st2_qlvls_min   = -0.45f;
static const float lsf_st2_qlvls_scale = 0.0034478905f;
static const float lsf_qstep_cond_mult = 0.9f;
static const float smpl_pi_f32         = 3.1415927410125f;

/* ── lsfSeed: parsed seed data ─────────────────────────────────────────────── */
typedef struct {
    uint8_t  rot8[2][LSF_CENTROIDS][LSF_ORDER][LSF_ORDER];
    uint8_t  rot_cond8[2][2][LSF_ORDER][LSF_ORDER];
    uint8_t *st2_qlvls8;  int st2_qlvls8_len;
    uint8_t *st2_dcmfs;   int st2_dcmfs_len;
    int8_t   min_qi[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    int8_t   max_qi[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    uint16_t cb16[2][LSF_CENTROIDS][LSF_ORDER];
    uint16_t cinv16[2][LSF_CINV_LEN];
    uint16_t cmf[2][LSF_NUM_CONFIG];
    uint16_t cmf_cond[2][LSF_NUM_CONFIG + 1];
    uint16_t lsf_sel[3][3];
    uint16_t lsf_extra[3];
    float    mean[2][LSF_ORDER];
    float    min_dist[2][LSF_NUM_CONFIG];
    float    reg_cond[2];
    float    qstep[2][2];
} lsf_seed_t;

/* ── Protobuf field helper ─────────────────────────────────────────────────── */
static const proto_field_t *find_pf(const proto_field_t *fields, int nf, int num) {
    for (int i = 0; i < nf; i++)
        if (fields[i].field == num) return &fields[i];
    return NULL;
}

/* ── loadLsfSeed ────────────────────────────────────────────────────────────── */
static void load_lsf_seed(lsf_seed_t *s) {
    memset(s, 0, sizeof(*s));

    uint8_t raw[262144];
    int raw_len = inflate_zlib(lsf_seed_data, lsf_seed_data_len, raw, sizeof(raw));
    if (raw_len < 0) abort();

    proto_field_t fields[32];
    int nf = parse_proto(raw, raw_len, fields, 32);

    /* Field 1: rot_8 [2][16][16][16] u8 (flat row-major) */
    const proto_field_t *f1 = find_pf(fields, nf, 1);
    if (f1) {
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int c = 0; c < LSF_CENTROIDS; c++)
                for (int i = 0; i < LSF_ORDER; i++)
                    for (int j = 0; j < LSF_ORDER; j++)
                        s->rot8[v][c][i][j] = f1->bytes[p++];
    }

    /* Field 2: rot_cond_8 [2][2][16][16] u8 */
    const proto_field_t *f2 = find_pf(fields, nf, 2);
    if (f2) {
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int lr = 0; lr < 2; lr++)
                for (int i = 0; i < LSF_ORDER; i++)
                    for (int j = 0; j < LSF_ORDER; j++)
                        s->rot_cond8[v][lr][i][j] = f2->bytes[p++];
    }

    /* Field 3: st2_qlvls8 �?copy to heap, ...)) */
    const proto_field_t *f3 = find_pf(fields, nf, 3);
    if (f3) {
        s->st2_qlvls8 = (uint8_t *)malloc(f3->len);
        memcpy(s->st2_qlvls8, f3->bytes, f3->len);
        s->st2_qlvls8_len = f3->len;
    }

    /* Field 4: st2_dcmfs �?copy to heap */
    const proto_field_t *f4 = find_pf(fields, nf, 4);
    if (f4) {
        s->st2_dcmfs = (uint8_t *)malloc(f4->len);
        memcpy(s->st2_dcmfs, f4->bytes, f4->len);
        s->st2_dcmfs_len = f4->len;
    }

    /* Fields 5,6: min_qi / max_qi [2][2][17][16] i8 */
    for (int idx = 0; idx < 2; idx++) {
        const proto_field_t *f = find_pf(fields, nf, 5 + idx);
        if (!f) continue;
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int lr = 0; lr < 2; lr++)
                for (int c = 0; c < LSF_NUM_CONFIG; c++)
                    for (int i = 0; i < LSF_ORDER; i++) {
                        int8_t q = (int8_t)f->bytes[p++];
                        if (idx == 0) s->min_qi[v][lr][c][i] = q;
                        else          s->max_qi[v][lr][c][i] = q;
                    }
    }

    /* Field 7: cb_16 [2][16][16] (u32 �?u16) */
    const proto_field_t *f7 = find_pf(fields, nf, 7);
    if (f7) {
        uint32_t cb[2 * LSF_CENTROIDS * LSF_ORDER];
        int n = decode_varints_u32(f7->bytes, f7->len, cb, 2 * LSF_CENTROIDS * LSF_ORDER);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int c = 0; c < LSF_CENTROIDS; c++)
                for (int i = 0; i < LSF_ORDER; i++)
                    s->cb16[v][c][i] = (uint16_t)cb[p++];
    }

    /* Field 8: cinv_16 [2][136] */
    const proto_field_t *f8 = find_pf(fields, nf, 8);
    if (f8) {
        uint32_t cinv[2 * LSF_CINV_LEN];
        decode_varints_u32(f8->bytes, f8->len, cinv, 2 * LSF_CINV_LEN);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < LSF_CINV_LEN; i++)
                s->cinv16[v][i] = (uint16_t)cinv[p++];
    }

    /* Field 9: cmf [2][17] */
    const proto_field_t *f9 = find_pf(fields, nf, 9);
    if (f9) {
        uint32_t cmf[2 * LSF_NUM_CONFIG];
        decode_varints_u32(f9->bytes, f9->len, cmf, 2 * LSF_NUM_CONFIG);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < LSF_NUM_CONFIG; i++)
                s->cmf[v][i] = (uint16_t)cmf[p++];
    }

    /* Field 10: cmf_cond [2][18] */
    const proto_field_t *f10 = find_pf(fields, nf, 10);
    if (f10) {
        uint32_t cmfc[2 * (LSF_NUM_CONFIG + 1)];
        decode_varints_u32(f10->bytes, f10->len, cmfc, 2 * (LSF_NUM_CONFIG + 1));
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < LSF_NUM_CONFIG + 1; i++)
                s->cmf_cond[v][i] = (uint16_t)cmfc[p++];
    }

    /* Field 11: lsf_sel [3][3] */
    const proto_field_t *f11 = find_pf(fields, nf, 11);
    if (f11) {
        uint32_t sel[9];
        decode_varints_u32(f11->bytes, f11->len, sel, 9);
        int p = 0;
        for (int a = 0; a < 3; a++)
            for (int b = 0; b < 3; b++)
                s->lsf_sel[a][b] = (uint16_t)sel[p++];
    }

    /* Field 12: lsf_extra [3] */
    const proto_field_t *f12 = find_pf(fields, nf, 12);
    if (f12) {
        uint32_t ex[3];
        decode_varints_u32(f12->bytes, f12->len, ex, 3);
        for (int i = 0; i < 3; i++) s->lsf_extra[i] = (uint16_t)ex[i];
    }

    /* Field 13: mean [2][16] (floats) */
    const proto_field_t *f13 = find_pf(fields, nf, 13);
    if (f13) {
        float mean[2 * LSF_ORDER];
        decode_floats(f13->bytes, f13->len, mean, 2 * LSF_ORDER);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < LSF_ORDER; i++)
                s->mean[v][i] = mean[p++];
    }

    /* Field 14: min_dist [2][17] (floats) */
    const proto_field_t *f14 = find_pf(fields, nf, 14);
    if (f14) {
        float md[2 * LSF_NUM_CONFIG];
        decode_floats(f14->bytes, f14->len, md, 2 * LSF_NUM_CONFIG);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < LSF_NUM_CONFIG; i++)
                s->min_dist[v][i] = md[p++];
    }

    /* Field 15: reg_cond [2] (floats) */
    const proto_field_t *f15 = find_pf(fields, nf, 15);
    if (f15) {
        float rc[2];
        decode_floats(f15->bytes, f15->len, rc, 2);
        s->reg_cond[0] = rc[0]; s->reg_cond[1] = rc[1];
    }

    /* Field 16: qstep [2][2] (floats) */
    const proto_field_t *f16 = find_pf(fields, nf, 16);
    if (f16) {
        float qs[4];
        decode_floats(f16->bytes, f16->len, qs, 4);
        int p = 0;
        for (int v = 0; v < 2; v++)
            for (int i = 0; i < 2; i++)
                s->qstep[v][i] = qs[p++];
    }
}

/* ── Float expansion primitives ────────────────────────────────────────────── */

/* lsfMatMultTransp16: transposed 16x16 matrix-vector multiply.
 * y[i] = sum_j C[j][i] * x[j] (accumulate seeded at j=0, then += for j>0).
 * IMPORTANT: round the product before accumulating (defeat FMA fusion). */
static void lsf_mat_mult_transp16(const float c[LSF_ORDER][LSF_ORDER],
                                   const float x[LSF_ORDER],
                                   float y[LSF_ORDER]) {
    float x0 = x[0];
    for (int i = 0; i < LSF_ORDER; i++) {
        y[i] = c[0][i] * x0;
    }
    for (int j = 1; j < LSF_ORDER; j++) {
        float xj = x[j];
        for (int i = 0; i < LSF_ORDER; i++) {
            float prod = c[j][i] * xj;  /* separate rounding */
            y[i] += prod;
        }
    }
}

/* lsfSeedLaroia: Laroia inverse-gap LSF weights, gap floored at 1e-3. */
static void lsf_seed_laroia(const float lsf[LSF_ORDER], float w[LSF_ORDER]) {
    const float minDist = 1e-3f;
    float inv[LSF_ORDER + 1];
    inv[0] = 1.0f / mlow_maxf32(lsf[0], minDist);
    for (int i = 1; i < LSF_ORDER; i++) {
        inv[i] = 1.0f / mlow_maxf32(lsf[i] - lsf[i - 1], minDist);
    }
    inv[LSF_ORDER] = 1.0f / mlow_maxf32(smpl_pi_f32 - lsf[LSF_ORDER - 1], minDist);
    for (int i = 0; i < LSF_ORDER; i++) {
        w[i] = inv[i] + inv[i + 1];
    }
}

/* lsfRotApplyWght: apply Laroia weights to the rotation.
 * lsfw = sqrt(laroia(lsf)), we[i][j] = rot[i][j]/lsfw[j], wie[j][i] = rot[i][j]*lsfw[j]. */
static void lsf_rot_apply_wght(const float rot[LSF_ORDER][LSF_ORDER],
                                const float lsf[LSF_ORDER],
                                float we[LSF_ORDER][LSF_ORDER],
                                float wie[LSF_ORDER][LSF_ORDER]) {
    float lsfw[LSF_ORDER];
    lsf_seed_laroia(lsf, lsfw);
    for (int i = 0; i < LSF_ORDER; i++) {
        lsfw[i] = mlow_sqrtf32(lsfw[i]);
    }
    float lsfw_inv[LSF_ORDER];
    for (int i = 0; i < LSF_ORDER; i++) {
        lsfw_inv[i] = 1.0f / lsfw[i];
    }
    for (int i = 0; i < LSF_ORDER; i++) {
        for (int j = 0; j < LSF_ORDER; j++) {
            we[i][j] = rot[i][j] * lsfw_inv[j];
            wie[j][i] = rot[i][j] * lsfw[j];
        }
    }
}

/* lsfCmfToBits: per-symbol bit cost. */
static void lsf_cmf_to_bits(const uint16_t *cmf, int n, float *bits) {
    float den = (float)cmf[n - 1];
    for (int i = 0; i < n - 1; i++) {
        float num = (float)((int32_t)cmf[i + 1] - (int32_t)cmf[i]);
        bits[i] = -mlow_log2f32(num / den);
    }
}

/* lsfUnpack8: out[i][j] = min + packed[i][j]*scale, scalar.
 * IMPORTANT: round packed*scale before adding min (defeat FMA fusion). */
static void lsf_unpack8(const uint8_t packed[LSF_ORDER][LSF_ORDER],
                         float scale, float min,
                         float out[LSF_ORDER][LSF_ORDER]) {
    for (int i = 0; i < LSF_ORDER; i++) {
        for (int j = 0; j < LSF_ORDER; j++) {
            float prod = (float)((float)packed[i][j] * scale);
            out[i][j] = min + prod;
        }
    }
}

/* ── Build LSF tables from seed ────────────────────────────────────────────── */
void lsf_tables_build(void) {
    lsf_seed_t s;
    load_lsf_seed(&s);

    /* Allocate pools for ragged stage-2 arrays */
    g_lsf_cb.qlvls_pool = (float *)malloc(LSF_ST2_LEN * sizeof(float));
    g_lsf_cb.numbits_pool = (float *)malloc(LSF_ST2_LEN * sizeof(float));

    /* ── Stage 1 + synth centroids/matrices ─────────────────────────────────── */
    for (int voiced = 0; voiced < 2; voiced++) {
        /* cInv (symmetric lower-triangular fill) */
        float c_inv[LSF_ORDER][LSF_ORDER];
        int p = 0;
        for (int i = 0; i < LSF_ORDER; i++) {
            for (int j = 0; j <= i; j++) {
                float prod = lsf_cinv_scale[voiced] * (float)s.cinv16[voiced][p];
                float v = lsf_cinv_min[voiced] + prod;
                c_inv[i][j] = v;
                c_inv[j][i] = v;
                p++;
            }
        }
        memcpy(g_lsf_cb.st1[voiced].cinv, c_inv, sizeof(c_inv));

        float cbhalf[LSF_CENTROIDS][LSF_ORDER];
        float cb_cinv[LSF_CENTROIDS][LSF_ORDER];
        float we[LSF_CENTROIDS][LSF_ORDER][LSF_ORDER];
        float wie[LSF_CENTROIDS][LSF_ORDER][LSF_ORDER];

        for (int c = 0; c < LSF_CENTROIDS; c++) {
            float lsf_cb[LSF_ORDER];
            for (int i = 0; i < LSF_ORDER; i++) {
                float prod = (float)((float)s.cb16[voiced][c][i] * lsf_cb_scale[voiced]);
                lsf_cb[i] = lsf_cb_min[voiced] + prod + s.mean[voiced][i];
                cbhalf[c][i] = lsf_cb[i] * 0.5f;
            }
            lsf_mat_mult_transp16(c_inv, lsf_cb, cb_cinv[c]);

            float rot[LSF_ORDER][LSF_ORDER];
            lsf_unpack8(s.rot8[voiced][c], lsf_rot_scale[voiced], lsf_rot_min[voiced], rot);
            lsf_rot_apply_wght(rot, lsf_cb, we[c], wie[c]);
        }

        memcpy(g_lsf_cb.st1[voiced].cbhalf, cbhalf, sizeof(cbhalf));
        memcpy(g_lsf_cb.st1[voiced].cb_cinv, cb_cinv, sizeof(cb_cinv));
        memcpy(g_lsf_cb.st1[voiced].we, we, sizeof(we));
        memcpy(g_lsf_cb.st1[voiced].wie, wie, sizeof(wie));

        /* Rotcond[lowRate] = unpack8(rot_cond_8[lowRate]) */
        float rotcond[2][LSF_ORDER][LSF_ORDER];
        for (int lr = 0; lr < 2; lr++) {
            lsf_unpack8(s.rot_cond8[voiced][lr], lsf_rot_cond_scale[voiced], lsf_rot_cond_min[voiced], rotcond[lr]);
        }
        memcpy(g_lsf_cb.st1[voiced].rotcond, rotcond, sizeof(rotcond));

        /* Bits / BitsCond */
        lsf_cmf_to_bits(s.cmf[voiced], LSF_NUM_CONFIG, g_lsf_cb.st1[voiced].bits);
        lsf_cmf_to_bits(s.cmf_cond[voiced], LSF_NUM_CONFIG + 1, g_lsf_cb.st1[voiced].bits_cond);

        /* Synth centroids/matrices: grid g<16 == cbhalf[g]/we[g] */
        for (int g = 0; g < LSF_CENTROIDS; g++) {
            for (int i = 0; i < LSF_ORDER; i++) {
                g_smpl_synth.centroids[voiced][g][i] = cbhalf[g][i];
            }
            memcpy(g_smpl_synth.matrices[voiced][g], we[g], sizeof(we[g]));
        }

        /* Grid16Matrices[voiced][lr] = rotcond[lr] flattened */
        for (int lr = 0; lr < 2; lr++) {
            int idx = 0;
            for (int i = 0; i < LSF_ORDER; i++) {
                for (int j = 0; j < LSF_ORDER; j++) {
                    g_smpl_synth.grid16_matrices[voiced][lr][idx++] = rotcond[lr][i][j];
                }
            }
        }

        /* Grid16W[voiced] = mean[1-voiced] (the 1-v swap) */
        for (int i = 0; i < LSF_ORDER; i++) {
            g_smpl_synth.grid16_w[voiced][i] = s.mean[1 - voiced][i];
        }
        g_smpl_synth.grid16_alpha[voiced] = s.reg_cond[voiced];

        /* MinSpacing[voiced] = min_dist[1-voiced] (the index swap) */
        for (int i = 0; i < LSF_NUM_CONFIG; i++) {
            g_smpl_synth.min_spacing[voiced][i] = s.min_dist[1 - voiced][i];
        }
    }

    /* ── Stage 2: flat QlvlsTable / cmfTable / numBitsTable walks ────────────── */
    int q_ptr = 0, q8_ptr = 0, dcmf_ptr = 0;
    for (int voiced = 0; voiced < 2; voiced++) {
        for (int lr = 0; lr < 2; lr++) {
            for (int c = 0; c < LSF_NUM_CONFIG; c++) {
                float qstep = s.qstep[voiced][lr];
                if (c == LSF_CENTROIDS) {
                    qstep *= lsf_qstep_cond_mult;
                }
                for (int i = 0; i < LSF_ORDER; i++) {
                    int32_t minQi = (int32_t)s.min_qi[voiced][lr][c][i];
                    int32_t maxQi = (int32_t)s.max_qi[voiced][lr][c][i];
                    int numQlvls = (int)(maxQi - minQi + 1);

                    g_lsf_cb.st2[voiced][lr][c].num_qlvls[i] = (int32_t)numQlvls;
                    g_lsf_cb.st2[voiced][lr][c].qlvls[i] = &g_lsf_cb.qlvls_pool[q_ptr];
                    g_smpl_synth.valtables[voiced][lr][c][i] = &g_lsf_cb.qlvls_pool[q_ptr];
                    g_smpl_synth.valtables_len[voiced][lr][c][i] = numQlvls;

                    for (int lvl = 0; lvl < numQlvls; lvl++) {
                        float q8 = (float)s.st2_qlvls8[q8_ptr];
                        float prod = lsf_st2_qlvls_scale * q8;
                        g_lsf_cb.qlvls_pool[q_ptr] = (lsf_st2_qlvls_min + prod +
                            (float)lvl + (float)minQi) * qstep;
                        q_ptr++;
                        q8_ptr++;
                    }

                    /* DCMF �?CMF �?bits */
                    int dcmf_len = numQlvls;
                    uint16_t *cmf = (uint16_t *)malloc((dcmf_len + 1) * sizeof(uint16_t));
                    lsf_dcmf_to_cmf(s.st2_dcmfs + dcmf_ptr, dcmf_len, cmf);
                    dcmf_ptr += dcmf_len;

                    float *nb = (float *)malloc(dcmf_len * sizeof(float));
                    lsf_cmf_to_bits(cmf, dcmf_len + 1, nb);
                    g_lsf_cb.st2[voiced][lr][c].num_bits[i] = nb;

                    /* Store CDF pointer for SmplTables.lsf_stage2 */
                    g_smpl_tables.lsf_stage2_ptr[voiced][lr][c][i] = cmf;
                    g_smpl_tables.lsf_stage2_len[voiced][lr][c][i] = dcmf_len + 1;
                }
            }
        }
    }

    /* Verify pointer counts */
    if (q_ptr != LSF_ST2_LEN || q8_ptr != LSF_ST2_LEN || dcmf_ptr != LSF_ST2_LEN) {
        abort(); /* corrupt seed */
    }

    /* ── Assemble LsfCb remaining fields ───────────────────────────────────── */
    for (int v = 0; v < 2; v++) {
        for (int lr = 0; lr < 2; lr++) {
            g_lsf_cb.qstep[v][lr] = s.qstep[v][lr];
        }
        for (int c = 0; c < LSF_NUM_CONFIG; c++) {
            for (int i = 0; i < LSF_ORDER; i++) {
                g_lsf_cb.min_qi[v][0][c][i] = (int32_t)s.min_qi[v][0][c][i];
                g_lsf_cb.max_qi[v][0][c][i] = (int32_t)s.max_qi[v][0][c][i];
                g_lsf_cb.min_qi[v][1][c][i] = (int32_t)s.min_qi[v][1][c][i];
                g_lsf_cb.max_qi[v][1][c][i] = (int32_t)s.max_qi[v][1][c][i];
            }
        }
        for (int i = 0; i < LSF_ORDER; i++) {
            g_lsf_cb.mean_v[i] = s.mean[1][i];
            g_lsf_cb.mean_uv[i] = s.mean[0][i];
        }
        for (int i = 0; i < LSF_NUM_CONFIG; i++) {
            g_lsf_cb.min_dist_v[i] = s.min_dist[1][i];
            g_lsf_cb.min_dist_uv[i] = s.min_dist[0][i];
        }
        g_lsf_cb.reg_cond[v] = s.reg_cond[v];
    }

    /* ── Assemble SmplTables ───────────────────────────────────────────────── */
    for (int a = 0; a < 3; a++)
        for (int b = 0; b < 3; b++)
            g_smpl_tables.lsf_sel[a][b] = s.lsf_sel[a][b];

    /* match1 = CMF_cond_v, match1_alt = CMF_cond_uv */
    for (int i = 0; i < LSF_NUM_CONFIG + 1; i++) {
        g_smpl_tables.match1[i] = s.cmf_cond[1][i];
        g_smpl_tables.match1_alt[i] = s.cmf_cond[0][i];
    }
    /* match0 = CMF_uv, match0_alt = CMF_v */
    for (int i = 0; i < LSF_NUM_CONFIG; i++) {
        g_smpl_tables.match0[i] = s.cmf[0][i];
        g_smpl_tables.match0_alt[i] = s.cmf[1][i];
    }
    for (int i = 0; i < 3; i++) {
        g_smpl_tables.lsf_extra[i] = s.lsf_extra[i];
    }
}