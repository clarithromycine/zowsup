/*
 * mem.c — WASM heap layout simulation for pitch lag/contour (Group D).
 *
 * The window is built at fixed absolute addresses so the pitch lag/contour
 * pointer-chase lands unchanged.
 */

#include "mem.h"
#include "seed.h"
#include "tables/pitch_seed.h"
#include "tables/pitch_seed_data.h"
#include <stdlib.h>
#include <string.h>

/* ── Constants ──────────────────────────────────────────────────────────────── */
static const uint32_t mem_hdr_unused[3] = {0xe7d20u, 0xe7ef0u, 0xe8096u};

/* ── Global singleton ──────────────────────────────────────────────────────── */
smpl_mem_t g_smpl_mem;

/* ── silkLSFCosTabFIXQ12 (Q12 cosine table for LSF root search) ────────────── */
const int32_t silk_lsf_cos_tab_fix_q12[129] = {
    8192, 8190, 8182, 8170, 8152, 8130, 8104, 8072,
    8034, 7994, 7946, 7896, 7840, 7778, 7714, 7644,
    7568, 7490, 7406, 7318, 7226, 7128, 7026, 6922,
    6812, 6698, 6580, 6458, 6332, 6204, 6070, 5934,
    5792, 5648, 5502, 5352, 5198, 5040, 4880, 4718,
    4552, 4382, 4212, 4038, 3862, 3684, 3502, 3320,
    3136, 2948, 2760, 2570, 2378, 2186, 1990, 1794,
    1598, 1400, 1202, 1002, 802, 602, 402, 202,
    0, -202, -402, -602, -802, -1002, -1202, -1400,
    -1598, -1794, -1990, -2186, -2378, -2570, -2760, -2948,
    -3136, -3320, -3502, -3684, -3862, -4038, -4212, -4382,
    -4552, -4718, -4880, -5040, -5198, -5352, -5502, -5648,
    -5792, -5934, -6070, -6204, -6332, -6458, -6580, -6698,
    -6812, -6922, -7026, -7128, -7226, -7318, -7406, -7490,
    -7568, -7644, -7714, -7778, -7840, -7896, -7946, -7994,
    -8034, -8072, -8104, -8130, -8152, -8170, -8182, -8190,
    -8192,
};

/* ── u16Bytes: convert uint32 array to little-endian u16 bytes ──────────────── */
static void u16_bytes(const uint32_t *v, int vlen, uint8_t *out) {
    for (int i = 0; i < vlen; i++) {
        out[2 * i] = (uint8_t)(v[i] & 0xff);
        out[2 * i + 1] = (uint8_t)((v[i] >> 8) & 0xff);
    }
}

/* ── put32: append a little-endian uint32 to a byte buffer ──────────────────── */
static void put32(uint8_t **buf, int *len, int *cap, int32_t x) {
    if (*len + 4 > *cap) {
        *cap = (*cap + 4) * 2;
        *buf = (uint8_t *)realloc(*buf, *cap);
    }
    uint32_t u = (uint32_t)x;
    (*buf)[(*len)++] = (uint8_t)(u & 0xff);
    (*buf)[(*len)++] = (uint8_t)((u >> 8) & 0xff);
    (*buf)[(*len)++] = (uint8_t)((u >> 16) & 0xff);
    (*buf)[(*len)++] = (uint8_t)((u >> 24) & 0xff);
}

static void push_region(uint32_t base, const uint8_t *data, int data_len) {
    int idx = g_smpl_mem.num_regions;
    if (idx >= 16) return;
    g_smpl_mem.regions[idx].base = base;
    g_smpl_mem.regions[idx].data = (uint8_t *)malloc(data_len);
    memcpy(g_smpl_mem.regions[idx].data, data, data_len);
    g_smpl_mem.regions[idx].len = data_len;
    g_smpl_mem.num_regions++;
}

