/* logging.c — Logging (minimal). */
/* Phase 1 stub */
#include "mlow_internal.h"
#include <stdio.h>

/* Minimal logging — will be wired to Python-side logging if needed. */
void mlow_log_trace(const char *msg) { (void)msg; }
void mlow_log_debug(const char *msg) { (void)msg; }
void mlow_log_warn(const char *msg)  { (void)msg; }