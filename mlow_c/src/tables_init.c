/*
 * tables_init.c — Global table initialization.
 * Loads and expands all three seed ROMs (cc_seed.bin, lsf_seed.bin, pitch_seed.bin)
 * and builds the WASM heap window (SmplMem).
 */

#include "mlow_internal.h"
#include "tables/pitch_seed.h"
#include "tables/cc_tables.h"
#include "tables/lsf_seed.h"
#include "mem.h"

void mlow_tables_init(void) {
    pitch_tables_build();
    cc_tables_build();
    lsf_tables_build();
    smpl_mem_build();
}