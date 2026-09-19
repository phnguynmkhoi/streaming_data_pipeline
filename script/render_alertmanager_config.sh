#!/bin/bash
# Renders monitoring/alertmanager/alertmanager.yml from the tracked template
# using SMTP settings in .env (PLAN.md 4.1). The rendered file is gitignored:
# it contains the SMTP app password, and this repo is public.
# Alertmanager cannot read environment variables in its own config, which is
# why this exists. .env is parsed key-by-key rather than sourced -- it holds
# entries that aren't valid shell.
set -eu
cd "$(dirname "$0")/.."

TEMPLATE="monitoring/alertmanager/alertmanager.yml.template"
OUT="monitoring/alertmanager/alertmanager.yml"

write_fallback() {
  # Alertmanager refuses to start without a config file, so write one that
  # accepts alerts and drops them rather than blocking the whole stack.
  cat > "$OUT" <<'FALLBACK'
route:
  receiver: none
receivers:
  - name: none
FALLBACK
}

if [ ! -f .env ]; then
  echo "  .env not found -- email alerts disabled (alerts will fire in Prometheus only)" >&2
  write_fallback
  exit 0
fi

# accepts KEY=value and KEY: value; strips surrounding quotes
read_env() {
  sed -nE "s/^[[:space:]]*$1[[:space:]]*[=:][[:space:]]*(.*)\$/\1/p" .env \
    | tail -1 | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"
}

missing=""
for var in ALERT_EMAIL_TO SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD; do
  eval "$var=\$(read_env $var)"
  eval "value=\${$var}"
  [ -n "$value" ] || missing="$missing $var"
done
if [ -n "$missing" ]; then
  echo "  .env is missing:$missing -- email alerts disabled (alerts will fire in Prometheus only)" >&2
  write_fallback
  exit 0
fi

sed -e "s|__SMTP_HOST__|${SMTP_HOST}|g" \
    -e "s|__SMTP_PORT__|${SMTP_PORT}|g" \
    -e "s|__SMTP_USER__|${SMTP_USER}|g" \
    -e "s|__SMTP_PASSWORD__|${SMTP_PASSWORD}|g" \
    -e "s|__ALERT_EMAIL_TO__|${ALERT_EMAIL_TO}|g" \
    "$TEMPLATE" > "$OUT"
chmod 600 "$OUT"
echo "  wrote $OUT"
