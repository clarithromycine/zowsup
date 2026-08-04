#ifndef MLOW_MEM_H
#define MLOW_MEM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── SmplMem: embedded window of the codec's heap ──────────────────────────── */
/* Fixed WASM-build globals for the Group-D heap layout (smpl_mem.rs). */

#define MEM_GCLK           0xb9f9a8u
#define MEM_GPITCH         0xb9d378u
#define MEM_PCFG           (MEM_GCLK + 0x5704u)
#define MEM_HDR_CONTOUR_MAP 0xe7c10u
#define MEM_HDR_LAG_CDF    0xbaa7b0u
#define MEM_HDR_FRAC_BASE  0xbaa9beu
#define MEM_HDR_DELTA_CDF  0xbab13eu
#define MEM_DELTA_BOUNDS   0xe7ef0u
#define MEM_NUM_CONTOURS   217

typedef struct {
    uint32_t base;
    uint8_t *data;
    int len;
} smpl_mem_region_t;

typedef struct {
    smpl_mem_region_t regions[16];
    int num_regions;
    uint32_t GCC;
    uint32_t GNrg;
    uint32_t GPitch;
    uint32_t GClk;
} smpl_mem_t;

/* Global singleton — initialized by mlow_tables_init(). */
extern smpl_mem_t g_smpl_mem;

/* Build the pitch lag/contour (Group D) heap window from the pitch seed. */
void smpl_mem_build(void);

/* Memory accessors */
uint8_t  smpl_mem_u8(uint32_t addr);
uint16_t smpl_mem_u16(uint32_t addr);
int16_t  smpl_mem_i16(uint32_t addr);
uint32_t smpl_mem_u32(uint32_t addr);
int32_t  smpl_mem_i32(uint32_t addr);

/* CDFAt: materialize n-entry cumulative uint16 CDF at addr. */
void smpl_mem_cdf_at(uint32_t addr, int n, uint16_t *out);

#ifdef __cplusplus
}
#endif

#endif /* MLOW_MEM_H */