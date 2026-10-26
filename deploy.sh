#!/usr/bin/env bash
# One-click deploy for AMLI on a CLI-only Linux server (Docker or Podman).
# Usage:  chmod +x deploy.sh && ./deploy.sh
#
# Database modes (picked automatically from DB_HOST in .env):
#   DB_HOST=db            -> SQL Server runs in a container on this same server (easiest)
#   DB_HOST=<ip/hostname> -> external SQL Server (e.g. the Windows DB server)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- 1. Container engine + compose provider --------------------------------
say "1/7 Detecting container engine"
if   command -v docker >/dev/null 2>&1; then ENGINE=docker
elif command -v podman >/dev/null 2>&1; then ENGINE=podman
else fail "Neither docker nor podman found"; fi

IS_PODMAN=0
$ENGINE --version 2>&1 | grep -qi podman && IS_PODMAN=1

SUDO=""
if ! $ENGINE info >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null; then SUDO="sudo"; else fail "Cannot talk to $ENGINE (permission denied?). Add your user to the docker group or run with sudo."; fi
  $SUDO $ENGINE info >/dev/null 2>&1 || fail "$ENGINE is not running"
fi

if [ "$IS_PODMAN" = 1 ] && [ -x /usr/local/bin/docker-compose ]; then
  # Installed by AMLI-prereqs: standalone docker-compose talking to the Podman socket
  if [ -n "$SUDO" ] || [ "$(id -u)" = 0 ]; then export DOCKER_HOST="unix:///run/podman/podman.sock"
  else export DOCKER_HOST="unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"; fi
  [ -S "${DOCKER_HOST#unix://}" ] || fail "Podman socket not found at ${DOCKER_HOST#unix://}. Run: systemctl --user enable --now podman.socket (or re-run AMLI-prereqs/install-prereqs.sh)"
  COMPOSE="$SUDO /usr/local/bin/docker-compose"
elif $SUDO $ENGINE compose version >/dev/null 2>&1; then COMPOSE="$SUDO $ENGINE compose"
elif command -v docker-compose >/dev/null 2>&1;     then COMPOSE="$SUDO docker-compose"
elif command -v podman-compose >/dev/null 2>&1;     then COMPOSE="$SUDO podman-compose"
else fail "No compose provider found. Install docker-compose (v2) or podman-compose."; fi

ROOTLESS=0
if [ "$IS_PODMAN" = 1 ] && [ -z "$SUDO" ] && [ "$(id -u)" != 0 ]; then ROOTLESS=1; fi
echo "engine=$ENGINE podman=$IS_PODMAN rootless=$ROOTLESS compose='$COMPOSE'"

# ---- 2. .env checks ---------------------------------------------------------
say "2/7 Checking .env"
if [ ! -f .env ]; then
  TEMPLATE=.env.localdb.example; DB_PW_GEN=""
  if [ "${AMLI_DB_MODE:-}" = "external" ]; then
    TEMPLATE=.env.external.example
    [ -n "${AMLI_DB_PASSWORD:-}" ] || fail "External DB mode: run as  AMLI_DB_MODE=external AMLI_DB_PASSWORD='<password>' bash deploy.sh"
    DB_PW_GEN="$(printf '%s' "$AMLI_DB_PASSWORD" | sed -e 's#[\\/&|]#\\&#g')"
  fi
  [ -f "$TEMPLATE" ] || fail "Neither .env nor $TEMPLATE found in $(pwd)"
  echo "No .env found: creating it from $TEMPLATE"
  HOST_IP="${AMLI_HOST:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
  [ -n "$HOST_IP" ] || HOST_IP="localhost"
  rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
  SECRET_KEY_GEN="${AMLI_SECRET_KEY:-$(rand 64)}"
  [ -n "$DB_PW_GEN" ] || DB_PW_GEN="Isg$(rand 16)Aa1!"
  cp "$TEMPLATE" .env
  sed -i -e "s|__HOST__|${HOST_IP}|g" -e "s|__SECRET_KEY__|${SECRET_KEY_GEN}|" -e "s|__DB_PASSWORD__|${DB_PW_GEN}|g" -e "s|__DB_NAME__|${AMLI_DB_NAME:-master}|g" .env
  chmod 600 .env
  echo "Server address set to ${HOST_IP} (override with: AMLI_HOST=<ip-or-name> bash deploy.sh)"
