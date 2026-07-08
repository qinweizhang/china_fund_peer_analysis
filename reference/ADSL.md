**AbleMind Pro 设计语言系统 (ADLS) - 浅色模式 / 原生工业版**。

彭博终端（Bloomberg Terminal）的**数据密度**与瑞士国际主义（Swiss Style）的**排版秩序**结合。

# AbleMind Pro Design Language System (ADLS)

Version: 2.1 Native Industrial (Light Mode) - Backgroundless Strategy

Core Philosophy: Rationality over Decoration (理性大于装饰)

**🆕 v2.1 更新 (2025-12-16):** 实施"完全去背"策略 (Backgroundless Strategy)，所有内容面板与全局底色统一为 Slate-50，仅输入框保持白色以建立"白色=可编辑"的心智模型。

## 1. 核心设计原则 (Design Pillars)

### A. 绝对正交 (Strict Orthogonality)

- **规则：** border-radius: 0 是绝对法则。

- **理由：** 圆角代表“亲和”与“柔顺”，直角代表“精确”与“坚固”。在金融终端中，我们需要的是数据的**刚性**。

- **应用：** 所有的按钮、输入框、模态窗、卡片、标签，全部移除圆角。

### B. 微边框主义 (Micro-Borderism)

- **规则：** 放弃“投影 (Drop Shadow)”来构建层级，改用 **1px 的极细边框** 和 **色块区分**。

- **理由：** 投影会产生“悬浮感”和视觉噪音。微边框能让界面像打印出来的报表一样平整、清晰。

- **实现：** 使用 border-slate-200 作为常态边界，border-able-primary 作为选中边界。

### C. 极高密度 (High Density)

- **规则：** 默认字体更小（12px/13px），行高更紧（leading-tight），间距更密。

- **理由：** 专业交易员/分析师需要在一屏内看到尽可能多的上下文。留白（Whitespace）用于逻辑分组，而不是为了“透气”。

## 2. 色彩体系：深海 (The "Deep Sea" Palette)

这是专为**浅色模式**调教的“冷静”色盘，避免了纯黑白的高反差刺眼，采用了冷灰与深蓝的搭配。

### 基础色板 (Foundations)

| **用途** | **色值 (Hex)** | **Tailwind 类名映射** | **视觉感受** | **v2.1 变化** |
|----|----|----|----|----|
| **主色 (Primary)** | \#205781 | bg-able-primary | **深海蓝**。沉稳、权威，用于主按钮、激活状态、重要边框。 | 无变化 |
| **辅色 (Accent)** | \#4F959D | bg-able-mint | **冷杉绿/薄荷青**。用于次级高亮、Tag、选中态背景（需调低透明度）。 | 无变化 |
| **画布 (App Bg)** | \#F8FAFC | bg-slate-50 | **冷灰白**。极淡的冷灰色，避免纯白的刺眼，增加纸质感。 | 无变化 |
| **容器 (Surface)** | \#F8FAFC | bg-slate-50 | **去背设计**。内容面板与全局底色统一，不再使用白色容器。 | ⚠️ **从 White 改为 Slate-50** |
| **输入框 (Input Bg)** | \#FFFFFF | bg-white | **纯白**。仅输入框使用，建立"白色=可编辑"心智模型。 | 🆕 **新增专用色** |
| **边框 (Border)** | \#CBD5E1 | border-slate-300 | **结构灰**。因去背需加深边框以确保结构清晰。 | ⚠️ **从 Slate-200 加深到 Slate-300** |
| **次级边框 (Border Subtle)** | \#E2E8F0 | border-slate-200 | **辅助线**。用于内部分隔、辅助网格。 | 🆕 **降级为次级边框** |

### 功能色 (Functional) - 信号灯

- **涨/正向 (Up):** \#10b981 (Emerald-500) —— *金融界通常红跌绿涨（A股）或 绿跌红涨（美股），请根据配置切换，此处以“安全/通行”为绿为例。*

- **跌/警示 (Down/Crit):** \#ef4444 (Red-500)

- **警告 (Warn):** \#f59e0b (Amber-500)

- **中性/文本 (Text):**

  - 主要文字: \#334155 (Slate-700) —— *非纯黑，降低阅读疲劳*

  - 次要文字: \#64748b (Slate-500)

## 3. 排版系统：原生工业体 (System Industrial)

放弃加载 Web Font，利用系统原生字体的渲染优势，配合 CSS 特性打造“数字美学”。

- **Font Family:** ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif

- **Feature Settings:** font-feature-settings: "tnum" (开启等宽数字，Tabular Nums)。这是金融数据的核心。

