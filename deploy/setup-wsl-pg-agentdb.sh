#!/usr/bin/env bash
# 本机 WSL PostgreSQL：库 agentDB / 用户 admin / 密码 admin，允许 Windows 连接
set -euo pipefail

DB_NAME="agentDB"
DB_USER="admin"
DB_PASS="admin"
HBA="/etc/postgresql/16/main/pg_hba.conf"
CONF="/etc/postgresql/16/main/postgresql.conf"
MARKER="# LangGraph_Agent Windows access"

echo "[info] 安装/确认 PostgreSQL 16 ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib >/dev/null

# 若集群未起来
if ! pg_lsclusters 2>/dev/null | grep -q online; then
  echo "[info] 启动集群 ..."
  pg_ctlcluster 16 main start || service postgresql start || true
fi
systemctl enable postgresql 2>/dev/null || true
systemctl start postgresql 2>/dev/null || service postgresql start || true

if [ ! -f "$HBA" ] || [ ! -f "$CONF" ]; then
  echo "[error] 未找到 $HBA 或 $CONF"
  pg_lsclusters || true
  exit 1
fi

echo "[info] listen_addresses = '*' ..."
if grep -qE "^#?\s*listen_addresses\s*=" "$CONF"; then
  sed -i "s/^#\?\s*listen_addresses\s*=.*/listen_addresses = '*'/" "$CONF"
else
  echo "listen_addresses = '*'" >> "$CONF"
fi

echo "[info] 配置 pg_hba.conf ..."
# 去掉旧标记块后重写，避免重复
if grep -qF "$MARKER" "$HBA"; then
  # 删除标记行及其后连续 host 规则到文件尾的自定义块较麻烦，改为若不存在关键规则再追加
  :
fi
if ! grep -qF "$MARKER" "$HBA"; then
  cat >> "$HBA" <<EOF

$MARKER
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    all             all             172.16.0.0/12           scram-sha-256
host    all             all             192.168.0.0/16          scram-sha-256
host    all             all             10.0.0.0/8              scram-sha-256
EOF
fi

echo "[info] 重启 PostgreSQL ..."
systemctl restart postgresql 2>/dev/null || service postgresql restart
sleep 2
pg_isready -h 127.0.0.1 -p 5432

echo "[info] 创建用户/库 ..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}' CREATEDB;
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}' CREATEDB;
  END IF;
END
\$\$;

SELECT 'user_ok' AS status;
SQL

# 库名保留大小写 agentDB
EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")
if [ "$EXISTS" != "1" ]; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${DB_NAME}\" OWNER ${DB_USER} ENCODING 'UTF8';"
  echo "[ok] 已创建数据库 \"${DB_NAME}\""
else
  echo "[info] 数据库 \"${DB_NAME}\" 已存在，调整 OWNER"
  sudo -u postgres psql -c "ALTER DATABASE \"${DB_NAME}\" OWNER TO ${DB_USER};" || true
fi

echo "[info] 本机密码登录探测 ..."
PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" -c "SELECT current_user, current_database();"

WSL_IP=$(hostname -I | awk '{print $1}')
echo
echo "[ok] 配置完成"
echo "----- DBeaver / Windows -----"
echo "  主机: 127.0.0.1   （不行则用 $WSL_IP）"
echo "  端口: 5432"
echo "  数据库: ${DB_NAME}"
echo "  用户名: ${DB_USER}"
echo "  密码: ${DB_PASS}"
echo "----- .env 建议 -----"
echo "  DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}"
