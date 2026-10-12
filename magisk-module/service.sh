#!/system/bin/sh
# 开机加载本模块 ko/ 目录下的所有内核模块
# 模式与项目原有的 zram.zip 一致（由 KernelSU/Magisk 的 late_start service 触发）
# 日志写在 $MODDIR/load.log，可用模块的“操作”按钮查看（见 action.sh）

MODDIR=${0%/*}
KODIR="$MODDIR/ko"
LOG="$MODDIR/load.log"

: > "$LOG"
echo "=== $(date) 开始加载内核模块 ===" >> "$LOG"

if [ ! -d "$KODIR" ]; then
  echo "ko 目录不存在: $KODIR" >> "$LOG"
  exit 0
fi

# 等系统启动完成，避免与 vendor/system_dlkm 的模块加载竞争
try=0
while [ "$(getprop sys.boot_completed)" != "1" ] && [ $try -lt 120 ]; do
  sleep 2
  try=$((try + 1))
done
sleep 5

loaded=0
failed=0
# 模块之间有依赖（例如 nfs -> lockd -> sunrpc），insmod 在依赖未就绪时会失败。
# 这里做 3 轮扫描：每轮只尝试尚未加载的模块，让下一轮能补上依赖。
for round in 1 2 3; do
  for ko in "$KODIR"/*.ko; do
    [ -e "$ko" ] || continue
    name=$(basename "$ko" .ko)
    # /proc/modules 里的模块名使用下划线
    if grep -q "^${name//-/_} " /proc/modules; then
      continue
    fi
    if insmod "$ko" 2>>"$LOG"; then
      echo "第 $round 轮加载成功: $name" >> "$LOG"
      loaded=$((loaded + 1))
    fi
  done
done

# 收尾统计：仍未加载的记入失败
for ko in "$KODIR"/*.ko; do
  [ -e "$ko" ] || continue
  name=$(basename "$ko" .ko)
  if ! grep -q "^${name//-/_} " /proc/modules; then
    echo "最终未加载: $name" >> "$LOG"
    failed=$((failed + 1))
  fi
done

echo "=== 完成：成功 $loaded 个，失败 $failed 个 ===" >> "$LOG"

# USB 网络相关模块状态：RNDIS 主机端能不能起来，直接决定手机 USB 共享能不能用
for m in usbnet cdc_ether rndis_host cdc_mbim; do
  if [ -e "$KODIR/$m.ko" ]; then
    if grep -q "^${m} " /proc/modules; then
      echo "USB共享: $m 已加载" >> "$LOG"
    else
      echo "USB共享: $m 未加载（看上面的 insmod 报错）" >> "$LOG"
    fi
  fi
done