### 文本层级 (Type Hierarchy)

- **H1 / Page Title:** text-lg font-bold tracking-tight text-slate-800 uppercase (无衬线，大写，紧凑)

- **H2 / Section Header:** text-sm font-bold text-able-primary uppercase tracking-wider (带有工业铭牌感的小标题)

- **Body / Markdown:** text-sm leading-7 text-slate-700 font-normal (参考 markdown_adj.md 的 Investment Memo 风格)

- **Data Cell:** text-xs font-mono tabular-nums text-slate-900 (表格数据专用)

- **Label / Caption:** text-\[10px\] font-bold text-slate-400 uppercase (微型标签)

## 4. 核心组件规范 (Component Specs)

### A. 容器 (The Container) - "Bento Box"

**v2.1 完全去背版本：**

- **外观：** Slate-50 背景（与全局底色统一），1px slate-300 边框（加深），无圆角，无阴影。

- **标题栏：** 容器顶部有一条 32px 高的 Header，底色为 slate-100（比面板深一级），文字为 text-xs font-bold uppercase。

- **理念：** 内容直接渲染在纸质底色上，不再有"浮起"的白色卡片。边框加深以补偿背景色差的消失。


```TypeScript  
  \<div className="border border-slate-300 bg-[var(--bg-panel)] flex flex-col h-full"\>  
  \<div className="h-8 bg-slate-100 border-b border-slate-300 px-3 flex items-center"\>  
  \<span className="text-xs font-bold text-slate-600 uppercase tracking-wider"\>Market Depth\</span\>  
  \</div\>  
  \<div className="p-0 overflow-auto flex-1"\>  
  {/\* Content \*/}  
  \</div\>  
  \</div\>

### B. 按钮 (The Switch) - "Mechanical Click"

- **主按钮：** bg-able-primary text-white hover:bg-\[#1a4a6e\] active:translate-y-\[1px\]
  - *交互：* 点击时产生 1px 的物理位移，模拟机械按键的键程，而不是颜色渐变。
  
- **次级按钮：** bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 hover:border-able-primary hover:text-able-primary

- **形状：** 严格直角，高度通常为 32px (Compact) 或 28px (Ultra-Compact)。

### C. 输入框 (The Input) - "Terminal Field"

**v2.1 心智模型强化：**

- **常态：** bg-white border border-slate-300 text-sm
  - ⚠️ **仅输入框保持白色背景**，建立"白色=可编辑"的视觉语言。

- **聚焦 (Focus)：** **不使用** 模糊的 ring (Glow effect)。使用 **加粗的边框** 或 **双重边框**。

  - focus:border-able-primary focus:ring-1 focus:ring-able-primary focus:ring-offset-0

- **占位符：** placeholder:text-slate-300 italic

- **设计理念：** 在灰色底色的环境中，白色成为了视觉焦点。用户一眼就能识别哪些区域是可编辑的。

### D. 智能体交互 (The Agent) - "Reasoning Stack"

参考 agent-trace.md，彻底改变“对话气泡”模式。

1.  **用户输入：** 显示为一条“指令行” (Command Line)，背景微灰。

2.  **思考过程 (Thinking)：** 显示为 **"Flight Check" (飞行检查单)**。

    - 使用列表 \<ul\>，每一步是一个 \<li\>。

    - 图标使用线框风格（Lucide React Icons）。

    - 进行中：闪烁的光标 \_。

    - 完成：实心复选框 \[x\]。

3.  **最终输出：** 渲染为 **"Investment Memo" (投资备忘录)**。

    - 参考 markdown_adj.md。

    - 高亮重点使用“底色高亮”而非“粗体”。

    - 表格使用 AG Grid 样式渲染，而非简单的 HTML Table。

### E. 数据表格 (The Grid) - AG Grid Theme

参考 aggrid.md。
```TypeScript 
- **Header:** bg-slate-50 border-b border-slate-300 text-xs font-bold text-slate-500

- **Cell:** text-xs font-mono border-r border-slate-100 leading-\[28px\]

- **Selection:** 选中行背景色为 bg-able-mint/10 (极淡的薄荷绿)，选中单元格边框为 border-able-primary。

## 5. v2.1 完全去背策略详解 (Backgroundless Strategy Deep Dive)

### 设计理念

传统设计使用"白色卡片浮在灰色背景上"来建立层次感，但这在专业终端应用中会产生以下问题：

1. **视觉碎片化：** 过多的白色卡片让界面显得支离破碎
2. **眩光问题：** 大面积白色在长时间使用中容易造成视觉疲劳
3. **信息密度降低：** 边距和阴影占用了宝贵的屏幕空间

