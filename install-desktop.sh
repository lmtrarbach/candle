#!/usr/bin/env bash
# Add Candle to your applications menu and associate .candle files with it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mime="${XDG_DATA_HOME:-$HOME/.local/share}/mime"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
mkdir -p "$apps" "$mime/packages" "$icons/256x256/apps" "$icons/scalable/apps" "$icons/256x256/mimetypes"

# Register the icon by name in the icon theme, so desktops refresh it on update.
cp "$here/candle/resources/candle.png" "$icons/256x256/apps/candle.png"
cp "$here/candle/resources/candle.svg" "$icons/scalable/apps/candle.svg"
cp "$here/candle/resources/candle.png" "$icons/256x256/mimetypes/application-x-candle.png"

cat > "$apps/candle.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Candle
GenericName=Novel Writing
Comment=Plan and write your novel
Exec="$here/run.sh" %f
Icon=candle
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
    <icon name="application-x-candle"/>
  </mime-type>
</mime-info>
MIME

update-mime-database "$mime" 2>/dev/null || true
update-desktop-database "$apps" 2>/dev/null || true
touch "$icons"
gtk-update-icon-cache -f -t "$icons" 2>/dev/null || true
echo "Installed: Candle is now in your applications menu."