fi
GENERATED_ADMIN_PW=""
if grep -q '^CISO_ASSISTANT_SUPERUSER_PASSWORD=CHANGE_ME_ADMIN_PASSWORD' .env; then
  GENERATED_ADMIN_PW="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 14)#9Aa"
  sed -i "s|^CISO_ASSISTANT_SUPERUSER_PASSWORD=CHANGE_ME_ADMIN_PASSWORD|CISO_ASSISTANT_SUPERUSER_PASSWORD=${GENERATED_ADMIN_PW}|" .env
  echo "Generated a random admin password (shown at the end)."
fi
if grep -q 'CHANGE_ME' .env; then
  grep -n 'CHANGE_ME' .env
  fail "Replace the CHANGE_ME values in .env first"
fi
envval() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | sed -e "s/^['\"]//" -e "s/['\"]$//"; }
DB_HOST="$(envval DB_HOST)"; DB_PORT="$(envval DB_PORT)"; URL="$(envval CISO_ASSISTANT_URL)"

LOCAL_DB=0; [ "$DB_HOST" = "db" ] && LOCAL_DB=1
if [ "$LOCAL_DB" = 1 ]; then
  echo "Database mode: local container (DB_HOST=db)"
else
  say "Checking external database reachability (${DB_HOST}:${DB_PORT})"
  timeout 5 bash -c "exec 3<>/dev/tcp/${DB_HOST}/${DB_PORT}" 2>/dev/null \
    || fail "Cannot reach ${DB_HOST}:${DB_PORT}. Ask the DB team to allow this server through the firewall and enable SQL Server TCP/IP."
  echo "Database port is reachable."
fi

# ---- 3. Data directory permissions -----------------------------------------
say "3/7 Preparing data directory"
mkdir -p db
if [ "$ROOTLESS" = 1 ]; then
  podman unshare chown -R 1001:1001 db
else
  chown -R 1001:1001 db 2>/dev/null || sudo chown -R 1001:1001 db
fi
if command -v getenforce >/dev/null 2>&1 && [ "$(getenforce)" = "Enforcing" ]; then
  echo "SELinux is enforcing: labelling ./db for containers"
  chcon -R -t container_file_t db 2>/dev/null || sudo chcon -R -t container_file_t db
fi

# ---- 4. Build ---------------------------------------------------------------
say "4/7 Building images (first time takes several minutes)"
images_present() {
  $SUDO $ENGINE image inspect localhost/amli-backend:local >/dev/null 2>&1     && $SUDO $ENGINE image inspect localhost/amli-frontend:local >/dev/null 2>&1
}
if ! images_present; then
  # Try the pre-built images published by AMLI-prereqs before building (building needs
  # Docker Hub / PyPI / npm access, which locked-down servers do not have).
  IMG_REPO="${AMLI_IMAGES_REPO:-Pentest0017/AMLI-prereqs}"; IMG_TAG="${AMLI_IMAGES_TAG:-images-app-v1}"
  for d in "$(pwd)/../AMLI-prereqs" "$HOME/AMLI-prereqs"; do
    if [ -f "$d/load-images.sh" ]; then
      if [ -d "$d/payload/app" ]; then
        echo "Pre-built images not loaded - loading them from $d/payload/app"
        bash "$d/load-images.sh" --local "$d/payload/app" || echo "Loading failed - will try to build instead."
      else
        echo "Pre-built images not loaded - downloading ${IMG_REPO}@${IMG_TAG} via $d/load-images.sh"
        bash "$d/load-images.sh" "$IMG_REPO" "$IMG_TAG" || echo "Download/load failed - will try to build instead."
      fi
      break
    fi
  done