/* ── regionFor: find the region containing [addr, addr+n) ──────────────────── */
static int region_for(uint32_t addr, int n, const uint8_t **data, int *off) {
    for (int i = 0; i < g_smpl_mem.num_regions; i++) {
        smpl_mem_region_t *r = &g_smpl_mem.regions[i];
        if (addr >= r->base && (int)(addr - r->base) + n <= r->len) {
            *data = r->data;
            *off = (int)(addr - r->base);
            return 1;
        }
    }
    return 0;
}

/* ── Memory accessors ──────────────────────────────────────────────────────── */
uint8_t smpl_mem_u8(uint32_t addr) {
    const uint8_t *data; int off;
    if (region_for(addr, 1, &data, &off)) return data[off];
    return 0;
}

uint16_t smpl_mem_u16(uint32_t addr) {
    const uint8_t *data; int off;
    if (region_for(addr, 2, &data, &off)) {
        return (uint16_t)data[off] | ((uint16_t)data[off + 1] << 8);
    }
    return 0;
}

int16_t smpl_mem_i16(uint32_t addr) {
    return (int16_t)smpl_mem_u16(addr);
}

uint32_t smpl_mem_u32(uint32_t addr) {
    const uint8_t *data; int off;
    if (region_for(addr, 4, &data, &off)) {
        return (uint32_t)data[off] | ((uint32_t)data[off + 1] << 8) |
               ((uint32_t)data[off + 2] << 16) | ((uint32_t)data[off + 3] << 24);
    }
    return 0;
}

int32_t smpl_mem_i32(uint32_t addr) {
    return (int32_t)smpl_mem_u32(addr);
}

void smpl_mem_cdf_at(uint32_t addr, int n, uint16_t *out) {
    for (int i = 0; i < n; i++) {
        out[i] = smpl_mem_u16(addr + (uint32_t)i * 2);
    }
}

