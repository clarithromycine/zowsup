/*
 * pitch_seed.c — Pitch lag/contour table expansion from seed.
 *
 * All integer — bit-exact with the reference.
 */

#include "pitch_seed.h"
#include "../seed.h"
#include "../range_coder.h"
#include <stdlib.h>
#include <string.h>

/* ── Embedded seed data ─────────────────────────────────────────────────────── */

/* We embed the seed binary directly.  On platforms without embed support we
 * would load from file, but C11 has no standard embed mechanism.  Instead we
 * use a generated .h with the byte array.  For now we generate it at build time. */
#include "pitch_seed_data.h"

/* ── Global singleton ──────────────────────────────────────────────────────── */
pitch_tables_t g_pitch_tables;

/* Helper: find a proto field by number. */
static const proto_field_t *find_pf(const proto_field_t *fields, int nf, int num) {
    for (int i = 0; i < nf; i++)
        if (fields[i].field == num) return &fields[i];
    return NULL;
}

/* ── pitchSeed: parsed protobuf fields ──────────────────────────────────────── */
typedef struct {
    const uint8_t *blocksegsBitstream;
    int blocksegsBitstreamLen;
    const uint8_t *blocksegs2idx;
    int blocksegs2idxLen;
    const uint8_t *blocksegsIx;
    int blocksegsIxLen;
    const uint8_t *firstblockRange;
    int firstblockRangeLen;
    const uint8_t *blocksegIdxDcmf;
    int blocksegIdxDcmfLen;
    const uint8_t *deltaLagDcmfs;
    int deltaLagDcmfsLen;
    const uint8_t *blockTransitionDcmf;
    int blockTransitionDcmfLen;
} pitch_seed_t;

static void load_pitch_seed(pitch_seed_t *s) {
    /* Decompress */
    uint8_t raw[65536];
    int raw_len = inflate_zlib(pitch_seed_data, pitch_seed_data_len, raw, sizeof(raw));
    if (raw_len < 0) {
        /* fatal */
        abort();
    }

    /* Parse protobuf */
    proto_field_t fields[32];
    int nf = parse_proto(raw, raw_len, fields, 32);

    /* Helper to find a field by number */
    const proto_field_t *f;

    /* Helper: copy field bytes to heap */
    #define HEAP_COPY(dst, dstLen, fld) do { \
        if (fld) { \
            (dst) = (uint8_t *)malloc((fld)->len); \
            memcpy((dst), (fld)->bytes, (fld)->len); \
            (dstLen) = (fld)->len; \
        } else { (dst) = NULL; (dstLen) = 0; } \
    } while(0)

    f = find_pf(fields, nf, 1);  HEAP_COPY(s->blocksegsBitstream, s->blocksegsBitstreamLen, f);
    f = find_pf(fields, nf, 2);  HEAP_COPY(s->blocksegs2idx, s->blocksegs2idxLen, f);
    f = find_pf(fields, nf, 3);  HEAP_COPY(s->blocksegsIx, s->blocksegsIxLen, f);
    f = find_pf(fields, nf, 4);  HEAP_COPY(s->firstblockRange, s->firstblockRangeLen, f);
    f = find_pf(fields, nf, 5);  HEAP_COPY(s->blocksegIdxDcmf, s->blocksegIdxDcmfLen, f);
    f = find_pf(fields, nf, 6);  HEAP_COPY(s->deltaLagDcmfs, s->deltaLagDcmfsLen, f);
    f = find_pf(fields, nf, 7);  HEAP_COPY(s->blockTransitionDcmf, s->blockTransitionDcmfLen, f);

    #undef HEAP_COPY
}

/* ── ecDecodeUniform: decode a uniform symbol in [0, n) ────────────────────── */
static uint32_t ec_decode_uniform(RangeDecoder *dec, uint32_t n) {
    uint32_t v = range_dec_decode(dec, n);
    range_dec_update(dec, v, v + 1, n);
    return v;
}

/* ── decodeBlockseg ────────────────────────────────────────────────────────── */
static void decode_blockseg(RangeDecoder *dec, pitch_block_seg_t *bs) {
    int length = (int)ec_decode_uniform(dec, 6) + 1;
    bs->nblocks = length;
    for (int j = 0; j < length; j++) {
        bs->blocks[j] = (int)ec_decode_uniform(dec, 9);
        bs->seglens[j] = (int)ec_decode_uniform(dec, 4) + 1;
    }
}

