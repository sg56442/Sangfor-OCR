# Sangfor-OCR

**Sangfor-OCR** 是由 MinerU2.5-Pro-2605-1.2B 训练得到的 1.2B 文档解析视觉语言模型，以模型身份参评 OmniDocBench v1.6。
推理全程只使用 Sangfor-OCR 本身，不调用其他 OCR、版面或语言模型。

本仓库只提供推理接口：输入 OmniDocBench v1.6 的 1651 张页面图像，每页输出一个与图像同名的 Markdown 文件；
评分使用官方仓库 `opendatalab/OmniDocBench`（提交 `f133a71`）。

## 结果

OmniDocBench v1.6_full，1651 页，官方评测代码（`configs/end2end.yaml`，`quick_match`，`python pdf_validation.py`）。
Overall = [(1 − 文本编辑距离) × 100 + 公式 CDM + 表格 TEDS] / 3。

| 模型 | 参数量 | Overall ↑ | 文本 Edit ↓ | 公式 CDM ↑ | 表格 TEDS ↑ | 表格 TEDS-S ↑ | 阅读顺序 Edit ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Sangfor-OCR** | 1.2B | **97.197** | **0.0290** | **98.622** | **95.870** | **97.805** | **0.1176** |

**评测说明。** 有 2 页（`docstructbench_enbook-zlib-o.O-17208435.pdf_57`、`_105`）公式非常密集，官方 quick_match
匹配耗时很长，超过了默认配置的匹配时限（`quick_match_truncated_timeout_sec` 300 秒、`match_timeout_sec` 420 秒）。
超时后，官方回退逻辑会把这两页的文本编辑距离记为 1.0。

- 上表把这两个时限放宽后评测，评测代码与其余配置不变。在我们评测机上的全集评测中，这两页分别用时 1731 秒和 1437 秒，
  其余页面最长 407 秒。推荐把两个时限设为 **2400 秒**（约为最长实测值的 1.4 倍），在我们的评测机上，时限只要不低于 1732 秒，结果都相同。
- 在默认时限下，同一份预测的 Overall 为 **97.155**：差异全部来自这 2 页，公式与表格指标完全相同。
- 两种配置的官方评测原始输出都在 `results/`。

**保持默认时限的评测环境。** 这两页的耗时主要在单线程上（每次 LaTeX 转文本都会新建一个子进程），而且受并发影响很大：
单独评测时约 550–600 秒，在全集评测中与其他匹配进程争用 CPU，增加到约 1440–1730 秒。要在 300 秒内完成，需要同时满足：

- 单核性能达到我们评测机（2 × Intel Xeon Platinum 8460Y+，睿频 3.7 GHz）的 2 倍以上：选最高频的桌面或工作站 CPU，
  如 AMD Ryzen Threadripper 9970X / 9980X（32 / 64 核，睿频 5.4 GHz），或 AMD Ryzen 9 9950X、Intel Core Ultra 9 285K，配 DDR5 内存；
- 评测时 CPU 不被争用：在空闲机器上运行，评测容器使用全部核心（`EVAL_CPUS` 设为核心数），空闲物理核数明显多于 `match_workers`（默认 13）；
  核数较少的桌面 CPU 需把 `match_workers` 降到 4–8。

以上是估算，没有实测，余量也很小。服务器级 CPU 通常达不到，因此我们推荐放宽时限的评测方式。

## 方法概述

### 训练：RSI 自迭代

Sangfor-OCR 以 MinerU2.5-Pro-2605-1.2B 为起点，在 RSI（递归自我改进）框架下迭代训练了十个阶段。
每一轮由自主研究代理执行一次闭环：

> 缺陷分析 → 数据与样本构造 → 训练 → 全集评估 → 决策（采纳或回退）

在这个闭环中，每一轮都根据当前定位到的缺陷，组合以下三类要素：

- **数据：开放数据源 + 内部数据源自蒸馏。** 开放数据包括 PubTabNet、SynthTabNet 等；内部文档在非评测页面上
  用当前模型做多轮自蒸馏和拒绝采样，按可验证指标挑选优于贪心输出的样本作为监督。
- **针对能力缺陷的样本生成。** 按失分机制定位薄弱环节，针对性地生成训练样本，例如公式与图文版面难例、
  复杂表格，以及按版式骨架生成全新内容的兄弟页面。
- **多种训练算法。** 按本轮缺陷选择或组合可验证奖励的强化学习（RLVR / GRPO）、RFT 选优偏好对 DPO、
  自蒸馏 SFT、视觉侧低秩 SFT、局部约束优化，以及带元素级信用分配的表格强化学习（P2TPO）。

为保持已有能力，每一轮都用父模型输出做 KL 约束；后期阶段只训练 rank-16 低秩因子。
训练数据不含 OmniDocBench 评测页的图像与标注。

### 推理

推理时权重冻结，全程只使用 Sangfor-OCR：先按 MinerU 原生两阶段流程（版面检测 → 区块识别）贪心解码，
再进行确定性后处理，并对少量高风险区域用同一模型选择性补读。补读结果须通过一致性校验才会采用，
额外请求约为原生请求的 2.8%，并设有总量上限。

## 快速开始

