#!/usr/bin/env bash
# 允许 Windows 经 WSL 虚拟网访问本机 PostgreSQL
set -euo pipefail

HBA="/etc/postgresql/16/main/pg_hba.conf"
CONF="/etc/postgresql/16/main/postgresql.conf"
MARKER="# LangGraph_Agent: allow Windows/WSL LAN"

if [ ! -f "$HBA" ]; then
  echo "[error] 未找到 $HBA，请确认 PostgreSQL 16 已安装"
  exit 1
fi

echo "[info] 当前 listen_addresses:"
sudo -u postgres psql -tAc "SHOW listen_addresses;" 2>/dev/null || true

# 监听所有接口，便于 Windows / 127.0.0.1 访问
if sudo grep -qE "^listen_addresses\s*=" "$CONF"; then
  sudo sed -i "s/^listen_addresses\s*=.*/listen_addresses = '*'/" "$CONF"
else
  echo "listen_addresses = '*'" | sudo tee -a "$CONF" >/dev/null
fi

if sudo grep -qF "$MARKER" "$HBA"; then
  echo "[info] pg_hba 规则已存在，跳过追加"
else
  echo "[info] 追加 pg_hba 规则 ..."
  sudo tee -a "$HBA" >/dev/null <<EOF

$MARKER
# Windows 主机在 WSL 侧常见为 172.30.x.1；整段私网一并放行
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    all             all             172.16.0.0/12           scram-sha-256
host    all             all             192.168.0.0/16          scram-sha-256
EOF
fi

echo "[info] 重载 PostgreSQL ..."
sudo systemctl reload postgresql || sudo service postgresql reload

echo "[ok] 完成。请在 DBeaver 使用:"
echo "     主机 127.0.0.1 或 $(hostname -I | awk '{print $1}')"
echo "     端口 5432  用户 postgres  密码=本机 WSL 的 postgres 密码"
echo
echo "若仍报错，先设密码:"
echo "  sudo -u postgres psql -c \"ALTER USER postgres PASSWORD '你的密码';\""
