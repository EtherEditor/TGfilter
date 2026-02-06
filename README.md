# TGfilter
filter for TG   【currently not with AI used. Looking forward to a breakthrough!】

这是一份为您定制的深度技术实验报告（Markdown 格式）。它不仅记录了对话，还从系统架构和 AI 研究的角度对本次“TG 消息过滤实验”进行了复盘，非常适合作为项目的 `EXPERIMENT_LOG.md` 或 `README` 补充文档。

---

# 实验报告：基于 AI 推理的 Telegram 消息过滤系统与 OOD 泛化实测

**项目名称**：Project TG-Filter-Watchdog

**实验日期**：2026-02-06

**研究视角**：硅谷 Tech Lead / AI PhD Candidate (Fall 26)

**文档状态**：Final Release

---

## 1. 实验背景与目标 (Abstract)

针对用户在 Telegram 中面临的“高价值信息获取”与“低价值噪音/剧透回避”的矛盾，本实验旨在构建一套自动化的拦截与转发系统。核心目标是解决在缺乏人工干预的情况下，系统如何对“零时差爆料图”（Zero-day Spoiling Images）进行精准识别与重定向。

## 2. 问题定义 (Problem Statement)

* **人工瓶颈**：用户依赖“手动点开”分辨图片内容，导致信息获取效率低下且无法彻底戒掉频道依赖。
* **模型边界**：现有的预训练模型（如 CLIP、WD14）在面对刚刚发布的、分布外（OOD）的数据时，由于知识截断（Knowledge Cutoff），会出现严重的分类偏离。
* **环境约束**：系统需部署在 GitHub Actions 等无界面计算节点，要求逻辑必须是 Headless 且轻量化的。

## 3. 实验记录：Failure Case 分析

### 3.1 测试样本描述(At the End are Samples)

* **样本 A**：绝区零 (ZZZ) 角色艾莲·乔 (Ellen Joe) 剧情插画。
* **样本 B & C**：绝区零角色艾莲、朱鸢的头像。
* **样本 D**：星穹铁道 (HSR) 2.1+ 版本新角色知更鸟 (Robin) 与米沙 (Misha) 的插画。

### 3.2 失败复盘

在实测中，通用大模型对上述四张图片的识别**全部错误**。

* **原因分析**：这些图片属于本周内新发布的爆料内容。在模型的权重空间里，它们被强行投影到了最接近的已知聚类上（如错误的归类游戏），这种“幻觉”证明了**静态权重在实时流数据处理中的无能**。

## 4. 核心技术论证 (Technical Discussion)

### 4.1 认知升级：从分类到推理

实验指出，不应将 AI 视为一个“百科全书”，而应将其视为一个“特征提取器”。

* **分类思维（失效）**：（分类标签）。当  是未见过的新品种，输出必然错误。
* **推理/对比思维（有效）**：利用 **Zero-shot Generalization**。计算图片向量  在语义空间中与目标概念（如 "Anime Leak"）的余弦相似度。

### 4.2 OOD (Out-of-Distribution) 挑战

这是本次实验的核心收获：**在科研中，当 SOTA 模型在大规模分布外数据上崩掉时，正是体现工程架构价值的时刻。** 解决之道在于建立“动态反馈闭环”。

## 5. 推荐解决方案架构 (Proposed Architecture)

| 模块 | 技术选型 | 逻辑描述 |
| --- | --- | --- |
| **感知层 (Perception)** | **DINOv2 / OpenCLIP** | 提取图片的深层语义向量，不强求命名，只求特征准确。 |
| **存储层 (Memory)** | **Vector Cache (Local)** | 存储由用户手动确认的 1-2 张“正样本”特征向量。 |
| **判定层 (Decision)** | **Cosine Similarity** | 当新图  与缓存  距离小于阈值  时，触发拦截。 |
| **兜底层 (Agentic)** | **Metadata + OCR** | 结合消息 Caption 的正则表达式匹配，作为视觉识别的冗余备份。 |

## 6. 实验结论 (Conclusion)

1. **拒绝平庸自动化**：简单的转发脚本无法解决语义级的剧透问题。
2. **拥抱不确定性**：AI 系统必须具备处理“我不知道”的能力。
3. **鲁棒性优先**：最好的过滤系统应该是 **HITL (Human-in-the-loop)** 的，即用户标记一张，系统自动屏蔽一批。

---

## 7. Tech Lead 寄语 (Final Note)

本次实验的挫败是通往 PhD 的必经之路。在硅谷，我们不相信 100% 的准确率，我们相信**系统的鲁棒性（Robustness）**。请记住：**不要为了那 10% 的模型失效而回退到手动操作，去用工程架构去约束那 10% 的不确定性。**

---
## 实验样本归档 (Experimental Samples)

<table>
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/52cce3de-bb8a-48e1-8b52-a0b66e97771b" width="400px"/><br/>
      <b>Sample A: ZZZ Illustration</b>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/2c52a8a3-e7c1-45da-b831-5caa40d8198c" width="200px"/><br/>
      <b>Sample B: ZZZ Avatar (Ellen)</b>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/9ce21210-e907-4923-b867-de902f9f3627" width="200px"/><br/>
      <b>Sample C: ZZZ Avatar (Zhu Yuan)</b>
    </td>
    <td align="center">
      <img src="https://github.com/user-attachments/assets/7ca7d5f3-c9e4-41dd-8a5b-4ea819971355" width="400px"/><br/>
      <b>Sample D: HSR Leak (Robin & Misha)</b>
    </td>
  </tr>
</table>

##  Original Post
SampleA: https://t.me/Seele_Leaks/26025
"
（Spolier）
缺失的图片
"

SampleB/C: https://t.me/Seele_Leaks/26031
"
头像
"

SampleD: https://t.me/Seele_Leaks/26007
"
［ZZZ 2.6Pre］
（Spolier）
？？？与维琳娜，诺姆的对话
"


*Generated for the TG-Filter Project. Copyright 2026.*
