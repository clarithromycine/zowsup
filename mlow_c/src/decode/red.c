/*
 * red.c — RED (redundancy) depack/split.
 */

#include "decode.h"
#include <string.h>

int depack_split_red(const uint8_t *p, int n, mlow_frame_t *frames, int max_frames) {
    if (n == 0) return -1;  /* ErrPktSizeZero */

    int cur = 0;
    int rem = n;
    int frame_count = 0;

    /* Parse redundant blocks */
    typedef struct { uint8_t code; uint8_t size; } red_block_t;
    red_block_t red[16];
    int red_count = 0;

    for (;;) {
        if (rem == 0) return -2;  /* ErrHeaderTooShort */
        uint8_t b0 = p[cur];
        if (b0 < 0x80) {
            if (rem <= 1) return -4;  /* ErrMainTooShort */
            break;
        }
        if (rem <= 2) return -3;  /* ErrRedundantTooShort */
        uint8_t size = p[cur + 1];
        if ((int)size + 2 >= rem) return -3;  /* ErrRedundantTooShort */
        red[red_count].code = b0 & 0x7f;
        red[red_count].size = size;
        red_count++;
        cur += 2;
        rem -= (int)size + 2;
    }

    uint8_t main_code = p[cur] & 0x7f;
    cur++;

    /* Build frames: redundant blocks first, then main */
    for (int i = 0; i < red_count && frame_count < max_frames; i++) {
        frames[frame_count].data = p + cur;
        frames[frame_count].len = red[i].size;
        frames[frame_count].time_code = red[i].code;
        frames[frame_count].is_main = false;
        cur += red[i].size;
        frame_count++;
    }

    int main_size = rem - 1;
    if (frame_count < max_frames) {
        frames[frame_count].data = p + cur;
        frames[frame_count].len = main_size;
        frames[frame_count].time_code = main_code;
        frames[frame_count].is_main = true;
        frame_count++;
    }

    return frame_count;
}