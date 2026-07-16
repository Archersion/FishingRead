# 鱼阅（FishingRead）

鱼阅是一款使用 Rust + Tauri 2 开发的 Windows 轻量网络阅读器，面向希望在桌面上低干扰阅读网络书籍的用户。

项目通过 Legado Web 服务获取网络书架、章节目录和正文内容，只保留网络阅读主链路，不包含本地 TXT 书架与本地文件阅读功能。

## 核心功能

- 网络书架：读取 Legado 网络书架，支持按书名或作者搜索并选择书籍。
- 章节阅读：加载章节目录、切换上一章或下一章，并在选择书籍后直接显示正文。
- 低干扰界面：主窗口透明、无系统边框、无任务栏图标，正文与底部状态栏分区显示。
- 幽灵模式：鼠标离开阅读区后隐藏正文，重新移入并双击阅读区域后恢复。
- 全局快捷键：支持独立的显示和隐藏快捷键，默认分别为 `Ctrl+Shift+R` 和 `Ctrl+Shift+Q`。
- 原生右键菜单：默认使用 `Ctrl + 右键`打开系统菜单，可进入网络书架、章节目录、阅读设置，或隐藏、退出程序。
- 阅读外观：支持字体、字号、行距、文字颜色、背景颜色、文字透明度和背景透明度配置。
- 窗口管理：主窗口和各个功能弹窗分别记忆上次的坐标与尺寸；主窗口四边及四角支持拖动缩放。
- 系统托盘：可通过托盘菜单显示、隐藏或保存并退出程序。
- 自动保存：滚动停止、周期保存、切书、切章、隐藏和退出都会进入统一的阅读进度保存链。

## 交互说明

### 主窗口

- 在正文区域按住鼠标左键可以移动窗口。
- 将鼠标移动到窗口四边或四角，可以调整窗口尺寸。
- 正文不允许选择，避免拖动窗口时误选文字。
- 鼠标离开窗口后，幽灵模式会隐藏正文和状态栏；重新移入后双击可恢复。

### 右键菜单

默认按住 `Ctrl` 后点击鼠标右键打开菜单。可以在阅读设置中关闭“仅允许 Ctrl + 右键打开菜单”，改为直接右键打开。

### 托盘与快捷键

- 显示窗口：`Ctrl+Shift+R`
- 隐藏窗口：`Ctrl+Shift+Q`
- 关闭主窗口：隐藏到系统托盘，不直接退出。
- 托盘“退出”或右键菜单“保存并退出”：等待最后一次阅读进度保存完成后退出。

显示窗口时会临时提升到前台并恢复正文，随后恢复“窗口始终置顶”的用户配置，不会强制永久置顶。

## Legado 接口

鱼阅需要连接可访问的 Legado Web 服务，当前使用以下接口：

- `getBookshelf`：获取网络书架。
- `getChapterList`：获取章节目录。
- `getBookContent`：获取章节正文。
- `saveBookProgress`：保存阅读进度。

首次启动后，通过右键菜单进入“阅读设置”，填写 Legado Web 地址，例如：

```text
http://192.168.1.10:1122
```

## 技术栈

- Rust 2021
- Tauri 2
- Vite 7
- 原生 JavaScript、HTML、CSS
- Reqwest + Rustls
- Tauri Global Shortcut 插件
- Tauri Tray Icon

## 项目结构

```text
FishingRead/
├─ src/                         # 前端脚本与样式
│  ├─ main.js                   # 主阅读窗口、快捷键、缩放与进度采样
│  ├─ bookshelf.js              # 网络书架窗口
│  ├─ toc.js                    # 章节目录窗口
│  ├─ settings.js               # 阅读设置窗口
│  ├─ style.css                 # 主窗口与通用样式
│  ├─ panel.css                 # 书架、目录窗口样式
│  └─ settings.css              # 设置窗口样式
├─ src-tauri/
│  ├─ src/lib.rs                # 网络接口、阅读状态、配置、托盘和窗口生命周期
│  ├─ src/main.rs               # Windows GUI 程序入口
│  ├─ capabilities/default.json # Tauri 窗口与快捷键权限
│  ├─ Cargo.toml                # Rust 依赖
│  └─ tauri.conf.json           # Tauri 窗口与打包配置
├─ index.html                   # 主阅读窗口入口
├─ bookshelf.html               # 网络书架入口
├─ toc.html                     # 章节目录入口
├─ settings.html                # 阅读设置入口
├─ package.json                 # Node.js 脚本与依赖
└─ vite.config.js               # Vite 多页面构建配置
```

## 开发环境

Windows 开发需要：

- Node.js `20.19+` 或 `22.12+`。
- Rust stable，目标为 `x86_64-pc-windows-msvc`。
- Microsoft Edge WebView2 Runtime。
- Visual Studio 2017 或更高版本，或 Visual Studio Build Tools。
- Visual C++ 生成工具与 Windows SDK。

VS Code 本身不包含 Rust MSVC 所需的 `link.exe`。

## 安装依赖

以下命令均在项目根目录下执行。

```powershell
npm install
```

## 开发运行

```powershell
npm run tauri dev
```

开发模式需要保持终端窗口开启，用于运行 Vite、Cargo、热更新和输出日志。

## 构建安装包

```powershell
npm run tauri build
```

构建产物位于：

```text
src-tauri/target/release/bundle/
```

Windows MSI 安装包使用简体中文 WiX 配置。正式版程序使用 Windows GUI 子系统，直接运行不会额外显示 CMD 窗口。

## 配置与数据

用户设置保存在 Tauri 应用配置目录下的 `config.json`，不依赖程序启动目录。配置内容包括：

- Legado Web 地址。
- 字体与颜色设置。
- 透明度、字号和行距。
- 显示、隐藏快捷键。
- 幽灵模式、右键菜单限制和窗口置顶开关。
- 主窗口及各功能窗口的坐标与尺寸。

阅读进度通过 Legado 的 `saveBookProgress` 接口保存，不在项目目录中维护本地书架数据库。

## 当前范围

本项目专注于轻量网络阅读体验，目前不包含：

- 本地 TXT 文件导入。
- 本地书架管理。
- 复杂排版或富文本阅读。
- 多阅读源管理。
