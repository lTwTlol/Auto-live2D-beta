# Auto虚拟形象  Q群 1109589009

<div align="center">
  <a href="README.md">简体中文</a> | 
  <a href="README.ja.md">日本語</a> | 
  <a href="README.en.md">English</a>
</div>

> 本项目基于开源项目 [852wa/Anime2.5DRig](https://github.com/852wa/Anime2.5DRig) 二次开发。
> 仓库地址：https://github.com/lTwTlol/Auto-live2D-beta

一个 2.5D 头像工具：把分层 PSD 拖进浏览器，即可自动绑定并动起来。
以往需要手工完成的设置（网格切分、变形、物理）全部自动化。无需安装，全部在客户端本地处理。

## 使用方法

1. 直接用浏览器打开 `index.html`。
2. 拖入分层 PSD（或点击「加载 sample.psd」）。
3. 自动绑定随即运行，并立刻带待机动作、眨眼、口型、头发物理动起来。

> 摄像头追踪（MediaPipe FaceMesh）和麦克风口型仅支持 https 或 localhost（浏览器权限规范）。直接以 file:// 打开也可拖放播放。

## Python 版（桌面应用）

除浏览器版外，还附带 Python 桌面版。UI 与布局和浏览器版完全一致。

### 使用方法

- 双击根目录下的 `run.bat` 即可启动。脚本会在首次运行时创建项目专用的 `.venv`，并将依赖安装到其中；系统 Python 仅用于创建虚拟环境（需 Python 3.10+）。
- 要求：Microsoft Edge WebView2（Windows 11 已预装）。
- 启动后弹出桌面窗口，可与浏览器版一样拖入 PSD。

### OpenSeeFace 追踪

桌面版在摄像头追踪之外，还支持 OpenSeeFace 追踪（含头部、眨眼、口型与虹膜/眼球视线）。进入 `opennseeface/Binary` 目录，双击运行 `run.bat`：程序会列出摄像头，按提示选择自己的摄像头编号及各项参数（模式、帧率）后即开始追踪。随后回到本应用，在「自动」区块启用 **OpenSeeFace** 开关，即会读取 `127.0.0.1:11573` 的 UDP 数据流并驱动头像。

### 语言切换（三语）

右上角语言下拉框（日本語 / English / 简体中文）即时切换。选择保存在本地，下次启动仍保持。

## 自动完成的内容

- 直接接受 [see-through](https://github.com/shitagaki-lab/see-through) 输出的 PSD（`mouth`→`mouth_open` 自动重命名）
- **缺少闭眼/闭口差分时自动生成通用差分**（按锚点缩放摆放，颜色自动匹配睫毛/口部；专用滑块可微调位置与角度）
  - 差分原图优先使用仓库根目录的 `eye_close.psd`（左右眼合一张、中间留空）/ `mouth_close.psd`；否则使用内置数据
- 低透明度噪点去除（连通域滤波）
- 眼睛、眉毛、睫毛、闭眼的**左右自动分离**（按连通域重心判定）
- 眼睑位置、虹膜中心、口、颈部支点等**锚点自动检测**
- **发丝自动检测**（发梢轮廓的峰值检测，每层最多 6 束）
- 按图层深度分配实现**伪 3D 转头**（视差 + 剪切）
- 每束发丝的双弹簧物理（**根部硬、发梢柔**）、胸部晃动、呼吸
- 闭眼/闭口差分的**交叉淡入淡出**、瞳孔模板裁剪（限制在白眼球内）

## 图层命名规范

图层名（日文「のコピー」及全角字符会自动规范化）：

| 图层名 | 内容 | 必填 | 备注 |
|---|---|---|---|
| `face` | 脸部基底 | ◎ | 锚点基准，必须存在 |
| `eyewhite` | 白眼球（左右） | ○ | 自动左右分离 |
| `irides` | 虹膜（左右） | ○ | 视线移动、瞳孔缩放对象 |
| `eyelash` | 睫毛（睁眼） | ○ | |
| `eye_close` | 闭眼 | ○ | 眨眼时交叉淡入 |
| `eyebrow` | 眉毛（左右） | ○ | 角度、上下操作对象 |
| `mouth_open` | 开口 | ○ | 随开度下移下巴 |
| `mouth_close` | 闭口 | ○ | |
| `nose` | 鼻子 | | |
| `ears` | 耳朵 | | |
| `earwear` | 耳饰 | | |
| `neck` | 脖子 | | 上端跟随头部 |
| `topwear` | 上半身服装 | | 呼吸、胸部晃动对象 |
| `bottomwear` | 下半身服装 | | |
| `handwear` | 手臂、手 | | 手臂高度操作对象 |
| `headwear` | 帽子、发箍等 | | |
| `front hair` | 前发 | | 发束物理 + 3 块操作 |
| `back hair` | 后发 | | 发束物理 |

- **头发分层时**：加 `_序号` 后缀，如 `front hair_1`、`front hair_2`、`back hair_1` …，各层将作为独立的发束组进行物理演算（发束数按图层宽度自动决定）。
- 规范外的图层名也会被载入（根据位置推断头部/躯干，仅做跟随）。
- 不支持图层组（文件夹）。请使用扁平结构。
- **关于脖子（neck）与躯干（topwear）**：直接使用 see-through 输出时，脖子与躯干的前后关系较难解决，移动时接缝可能崩坏。若不理想，将脖子并入躯干图层（不要 neck 图层，topwear 包含脖子）的**一体式**更容易成功。
- 推荐正方形画布（已在 768×768～2048×2048 验证）。

## 功能

表情预设（微笑/惊讶/半闭眼/左右眨眼）、左右独立的眼睛开度、眉角（左右独立 + 对称）、视线、瞳孔缩放、眼/口「闭合难易」阈值、前发 3 块操作与**前发专属的晃动·柔软度**、手臂高度/位置、胸部晃动（强度·位置可调）、身体倾斜、待机/随机动作、随机口型、麦克风口型、鼠标追踪、**摄像头追踪**（头 XYZ、左右眨眼、口、视线）、背景切换（透明/绿幕）、**三语界面**（日本語/English/简体中文）。

## 结构

```
index.html        应用本体（UI + WebGL 运行时 + i18n）
lib/rigger.js     自动绑定生成（纯 TypedArray 实现，可在 Node 中测试）
lib/ag-psd.min.js PSD 解析器（ag-psd, MIT）
lib/genericparts.js  通用闭眼/闭口差分（内置回退）
main.py           Python 桌面版入口（pywebview）
requirements.txt  Python 版依赖
eye_close.psd     闭眼差分原图（可选，可替换）
mouth_close.psd   闭口差分原图（可选，可替换）
sample.psd        示例模型（请自行放置）
```

运行时为 WebGL1（网格变形 + 模板）。外部通信仅启用摄像头追踪时对 MediaPipe CDN 的加载。

## 已知限制

- 应用内不做单图分解。请拖入已用 [see-through 官方演示（HuggingFace Space）](https://huggingface.co/spaces/24yearsold/see-through-demo)等分割好的 PSD（后处理全自动）
- 嘴部开度为「差分切换 + 变形」的简化表现（中间差分越多越平滑）
- 深度为基于名称的固定表（图层顺序仍按 PSD 保留）

## 许可证

MIT（随附 ag-psd 亦为 MIT；MediaPipe 为 Apache-2.0，经 CDN 引用）。

单图分层假定使用 [shitagaki-lab/see-through](https://github.com/shitagaki-lab/see-through)（Apache-2.0, SIGGRAPH 2026）。本工具是对该项目输出 PSD 进行后处理与绑定的独立第三方工具，不随附 see-through 的代码或模型。
**示例 PSD 图画的版权归各作者所有。** 分发自有模型时请使用自己拥有版权的素材。