/* ── genBlocktracks ────────────────────────────────────────────────────────── */
static void gen_blocktracks(const pitch_block_seg_t *blocksegs,
                            const int blocksegs_ix[][2],
                            pitch_block_track_t *out) {
    for (int trackIdx = 0; trackIdx < PITCH_NUM_BLOCKTRACKS; trackIdx++) {
        const pitch_block_seg_t *seg = &blocksegs[blocksegs_ix[trackIdx][0]];
        int track[NUM_SUBFRAMES];
        int segIdx = 0;
        float meanblock = 0.0f, trackdeltas = 0.0f;
        for (int b = 0; b < seg->nblocks; b++) {
            for (int k = 0; k < seg->seglens[b]; k++) {
                if (segIdx < NUM_SUBFRAMES) track[segIdx] = seg->blocks[b];
                segIdx++;
            }
            meanblock += (float)(seg->blocks[b] * seg->seglens[b]);
            if (b != 0) {
                int d = seg->blocks[b - 1] - seg->blocks[b];
                if (d < 0) d = -d;
                trackdeltas += (float)d;
            }
        }
        meanblock /= (float)NUM_SUBFRAMES;
        for (int i = 0; i < NUM_SUBFRAMES; i++) {
            out[trackIdx].track[i] = (segIdx > i) ? track[i] : 0;
        }
        out[trackIdx].meanblock = meanblock;
        out[trackIdx].trackdeltas = trackdeltas;
    }
}

/* ── chunkPairs ────────────────────────────────────────────────────────────── */
static int chunk_pairs(const uint8_t *b, int blen, int out[][2], int max_out) {
    int count = 0;
    for (int i = 0; i + 1 < blen && count < max_out; i += 2) {
        out[count][0] = (int)b[i];
        out[count][1] = (int)b[i + 1];
        count++;
    }
    return count;
}

/* ── Build pitch tables from seed ──────────────────────────────────────────── */
void pitch_tables_build(void) {
    pitch_seed_t s;
    memset(&s, 0, sizeof(s));
    load_pitch_seed(&s);

    /* Decode blocksegs bitstream */
    RangeDecoder dec;
    range_dec_init(&dec, s.blocksegsBitstream, s.blocksegsBitstreamLen);

    pitch_block_seg_t blocksegs[PITCH_NUM_BLOCKSEGS];
    for (int i = 0; i < PITCH_NUM_BLOCKSEGS; i++) {
        decode_blockseg(&dec, &blocksegs[i]);
    }

    /* BlocksegsIx */
    int blocksegs_ix[PITCH_NUM_BLOCKTRACKS][2];
    chunk_pairs(s.blocksegsIx, s.blocksegsIxLen, blocksegs_ix, PITCH_NUM_BLOCKTRACKS);
    memcpy(g_pitch_tables.blocksegs_ix, blocksegs_ix, sizeof(blocksegs_ix));

    /* FirstblockRange */
    int firstblock_range[PITCH_NUM_BLOCKS][2];
    int nfb = chunk_pairs(s.firstblockRange, s.firstblockRangeLen, firstblock_range, PITCH_NUM_BLOCKS);
    memcpy(g_pitch_tables.firstblock_range, firstblock_range, sizeof(firstblock_range));
    g_pitch_tables.num_firstblock_range = nfb;

    /* Blocktracks */
    gen_blocktracks(blocksegs, (const int (*)[2])blocksegs_ix, g_pitch_tables.blocktracks);
    g_pitch_tables.num_blocktracks = PITCH_NUM_BLOCKTRACKS;

    /* Copy blocksegs */
    memcpy(g_pitch_tables.blocksegs, blocksegs, sizeof(blocksegs));
    g_pitch_tables.num_blocksegs = PITCH_NUM_BLOCKSEGS;

    /* Blocksegs2idx */
    for (int i = 0; i < s.blocksegs2idxLen && i < PITCH_NUM_BLOCKSEGS; i++) {
        g_pitch_tables.blocksegs2idx[i] = (int)s.blocksegs2idx[i];
    }

    /* BlocksegIdxCmf */
    pitch_dcmf_to_cmf(s.blocksegIdxDcmf, s.blocksegIdxDcmfLen, g_pitch_tables.blockseg_idx_cmf);
    g_pitch_tables.blockseg_idx_cmf_len = s.blocksegIdxDcmfLen + 1;

    /* DeltaLagCmfs: 3 chunks of 319 */
    for (int i = 0; i + 319 <= s.deltaLagDcmfsLen; i += 319) {
        int idx = i / 319;
        if (idx >= 3) break;
        pitch_dcmf_to_cmf(s.deltaLagDcmfs + i, 319, g_pitch_tables.delta_lag_cmfs[idx]);
    }

    /* BlockTransitionCmf: 9 chunks of 9 */
    for (int i = 0; i + PITCH_NUM_BLOCKS <= s.blockTransitionDcmfLen; i += PITCH_NUM_BLOCKS) {
        int idx = i / PITCH_NUM_BLOCKS;
        if (idx >= PITCH_NUM_BLOCKS) break;
        pitch_dcmf_to_cmf(s.blockTransitionDcmf + i, PITCH_NUM_BLOCKS, g_pitch_tables.block_transition_cmf[idx]);
    }
}