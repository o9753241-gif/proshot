#!/bin/bash
# Deploy of the ProShot iOS backend on 81.90.29.8. Run on the server as root:
#     bash /root/proshot-ios-src/deploy/deploy.sh
#
# Touches nothing that already exists: own folder, own port (8011), own
# database, own systemd unit, own file in /etc/caddy/conf.d.
# Android ProShot (8010, /srv/proshot) is only READ: scene thumbnails and the
# DashScope key are copied from it, the key is never printed.
# Output is in Latin on purpose: the local terminal mangles Cyrillic.
set -e

APP_DIR=/root/backend-ios
PORT=8011
UNIT=proshot-ios
DOMAIN=ios-proshot.myprojekts.online
ANDROID_ENV=/srv/proshot/.env
ANDROID_THUMBS=/srv/proshot/src/media/thumbs
APPLE_ROOTS_SRC=/opt/star-app-ios/secrets/apple_roots
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 1. port $PORT ==="
if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    if systemctl is-active --quiet "$UNIT"; then
        echo "used by $UNIT itself - ok, this is an update"
    else
        echo "PORT $PORT IS BUSY BY SOMETHING ELSE:"
        ss -tlnp | grep ":$PORT "
        exit 1
    fi
else
    echo "free"
fi

echo "=== 2. code -> $APP_DIR ==="
mkdir -p "$APP_DIR"
STAGE=$(mktemp -d)
cp -r "$SRC/server/app" "$STAGE/app"
cp "$SRC/server/requirements.txt" "$STAGE/"
find "$STAGE/app" -name "*.py" -print0 | xargs -0 python3 -m py_compile
echo "syntax ok"

echo "=== 3. venv ==="
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$STAGE/requirements.txt"

echo "=== 4. .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$SRC/server/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|^APP_SECRET=.*|APP_SECRET=$SECRET|" "$APP_DIR/.env"
    echo "created from example, APP_SECRET generated"
else
    echo "exists, keeping it"
fi
# DashScope key: copy from Android ProShot if ours is empty. Never printed.
if ! grep -qE '^DASHSCOPE_API_KEY=.+' "$APP_DIR/.env"; then
    KEYLINE=$(grep -E '^DASHSCOPE_API_KEY=.+' "$ANDROID_ENV" | tail -1)
    if [ -z "$KEYLINE" ]; then
        echo "NO DASHSCOPE_API_KEY in $ANDROID_ENV - generation will fail"
    else
        python3 - "$APP_DIR/.env" "$KEYLINE" <<'PY'
import sys
path, line = sys.argv[1], sys.argv[2]
rows = open(path, encoding="utf-8").read().splitlines()
rows = [line if r.startswith("DASHSCOPE_API_KEY=") else r for r in rows]
if not any(r.startswith("DASHSCOPE_API_KEY=") for r in rows):
    rows.append(line)
open(path, "w", encoding="utf-8").write("\n".join(rows) + "\n")
PY
        echo "DASHSCOPE_API_KEY copied from Android (value hidden)"
    fi
else
    echo "DASHSCOPE_API_KEY already set (value hidden)"
fi
grep -E '^(PUBLIC_BASE_URL|APPLE_APP_APPLE_ID|APPLE_BUNDLE_ID|DATABASE_URL)=' "$APP_DIR/.env"

echo "=== 5. Apple root certificates ==="
mkdir -p "$APP_DIR/secrets/apple_roots"
if [ -z "$(ls -A "$APP_DIR/secrets/apple_roots" 2>/dev/null)" ]; then
    cp "$APPLE_ROOTS_SRC"/*.cer "$APP_DIR/secrets/apple_roots/"
fi
ls "$APP_DIR/secrets/apple_roots"

echo "=== 6. scene thumbnails ==="
mkdir -p "$APP_DIR/media/thumbs"
cp -n "$ANDROID_THUMBS"/*.jpg "$APP_DIR/media/thumbs/" 2>/dev/null || true
echo "thumbs: $(ls "$APP_DIR/media/thumbs"/*.jpg 2>/dev/null | wc -l)"

echo "=== 7. import check, then swap code ==="
CHECK=$(mktemp -d)
cp -r "$STAGE/app" "$CHECK/app"
cp "$APP_DIR/.env" "$CHECK/.env"
if ( cd "$CHECK" && set -a && . ./.env && set +a && "$APP_DIR/.venv/bin/python" -c "import app.main" ) >"$CHECK.log" 2>&1; then
    echo "import ok"
else
    echo "IMPORT FAILED - nothing changed:"
    tail -15 "$CHECK.log"
    rm -rf "$CHECK" "$CHECK.log" "$STAGE"
    exit 1
fi
rm -rf "$CHECK" "$CHECK.log"
rm -rf "$APP_DIR/app.old"
[ -d "$APP_DIR/app" ] && mv "$APP_DIR/app" "$APP_DIR/app.old"
cp -r "$STAGE/app" "$APP_DIR/app"
cp "$STAGE/requirements.txt" "$APP_DIR/requirements.txt"
rm -rf "$STAGE"

echo "=== 8. systemd ==="
cp "$SRC/deploy/$UNIT.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$UNIT" >/dev/null 2>&1 || true
systemctl restart "$UNIT"
sleep 4
systemctl is-active "$UNIT"

echo "=== 9. Caddy ==="
cp "$SRC/deploy/$UNIT.caddy" /etc/caddy/conf.d/
caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 && systemctl reload caddy && echo "caddy reloaded" \
  || { echo "CADDY CONFIG INVALID - removing our file"; rm -f /etc/caddy/conf.d/$UNIT.caddy; }

echo "=== 10. check ==="
H=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health")
echo "local health: $H"
if [ "$H" != "200" ] && [ -d "$APP_DIR/app.old" ]; then
    echo "ROLLBACK to previous code"
    rm -rf "$APP_DIR/app" && mv "$APP_DIR/app.old" "$APP_DIR/app"
    systemctl restart "$UNIT"
    journalctl -u "$UNIT" -n 20 --no-pager
    exit 1
fi
[ "$H" != "200" ] && journalctl -u "$UNIT" -n 30 --no-pager
sleep 3
echo "public health: $(curl -s -o /dev/null -w '%{http_code}' https://$DOMAIN/health)"
echo "styles: $(curl -s https://$DOMAIN/api/v1/styles | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d), "scenes")' 2>&1 | tail -1)"
echo "Android untouched: $(systemctl is-active proshot)"
