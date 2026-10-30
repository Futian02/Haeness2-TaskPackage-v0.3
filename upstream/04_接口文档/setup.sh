#!/usr/bin/env bash
# 本脚本将四个参考代码仓库浅克隆到运行时当前目录的 reference_code/ 下。
# 运行前请先安装 Git，并确保终端能执行 git；每个仓库使用 --depth 1 节省体积。
# 已存在的目标路径会跳过，单个仓库克隆失败后继续处理其余仓库。

target_root="./reference_code"
success=()
skipped=()
failed=()

if ! command -v git >/dev/null 2>&1; then
    printf '[错误] 未找到 Git，请先安装 Git 并将其加入 PATH。\n' >&2
    exit 1
fi

if ! mkdir -p "$target_root"; then
    printf '[错误] 无法创建目录：%s\n' "$target_root" >&2
    exit 1
fi

clone_repo() {
    local name="$1"
    local url="$2"
    local destination="$target_root/$name"

    if [[ -e "$destination" || -L "$destination" ]]; then
        printf '[跳过] %s：目标路径已存在（%s）。\n' "$name" "$destination"
        skipped+=("$name")
        return 0
    fi

    printf '\n[开始] %s\n' "$name"
    if git clone --depth 1 "$url" "$destination"; then
        success+=("$name")
        printf '[成功] %s\n' "$name"
    else
        failed+=("$name")
        printf '[失败] %s：继续处理下一个仓库。\n' "$name" >&2
    fi
}

clone_repo "Qwen-Agent" "https://github.com/QwenLM/Qwen-Agent"
clone_repo "gorilla" "https://github.com/ShishirPatil/gorilla"
clone_repo "LLaMA-Factory" "https://github.com/hiyouga/LLaMA-Factory"
clone_repo "ToolAlpaca" "https://github.com/tangqiaoyu/ToolAlpaca"

printf '\n========== 下载汇总 ==========\n'
printf '成功（%d）：\n' "${#success[@]}"
if (( ${#success[@]} == 0 )); then printf '  无\n'; fi
for name in "${success[@]}"; do printf '  %s\n' "$name"; done
printf '跳过（%d）：\n' "${#skipped[@]}"
if (( ${#skipped[@]} == 0 )); then printf '  无\n'; fi
for name in "${skipped[@]}"; do printf '  %s\n' "$name"; done
printf '失败（%d）：\n' "${#failed[@]}"
if (( ${#failed[@]} == 0 )); then printf '  无\n'; fi
for name in "${failed[@]}"; do printf '  %s\n' "$name"; done

printf '\n提示：数据集文件很大，需要按各仓库 README 单独下载。\n'

if (( ${#failed[@]} > 0 )); then
    exit 1
fi
exit 0
