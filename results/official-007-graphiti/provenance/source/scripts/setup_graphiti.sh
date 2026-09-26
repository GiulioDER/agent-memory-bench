#!/usr/bin/env bash
set -euo pipefail

# Install the official Graphiti MCP checkout for a Linux AMB host.
# Usage: bash scripts/setup_graphiti.sh $HOME/graphiti

install_root=${1:?usage: setup_graphiti.sh INSTALL_ROOT}
upstream_url="https://github.com/getzep/graphiti.git"
pinned_ref="4bd728790e836950c3922e84f6f989f1380f54f2"
uv_bin=${UV_BIN:-}

if [[ -z "$uv_bin" ]]; then
  uv_bin=$(command -v uv || true)
fi
if [[ -z "$uv_bin" && -x "$HOME/.local/bin/uv" ]]; then
  uv_bin="$HOME/.local/bin/uv"
fi
if [[ -z "$uv_bin" ]]; then
  echo "uv is required; install it on the Linux host before running this script" >&2
  exit 2
fi

if [[ -e "$install_root" ]]; then
  if [[ ! -d "$install_root/.git" ]]; then
    echo "refusing existing non Git install root: $install_root" >&2
    exit 2
  fi
  actual_ref=$(git -C "$install_root" rev-parse HEAD)
  if [[ "$actual_ref" != "$pinned_ref" ]]; then
    echo "refusing checkout at $actual_ref, expected $pinned_ref" >&2
    exit 2
  fi
else
  git clone "$upstream_url" "$install_root"
  git -C "$install_root" fetch --depth 1 origin "$pinned_ref"
  git -C "$install_root" checkout --detach "$pinned_ref"
fi

if [[ ! -f "$install_root/mcp_server/main.py" ]]; then
  echo "pinned checkout has no official mcp_server/main.py: $install_root" >&2
  exit 2
fi

"$uv_bin" sync --directory "$install_root/mcp_server" --locked --no-dev
printf 'GRAPHITI_MCP_DIR=%s\n' "$install_root/mcp_server"
printf 'GRAPHITI_UPSTREAM_REF=%s\n' "$pinned_ref"
