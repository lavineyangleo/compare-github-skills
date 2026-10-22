# GitHub 多技能对比

输入两个或更多 GitHub 地址，让 Agent 自动下载技能仓库，阅读实际文件并比较共同点与差异。

**默认只做对比**：不扩展候选、不排名推荐、不提供融合或改写方案。

## 使用

将本仓库中的 `SKILL.md`、`agents/`、`references/`、`scripts/` 放入 Agent 的技能目录，文件夹命名为 `compare-github-skills-v2`。例如 Codex 的用户技能目录 `~/.codex/skills/compare-github-skills-v2/`。

安装后向 Agent 发送：

```text
使用 $compare-github-skills-v2 比较以下仓库：
https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill
https://github.com/Kiterlin/anti-defensive-writing
```

可以继续增加 GitHub 地址。支持仓库根地址、技能目录的 `tree` 链接和 `SKILL.md` 的 `blob` 链接。

## 比较内容

| 维度 | 内容 |
|---|---|
| 定位与触发 | 解决什么问题、哪些请求会触发 |
| 输入与输出 | 需要的材料、交付物及格式 |
| 执行流程 | 处理步骤、分支、重试与结束条件 |
| 约束 | 事实保留、修改范围与必要限定 |
| 工具依赖 | 配套脚本、运行环境和外部服务 |
| 一致性 | 主规则、精简提示词和示例是否一致 |
| 验证证据 | 区分测试存在、CI 配置、实际通过和效果实测 |
| 分发方式 | 语言版本、相同入口镜像与插件结构 |

结果包括核心异同、共同点、差异矩阵和文件证据，附实际下载位置与来源清单。仓库包含多个技能时，先建立技能对应关系；未能获取的材料明确标记。

## 下载工具

下载器只依赖 **Python 3.10+ 标准库**，推荐 Python 3.12。它负责获取与记录材料；内容分析由 Agent 完成。

Windows：

```powershell
py -3.12 "scripts/fetch-技能仓库下载-v2.py" --urls "https://github.com/Adkid-Zephyr/anti-defensive-writing-Skill" "https://github.com/Kiterlin/anti-defensive-writing" --output "./github-skill-comparisons"
```

macOS / Linux 将 `py -3.12` 替换为 `python3`。

| 参数 | 说明 |
|---|---|
| `--urls` | 两个或更多 GitHub 地址 |
| `--output` | 下载运行目录的父目录 |
| `--ref 1=main` | 按输入序号指定分支、标签或提交；可重复使用 |
| `--no-proxy` | 仅对本次请求禁用环境代理 |
| `--max-download-mb` | 单仓库压缩包上限，默认 100 MiB |
| `--max-extract-mb` | 单仓库解压后上限，默认 400 MiB |

对于 `tree` / `blob` 链接，`--ref` 必须匹配链接中的引用前缀；要覆盖版本时使用仓库根地址。下载器使用 GitHub API 固定提交，并通过源码归档下载，不需要 Git。

GitHub API 请求可使用已有 `GITHUB_TOKEN` 环境变量；令牌不会写入来源清单。当前下载流程面向公开仓库。

每次运行创建独立目录：

```text
comparison-时间-唯一标识/
├── manifest.json
├── 01/
│   ├── archive.zip
│   └── source/
├── 02/
│   ├── archive.zip
│   └── source/
└── ...
```

清单记录输入 URL、提交 SHA、下载时间、选定路径、Skill 文件哈希及逐仓库状态。某一项失败不阻止其余仓库处理；所有项目就绪时退出码为 0，否则为 2。

下载器检查路径越界、符号链接和压缩包大小，不执行下载仓库中的代码。源码归档不会额外递归获取子模块或外部大文件；相关材料缺失时需要在比较中注明。

## 项目结构

```text
SKILL.md                         技能入口
agents/openai.yaml               界面元数据
references/                     比较维度和报告结构
scripts/fetch-技能仓库下载-v2.py  命令行入口
scripts/skill_compare/           GitHub 获取、解压和工作流模块
```

## 已完成验证

使用 A 家、K 家和 `openai/skills` 三个真实公开仓库验证了批量下载与入口识别；另外验证了固定提交、目录及文件链接、无效输入拒绝，以及一项失败后继续处理后续仓库。技能元数据、Python 语法和引用文件检查已通过。

这些检查验证下载与识别行为，不代表对任意技能生成效果完成了基准测试。项目不使用模拟结果填补缺失证据。
