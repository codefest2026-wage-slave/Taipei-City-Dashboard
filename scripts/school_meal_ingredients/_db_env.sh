# scripts/school_meal_ingredients/_db_env.sh
#
# Source this from apply.sh / rollback.sh / backup_db.sh to populate
# DB_URL_DASHBOARD plus a `pg_psql` shell function that runs psql against
# the dashboard DB (host's local docker, or cloud).
#
# Credential resolution order (first wins per key):
#   1. value already in environment (override at invocation)
#   2. scripts/school_meal_ingredients/.env.script   (user-maintained, gitignored)
#   3. docker/.env                                   (BE config; only useful for local docker)
#   4. defaults below                                (host-reachable local docker)

_SMI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SMI_REPO="$(cd "$_SMI_ROOT/../.." && pwd)"

_load_env_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  while IFS='=' read -r key val; do
    case "$key" in
      DB_DASHBOARD_*)
        if [ -z "${!key+x}" ]; then
          val="${val%$'\r'}"
          val="${val#\"}"; val="${val%\"}"
          val="${val#\'}"; val="${val%\'}"
          export "$key=$val"
        fi
        ;;
    esac
  done < <(grep -E '^DB_DASHBOARD_[A-Z_]+=' "$f" 2>/dev/null)
}

_load_env_file "$_SMI_ROOT/.env.script"
_load_env_file "$_SMI_REPO/docker/.env"

: "${PG_CLIENT_IMAGE:=postgres:17}"
export PG_CLIENT_IMAGE

# Defaults — local docker postgres exposed on host
: "${DB_DASHBOARD_HOST:=localhost}"
: "${DB_DASHBOARD_PORT:=5433}"
: "${DB_DASHBOARD_USER:=postgres}"
: "${DB_DASHBOARD_PASSWORD:=test1234}"
: "${DB_DASHBOARD_DBNAME:=dashboard}"
: "${DB_DASHBOARD_SSLMODE:=disable}"

# Translate docker-internal hostname (BE config bleed-through) to localhost.
case "$DB_DASHBOARD_HOST" in
  postgres-data) DB_DASHBOARD_HOST=localhost; DB_DASHBOARD_PORT=5433 ;;
esac

_urlenc() { python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"; }

DB_URL_DASHBOARD="postgresql://${DB_DASHBOARD_USER}:$(_urlenc "$DB_DASHBOARD_PASSWORD")@${DB_DASHBOARD_HOST}:${DB_DASHBOARD_PORT}/${DB_DASHBOARD_DBNAME}?sslmode=${DB_DASHBOARD_SSLMODE}"

export DB_URL_DASHBOARD
export DB_DASHBOARD_HOST DB_DASHBOARD_PORT DB_DASHBOARD_USER DB_DASHBOARD_PASSWORD DB_DASHBOARD_DBNAME DB_DASHBOARD_SSLMODE

# pg_psql -1 < some.sql        — run psql with single-transaction file
# pg_psql -c "SELECT ..."      — run psql with arbitrary args
pg_psql() {
  docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_DASHBOARD" -v ON_ERROR_STOP=1 "$@"
}

# pg_dump_to FILE              — pg_dump dashboard DB to FILE
pg_dump_to() {
  local out="$1"
  docker run --rm --network=host "$PG_CLIENT_IMAGE" pg_dump "$DB_URL_DASHBOARD" > "$out"
}