环境要求：
- Linux x86_64，Docker Engine ≥ 25；
- 1 张 GPU（实测 80 GB H100）；
- 16 核以上 CPU、64 GB 以上内存；
- 宿主机 Python ≥ 3.8。

```bash
# 0. 权重：从 ModelScope 下载，权重位于 weights/ 子目录
pip install modelscope
modelscope download --model zzxxhh0908/Sangfor-OCR --local_dir ./Sangfor-OCR-model
sha256sum ./Sangfor-OCR-model/weights/model.safetensors   # 应为 01dcb5addfa1d6133fd0930e79fa2484817cb0228af21cb4917fa73d04fa3147

# 1. 镜像：推理服务 + 处理引擎
docker pull vllm/vllm-openai:v0.8.5
docker build -f docker/Dockerfile.engine -t sangfor-ocr-engine:1.0 docker/

# 2. 推理：1651 页，单卡 H100 约 80 分钟
python3 infer.py --images /path/OmniDocBench/images --model ./Sangfor-OCR-model/weights --out ./predictions --gpu 0 --verify-images

# 3. 官方评测
git clone https://github.com/opendatalab/OmniDocBench && git -C OmniDocBench checkout f133a71e9e91c3621c7ce8994200a7b394a06eb3
docker pull ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204
QUICK_MATCH_TRUNCATED_TIMEOUT_SEC=2400 MATCH_TIMEOUT_SEC=2400 \
  bash eval/run_official_eval.sh /path/OmniDocBench/OmniDocBench.json ./predictions/markdown ./eval_out ./OmniDocBench
#   去掉两个环境变量即为官方默认时限
```

`predictions/markdown/` 即为 1651 份预测。

关于运行环境：
- `--model` 指向 `weights/` 目录，请勿在其中增删文件：引擎会校验权重哈希与目录内的配置文件。
- 引擎容器需要 `CAP_SYS_ADMIN` 和 Docker socket，`infer.py` 会自动添加。
- 无法使用 NVIDIA Container Toolkit 的主机，可加 `--gpu-access device`，把 GPU 设备直接透传给服务容器。

## 可复现性

- **环境锁定**：推理服务（vLLM 0.8.5）与处理引擎（Ubuntu 24.04、Python 3.12、TeX Live 2023 及逐个锁定的依赖）都按版本固定；
  引擎运行时会校验全部代码与依赖的哈希。
- **处理确定**：给定相同的原生输出与模型响应，处理阶段的输出逐字节一致。
- **推理波动**：vLLM 批处理与 MinerU 表格内嵌图片的随机占位令牌会带来少量推理波动。两次独立完整运行的 Overall 相差 0.001
  （默认时限下分别为 97.155、97.154）。
- **复现材料**：`results/` 包含本次提交的预测、官方评测输出、推理记录与验证记录。

## 说明

- **只支持整批运行。** 推理流程按 OmniDocBench v1.6 全集 1651 页整批运行：冻结方案会校验输入批次是否完整，
  补读预算也按整批设定总量上限。这些都是批次级的检查，不针对任何具体页面。
- **规则的研发方式。** 推理阶段的后处理与补读规则，是基于 bad case 分析提出的通用性处理规则，
  只依据页面图像与模型输出做判断，不针对任何具体页面。
- **合规性。** 推理阶段不读取标注，也不按页面身份处理：
  - 引擎镜像不含任何标注。原方案引用的 3 个标注路径在镜像内都是空占位文件，仅用于断言其为空或将其屏蔽。
  - `engine/` 的代码与数据中没有页面名称、基准图像哈希或来源标签。唯一含页面名称的是输入清单，只用于枚举待处理的图像。
  - 规则的判断依据是页面图像与模型输出，不使用页面名称、来源或标注。
  - `engine/` 中保留了几份研究期的评分脚本，例如 `code/runtime/score_frozen.py`。冻结方案会逐个校验依赖文件的哈希，
    所以它们必须原样存在，但推理流程从不执行它们；评分只由官方仓库完成（`eval/`）。
  - 冻结清单与控制文件中的研究期记录（例如阶段目标分数）只用于运行时校验，不影响推理输出。
  - 以上各项可用 `python3 tools/audit_compliance.py . <运行目录>/engine` 复查，本次提交的检查结果见
    `results/compliance_audit.json`。
- **命名。** `engine/` 内的容器路径与文件名沿用研发代号 P2T10。

## 许可证

代码与模型权重均以 Apache-2.0 许可证发布，见 `LICENSE`。
Sangfor-OCR 由 MinerU2.5-Pro-2605-1.2B（OpenDataLab，Apache-2.0）训练得到，署名见 `NOTICE`。

- 模型权重：https://www.modelscope.cn/models/zzxxhh0908/Sangfor-OCR
- 代码仓库：https://github.com/sg56442/Sangfor-OCR

## 目录

```
infer.py                   推理入口
engine/                    推理流水线
docker/                    处理引擎镜像定义
eval/run_official_eval.sh  官方评测脚本
configs/                   镜像版本、OmniDocBench v1.6 图像哈希
results/                   提交预测、官方评测输出、推理与验证记录
tools/audit_compliance.py  合规检查（推理不需要）
LICENSE, NOTICE            许可证与署名
```
