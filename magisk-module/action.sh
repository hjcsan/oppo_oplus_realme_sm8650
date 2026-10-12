#!/system/bin/sh
# 模块“操作”按钮：显示上次开机加载结果
MODDIR=${0%/*}
if [ -f "$MODDIR/load.log" ]; then
  cat "$MODDIR/load.log"
else
  echo "暂无日志（模块可能尚未在重启后生效）"
fi
echo
echo "--- 当前已加载的相关模块 ---"
for m in squashfs isofs udf cifs nfs nf_tables macvlan vxlan zram; do
  if grep -q "^${m} " /proc/modules; then
    echo "已加载: $m"
  fi
done
