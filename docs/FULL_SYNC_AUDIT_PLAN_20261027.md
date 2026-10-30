# 完整Git仓库同步 / 原始文档审计实施单

## 当前核实
2026-10-27 本地 `upstream` 是Git工作树`master`，HEAD=d7877bf387482b2fa9b148d30860da59ccad48b3，工作树干净，但Git处于cone sparse-checkout，只检出上游根目录、`04_接口文档/harness_skeleton`/`schema`以及`05_提交区`。只读 `scripts/check_sources.py` 统计关键19份中9 PRESENT /10 MISSING（PDF、XLSX、03例子），所以**目前不得声称全量仓库同步完成**。

## 两种范围与用户本轮选择
原先推荐仅取官方业务PDF与三目录；现在用户明确要求“所有仓库文件都同步下来”，最终执行策略应改为真正全仓：
```powershell
cd "D:\作业\竞赛\计算机设计智能体\机械智能体"
git -C upstream status --short --branch
git -C upstream rev-parse HEAD
git -C upstream sparse-checkout disable
git -C upstream ls-files | Measure-Object -Line
git -C upstream status --short --branch
python -B -m scripts.check_sources
```
这会让`upstream/`工作树检出Git版本的**所有被追踪文件**，包含PDF、源表、范例、reference_code 和原来的中间缓存；需要预留足够下载空间，避免中途断开造成半检出。原仓库历史树约2,960文件，约655MB树项容量（之前GitHub接口查询的历史估计；此次仍需精确清点）。`git sparse-checkout disable` 不会主动下载所有Git历史版本；仓库最初为 `--depth 1` 浅克隆，若“所有历史提交也要同步”则需另行 `git fetch --unshallow`，当前任务只要求**HEAD全文件**。
不要全量复制到外层产品目录；`upstream`本身就是完整工作区。

## 推荐完整性检验（全部只读）
1. `git -C upstream sparse-checkout list`：禁用后可能提示非sparse，视为正常。
2. `git -C upstream ls-files` 数量与 `git -C upstream ls-tree -r --name-only HEAD`一致，人工排除gitlinks/submodules。
3. `git -C upstream status --porcelain=v1`：无用户意外修改；`git -C upstream fsck --no-reflogs` 可能因浅克隆有边界提示，需区分损坏与shallow。
4. `python -B -m scripts.check_sources`：19/19；
5. PDF关键版本与大小、两份源XLSX存在，抽样阅读非损坏；如工具支持，检查pdfinfo页数与checksum；
6. 对 `04_接口文档/reference_code` 中四大参考仓库目录做单独版本与来源清单，严禁以后运行 `setup.sh` 再往里面重复clone。
7. 对可公开的标准PDF遵照授权；不必把PDF再传远程服务。

## 文件分类
冻结教师合同：`upstream/README.md`、`04_接口文档/工具接口规范.md`、`技术指标验证方法.md`、`任务包问题答复.docx`。
不可随意改动原始：`01_RBI标准/**`、`02_损伤机理参考/**`、`03_案例样例/**`。
生成与交付：`04_接口文档/convert.py,validate.py,schema/**`、`05_提交区/**`。
第三方参考：`04_接口文档/reference_code/**`，只借鉴，不再复制到自建产品层。
历史产物/缓存：原上游根目录的 `_*.json`, `_*.txt`, `**/*.bak*`, `**/runs/*`；不删除，依据文件分类表归档索引即可。
自己建设：`app/,knowledge/,evals/,tests/,scripts/,docs/` 与原上游分开。

## 本轮执行可达性
目前已授权的DevSpace shell接口仅用于测试/检查，不允许执行修改Git文件的命令；`dorqinspace__codex_bind_workspace` 两个候选路径均返回内部工具错误，无法据此启动本地Luna任务。因此：已落实文件分类/计划；**全量Git检出本轮未完成**。由本地Codex或用户PowerShell执行上述命令后，再进行PDF/XLSX审计；不得凭计划改写`PROJECT_STATE`为FULL_SYNC_DONE。
