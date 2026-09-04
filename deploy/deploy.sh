#!/bin/bash
# Развёртывание iOS-инстанса ProShot на VPS. Запускать на сервере от root.
#
# Ничего из существующего не трогает: своя папка, свой порт, своя база,
# свой systemd-юнит, свой файл в conf.d. Android-инстанс на 8010 не задевается.
set -e

APP_DIR=/root/backend-ios
PORT=8011
UNIT=proshot-ios
SRC="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 1. Порт $PORT свободен? ==="
if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "ПОРТ $PORT ЗАНЯТ. Что на нём:"
    ss -tlnp | grep ":$PORT "
    echo "Выбери другой порт и поменяй его в трёх местах: здесь, в proshot-ios.service и в proshot-ios.caddy."
    exit 1
fi
echo "свободен"

echo "=== 2. Код в $APP_DIR ==="
mkdir -p "$APP_DIR"
cp -r "$SRC/server/app" "$APP_DIR/"
cp "$SRC/server/requirements.txt" "$APP_DIR/"

echo "=== 3. Виртуальное окружение ==="
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "=== 4. .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$SRC/server/.env.example" "$APP_DIR/.env"
    echo "СОЗДАН $APP_DIR/.env из примера — впиши ключи ДО первого запуска:"
    echo "  DASHSCOPE_API_KEY, PUBLIC_BASE_URL"
    echo "База по умолчанию своя: sqlite:///./proshot_ios.db — с Android-инстансом не пересекается."
else
    echo "уже есть, не трогаю"
fi

echo "=== 5. systemd ==="
cp "$SRC/deploy/$UNIT.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$UNIT" >/dev/null 2>&1 || true
systemctl restart "$UNIT"
sleep 2
systemctl status "$UNIT" --no-pager | head -5

echo "=== 6. Caddy ==="
mkdir -p /etc/caddy/conf.d
if ! grep -q "conf.d" /etc/caddy/Caddyfile 2>/dev/null; then
    echo "ВНИМАНИЕ: в /etc/caddy/Caddyfile нет строки импорта conf.d."
    echo "Добавь в него:  import conf.d/*.caddy"
    echo "Файл сайта скопирован, но без импорта он не подхватится."
fi
cp "$SRC/deploy/$UNIT.caddy" /etc/caddy/conf.d/
caddy validate --config /etc/caddy/Caddyfile >/dev/null && systemctl reload caddy
echo "caddy перезагружен"

echo "=== 7. Проверка ==="
curl -s "http://127.0.0.1:$PORT/health" || echo "health не ответил — смотри journalctl -u $UNIT -n 50"
echo
