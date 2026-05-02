# scripts/food_safety/_db_env.sh
#
# Source this from apply.sh / rollback.sh / backup_db.sh to populate
# DB_URL_DASHBOARD and DB_URL_MANAGER plus a `pg` shell function that
# runs psql against the right server (host's local docker, or cloud).
#
# Credential resolution order (first wins per key):
#   1. value already in environment (override at invocation)
#   2. scripts/food_safety/.env.script           (user-maintained, gitignored)
#   3. docker/.env                                (BE config; only useful for local docker)
#   4. defaults below                             (host-reachable local docker)
#
# All `docker run` invocations use --network=host so the temp $PG_CLIENT_IMAGE
# container reaches `localhost` the same way the host does. For cloud DBs,
# the connection just resolves the public hostname normally.

_FS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_FS_REPO="$(cd "$_FS_ROOT/../.." && pwd)"

_load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS='=' read -r key val; do
    case "$key" in
      DB_DASHBOARD_*|DB_MANAGER_*)
        if [ -z "${!key+x}" ]; then
          # strip CR / surrounding quotes
          val="${val%$'\r'}"
          val="${val#\"}"; val="${val%\"}"
          val="${val#\'}"; val="${val%\'}"
          export "$key=$val"
        fi
        ;;
    esac
  done < <(grep -E '^(DB_DASHBOARD|DB_MANAGER)_[A-Z_]+=' "$f" 2>/dev/null)
}

_load_env_file "$_FS_ROOT/.env.script"
_load_env_file "$_FS_REPO/docker/.env"

# Postgres client image used by `docker run` for psql / pg_dump. Must match
# server major version (>= server major). Override in .env.script if needed.
: "${PG_CLIENT_IMAGE:=postgres:17}"
export PG_CLIENT_IMAGE

# Defaults — local docker postgres exposed on host (5433 / 5432)
: "${DB_DASHBOARD_HOST:=localhost}"
: "${DB_DASHBOARD_PORT:=5433}"
: "${DB_DASHBOARD_USER:=postgres}"
: "${DB_DASHBOARD_PASSWORD:=test1234}"
: "${DB_DASHBOARD_DBNAME:=dashboard}"
: "${DB_DASHBOARD_SSLMODE:=disable}"

: "${DB_MANAGER_HOST:=localhost}"
: "${DB_MANAGER_PORT:=5432}"
: "${DB_MANAGER_USER:=postgres}"
: "${DB_MANAGER_PASSWORD:=test1234}"
: "${DB_MANAGER_DBNAME:=dashboardmanager}"
: "${DB_MANAGER_SSLMODE:=disable}"

# If host is a docker-internal name (BE config bleed-through), translate so the
# temp $PG_CLIENT_IMAGE container --network=host can reach the exposed port.
case "$DB_DASHBOARD_HOST" in
  postgres-data) DB_DASHBOARD_HOST=localhost; DB_DASHBOARD_PORT=5433 ;;
esac
case "$DB_MANAGER_HOST" in
  postgres-manager) DB_MANAGER_HOST=localhost; DB_MANAGER_PORT=5432 ;;
esac

_urlenc() { python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }

DB_URL_DASHBOARD="postgresql://${DB_DASHBOARD_USER}:$(_urlenc "$DB_DASHBOARD_PASSWORD")@${DB_DASHBOARD_HOST}:${DB_DASHBOARD_PORT}/${DB_DASHBOARD_DBNAME}?sslmode=${DB_DASHBOARD_SSLMODE}"
DB_URL_MANAGER="postgresql://${DB_MANAGER_USER}:$(_urlenc "$DB_MANAGER_PASSWORD")@${DB_MANAGER_HOST}:${DB_MANAGER_PORT}/${DB_MANAGER_DBNAME}?sslmode=${DB_MANAGER_SSLMODE}"

export DB_URL_DASHBOARD DB_URL_MANAGER
export DB_DASHBOARD_HOST DB_DASHBOARD_PORT DB_DASHBOARD_USER DB_DASHBOARD_PASSWORD DB_DASHBOARD_DBNAME DB_DASHBOARD_SSLMODE
export DB_MANAGER_HOST   DB_MANAGER_PORT   DB_MANAGER_USER   DB_MANAGER_PASSWORD   DB_MANAGER_DBNAME   DB_MANAGER_SSLMODE

# pg_psql DASHBOARD < some.sql        — run psql against dashboard DB
# pg_psql MANAGER -c "SELECT ..."     — run psql with arbitrary args
pg_psql() {
  local which="$1"; shift
  local url
  case "$which" in
    DASHBOARD) url="$DB_URL_DASHBOARD" ;;
    MANAGER)   url="$DB_URL_MANAGER" ;;
    *) echo "pg_psql: first arg must be DASHBOARD or MANAGER" >&2; return 2 ;;
  esac
  docker run --rm -i --network=host $PG_CLIENT_IMAGE psql "$url" -v ON_ERROR_STOP=1 "$@"
}

# pg_dump_to FILE DASHBOARD          — pg_dump dashboard DB to FILE
pg_dump_to() {
  local out="$1" which="$2"
  local url
  case "$which" in
    DASHBOARD) url="$DB_URL_DASHBOARD" ;;
    MANAGER)   url="$DB_URL_MANAGER" ;;
    *) echo "pg_dump_to: second arg must be DASHBOARD or MANAGER" >&2; return 2 ;;
  esac
  docker run --rm --network=host $PG_CLIENT_IMAGE pg_dump "$url" > "$out"
}
