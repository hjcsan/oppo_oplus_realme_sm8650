#!/usr/bin/env python3
"""
在 AnyKernel3 的 anykernel.sh 里插入 kernel_modules.zip 的自动安装块。

原项目已有的逻辑是：刷机时若目录里存在 zram.zip，就用
    /data/adb/ksud module install <zip>
把它作为 KernelSU/Magisk 模块装进去。本脚本在同样的位置插入一段
针对 kernel_modules.zip 的等价逻辑，从而实现“刷内核时顺便装内核模块包”。

自动安装按 root 环境选择路径：
    KernelSU 系 → /data/adb/ksud module install
    Magisk 系   → magisk --install-module
    都没有      → 打印提示，让用户手动在 root 管理器里装
（Magisk 与 KernelSU 的模块格式相同，module.prop + service.sh 通用，
 所以 zip 本身在两种环境下都能装，只是安装命令不同。）

用法:
    python3 patch-anykernel.py [anykernel.sh 路径]

特性:
    - 幂等：已包含 kernel_modules.zip 逻辑时直接跳过
    - 安全：找不到唯一锚点时只告警、不修改，绝不破坏刷机脚本
"""
import pathlib
import sys

ANCHOR = 'if [ -f "$AKHOME/zram.zip" ]; then'

BLOCK = '''if [ -f "$AKHOME/kernel_modules.zip" ]; then
    MODULE_PATH="$AKHOME/kernel_modules.zip"
    # KernelSU 系：/data/adb/ksud
    # Magisk 系：magisk --install-module（Magisk 里没有 ksud）
    # 两者模块格式相同，module.prop + service.sh + ko/ 通用
    if [ -f /data/adb/ksud ]; then
        ui_print "Installing kernel modules (KernelSU)..."
        /data/adb/ksud module install "$MODULE_PATH"
    elif command -v magisk >/dev/null 2>&1; then
        ui_print "Installing kernel modules (Magisk)..."
        magisk --install-module "$MODULE_PATH"
    else
        ui_print "!! No KernelSU/Magisk CLI found"
        ui_print "!! Extract kernel_modules.zip from this zip and install it manually"
        ui_print "!! in your root manager (Modules -> Install from storage)"
    fi
else
    ui_print "kernel_modules.zip Not Found, skipping kernel modules installation..."
fi
'''


def main() -> int:
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "anykernel.sh")
    if not path.is_file():
        print(f"[跳过] 找不到文件: {path}")
        return 0

    text = path.read_text()
    if "kernel_modules.zip" in text:
        print("[跳过] 已包含 kernel_modules.zip 安装逻辑")
        return 0

    count = text.count(ANCHOR)
    if count != 1:
        print(f"[告警] 锚点出现 {count} 次（期望 1 次），未修改 {path}")
        return 0

    path.write_text(text.replace(ANCHOR, BLOCK + ANCHOR, 1))
    print(f"[完成] 已向 {path} 插入 kernel_modules.zip 安装块")
    return 0


if __name__ == "__main__":
    sys.exit(main())