**完全去背策略**借鉴了 Bloomberg Terminal、Refinitiv Eikon 等专业终端的设计：

> **"内容直接印在纸上，而不是贴一张白纸在纸上"**

### 色彩映射变化

| 区域 | v2.0 旧值 | v2.1 新值 | 理由 |
|------|-----------|-----------|------|
| **Global Bg** | Slate-50 | Slate-50 (#F8FAFC) | 保持纸质感底色 |
| **Panel Bg** | White | **Slate-50 (#F8FAFC)** | 不再使用白色容器，内容直接渲染在底色上 |
| **Input Bg** | White | White (#FFFFFF) | **仅输入框使用纯白**，建立"白色=可编辑"心智模型 |
| **Chart Area** | White | Transparent/Slate-50 | 图表轴线直接画在底色上，减少眩光 |
| **Border Main** | Slate-200 | **Slate-300 (#CBD5E1)** | 因去背需加深边框以确保结构清晰 |
| **Border Subtle** | Slate-100 | Slate-200 (#E2E8F0) | 原主边框降级为次级边框 |

### 视觉效果

**修改前 (v2.0):**
```
┌─────────────────────────────────┐
│  灰色背景 (Slate-50)             │
│  ┌──────────────────────────┐   │
│  │  白色面板 (White)         │   │ ← 形成明显的"卡片"感
│  │  [图表内容]               │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

**修改后 (v2.1):**
```
┌─────────────────────────────────┐
│  统一灰色底色 (Slate-50)         │
│  ┌──────────────────────────┐   │
│  │  灰色面板 (Slate-50)      │   │ ← 无背景色差，边框加深
│  │  [图表内容]               │   │
│  └──────────────────────────┘   │
│  [输入框 - 白色] ← 唯一的白色    │
└─────────────────────────────────┘
```

### 实施要点

1. **输入框必须保持白色：** 这是唯一的例外，用于建立视觉语言
2. **边框加深：** 从 Slate-200 → Slate-300，补偿背景色差的消失
3. **Header 区分：** 使用 Slate-100 让标题栏比面板深一级
4. **图表透明化：** 图表组件不再设置白色背景，直接渲染在 Slate-50 上

## 6. 实施指南 (Implementation Strategy)

### 步骤 1: 更新 tailwind.config.ts

将核心色板注入配置：

```TypeScript

// tailwind.config.ts  
import { fontFamily } from "tailwindcss/defaultTheme"  

export default {  
// ...  
theme: {  
extend: {  
colors: {  
// 覆盖 Shadcn/Base 默认颜色  
border: "#E2E8F0", // slate-200  
input: "#CBD5E1", // slate-300  
ring: "#205781", // able-primary  
background: "#F8FAFC", // slate-50  
foreground: "#334155", // slate-700  

// AbleMind 品牌色  
able: {  
primary: '#205781', // Deep Sea Blue  
mint: '#4F959D', // Industrial Mint  
dark: '#0F172A', // Ink  
}  
},  
borderRadius: {  
lg: "0",  
md: "0",  
sm: "0",  
DEFAULT: "0",  
},  
fontFamily: {  
// 强制使用系统栈，不引入 Web Font  
sans: \["ui-sans-serif", "system-ui", ...fontFamily.sans\],  
mono: \["ui-monospace", "SFMono-Regular", ...fontFamily.mono\],  
},  
},  
},  
}

### 步骤 2: 全局 CSS 重置 (globals.css)
```TypeScript
```CSS

@layer base {  
:root {  
--radius: 0px; /\* 强制覆盖 Shadcn 变量 \*/  
}  

\* {  
@apply border-border;  
}  

body {  
@apply bg-slate-50 text-slate-700 antialiased;  
/\* 开启字体平滑和等宽数字 \*/  
font-feature-settings: "tnum";  
-webkit-font-smoothing: antialiased;  
}  

/\* 滚动条极简风格 \*/  
::-webkit-scrollbar {  
width: 6px;  
height: 6px;  
}  
::-webkit-scrollbar-track {  
background: transparent;  
}  
::-webkit-scrollbar-thumb {  
@apply bg-slate-300 hover:bg-slate-400;  
}  
}

### 步骤 3: 替换关键组件

1.  **MessageBubble -\> MemoRenderer:** 不再使用圆角气泡，改为全宽度的文档流渲染。

2.  **ChatInput -\> CommandBar:** 输入框改为类似于 VS Code 的 Command Palette 样式，直角，顶部边框。

精准的数据和高效的执行。
