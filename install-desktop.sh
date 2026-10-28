#!/usr/bin/env bash
# Add Candle to your applications menu and associate .candle files with it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mime="${XDG_DATA_HOME:-$HOME/.local/share}/mime"
mkdir -p "$apps" "$mime/packages"

cat > "$apps/candle.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Candle
GenericName=Novel Writing
Comment=Plan and write your novel
Exec="$here/run.sh" %f
Icon=$here/candle/resources/candle.png
Terminal=false
Categories=Office;WordProcessor;
MimeType=application/x-candle;
StartupWMClass=candle
DESKTOP

cat > "$mime/packages/candle.xml" <<MIME
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-candle">
    <comment>Candle novel project</comment>
    <glob pattern="*.candle"/>
  </mime-type>
</mime-info>
MIME

update-mime-database "$mime" 2>/dev/null || true
update-desktop-database "$apps" 2>/dev/null || true
echo "Installed: Candle is now in your applications menu."
