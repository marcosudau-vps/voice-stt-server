#!/usr/bin/env bash
#
# Kanonischer VPS-Release fuer VoiceSTT. Die allgemeine Buildbeschreibung steht
# in ../BUILD.md, die servergebundene Bedienung in
# VOICE_STT_SERVER_RELEASE_ANLEITUNG.md.
#
# Nutzung:
#   ./release-voice-stt.sh [--variant pro|free] [--prune] [--with-venv]
#                          [--dry-run] [--skip-build]
#
set -euo pipefail

SELFHOST_ROOT="${SELFHOST_ROOT:-/home/marco/selfhost}"
CHECKOUT="${SELFHOST_ROOT}/apps/services/voice/voice-stt-server"
BUILD_AREA_ROOT="/home/marco/selfhost_outsourced/build_area/services/voice"
BUILD_DIR="${BUILD_AREA_ROOT}/voice-stt-server"
STACK_COMPOSE="${SELFHOST_ROOT}/stacks/services/voice/docker-compose.yml"
STACK_CONFIG="${SELFHOST_ROOT}/stacks/services/voice/stt-config.yaml"
GITHUB_ENV="${SELFHOST_ROOT}/secrets/github.env"
KROKO_ENV="${SELFHOST_ROOT}/secrets/kroko.env"
KROKO_MODELS="/home/marco/selfhost_outsourced/models/stt/kroko_asr"
RUNTIME_CONFIG="${SELFHOST_ROOT}/data/services/voice/stt-voice/config/runtime.json"
BACKUP_DIR="${SELFHOST_ROOT}/backups"
RELEASE_LOG="${SELFHOST_ROOT}/apps/services/voice/VOICE_STT_SERVER_RELEASE_LOG.md"
RESULT_JSON="${SELFHOST_ROOT}/apps/services/voice/release-result.json"

IMAGE="selfhost/stt-voice:local"
PREV_IMAGE="selfhost/stt-voice:previous"
CACHE_IMAGE_FREE="selfhost/stt-voice:kroko-cache"
CACHE_IMAGE_PRO="selfhost/stt-voice:kroko-cache-pro"
KROKO_VARIANT="${KROKO_VARIANT:-pro}"
EXPECTED_KROKO_MODEL="${EXPECTED_KROKO_MODEL:-}"
CONTAINER="stt-voice"
HEALTH_LOCAL="http://127.0.0.1:2000/health"
HEALTH_PUBLIC="https://stt.voice.marcosudau.com/health"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-480}"
LOCK_FILE="/tmp/release-voice-stt.lock"
LOG_FILE="/tmp/release-voice-stt-$(date -u +%F_%H%M%S).log"
TODAY="$(date -u +%F)"

PRUNE=0
WITH_VENV=0
DRY_RUN=0
SKIP_BUILD=0

GIT_COMMIT=""
IMAGE_ID=""
PREV_IMAGE_ID=""
BACKUP_FILE=""
RUNTIME_SNAPSHOT=""
PRUNE_RESULT="nicht ausgefuehrt"
HEALTH_LOCAL_RESULT="nicht geprueft"
HEALTH_PUBLIC_RESULT="nicht geprueft"
LOG_NOTES=""

log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$LOG_FILE"; }
warn() { printf '[%s] WARNUNG: %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$LOG_FILE" >&2; }
die()  { printf '[%s] FEHLER: %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$LOG_FILE" >&2; exit 1; }

usage() {
  cat <<'EOF'
VoiceSTT auf Marcos VPS veroeffentlichen.

Nutzung:
  release-voice-stt.sh [--variant pro|free] [--prune] [--with-venv]
                       [--dry-run] [--skip-build]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      [[ $# -ge 2 ]] || die "--variant erwartet pro oder free"
      KROKO_VARIANT="$2"
      shift 2
      ;;
    --prune) PRUNE=1; shift ;;
    --with-venv) WITH_VENV=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unbekanntes Argument: $1" ;;
  esac
done

case "$KROKO_VARIANT" in
  pro)
    EXPECTED_KROKO_MODEL="${EXPECTED_KROKO_MODEL:-Kroko-DE-Pro-16-L-Streaming-001.data}"
    ;;
  free)
    EXPECTED_KROKO_MODEL="${EXPECTED_KROKO_MODEL:-Kroko-DE-Community-64-L-Streaming-001.data}"
    ;;
  *) die "Ungueltige Kroko-Variante: $KROKO_VARIANT (erlaubt: pro, free)" ;;
