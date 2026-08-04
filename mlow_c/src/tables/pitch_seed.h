#ifndef MLOW_PITCH_SEED_H
#define MLOW_PITCH_SEED_H

#include <stdint.h>
#include "range_coder.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PITCH_NUM_BLOCKSEGS   217
#define PITCH_NUM_BLOCKTRACKS 187
#define NUM_SUBFRAMES         8
#define PITCH_NUM_BLOCKS       9

/* ── pitchBlockSeg ─────────────────────────────────────────────────────────── */
typedef struct {
    int nblocks;
    int blocks[8];    /* max 8 blocks per segment */
    int seglens[8];
} pitch_block_seg_t;

/* ── pitchBlockTrack ────────────────────────────────────────────────────────── */
typedef struct {
    int track[NUM_SUBFRAMES];
    float meanblock;
    float trackdeltas;
} pitch_block_track_t;

/* ── PitchTables ────────────────────────────────────────────────────────────── */
typedef struct {
    /* Blocksegs: PITCH_NUM_BLOCKSEGS entries */
    pitch_block_seg_t blocksegs[PITCH_NUM_BLOCKSEGS];
    int num_blocksegs;

    /* Blocktracks: PITCH_NUM_BLOCKTRACKS entries */
    pitch_block_track_t blocktracks[PITCH_NUM_BLOCKTRACKS];
    int num_blocktracks;

    /* Blocksegs2idx: PITCH_NUM_BLOCKSEGS ints */
    int blocksegs2idx[PITCH_NUM_BLOCKSEGS];

    /* BlocksegIdxCmf: variable-length uint32 CDF, max PITCH_NUM_BLOCKSEGS+1 */
    uint32_t blockseg_idx_cmf[PITCH_NUM_BLOCKSEGS + 1];
    int blockseg_idx_cmf_len;

    /* DeltaLagCmfs: 3 arrays of 320-entry uint32 CDFs (319 dcmf → 320 cmf) */
    uint32_t delta_lag_cmfs[3][320];

    /* BlocksegsIx: PITCH_NUM_BLOCKTRACKS pairs */
    int blocksegs_ix[PITCH_NUM_BLOCKTRACKS][2];

    /* FirstblockRange: variable pairs, max PITCH_NUM_BLOCKS */
    int firstblock_range[PITCH_NUM_BLOCKS][2];
    int num_firstblock_range;

    /* BlockTransitionCmf: PITCH_NUM_BLOCKS arrays of PITCH_NUM_BLOCKS+1 uint32 */
    uint32_t block_transition_cmf[PITCH_NUM_BLOCKS][PITCH_NUM_BLOCKS + 1];
} pitch_tables_t;

/* Global singleton — initialized by mlow_tables_init(). */
extern pitch_tables_t g_pitch_tables;

/* Build pitch tables from the embedded seed. Called once. */
void pitch_tables_build(void);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_PITCH_SEED_H */