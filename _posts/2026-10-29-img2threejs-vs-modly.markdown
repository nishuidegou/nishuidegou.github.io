---
layout: post
title:  "两种把图片变成 3D 的路线：img2threejs 与 Modly"
date:   2026-10-29 10:00:00 +0800
categories: 3d
---

把一张照片变成一个能在网页里转动的 3D 模型，是这两年很火的方向。最近试了两个开源项目，恰好代表了两条完全不同的技术路线：

- **img2threejs**：不生成网格文件，而是让 AI 把参考图"重新写"成一段可运行的 Three.js 代码。
- **Modly**：一个本地桌面应用，用开源扩散模型直接在你的 GPU 上重建带贴图的 3D 网格。

一个产出 **代码**，一个产出 **模型文件**。用下来各有各的舒服，这篇把两者放在一起聊聊。

## 一、img2threejs：代码即模型

[img2threejs](https://github.com/img2threejs/img2threejs) 的定位很特别——它不做摄影测量，也不下载现成模型，而是把参考图重建成一个**纯代码的程序化 Three.js 模型**。

它需要跑在一个 AI Agent 里（Claude Code、Codex、OpenCode、Hermes 都行），本质上是一个 skill。你给它一张图，它按阶段把对象"雕"出来：

```text
blockout → structural → form → material → surface → lighting → interaction → optimization
```

每一轮只生成当前解锁的这一小步，然后渲染出来、和原图并排对比、打分，过不了关就继续改。真正耗 token 的只有"看图和判断"，校验、门禁、规格生成这些都交给了不依赖第三方库的 Python 脚本（只要 3.10+ 标准库，连 numpy 都不用）。

最终得到两样东西：

- 一份 `ObjectSculptSpec` JSON，记录完整的组件树、材质、socket 和每一轮的评审历史；
- 一个 TypeScript 工厂函数，返回 `THREE.Group`，自带 pivot、socket、collider，可以直接做动画。

### 上手

```bash
npx --yes img2threejs@latest install   # 把 skill 装进检测到的每个 agent
npx --yes img2threejs@latest doctor    # 每个 agent 一行，managed 表示装好了
```

重启 agent 后，在会话里直接说：

```text
/img2threejs 把 ./reference.png 里的物体重建成程序化 Three.js 模型，
保持比例、轮廓和颜色，严格走质量门禁，报告输出文件和渲染对比证据。
```

### 适合谁

- 你需要的是**能进网页、能改、能动画**的资产，而不是一个几十 MB 的 mesh；
- 你希望产物是 diff 友好的 TS + JSON，可以进版本库、可以让团队 code review；
- 你已经在用 AI Agent 工作流，愿意接受"多轮渲染对比"这种慢一点的打磨过程。

官方 demo  gallery（[img2threejs.io](https://img2threejs.io/)）里每个模型都是现场跑的生成代码，没有网格文件下载——这点挺震撼的。

## 二、Modly：本地 GPU 上的开源 3D 生成器

[Modly](https://github.com/lightningpixel/modly) 走的是更"传统"的 AI 生成路线：一个 Electron 桌面应用，底层是 Python 后端 + 开源扩散模型，**全程在你的 GPU 上跑，图片不出本地**。

支持 Windows、Linux 和 Apple Silicon macOS，AMD 显卡在 Linux/Windows 上通过 ROCm 自动适配，不需要自己装 ROCm。核心卖点是"免费、无限次、无需账号、不联网上传"。

它的架构很模块化：每个模型都是一个 GitHub 扩展仓库，里面一个 `manifest.json` 加运行文件。在 **Models** 页面点 **Install from GitHub**，粘仓库地址就能装。官方扩展已经覆盖了几个主流开源模型：

| 扩展 | 模型 |
| --- | --- |
| modly-hunyuan3d-mini-extension | Hunyuan3D 2 Mini |
| modly-hunyuan3d-mini-turbo-extension | Hunyuan3D 2 Mini Turbo |
| modly-hunyuan3d-mini-fast-extension | Hunyuan3D 2 Mini Fast |
| modly-triposg-extension | TripoSG |
| modly-trellis2-gguf-extension | Trellis2 GGUF |

### 上手

直接去 Releases 下安装包，或者克隆下来跑：

```bash
npm install
cd api
python -m venv .venv
source .venv/bin/activate    # Windows 用 .venv\Scripts\activate
pip install -r requirements.txt
cd ..
npm run dev
```

打开后按 **Image → Generate Mesh → Add to Scene** 连一条最小工作流，在 Models 页把权重下好，去 Generate 页选工作流、点生成。生成的网格可以直接在视口里拖动缩放，也能平滑、减面后再写回工作区。

它还带一个只用标准库的 CLI，方便脚本和 Agent 调用：

```bash
python tools/modly-cli/agent.py health
python tools/modly-cli/agent.py model list
python tools/modly-cli/agent.py generate --image ./input.png --output ./export.glb
```

### 适合谁

- 你要的是**标准 3D 资产**（GLB 等），准备导入 Blender、Unity、游戏引擎或做 3D 打印；
- 你手里有还不错的显卡，想无限次免费试，且在意隐私；
- 你只想点几下鼠标，不想配 Agent、不想写代码。

## 三、放在一起对比

| 维度 | img2threejs | Modly |
| --- | --- | --- |
| 产物 | TypeScript 工厂 + JSON 规格 | 带贴图网格（GLB 等） |
| 运行方式 | 跑在 AI Agent 里的 skill | 本地桌面应用（GPU） |
| 是否用生成模型 | 不生成网格，靠 Agent 视觉判断 | 是，扩散模型重建 mesh |
| 是否联网 | 依赖 Agent 的模型 API | 完全本地，图片不上传 |
| 可编辑性 | 极高，代码可读可 diff | 常规网格，可进 DCC 工具改 |
| 上手成本 | 需要 Agent + Node + Python | 装包即用 |
| 典型用途 | 网页 3D、交互动画、程序化场景 | 游戏资产、建模素材、3D 打印 |

一句话：**img2threejs 给的是"活的代码"，Modly 给的是"实体的模型"**。

## 四、怎么选

- 目标是网页里的可交互动画、需要团队协作改代码 → 选 **img2threejs**。
- 目标是拿到一个能进 Blender / 引擎 / 打印机的模型，且想本地免费跑 → 选 **Modly**。
- 两个都装也不冲突：先用 Modly 快速出一个网格看形体，再用 img2threejs 把关键对象重建成轻量的程序化版本嵌进网页，反而是很顺的组合。

两个项目都是开源的（img2threejs 是 Apache-2.0，Modly 是 MIT），Star 也都不少，值得放进工具箱。

- img2threejs 仓库：<https://github.com/img2threejs/img2threejs>
- img2threejs 在线 gallery：<https://img2threejs.io/>
- Modly 仓库：<https://github.com/lightningpixel/modly>
- Modly 官网：<https://modly3d.app/>