esac

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  die "Ein anderer Release-Lauf ist aktiv (Lock $LOCK_FILE)."
fi

preflight() {
  log "Preflight fuer Kroko $KROKO_VARIANT / $EXPECTED_KROKO_MODEL"
  [[ -d "$CHECKOUT/.git" ]] || die "App-Checkout fehlt: $CHECKOUT"
  [[ -f "$STACK_COMPOSE" ]] || die "Stack-Compose fehlt: $STACK_COMPOSE"
  [[ -f "$STACK_CONFIG" ]] || die "Stack-Konfiguration fehlt: $STACK_CONFIG"
  [[ -f "$GITHUB_ENV" ]] || die "github.env fehlt: $GITHUB_ENV"
  [[ -d "$KROKO_MODELS" ]] || die "Kroko-Modellordner fehlt: $KROKO_MODELS"
  [[ -f "$KROKO_MODELS/$EXPECTED_KROKO_MODEL" ]] || \
    die "Erwartetes Kroko-Modell fehlt: $KROKO_MODELS/$EXPECTED_KROKO_MODEL"
  command -v docker >/dev/null || die "Docker CLI fehlt"
  command -v curl >/dev/null || die "curl fehlt"
  command -v rsync >/dev/null || die "rsync fehlt"
  command -v python3 >/dev/null || die "python3 fehlt"
  docker info >/dev/null 2>&1 || die "Docker-Daemon nicht erreichbar"

  grep -qF "        KROKO_VARIANT: $KROKO_VARIANT" "$STACK_COMPOSE" || \
    die "Aktives Compose ist nicht auf KROKO_VARIANT: $KROKO_VARIANT gesetzt"
  grep -qF "  model: $EXPECTED_KROKO_MODEL" "$STACK_CONFIG" || \
    die "Aktive Serverkonfiguration verwendet nicht $EXPECTED_KROKO_MODEL"
  grep -qF "  realtime_model: $EXPECTED_KROKO_MODEL" "$STACK_CONFIG" || \
    die "Aktive Realtime-Konfiguration verwendet nicht $EXPECTED_KROKO_MODEL"
  grep -q 'use_main_model_for_realtime:[[:space:]]*true' "$STACK_CONFIG" || \
    die "Der VPS-Release erwartet eine gemeinsame Kroko-Modellinstanz"

  if [[ "$KROKO_VARIANT" == "pro" ]]; then
    [[ -f "$KROKO_ENV" ]] || die "Kroko-Secret-Datei fehlt: $KROKO_ENV"
    grep -qE '^[[:space:]]*KROKO_API_KEY=' "$KROKO_ENV" || \
      die "KROKO_API_KEY fehlt in $KROKO_ENV"
  fi

  if [[ -n "$(git -C "$CHECKOUT" status --porcelain 2>/dev/null)" ]]; then
    die "App-Checkout ist nicht sauber. Release erst nach Commit/Push starten."
  fi

  local avail
  avail="$(df --output=avail /home/marco 2>/dev/null | tail -1 | tr -d ' ')"
  if [[ -n "$avail" && "$avail" -lt 20971520 ]]; then
    die "Zu wenig Plattenplatz (${avail} KB frei, mindestens 20 GB benoetigt)."
  fi
  if [[ "$WITH_VENV" == 1 ]] && ! command -v python3.12 >/dev/null; then
    die "python3.12 wird fuer --with-venv benoetigt."
  fi
  log "Preflight OK; Secret-Inhalte wurden nicht ausgegeben."
}

git_update() {
  log "Phase 1: Git-Update"
  set -a
  # shellcheck disable=SC1090
  . "$GITHUB_ENV"
  set +a
  : "${GITHUB_TOKEN:?GITHUB_TOKEN fehlt in github.env}"
  local helper='!f() { echo "username=x-access-token"; echo "password=${GITHUB_TOKEN}"; }; f'
  GIT_TERMINAL_PROMPT=0 git -C "$CHECKOUT" -c credential.helper="$helper" fetch origin
  GIT_TERMINAL_PROMPT=0 git -C "$CHECKOUT" merge --ff-only origin/main
  GIT_COMMIT="$(git -C "$CHECKOUT" rev-parse HEAD)"
  log "Checkout: $(git -C "$CHECKOUT" log --oneline -1)"
  unset GITHUB_TOKEN GITHUB_PASSWORT GITHUB_PASSWORD
}

