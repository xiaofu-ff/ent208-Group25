#!/usr/bin/env bash
# 在腾讯云 SSH 里执行：bash scripts/update_tencent_server.sh
# 默认仓库 ~/ent208-Group25；若不同：REPO=/path/to/repo bash scripts/update_tencent_server.sh
set -euo pipefail
REPO="${REPO:-$HOME/ent208-Group25}"
cd "$REPO"
git pull
cd "$REPO/backend"
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
sudo systemctl restart refapi
sudo systemctl --no-pager -l status refapi
