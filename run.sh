#!/usr/bin/env bash
# Launch Candle from the source folder, creating its virtualenv on first run.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -x "$here/.venv/bin/python" ]; then
    python3 -m venv "$here/.venv"
    "$here/.venv/bin/pip" install -q -e "$here"
fi
cd "$here"

# Started from a snap app (e.g. VS Code's terminal)? The snap leaks its own
# GTK/GLib paths, which make the system GTK abort on a missing GSettings key.
if [ -n "${SNAP:-}" ]; then
    unset GTK_PATH GTK_EXE_PREFIX GTK_IM_MODULE_FILE GIO_MODULE_DIR GSETTINGS_SCHEMA_DIR \
          GDK_PIXBUF_MODULE_FILE GDK_PIXBUF_MODULEDIR LOCPATH
    for var in XDG_DATA_DIRS XDG_CONFIG_DIRS; do
        orig="${var}_VSCODE_SNAP_ORIG"
        if [ -n "${!orig:-}" ]; then
            export "$var=${!orig}"
        fi
    done
fi

exec "$here/.venv/bin/python" -m candle "$@"
