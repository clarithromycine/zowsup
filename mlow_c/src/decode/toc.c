/*
 * toc.c — Table of contents routing.
 */

#include "decode.h"
#include <string.h>

static int standard_opus_frame_ms(uint8_t b) {
    int config = b >> 3;
    if (config < 12) {
        int tbl[] = {10, 20, 40, 60};
        return tbl[config & 3];
    } else if (config < 16) {
        int tbl[] = {10, 20};
        return tbl[(config - 12) & 1];
    } else {
        switch (config & 3) {
            case 0: return 3;
            case 1: return 5;
            case 2: return 10;
            default: return 20;
        }
    }
}

smpl_toc_t parse_smpl_toc(uint8_t b) {
    smpl_toc_t toc;
    memset(&toc, 0, sizeof(toc));

    if ((b & 0xC0) == 0xC0) {
        toc.std_opus = true;
        toc.sample_rate = 16000;
        toc.frame_ms = standard_opus_frame_ms(b);
        return toc;
    }

    bool bit1 = ((b >> 1) & 1) != 0;
    bool vad = ((b >> 6) & 1) != 0;
    int sample_rate = 16000;
    if (b & 0x20) sample_rate = 32000;

    int frame_ms_tbl[] = {10, 20, 60, 120};

    toc.sid = (b >> 7) != 0;
    toc.vad = vad;
    toc.sample_rate = sample_rate;
    toc.frame_ms = frame_ms_tbl[(b >> 3) & 3];
    toc.voiced = vad && bit1;
    toc.active = vad || bit1;
    toc.flag2 = ((b >> 2) & 1) != 0;
    toc.flag0 = (b & 1) != 0;
    return toc;
}