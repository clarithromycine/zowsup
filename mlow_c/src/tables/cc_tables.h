#ifndef MLOW_CC_TABLES_H
#define MLOW_CC_TABLES_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Constants ─────────────────────────────────────────────────────────────── */
#define CC_MAX_PULSES_PER_SF    40
#define CC_RUNLENGTH_STEP       8
#define CC_NUM_RUNLEN_CMFS      20
#define CC_SPLIT_NUM_TABLES     (CC_MAX_PULSES_PER_SF * 4 - 1)
#define CC_FCBG_OFFSET_STEPS    176
#define CC_FCBG_OFFSET_BUCKETS  4
#define CC_ACBG_N               16
#define CC_ACBG_ROWS            (CC_ACBG_N + 1)
#define CC_FCBG_VN              34
#define CC_FCBG_V_DELTA_N       67

/* ── CcTables ──────────────────────────────────────────────────────────────── */
typedef struct {
    /* nrgres gain/shape CDFs */
    uint16_t *nrgres_gain4;
    int nrgres_gain4_len;
    uint16_t *nrgres_shape4;
    int nrgres_shape4_len;

    /* fcbg offset: [CC_SPLIT_NUM_TABLES-ish rows] each 177-entry uint16 CDF */
    /* Stored as flat: fcbg_offset[tableIx * CC_FCBG_OFFSET_BUCKETS + bucket] */
    uint16_t fcbg_offset[CC_FCBG_OFFSET_STEPS * CC_FCBG_OFFSET_BUCKETS + CC_FCBG_OFFSET_BUCKETS][177];
    int num_fcbg_offset_rows;

    /* acbgains HR/LR: flattened (CC_ACBG_ROWS * CC_ACBG_N) uint16 each */
    uint16_t acbgains_hr[CC_ACBG_ROWS * (CC_ACBG_N + 1)];
    uint16_t acbgains_lr[CC_ACBG_ROWS * (CC_ACBG_N + 1)];

    /* acbgains codebook weights Q14 */
    int16_t acbgains_cb_hr_q14[CC_ACBG_ROWS * 2];
    int16_t acbgains_cb_lr_q14[CC_ACBG_ROWS * 2];

    /* fcbgains V / VDelta */
    uint16_t fcbgains_v[CC_FCBG_VN + 1];
    uint16_t fcbgains_v_delta[CC_FCBG_V_DELTA_N + 1];

    /* gain reconstruction */
    int16_t *gain_recon;
    int gain_recon_len;
    uint32_t gain_recon_base;

    /* nPulse CDFs: 3 arrays */
    uint16_t *n_pulse_cmfs[3];
    int n_pulse_cmfs_len[3];

    /* split CDFs: CC_SPLIT_NUM_TABLES arrays, variable length */
    /* Stored as flat array with offsets */
    uint16_t split_cmfs_data[8192];
    int split_cmfs_offsets[CC_SPLIT_NUM_TABLES + 1];
    int num_split_cmfs;

    /* runlen CDFs: 20 tables, each variable length */
    /* Stored as flat array with offsets. Total = 68000 uint16 entries. */
    uint16_t runlen_data[68000];
    int runlen_offsets[CC_NUM_RUNLEN_CMFS + 1];
    int runlen_max_samples[CC_NUM_RUNLEN_CMFS];
    int num_runlen;
} cc_tables_t;

/* Global singleton — initialized by mlow_tables_init(). */
extern cc_tables_t g_cc_tables;

/* Build cc tables from the embedded seed. Called once. */
void cc_tables_build(void);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_CC_TABLES_H */