/* ── buildSmplMemFromSeed ──────────────────────────────────────────────────── */
void smpl_mem_build(void) {
    /* The pitch tables must already be built */
    pitch_tables_t *pt = &g_pitch_tables;

    /* Build contour window parts from the pitch seed.
     * We re-decode the blocksegs bitstream (already done in pitch_tables_build),
     * but here we need the records in a specific layout for the heap window.
     */

    /* Re-load the pitch seed to get the raw fields */
    uint8_t raw[65536];
    int raw_len = inflate_zlib(pitch_seed_data, pitch_seed_data_len, raw, sizeof(raw));
    if (raw_len < 0) abort();

    proto_field_t fields[32];
    int nf = parse_proto(raw, raw_len, fields, 32);

    /* Get fields */
    const uint8_t *blocksegs2idx = NULL; int blocksegs2idx_len = 0;
    const uint8_t *firstblockRange = NULL; int firstblockRange_len = 0;
    const uint8_t *blocksegIdxDcmf = NULL; int blocksegIdxDcmf_len = 0;
    const uint8_t *deltaLagDcmfs = NULL; int deltaLagDcmfs_len = 0;
    const uint8_t *blockTransitionDcmf = NULL; int blockTransitionDcmf_len = 0;

    for (int i = 0; i < nf; i++) {
        switch (fields[i].field) {
            case 2: blocksegs2idx = fields[i].bytes; blocksegs2idx_len = fields[i].len; break;
            case 4: firstblockRange = fields[i].bytes; firstblockRange_len = fields[i].len; break;
            case 5: blocksegIdxDcmf = fields[i].bytes; blocksegIdxDcmf_len = fields[i].len; break;
            case 6: deltaLagDcmfs = fields[i].bytes; deltaLagDcmfs_len = fields[i].len; break;
            case 7: blockTransitionDcmf = fields[i].bytes; blockTransitionDcmf_len = fields[i].len; break;
        }
    }

    /* Build r0: the contour records region (at memPcfg + 0x1d38) */
    uint8_t *r0 = NULL; int r0_len = 0, r0_cap = 0;
    for (int rec = 0; rec < PITCH_NUM_BLOCKSEGS; rec++) {
        pitch_block_seg_t *bs = &pt->blocksegs[rec];
        for (int i = 0; i < 8; i++) {
            int v = (i < bs->nblocks) ? bs->blocks[i] : 0;
            put32(&r0, &r0_len, &r0_cap, (int32_t)v);
        }
        for (int i = 0; i < 8; i++) {
            int v = (i < bs->nblocks) ? bs->seglens[i] : 0;
            put32(&r0, &r0_len, &r0_cap, (int32_t)v);
        }
        put32(&r0, &r0_len, &r0_cap, (int32_t)bs->nblocks);
    }
    /* NUM_BLOCKTRACKS gap */
    put32(&r0, &r0_len, &r0_cap, 187);

    /* Header addresses */
    uint32_t headers[] = {
        (uint32_t)MEM_NUM_CONTOURS, MEM_HDR_CONTOUR_MAP, MEM_HDR_LAG_CDF,
        MEM_HDR_FRAC_BASE, mem_hdr_unused[0], mem_hdr_unused[1], mem_hdr_unused[2],
        MEM_HDR_DELTA_CDF
    };
    for (int i = 0; i < 8; i++) {
        put32(&r0, &r0_len, &r0_cap, (int32_t)headers[i]);
    }

    push_region(MEM_PCFG + 0x1d38, r0, r0_len);

    /* lagCdf: u16 bytes of blockseg_idx_cmf */
    {
        int cmf_len = pt->blockseg_idx_cmf_len;
        uint8_t *lag_bytes = (uint8_t *)malloc(cmf_len * 2);
        u16_bytes(pt->blockseg_idx_cmf, cmf_len, lag_bytes);
        push_region(MEM_HDR_LAG_CDF, lag_bytes, cmf_len * 2);
        free(lag_bytes);
    }

    /* fracCmfs: concatenate 3 delta_lag_cmfs arrays as u16 bytes */
    {
        uint32_t frac[3 * 320];
        int idx = 0;
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 320; j++) {
                frac[idx++] = pt->delta_lag_cmfs[i][j];
            }
        }
        uint8_t *frac_bytes = (uint8_t *)malloc(idx * 2);
        u16_bytes(frac, idx, frac_bytes);
        push_region(MEM_HDR_FRAC_BASE, frac_bytes, idx * 2);
        free(frac_bytes);
    }

    /* deltaCmfs: concatenate 9 block_transition_cmf arrays as u16 bytes */
    {
        uint32_t delta[PITCH_NUM_BLOCKS * (PITCH_NUM_BLOCKS + 1)];
        int idx = 0;
        for (int i = 0; i < PITCH_NUM_BLOCKS; i++) {
            for (int j = 0; j < PITCH_NUM_BLOCKS + 1; j++) {
                delta[idx++] = pt->block_transition_cmf[i][j];
            }
        }
        uint8_t *delta_bytes = (uint8_t *)malloc(idx * 2);
        u16_bytes(delta, idx, delta_bytes);
        push_region(MEM_HDR_DELTA_CDF, delta_bytes, idx * 2);
        free(delta_bytes);
    }

    /* contourMap: copy blocksegs2idx */
    push_region(MEM_HDR_CONTOUR_MAP, blocksegs2idx, blocksegs2idx_len);

    /* deltaBounds: firstblockRange pairs + trailing 0,0 */
    {
        int nfb = firstblockRange_len / 2;
        uint8_t *bounds = (uint8_t *)malloc(nfb * 2 + 2);
        for (int i = 0; i < nfb; i++) {
            bounds[2 * i] = firstblockRange[2 * i];
            bounds[2 * i + 1] = firstblockRange[2 * i + 1];
        }
        bounds[nfb * 2] = 0;
        bounds[nfb * 2 + 1] = 0;
        push_region(MEM_DELTA_BOUNDS, bounds, nfb * 2 + 2);
        free(bounds);
    }

    g_smpl_mem.GCC = 0;
    g_smpl_mem.GNrg = 0;
    g_smpl_mem.GPitch = MEM_GPITCH;
    g_smpl_mem.GClk = MEM_GCLK;

    free(r0);
}