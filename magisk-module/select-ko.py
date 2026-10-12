#!/usr/bin/env python3
"""
按 whitelist 挑选 .ko 并组装 Magisk/KernelSU 模块包。

用法:
    select-ko.py <out 目录> <ko.list> <输出 zip> [仓库根目录]

设计目标：评估期能只选一个模块、且不重编内核就能改包裹什么。
    select-ko.py kernel_workspace/common/out ko.list kernel_modules.zip .

行为:
  1. 从 out 目录递归找所有 *.ko（只按 basename 匹配，路径不限）；
  2. 按 ko.list 的白名单过滤，输出「选中 / 未选中的同类候选」对照表；
  3. 把 module.prop / service.sh / action.sh / META-INF 与选中的 ko 组装成 zip。

退出码: 0 成功；2 白名单里的模块一个都没编出来（说明 config 没生效）。
"""

import os
import shutil
import subprocess
import sys
import tempfile


def read_list(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line)
    return out


def find_kos(root):
    """递归收集 *.ko，返回 {模块名: 绝对路径}；同名冲突时保留第一个。"""
    found = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".ko"):
                found.setdefault(fn[:-3], os.path.join(dirpath, fn))
    return found


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1

    out_dir, list_path, zip_path = sys.argv[1], sys.argv[2], sys.argv[3]
    repo_root = sys.argv[4] if len(sys.argv) > 4 else "."

    if not os.path.isdir(out_dir):
        print("错误: 找不到 out 目录: %s" % out_dir, file=sys.stderr)
        return 1
    if not os.path.isfile(list_path):
        print("错误: 找不到白名单: %s" % list_path, file=sys.stderr)
        return 1

    wanted = read_list(list_path)
    available = find_kos(out_dir)

    print(">>> out 目录共找到 %d 个 .ko" % len(available))
    print(">>> 白名单 %d 项" % len(wanted))

    chosen, missing = [], []
    for name in wanted:
        if name in available:
            chosen.append((name, available[name]))
        else:
            missing.append(name)

    if chosen:
        print(">>> 选中:")
        for name, path in sorted(chosen):
            print("      %-20s %s" % (name, os.path.relpath(path, out_dir)))
    if missing:
        print(">>> 白名单里但未编出（检查 config/modules.config 是否有对应 =m）:")
        for name in missing:
            print("      %s" % name)

    # 顺手提示：有 .ko 但没进白名单的，避免"编了却没打进去"的困惑
    unchosen = sorted(set(available) - {n for n, _ in chosen})
    if unchosen:
        print(">>> 已编出但未选入（共 %d 个，前 10 个）:" % len(unchosen))
        for name in unchosen[:10]:
            print("      %s" % name)

    if not chosen:
        print("错误: 白名单里的模块一个都没编出来，包不做。"
              "请确认 config/modules.config 里有对应的 =m，且 CI 跑了 `make modules`。",
              file=sys.stderr)
        return 2

    stage = tempfile.mkdtemp(prefix="kmod_stage_")
    try:
        ko_stage = os.path.join(stage, "ko")
        os.makedirs(ko_stage, exist_ok=True)
        for _name, path in chosen:
            shutil.copy2(path, os.path.join(ko_stage, os.path.basename(path)))

        # 模块元数据：优先用 repo_root/magisk-module（本地），否则用脚本自身所在目录（CI）。
        # CI 里 repo_root 传的是 AnyKernel3 目录，那里没有 magisk-module/，所以必须有回退，
        # 否则 module.prop / service.sh / META-INF 会静默缺失，产出不是合法模块包。
        script_dir = os.path.dirname(os.path.abspath(__file__))
        meta_src = None
        for cand in (os.path.join(repo_root, "magisk-module"), script_dir):
            if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "module.prop")):
                meta_src = cand
                break
        if meta_src is None:
            print("错误: 找不到 magisk-module 骨架目录（module.prop 不存在），无法组装模块包。",
                  file=sys.stderr)
            return 2
        print(">>> 模块骨架来自: %s" % meta_src)

        for rel in ("module.prop", "service.sh", "action.sh"):
            src = os.path.join(meta_src, rel)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(stage, rel))
        for rel in ("service.sh", "action.sh"):
            p = os.path.join(stage, rel)
            if os.path.isfile(p):
                os.chmod(p, 0o755)
        meta = os.path.join(meta_src, "META-INF")
        if os.path.isdir(meta):
            shutil.copytree(meta, os.path.join(stage, "META-INF"))

        if os.path.exists(zip_path):
            os.remove(zip_path)
        subprocess.check_call(["zip", "-qr", os.path.abspath(zip_path), "."], cwd=stage)

        print(">>> 已生成: %s（%d 个模块）" % (zip_path, len(chosen)))
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
