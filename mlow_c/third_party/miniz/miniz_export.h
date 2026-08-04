/* miniz_export.h — stub (we don't use miniz as an installed library) */
#ifndef MINIZ_EXPORT_H
#define MINIZ_EXPORT_H

/* We compile miniz as part of our shared library, not as a standalone DLL.
 * MINIZ_EXPORT is normally set by CMake's GenerateExportHeader; we just
 * make it empty so the symbols are compiled normally. */
#define MINIZ_EXPORT

#endif