fi
# Base images (qdrant, caddy, mailhog) - load from the AMLI-prereqs release if they are not present,
# so the server never has to pull from a registry it cannot verify.
BASE_IMG_TAG="${AMLI_BASE_IMAGES_TAG:-images-base-v1}"
if ! $SUDO $ENGINE image inspect docker.io/qdrant/qdrant:v1.14.0 >/dev/null 2>&1; then
  for d in "$(pwd)/../AMLI-prereqs" "$HOME/AMLI-prereqs"; do
    if [ -f "$d/load-images.sh" ]; then
      if [ -d "$d/payload/base" ]; then
        echo "Base images not loaded - loading them from $d/payload/base"
        bash "$d/load-images.sh" --local "$d/payload/base" || echo "Loading failed - compose will try to pull them."
      else
        echo "Base images not loaded - downloading ${IMG_REPO:-Pentest0017/AMLI-prereqs}@${BASE_IMG_TAG}"
        bash "$d/load-images.sh" "${IMG_REPO:-Pentest0017/AMLI-prereqs}" "$BASE_IMG_TAG" || echo "Base image download failed - compose will try to pull them."
      fi
      break
    fi
  done
fi
# SQL Server image for the all-in-one mode (DB_HOST=db). It cannot be redistributed on GitHub, so it
# is either pulled from Microsoft's registry or copied once by hand (see the message below).
if [ "$LOCAL_DB" = 1 ]; then
  MSSQL_IMG="mcr.microsoft.com/mssql/server:2022-latest"
  if ! $SUDO $ENGINE image inspect "$MSSQL_IMG" >/dev/null 2>&1; then
    MSSQL_TAR="$(ls "$HOME"/mssql*.tar.gz "$(pwd)"/mssql*.tar.gz "$(pwd)"/../mssql*.tar.gz 2>/dev/null | head -n1 || true)"
    if [ -n "$MSSQL_TAR" ]; then
      echo "Loading the SQL Server image from $MSSQL_TAR (takes a minute)"
      gzip -dc "$MSSQL_TAR" | $SUDO $ENGINE load
    else
      echo "Pulling $MSSQL_IMG from Microsoft's registry..."
      $SUDO $ENGINE pull "$MSSQL_IMG" || fail "Cannot get the SQL Server image. On a PC that can reach it run:
    docker pull $MSSQL_IMG && docker save $MSSQL_IMG | gzip > mssql.tar.gz
  copy mssql.tar.gz to this server's home folder (~), then run deploy.sh again.
  (Or use your Windows SQL Server instead:  AMLI_DB_MODE=external AMLI_DB_PASSWORD='...' bash deploy.sh)"
    fi
  fi
fi
if images_present; then
  echo "Pre-built AMLI images found - skipping the build."
else
  # Podman has no BuildKit ("booting buildkit" error), so build the two images with the engine
  # directly and let compose only start containers. Docker keeps using compose to build.
  export DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0
  if [ "$IS_PODMAN" = 1 ]; then
    RAM_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
    HEAP_MB=$(( RAM_MB * 3 / 4 )); [ "$HEAP_MB" -gt 8192 ] && HEAP_MB=8192; [ "$HEAP_MB" -lt 3072 ] && HEAP_MB=3072
    [ "$RAM_MB" -lt 9000 ] && echo "WARNING: ${RAM_MB} MB RAM - the frontend build may run out of memory; prefer the prebuilt images (see AMLI-prereqs/load-images.sh)."
    echo "Building backend image..."
    $SUDO $ENGINE build -t localhost/amli-backend:local --build-arg PYTHON_IMAGE=docker.io/library/python:3.14-slim ./backend
    echo "Building frontend image (Node heap ${HEAP_MB} MB)..."
    $SUDO $ENGINE build -t localhost/amli-frontend:local --build-arg NODE_IMAGE=docker.io/library/node:22-slim --build-arg NODE_BUILD_HEAP_MB="$HEAP_MB" ./frontend
  else
    $COMPOSE build
  fi
fi