build_area_prepare() {
  log "Phase 2: Build-Area vorbereiten"
  case "$BUILD_DIR" in
    "$BUILD_AREA_ROOT"/*) ;;
    *) die "Ungueltiger Build-Pfad: $BUILD_DIR" ;;
  esac
  if [[ -e "$BUILD_DIR" ]]; then
    rm -rf "$BUILD_DIR"
  fi
  mkdir -p "$BUILD_AREA_ROOT"
  rsync -a --delete --exclude '.git' "$CHECKOUT/" "$BUILD_DIR/"
}

venv_build() {
  if [[ "$WITH_VENV" != 1 ]]; then
    log "Phase 3: optionalen venv-Restore uebersprungen"
    return
  fi
  log "Phase 3: Build-venv mit Kroko $KROKO_VARIANT aufbauen"
  KROKO_VARIANT="$KROKO_VARIANT" \
    "$CHECKOUT/build/vps/build-area/restore-venv.sh"
}

cache_image_for_variant() {
  if [[ "$KROKO_VARIANT" == "pro" ]]; then
    printf '%s\n' "$CACHE_IMAGE_PRO"
  else
    printf '%s\n' "$CACHE_IMAGE_FREE"
  fi
}

kroko_cache_build() {
  local cache_image
  cache_image="$(cache_image_for_variant)"
  log "Phase 4: Kroko-Builder-Cache $cache_image"
  docker build --pull --target kroko-builder \
    --build-arg KROKO_VARIANT="$KROKO_VARIANT" \
    --label selfhost.keep=kroko-cache \
    --cache-from "$cache_image" \
    -t "$cache_image" "$BUILD_DIR"
}

build_image() {
  local cache_image start
  cache_image="$(cache_image_for_variant)"
  start="$(date +%s)"
  log "Phase 5: Image $IMAGE mit Kroko $KROKO_VARIANT bauen"
  docker build --pull --target cpu \
    --build-arg KROKO_VARIANT="$KROKO_VARIANT" \
    --cache-from "$cache_image" \
    -t "$IMAGE" "$BUILD_DIR"
  IMAGE_ID="$(docker inspect --format '{{.Id}}' "$IMAGE")"
  log "Image $IMAGE_ID in $(( $(date +%s) - start )) Sekunden gebaut"
}

tag_previous_image() {
  if docker image inspect "$IMAGE" >/dev/null 2>&1; then
    PREV_IMAGE_ID="$(docker inspect --format '{{.Id}}' "$IMAGE")"
    docker tag "$IMAGE" "$PREV_IMAGE"
    log "Vorheriges Image als $PREV_IMAGE gesichert: $PREV_IMAGE_ID"
  else
    warn "Kein bisheriges Image vorhanden; automatisches Rollback ist nicht moeglich."
  fi
}

snapshot_runtime_config() {
  if [[ ! -f "$RUNTIME_CONFIG" ]]; then
    log "Keine persistierte runtime.json vorhanden."
    return
  fi
  RUNTIME_SNAPSHOT="$(mktemp /tmp/voice-stt-runtime.XXXXXX.json)"
  cp --preserve=mode,timestamps "$RUNTIME_CONFIG" "$RUNTIME_SNAPSHOT"
  log "Persistierte Runtime-Konfiguration fuer Rollback gesichert."
}

recreate() {
  log "Phase 6: Container ersetzen"
  docker compose -f "$STACK_COMPOSE" up -d --no-build --force-recreate "$CONTAINER"
}

health_matches_expected() {
  curl -fsS --max-time 5 "$HEALTH_LOCAL" 2>/dev/null | \
    EXPECTED_KROKO_MODEL="$EXPECTED_KROKO_MODEL" python3 -c '
import json, os, sys
d = json.load(sys.stdin)
active = ((d.get("models") or {}).get("active") or {})
final = active.get("final") or {}
realtime = active.get("realtime") or {}
model = os.environ["EXPECTED_KROKO_MODEL"]
ok = (
    d.get("ok") is True
    and d.get("ready") is True
    and final.get("engine") == "kroko_onnx"
    and realtime.get("engine") == "kroko_onnx"
    and final.get("model") == model
    and realtime.get("model") == model
    and realtime.get("sharedWithFinal") is True
)
raise SystemExit(0 if ok else 1)
' 2>/dev/null
}

health_check() {
  log "Phase 7: Health und aktives Modell pruefen (Timeout ${HEALTH_TIMEOUT}s)"
  local deadline ok=0
  deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  while (( $(date +%s) < deadline )); do
    if health_matches_expected; then
      ok=1
      break
    fi
    sleep 10
  done
  if [[ "$ok" != 1 ]]; then
    HEALTH_LOCAL_RESULT="FEHLGESCHLAGEN"
    warn "Health ist nicht bereit oder meldet nicht das erwartete geteilte Kroko-Modell."
    curl -fsS --max-time 5 "$HEALTH_LOCAL" 2>/dev/null | python3 -m json.tool >>"$LOG_FILE" 2>&1 || true
    return 1
  fi
  HEALTH_LOCAL_RESULT="ok+ready; kroko_onnx/$EXPECTED_KROKO_MODEL; shared"
  log "Lokaler Health-Nachweis: $HEALTH_LOCAL_RESULT"

  if curl -fsS --max-time 10 "$HEALTH_PUBLIC" 2>/dev/null | \
     python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("ok") and d.get("ready") else 1)' 2>/dev/null; then
    HEALTH_PUBLIC_RESULT="ok+ready"
  else
    HEALTH_PUBLIC_RESULT="nicht erreichbar; Caddy-Route pruefen"
    warn "Oeffentlicher Healthcheck ist nicht ok."
  fi

  docker exec "$CONTAINER" sh -lc '
    test -d /models/ctranslate2 && test -d /models/kroko &&
    test -d /models/openwakeword && test -d /data && test -d /config &&
    find /models/kroko -maxdepth 2 -type f | grep -q .
  ' >/dev/null || warn "Mindestens ein Modell-/Datenmount fehlt im Container."

  local log_hits
  log_hits="$(docker logs --tail 250 "$CONTAINER" 2>&1 | \
    grep -iE 'error|exception|traceback|segmentation' | \
    grep -v 'startupErrors.*\[\]' | head -5 || true)"
  if [[ -n "$log_hits" ]]; then
    LOG_NOTES="Auffaellige Logzeilen vorhanden; siehe $LOG_FILE"
    printf '%s\n' "$log_hits" >>"$LOG_FILE"
    warn "$LOG_NOTES"
  fi
}

restore_runtime_snapshot() {
  if [[ -n "$RUNTIME_SNAPSHOT" && -f "$RUNTIME_SNAPSHOT" ]]; then
    mkdir -p "$(dirname "$RUNTIME_CONFIG")"
    cp --preserve=mode,timestamps "$RUNTIME_SNAPSHOT" "$RUNTIME_CONFIG"
    log "Persistierte Runtime-Konfiguration wiederhergestellt."
  fi
}

rollback() {
  warn "ROLLBACK auf $PREV_IMAGE"
  [[ -n "$PREV_IMAGE_ID" ]] || die "Kein Rollback-Image vorhanden. Manueller Eingriff erforderlich."
  restore_runtime_snapshot
  docker tag "$PREV_IMAGE" "$IMAGE"
  docker compose -f "$STACK_COMPOSE" up -d --no-build --force-recreate "$CONTAINER"

  local deadline ok=0
  deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  while (( $(date +%s) < deadline )); do
    if curl -fsS --max-time 5 "$HEALTH_LOCAL" 2>/dev/null | \
       python3 -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("ok") and d.get("ready") else 1)' 2>/dev/null; then
      ok=1
      break
    fi
    sleep 10
  done
  [[ "$ok" == 1 ]] || die "Rollback-Image ist nicht gesund. Manueller Eingriff erforderlich."
  log "Rollback erfolgreich; vorheriges Image und Runtime-Konfiguration sind aktiv."
}

backup_build_area() {
  log "Phase 8: Build-Area sichern"
  local name archive
  name="${TODAY}_$(date -u +%H%M%S)_voice-stt-server_neu"
  archive="${BACKUP_DIR}/${name}.tar.gz"
  mkdir -p "$BACKUP_DIR"
  (cd "$BUILD_AREA_ROOT" && mv "$(basename "$BUILD_DIR")" "$name")
  tar -czf "$archive" -C "$BUILD_AREA_ROOT" "$name"
  case "${BUILD_AREA_ROOT}/${name}" in
    "$BUILD_AREA_ROOT"/*) rm -rf "${BUILD_AREA_ROOT:?}/${name}" ;;
    *) die "Ungueltiger temporaerer Backuppfad" ;;
  esac
  BACKUP_FILE="$archive"
}

prune_docker() {
  log "Phase 9: konservatives Docker-Cleanup"
  docker container prune -f --filter 'until=24h' >/dev/null || warn "container prune fehlgeschlagen"
  docker image prune -f --filter 'until=168h' --filter 'label!=selfhost.keep' || warn "image prune fehlgeschlagen"
  docker builder prune -f --filter 'until=168h' >/dev/null || warn "builder prune fehlgeschlagen"
  PRUNE_RESULT="OK; Kroko-Cache per Label geschuetzt"
}

write_docs() {
  log "Phase 10: externes Release-Ergebnis schreiben"
  python3 - "$RESULT_JSON" "$GIT_COMMIT" "$IMAGE" "$IMAGE_ID" \
    "$PREV_IMAGE_ID" "$HEALTH_LOCAL_RESULT" "$HEALTH_PUBLIC_RESULT" \
    "$BACKUP_FILE" "$PRUNE_RESULT" "$LOG_NOTES" "$KROKO_VARIANT" \
    "$EXPECTED_KROKO_MODEL" "$PRUNE" "$WITH_VENV" "$DRY_RUN" "$SKIP_BUILD" <<'PY'
import datetime
import json
import sys

(path, git_commit, image, image_id, previous_image_id, health_local,
 health_public, backup_file, prune_result, notes, variant, model,
 prune, with_venv, dry_run, skip_build) = sys.argv[1:]
payload = {
    "released_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "git_commit": git_commit,
    "image": image,
    "image_id": image_id,
    "previous_image_id": previous_image_id,
    "kroko_variant": variant,
    "kroko_model": model,
    "health_local": health_local,
    "health_public": health_public,
    "backup_file": backup_file,
    "prune": prune_result,
    "notes": notes,
    "mode": {
        "prune": int(prune),
        "with_venv": int(with_venv),
        "dry_run": int(dry_run),
        "skip_build": int(skip_build),
    },
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

  cat >>"$RELEASE_LOG" <<EOF

---

## Release ${TODAY} (automatisiert)

- Datum: $(date -u -Iseconds)
- Git-Commit: \`${GIT_COMMIT}\`
- Image: \`${IMAGE}\` -> \`${IMAGE_ID}\`
- Kroko: \`${KROKO_VARIANT}\`, \`${EXPECTED_KROKO_MODEL}\`, geteilte Instanz
- Health lokal: ${HEALTH_LOCAL_RESULT}
- Health oeffentlich: ${HEALTH_PUBLIC_RESULT}
- Backup: ${BACKUP_FILE}
- Prune: ${PRUNE_RESULT}
- Auffaelligkeiten: ${LOG_NOTES:-keine}
- Details: \`release-result.json\`
EOF
}

cleanup() {
  if [[ -n "$RUNTIME_SNAPSHOT" && -f "$RUNTIME_SNAPSHOT" ]]; then
    rm -f "$RUNTIME_SNAPSHOT"
  fi
}
trap cleanup EXIT

main() {
  log "=== Release voice/stt-voice gestartet ==="
  log "Modus: variant=$KROKO_VARIANT prune=$PRUNE with_venv=$WITH_VENV dry_run=$DRY_RUN skip_build=$SKIP_BUILD"
  preflight
  if [[ "$DRY_RUN" == 1 ]]; then
    log "DRY-RUN erfolgreich; keine Aenderung ausgefuehrt."
    return
  fi

  git_update
  build_area_prepare
  venv_build

  tag_previous_image
  if [[ "$SKIP_BUILD" != 1 ]]; then
    kroko_cache_build
    build_image
  else
    IMAGE_ID="$(docker inspect --format '{{.Id}}' "$IMAGE")"
    warn "--skip-build verwendet das bestehende Image $IMAGE_ID."
  fi

  snapshot_runtime_config
  recreate
  if ! health_check; then
    rollback
    HEALTH_LOCAL_RESULT="FEHLGESCHLAGEN; Rollback auf $PREV_IMAGE_ID"
    write_docs
    return 1
  fi

  backup_build_area
  if [[ "$PRUNE" == 1 ]]; then
    prune_docker
  else
    PRUNE_RESULT="uebersprungen"
  fi
  write_docs
  log "=== Release erfolgreich: $GIT_COMMIT / $IMAGE_ID ==="
}

main "$@"
