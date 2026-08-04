#ifndef MLOW_LSF_SEED_H
#define MLOW_LSF_SEED_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LSF_ORDER         16
#define LSF_CENTROIDS     16
#define LSF_CINV_LEN      136   /* LSF_ORDER * (LSF_ORDER + 1) / 2 */
#define LSF_ST2_LEN       9593
#define LSF_NUM_SUBFR     4
#define LSF_NUM_CONFIG    17    /* LSF_CENTROIDS + 1 */

/* ── st1Tables ────────────────────────────────────────────────────────────── */
typedef struct {
    float cbhalf[LSF_CENTROIDS][LSF_ORDER];      /* [16][16] */
    float cinv[LSF_ORDER][LSF_ORDER];            /* [16][16] */
    float bits_cond[LSF_NUM_CONFIG];             /* [17] */
    float rotcond[2][LSF_ORDER][LSF_ORDER];      /* [2][16][16] */
    float cb_cinv[LSF_CENTROIDS][LSF_ORDER];     /* [16][16] */
    float we[LSF_CENTROIDS][LSF_ORDER][LSF_ORDER]; /* [16][16][16] */
    float bits[LSF_CENTROIDS];                   /* [16] */
    float wie[LSF_CENTROIDS][LSF_ORDER][LSF_ORDER]; /* [16][16][16] */
} lsf_st1_t;

/* ── st2Tables ─────────────────────────────────────────────────────────────── */
/* Per-coefficient ragged arrays. Max numQlvls per coeff is bounded. */
#define LSF_MAX_QLVLS 128

typedef struct {
    int32_t num_qlvls[LSF_ORDER];
    float  *qlvls[LSF_ORDER];    /* each points into g_lsf.qlvls_pool */
    float  *num_bits[LSF_ORDER]; /* each points into g_lsf.numbits_pool */
} lsf_st2_t;

/* ── LsfCb ─────────────────────────────────────────────────────────────────── */
typedef struct {
    lsf_st1_t st1[2];                           /* [voiced] */
    lsf_st2_t st2[2][2][LSF_NUM_CONFIG];       /* [voiced][lowRate][config] */
    int32_t   min_qi[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    int32_t   max_qi[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    float     qstep[2][2];
    float     mean_v[LSF_ORDER];
    float     mean_uv[LSF_ORDER];
    float     reg_cond[2];
    float     min_dist_v[LSF_NUM_CONFIG];
    float     min_dist_uv[LSF_NUM_CONFIG];

    /* Pools for ragged arrays */
    float    *qlvls_pool;     /* size LSF_ST2_LEN */
    float    *numbits_pool;   /* size LSF_ST2_LEN */
} lsf_cb_t;

/* ── SmplTables ────────────────────────────────────────────────────────────── */
typedef struct {
    uint16_t lsf_sel[3][3];
    uint16_t match1[18];      /* cmfCond[1], 18 entries */
    uint16_t match1_alt[18];  /* cmfCond[0] */
    uint16_t match0[17];      /* cmf[0] */
    uint16_t match0_alt[17];  /* cmf[1] */
    uint16_t lsf_stage2_unused; /* placeholder — use lsf_stage2_ptr instead */
    uint16_t *lsf_stage2_ptr[2][2][LSF_NUM_CONFIG][LSF_ORDER]; /* [voiced][lr][config][coeff] → CDF */
    int      lsf_stage2_len[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    uint16_t lsf_extra[3];
} smpl_tables_t;

/* ── SmplSynthTables ──────────────────────────────────────────────────────── */
typedef struct {
    /* Valtables: [2][2][17][16] → pointer into qlvls_pool */
    float   *valtables[2][2][LSF_NUM_CONFIG][LSF_ORDER];
    int      valtables_len[2][2][LSF_NUM_CONFIG][LSF_ORDER];

    /* Centroids: [2][16][16] */
    float    centroids[2][LSF_CENTROIDS][LSF_ORDER];

    /* Matrices: [2][16][16][16] */
    float    matrices[2][LSF_CENTROIDS][LSF_ORDER][LSF_ORDER];

    /* MinSpacing: [2][17] */
    float    min_spacing[2][LSF_NUM_CONFIG];

    /* Grid16W: [2][16] */
    float    grid16_w[2][LSF_ORDER];

    /* Grid16Alpha: [2] */
    float    grid16_alpha[2];

    /* Grid16Matrices: [2][2][256] (flattened 16×16) */
    float    grid16_matrices[2][2][LSF_ORDER * LSF_ORDER];
} smpl_synth_tables_t;

/* ── Global singletons ─────────────────────────────────────────────────────── */
extern lsf_cb_t            g_lsf_cb;
extern smpl_tables_t       g_smpl_tables;
extern smpl_synth_tables_t g_smpl_synth;

/* Build LSF tables from the embedded seed. Called once. */
void lsf_tables_build(void);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_LSF_SEED_H */