wait_healthy() { # name, tries
  local name="$1" tries="${2:-60}" st
  for i in $(seq 1 "$tries"); do
    st="$($SUDO $ENGINE inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || true)"
    [ -z "$st" ] && st="$($SUDO $ENGINE inspect -f '{{.State.Healthcheck.Status}}' "$name" 2>/dev/null || true)"
    [ "$st" = "healthy" ] && return 0
    sleep 10
  done
  $SUDO $ENGINE logs --tail 60 "$name" || true
  fail "$name did not become healthy"
}

# ---- 5. Start services in stages -------------------------------------------
say "5/7 Starting services"
if [ "$LOCAL_DB" = 1 ]; then
  $COMPOSE up -d --no-build --no-deps db mailhog qdrant
  echo "Waiting for database container..."
  wait_healthy db 60
  # Restore a backup of the existing database, if one was supplied (see RESTORE_DB.md)
  BAK="$(ls "$(pwd)"/restore/*.bak "$HOME"/*.bak "$(pwd)"/../*.bak 2>/dev/null | head -n1 || true)"
  TARGET_DB="$(envval DB_NAME)"
  if [ -n "$BAK" ] && [ "$TARGET_DB" != "master" ]; then
    SAPW="$(envval MSSQL_SA_PASSWORD)"
    SQLC="$SUDO $ENGINE exec -e SQLCMDPASSWORD=$SAPW db /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b"
    if $SQLC -h -1 -W -Q "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE name='${TARGET_DB}'" | grep -qx "$TARGET_DB"; then
      echo "Database ${TARGET_DB} already exists - skipping restore."
    else
      say "Restoring ${TARGET_DB} from $BAK"
      chmod 644 "$BAK" 2>/dev/null || true
      $SUDO $ENGINE exec db mkdir -p /var/opt/mssql/backup
      $SUDO $ENGINE cp "$BAK" db:/var/opt/mssql/backup/restore.bak
      MOVES=""
      while IFS='|' read -r lname _ ftype _; do
        [ -n "$lname" ] || continue
        case "$ftype" in
          L) MOVES="$MOVES, MOVE N'$lname' TO N'/var/opt/mssql/data/${TARGET_DB}_$lname.ldf'";;
          *) MOVES="$MOVES, MOVE N'$lname' TO N'/var/opt/mssql/data/${TARGET_DB}_$lname.mdf'";;
        esac
      done < <($SQLC -h -1 -W -s '|' -Q "SET NOCOUNT ON; RESTORE FILELISTONLY FROM DISK=N'/var/opt/mssql/backup/restore.bak'")
      $SQLC -Q "RESTORE DATABASE [${TARGET_DB}] FROM DISK=N'/var/opt/mssql/backup/restore.bak' WITH REPLACE${MOVES}"         || fail "Database restore failed (see message above)."
      $SUDO $ENGINE exec db rm -f /var/opt/mssql/backup/restore.bak
      echo "Restore complete."
    fi
  fi
else
  $COMPOSE up -d --no-build --no-deps mailhog qdrant
fi
$COMPOSE up -d --no-build --no-deps backend
echo "Waiting for backend (first start can take a few minutes)..."
wait_healthy backend 60
$COMPOSE up -d --no-build --no-deps huey frontend caddy

# ---- 6. Migrate -------------------------------------------------------------
say "6/7 Running database migrations"
$SUDO $ENGINE exec backend python manage.py migrate --noinput

# ---- 7. Summary -------------------------------------------------------------
say "7/7 Done"
$COMPOSE ps
echo
echo "AMLI is running at: ${URL}"
echo "Admin login:  $(envval CISO_ASSISTANT_SUPERUSER_EMAIL)"
if [ -n "$GENERATED_ADMIN_PW" ]; then echo "Admin password: ${GENERATED_ADMIN_PW}   (also saved in .env - change it after first login)"; fi
echo "(Browser will warn about the self-signed certificate; this is expected.)"
echo "Make sure port 8443/tcp is open in the server firewall, e.g.:"
echo "  sudo firewall-cmd --permanent --add-port=8443/tcp && sudo firewall-cmd --reload"
echo "Logs:  $ENGINE logs -f backend"
