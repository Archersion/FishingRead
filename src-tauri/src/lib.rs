use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::Write,
    path::PathBuf,
    sync::{Arc, Mutex, OnceLock},
    time::Duration,
};

use serde::{de::Error as _, Deserialize, Deserializer, Serialize};
use serde_json::Value;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
    WindowEvent,
};

const BOOKSHELF_TIMEOUT_SECS: u64 = 3;
const CHAPTER_TIMEOUT_SECS: u64 = 10;
const PROGRESS_TIMEOUT_SECS: u64 = 3;
static LOG_FILE: OnceLock<PathBuf> = OnceLock::new();

fn append_log(level: &str, message: &str) -> Result<(), String> {
    let path = LOG_FILE.get().ok_or_else(|| "日志文件尚未初始化".to_string())?;
    let normalized_message = message.replace(['\r', '\n'], " ");
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| format!("打开日志文件失败: {error}"))?;
    writeln!(
        file,
        "[{}] [{}] {}",
        chrono_timestamp_millis(),
        level,
        normalized_message
    )
    .map_err(|error| format!("写入日志文件失败: {error}"))
}

fn initialize_logging() -> Result<PathBuf, String> {
    let executable = std::env::current_exe().map_err(|error| format!("获取程序路径失败: {error}"))?;
    let install_dir = executable
        .parent()
        .ok_or_else(|| "无法确定程序安装目录".to_string())?;
    let log_dir = install_dir.join("logs");
    fs::create_dir_all(&log_dir).map_err(|error| format!("创建日志目录失败: {error}"))?;
    let log_file = log_dir.join("fishing-read.log");
    let _ = LOG_FILE.set(log_file.clone());
    append_log("INFO", "鱼阅启动")?;
    Ok(log_file)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
struct AppConfig {
    ip: String,
    text_opacity: f64,
    background_opacity: f64,
    font_size: u16,
    line_spacing: u16,
    font_family: String,
    text_color: String,
    bg_color: String,
    hide_hotkey: String,
    show_hotkey: String,
    ghost_mode: bool,
    always_on_top: bool,
    context_menu_requires_ctrl: bool,
    window_x: i32,
    window_y: i32,
    window_width: u32,
    window_height: u32,
    window_geometries: BTreeMap<String, WindowGeometry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct WindowGeometry {
    x: i32,
    y: i32,
    width: u32,
    height: u32,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            ip: "http://192.168.6.94:1122".to_string(),
            text_opacity: 0.9,
            background_opacity: 0.78,
            font_size: 14,
            line_spacing: 4,
            font_family: "Microsoft YaHei".to_string(),
            text_color: "#c8c8c8".to_string(),
            bg_color: "#1e1e1e".to_string(),
            hide_hotkey: "Ctrl+Shift+Q".to_string(),
            show_hotkey: "Ctrl+Shift+R".to_string(),
            ghost_mode: true,
            always_on_top: false,
            context_menu_requires_ctrl: true,
            window_x: 100,
            window_y: 100,
            window_width: 550,
            window_height: 240,
            window_geometries: BTreeMap::new(),
        }
    }
}

impl AppConfig {
    fn normalize(&mut self) {
        self.text_opacity = self.text_opacity.clamp(0.05, 1.0);
        self.background_opacity = self.background_opacity.clamp(0.01, 1.0);
        self.font_size = self.font_size.clamp(9, 48);
        self.line_spacing = self.line_spacing.min(40);
        self.window_width = self.window_width.max(360);
        self.window_height = self.window_height.max(150);
        for (label, geometry) in &mut self.window_geometries {
            let (min_width, min_height) = match label.as_str() {
                "settings" => (420, 480),
                "bookshelf" => (420, 480),
                "toc" => (380, 460),
                _ => (320, 240),
            };
            geometry.width = geometry.width.max(min_width);
            geometry.height = geometry.height.max(min_height);
        }
        self.ip = self.ip.trim().trim_end_matches('/').to_string();
        self.hide_hotkey = self.hide_hotkey.trim().to_string();
        self.show_hotkey = self.show_hotkey.trim().to_string();
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase", default)]
struct Book {
    name: String,
    author: String,
    book_url: String,
    #[serde(deserialize_with = "deserialize_i64")]
    dur_chapter_index: i64,
    #[serde(deserialize_with = "deserialize_i64")]
    dur_chapter_pos: i64,
    #[serde(deserialize_with = "deserialize_i64")]
    dur_chapter_time: i64,
    dur_chapter_title: String,
    #[serde(flatten)]
    extra: BTreeMap<String, Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase", default)]
struct Chapter {
    title: String,
    #[serde(deserialize_with = "deserialize_optional_usize")]
    index: Option<usize>,
    #[serde(flatten)]
    extra: BTreeMap<String, Value>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ApiResponse<T> {
    #[serde(default)]
    is_success: Option<bool>,
    #[serde(default)]
    data: Option<T>,
    #[serde(default)]
    error_msg: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReaderPayload {
    book: Book,
    chapters: Vec<Chapter>,
    chapter_index: usize,
    chapter_title: String,
    full_text: String,
    raw_length: usize,
    title_prefix_len: usize,
    progress_pos: usize,
    scroll_to_bottom: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReaderContext {
    book: Book,
    chapters: Vec<Chapter>,
    chapter_index: usize,
}

#[derive(Debug, Clone, Default)]
struct ReaderState {
    current_book: Option<Book>,
    chapters: Vec<Chapter>,
    chapter_index: usize,
    raw_length: usize,
    progress_pos: usize,
}

struct AppState {
    config: Mutex<AppConfig>,
    reader: Mutex<ReaderState>,
    progress_save_lock: Arc<Mutex<()>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            config: Mutex::new(AppConfig::default()),
            reader: Mutex::new(ReaderState::default()),
            progress_save_lock: Arc::new(Mutex::new(())),
        }
    }
}

fn deserialize_i64<'de, D>(deserializer: D) -> Result<i64, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Value::deserialize(deserializer)?;
    match value {
        Value::Null => Ok(0),
        Value::Number(number) => number.as_i64().ok_or_else(|| D::Error::custom("整数超出范围")),
        Value::String(text) => text.trim().parse::<i64>().map_err(D::Error::custom),
        _ => Err(D::Error::custom("进度字段必须是整数或整数字符串")),
    }
}

fn deserialize_optional_usize<'de, D>(deserializer: D) -> Result<Option<usize>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Value::deserialize(deserializer)?;
    match value {
        Value::Null => Ok(None),
        Value::Number(number) => Ok(number.as_u64().map(|value| value as usize)),
        Value::String(text) if text.trim().is_empty() => Ok(None),
        Value::String(text) => text.trim().parse::<usize>().map(Some).map_err(D::Error::custom),
        _ => Err(D::Error::custom("章节序号必须是非负整数")),
    }
}

fn config_path(app: &AppHandle) -> Result<PathBuf, String> {
    let directory = app.path().app_config_dir().map_err(|error| error.to_string())?;
    fs::create_dir_all(&directory).map_err(|error| format!("创建配置目录失败: {error}"))?;
    Ok(directory.join("config.json"))
}

fn read_config(app: &AppHandle) -> AppConfig {
    let Ok(path) = config_path(app) else {
        return AppConfig::default();
    };
    let Ok(content) = fs::read_to_string(path) else {
        return AppConfig::default();
    };
    let mut config = serde_json::from_str::<AppConfig>(&content).unwrap_or_default();
    config.normalize();
    config
}

fn write_config(app: &AppHandle, config: &AppConfig) -> Result<(), String> {
    let path = config_path(app)?;
    let content = serde_json::to_string_pretty(config).map_err(|error| error.to_string())?;
    fs::write(path, content).map_err(|error| format!("保存配置失败: {error}"))
}

fn persist_window_geometry(window: &WebviewWindow, state: &AppState) {
    let Ok(position) = window.outer_position() else {
        return;
    };
    let Ok(size) = window.inner_size() else {
        return;
    };
    let mut config = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    if window.label() == "main" {
        config.window_x = position.x;
        config.window_y = position.y;
        config.window_width = size.width;
        config.window_height = size.height;
    } else if matches!(window.label(), "settings" | "bookshelf" | "toc") {
        config.window_geometries.insert(
            window.label().to_string(),
            WindowGeometry {
                x: position.x,
                y: position.y,
                width: size.width,
                height: size.height,
            },
        );
    } else {
        return;
    }
    let _ = write_config(window.app_handle(), &config);
}

fn persist_all_window_geometries(app: &AppHandle) {
    let state = app.state::<AppState>();
    for label in ["main", "settings", "bookshelf", "toc"] {
        if let Some(window) = app.get_webview_window(label) {
            persist_window_geometry(&window, &state);
        }
    }
}

fn apply_auxiliary_window_geometry(
    window: &WebviewWindow,
    geometry: &WindowGeometry,
    title: &str,
) -> Result<(), String> {
    window
        .set_position(tauri::PhysicalPosition::new(geometry.x, geometry.y))
        .map_err(|error| format!("恢复{title}窗口位置失败: {error}"))?;
    window
        .set_size(tauri::PhysicalSize::new(geometry.width, geometry.height))
        .map_err(|error| format!("恢复{title}窗口尺寸失败: {error}"))
}

fn open_auxiliary_window(
    app: &AppHandle,
    label: &'static str,
    page: &'static str,
    title: &'static str,
    default_width: f64,
    default_height: f64,
    min_width: f64,
    min_height: f64,
) -> Result<(), String> {
    let geometry = app
        .state::<AppState>()
        .config
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .window_geometries
        .get(label)
        .cloned();
    if let Some(window) = app.get_webview_window(label) {
        if let Some(geometry) = &geometry {
            apply_auxiliary_window_geometry(&window, geometry, title)?;
        }
        window.show().map_err(|error| error.to_string())?;
        window.unminimize().map_err(|error| error.to_string())?;
        return window.set_focus().map_err(|error| error.to_string());
    }

    let mut builder = WebviewWindowBuilder::new(app, label, WebviewUrl::App(page.into()))
        .title(title)
        .inner_size(default_width, default_height)
        .min_inner_size(min_width, min_height)
        .decorations(false)
        .visible(false)
        .always_on_top(true)
        .resizable(true);
    if geometry.is_none() {
        builder = builder.center();
    }
    let window = builder
        .build()
        .map_err(|error| format!("打开{title}窗口失败: {error}"))?;
    if let Some(geometry) = &geometry {
        apply_auxiliary_window_geometry(&window, geometry, title)?;
    }
    window.show().map_err(|error| error.to_string())?;
    window.unminimize().map_err(|error| error.to_string())?;
    window.set_focus().map_err(|error| error.to_string())
}

fn endpoint(ip: &str, path: &str) -> Result<String, String> {
    if !ip.starts_with("http://") && !ip.starts_with("https://") {
        return Err("请先在设置中填写有效的 Legado Web 服务地址".to_string());
    }
    Ok(format!("{}/{}", ip.trim_end_matches('/'), path.trim_start_matches('/')))
}

async fn fetch_chapters(ip: &str, book_url: &str) -> Result<Vec<Chapter>, String> {
    let url = endpoint(ip, "getChapterList")?;
    let response = reqwest::Client::new()
        .get(url)
        .query(&[("url", book_url)])
        .timeout(Duration::from_secs(CHAPTER_TIMEOUT_SECS))
        .send()
        .await
        .map_err(|error| format!("获取章节目录失败: {error}"))?
        .error_for_status()
        .map_err(|error| format!("获取章节目录失败: {error}"))?
        .json::<ApiResponse<Vec<Chapter>>>()
        .await
        .map_err(|error| format!("解析章节目录失败: {error}"))?;

    if response.is_success == Some(false) {
        return Err(response.error_msg.unwrap_or_else(|| "获取章节目录失败".to_string()));
    }
    Ok(response.data.unwrap_or_default())
}

async fn fetch_chapter_content(ip: &str, book_url: &str, index: usize) -> Result<String, String> {
    let url = endpoint(ip, "getBookContent")?;
    let index_text = index.to_string();
    let response = reqwest::Client::new()
        .get(url)
        .query(&[("url", book_url), ("index", index_text.as_str())])
        .timeout(Duration::from_secs(CHAPTER_TIMEOUT_SECS))
        .send()
        .await
        .map_err(|error| format!("读取章节失败: {error}"))?
        .error_for_status()
        .map_err(|error| format!("读取章节失败: {error}"))?
        .json::<ApiResponse<String>>()
        .await
        .map_err(|error| format!("解析章节内容失败: {error}"))?;

    if response.is_success == Some(false) {
        return Err(response.error_msg.unwrap_or_else(|| "读取章节失败".to_string()));
    }
    Ok(response.data.unwrap_or_default())
}

fn chapter_title(chapters: &[Chapter], index: usize) -> String {
    chapters
        .get(index)
        .map(|chapter| chapter.title.trim())
        .filter(|title| !title.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| format!("第 {} 章", index + 1))
}

fn build_reader_payload(
    book: Book,
    chapters: Vec<Chapter>,
    index: usize,
    raw_content: String,
    progress_pos: usize,
    scroll_to_bottom: bool,
) -> ReaderPayload {
    let title = chapter_title(&chapters, index);
    let content = raw_content
        .replace("<br />", "\n")
        .replace("<br/>", "\n")
        .replace("<br>", "\n")
        .replace("&nbsp;", " ");
    let title_prefix = format!("【 {title} 】\n\n");
    let raw_length = content.chars().count();
    let restored_pos = if scroll_to_bottom {
        raw_length
    } else {
        progress_pos.min(raw_length)
    };

    ReaderPayload {
        book,
        chapters,
        chapter_index: index,
        chapter_title: title,
        full_text: format!("{title_prefix}{content}"),
        raw_length,
        title_prefix_len: title_prefix.chars().count(),
        progress_pos: restored_pos,
        scroll_to_bottom,
    }
}

fn update_reader_from_payload(reader: &mut ReaderState, payload: &ReaderPayload) {
    reader.current_book = Some(payload.book.clone());
    reader.chapters = payload.chapters.clone();
    reader.chapter_index = payload.chapter_index;
    reader.raw_length = payload.raw_length;
    reader.progress_pos = payload.progress_pos;
}

#[derive(Clone)]
struct ProgressSnapshot {
    ip: String,
    name: String,
    author: String,
    chapter_index: usize,
    chapter_pos: usize,
    chapter_title: String,
}

fn current_progress_snapshot(state: &AppState) -> Option<ProgressSnapshot> {
    let config = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).clone();
    let reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    let book = reader.current_book.as_ref()?;
    Some(ProgressSnapshot {
        ip: config.ip,
        name: book.name.clone(),
        author: book.author.clone(),
        chapter_index: reader.chapter_index,
        chapter_pos: reader.progress_pos.min(reader.raw_length),
        chapter_title: chapter_title(&reader.chapters, reader.chapter_index),
    })
}

fn post_progress_blocking(
    snapshot: ProgressSnapshot,
    save_lock: Arc<Mutex<()>>,
) -> Result<(), String> {
    let _guard = save_lock.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    let url = endpoint(&snapshot.ip, "saveBookProgress")?;
    let body = serde_json::json!({
        "name": snapshot.name,
        "author": snapshot.author,
        "durChapterIndex": snapshot.chapter_index,
        "durChapterPos": snapshot.chapter_pos,
        "durChapterTime": chrono_timestamp_millis(),
        "durChapterTitle": snapshot.chapter_title,
    });
    reqwest::blocking::Client::new()
        .post(url)
        .json(&body)
        .timeout(Duration::from_secs(PROGRESS_TIMEOUT_SECS))
        .send()
        .map_err(|error| format!("保存阅读进度失败: {error}"))?
        .error_for_status()
        .map_err(|error| format!("保存阅读进度失败: {error}"))?;
    Ok(())
}

fn chrono_timestamp_millis() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

async fn sync_current_progress(state: &AppState) -> Result<(), String> {
    let Some(snapshot) = current_progress_snapshot(state) else {
        return Ok(());
    };
    let save_lock = state.progress_save_lock.clone();
    tauri::async_runtime::spawn_blocking(move || post_progress_blocking(snapshot, save_lock))
        .await
        .map_err(|error| format!("等待进度保存任务失败: {error}"))?
}

#[tauri::command]
fn get_config(state: State<'_, AppState>) -> AppConfig {
    state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).clone()
}

#[tauri::command]
fn write_log(level: String, message: String) -> Result<(), String> {
    let level = match level.trim().to_ascii_uppercase().as_str() {
        "INFO" => "INFO",
        "WARN" => "WARN",
        "ERROR" => "ERROR",
        _ => "INFO",
    };
    let message: String = message.chars().take(4_000).collect();
    append_log(level, &message)
}

#[tauri::command]
fn save_config(
    app: AppHandle,
    state: State<'_, AppState>,
    mut config: AppConfig,
) -> Result<AppConfig, String> {
    {
        // 窗口几何信息只由后端维护，避免设置窗口用打开时的旧快照覆盖最新位置。
        let current = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        config.window_x = current.window_x;
        config.window_y = current.window_y;
        config.window_width = current.window_width;
        config.window_height = current.window_height;
        config.window_geometries = current.window_geometries.clone();
    }
    config.normalize();
    if let Some(window) = app.get_webview_window("main") {
        window.set_always_on_top(config.always_on_top).map_err(|error| error.to_string())?;
        window.set_skip_taskbar(true).map_err(|error| error.to_string())?;
    }
    write_config(&app, &config)?;
    *state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()) = config.clone();
    app.emit_to("main", "config-updated", config.clone()).map_err(|error| error.to_string())?;
    Ok(config)
}

#[tauri::command]
fn show_context_menu(window: WebviewWindow) -> Result<(), String> {
    let bookshelf = MenuItem::with_id(&window, "context_bookshelf", "网络书架", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let toc = MenuItem::with_id(&window, "context_toc", "章节目录", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let settings = MenuItem::with_id(&window, "context_settings", "阅读设置", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let hide = MenuItem::with_id(&window, "context_hide", "隐藏窗口", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let quit = MenuItem::with_id(&window, "context_quit", "保存并退出", true, None::<&str>)
        .map_err(|error| error.to_string())?;
    let menu = Menu::with_items(&window, &[&bookshelf, &toc, &settings, &hide, &quit])
        .map_err(|error| error.to_string())?;

    // 使用系统原生弹出菜单，避免独立 WebView 的焦点、透明窗口和坐标换算互相干扰。
    window.popup_menu(&menu).map_err(|error| format!("打开右键菜单失败: {error}"))
}

#[tauri::command]
async fn open_settings_window(app: AppHandle) -> Result<(), String> {
    open_auxiliary_window(
        &app,
        "settings",
        "settings.html",
        "鱼阅设置",
        720.0,
        620.0,
        420.0,
        480.0,
    )
}

#[tauri::command]
async fn open_bookshelf_window(app: AppHandle) -> Result<(), String> {
    open_auxiliary_window(
        &app,
        "bookshelf",
        "bookshelf.html",
        "网络书架",
        760.0,
        640.0,
        420.0,
        480.0,
    )
}

#[tauri::command]
async fn open_toc_window(app: AppHandle) -> Result<(), String> {
    open_auxiliary_window(
        &app,
        "toc",
        "toc.html",
        "章节目录",
        720.0,
        680.0,
        380.0,
        460.0,
    )
}

#[tauri::command]
fn start_dragging(window: WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|error| error.to_string())
}

#[tauri::command]
fn get_reader_context(state: State<'_, AppState>) -> Result<ReaderContext, String> {
    let reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    Ok(ReaderContext {
        book: reader.current_book.clone().ok_or_else(|| "请先从网络书架选择一本书".to_string())?,
        chapters: reader.chapters.clone(),
        chapter_index: reader.chapter_index,
    })
}

#[tauri::command]
async fn fetch_bookshelf(state: State<'_, AppState>) -> Result<Vec<Book>, String> {
    let ip = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).ip.clone();
    let url = endpoint(&ip, "getBookshelf")?;
    let response = reqwest::Client::new()
        .get(url)
        .timeout(Duration::from_secs(BOOKSHELF_TIMEOUT_SECS))
        .send()
        .await
        .map_err(|error| format!("获取网络书架失败: {error}"))?
        .error_for_status()
        .map_err(|error| format!("获取网络书架失败: {error}"))?
        .json::<ApiResponse<Vec<Book>>>()
        .await
        .map_err(|error| format!("解析网络书架失败: {error}"))?;

    if response.is_success == Some(false) {
        return Err(response.error_msg.unwrap_or_else(|| "获取网络书架失败".to_string()));
    }
    Ok(response.data.unwrap_or_default())
}

#[tauri::command]
async fn select_book(
    app: AppHandle,
    window: WebviewWindow,
    state: State<'_, AppState>,
    book: Book,
) -> Result<ReaderPayload, String> {
    if book.book_url.trim().is_empty() {
        return Err("书籍数据缺少 bookUrl，无法打开".to_string());
    }
    sync_current_progress(&state).await?;
    let ip = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).ip.clone();
    let chapters = fetch_chapters(&ip, &book.book_url).await?;
    let index = usize::try_from(book.dur_chapter_index.max(0)).unwrap_or(0);
    let index = if chapters.is_empty() { index } else { index.min(chapters.len() - 1) };
    let raw_content = fetch_chapter_content(&ip, &book.book_url, index).await?;
    let progress = usize::try_from(book.dur_chapter_pos.max(0)).unwrap_or(0);
    let payload = build_reader_payload(book, chapters, index, raw_content, progress, false);
    update_reader_from_payload(
        &mut state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner()),
        &payload,
    );
    if window.label() != "main" {
        app.emit_to("main", "reader-loaded", payload.clone()).map_err(|error| error.to_string())?;
    }
    Ok(payload)
}

#[tauri::command]
async fn load_chapter(
    app: AppHandle,
    window: WebviewWindow,
    state: State<'_, AppState>,
    index: usize,
    scroll_to_bottom: bool,
) -> Result<ReaderPayload, String> {
    sync_current_progress(&state).await?;
    let (ip, book, chapters) = {
        let config = state.config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()).clone();
        let reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        let book = reader.current_book.clone().ok_or_else(|| "请先选择一本网络书籍".to_string())?;
        (config.ip, book, reader.chapters.clone())
    };
    if !chapters.is_empty() && index >= chapters.len() {
        return Err("已经到达目录末尾".to_string());
    }
    let raw_content = fetch_chapter_content(&ip, &book.book_url, index).await?;
    let payload = build_reader_payload(book, chapters, index, raw_content, 0, scroll_to_bottom);
    update_reader_from_payload(
        &mut state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner()),
        &payload,
    );
    if window.label() != "main" {
        app.emit_to("main", "reader-loaded", payload.clone()).map_err(|error| error.to_string())?;
    }
    Ok(payload)
}

#[tauri::command]
fn update_progress(state: State<'_, AppState>, progress_pos: usize) {
    let mut reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
    reader.progress_pos = progress_pos.min(reader.raw_length);
}

#[tauri::command]
async fn save_progress(state: State<'_, AppState>, progress_pos: usize) -> Result<(), String> {
    {
        let mut reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        reader.progress_pos = progress_pos.min(reader.raw_length);
    }
    sync_current_progress(&state).await
}

#[tauri::command]
async fn hide_window(
    window: WebviewWindow,
    state: State<'_, AppState>,
    progress_pos: usize,
) -> Result<(), String> {
    {
        let mut reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        reader.progress_pos = progress_pos.min(reader.raw_length);
    }
    persist_window_geometry(&window, &state);
    window.hide().map_err(|error| error.to_string())?;
    sync_current_progress(&state).await
}

#[tauri::command]
fn show_window(window: WebviewWindow) -> Result<(), String> {
    activate_main_window(&window)
}

fn activate_main_window(window: &WebviewWindow) -> Result<(), String> {
    let configured_always_on_top = window
        .state::<AppState>()
        .config
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .always_on_top;
    // 快捷键和托盘唤起时临时置顶，显示聚焦后恢复用户配置。
    // 置顶在部分 Windows 桌面状态下可能失败，不能因此阻断窗口显示主链路。
    let _ = window.set_always_on_top(true);
    window.show().map_err(|error| error.to_string())?;
    window.unminimize().map_err(|error| error.to_string())?;
    window.emit("show-reader-content", ()).map_err(|error| error.to_string())?;
    window.set_focus().map_err(|error| error.to_string())?;
    window
        .set_always_on_top(configured_always_on_top)
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn quit_app(
    app: AppHandle,
    state: State<'_, AppState>,
    progress_pos: usize,
) -> Result<(), String> {
    {
        let mut reader = state.reader.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        reader.progress_pos = progress_pos.min(reader.raw_length);
    }
    sync_current_progress(&state).await?;
    persist_all_window_geometries(&app);
    app.exit(0);
    Ok(())
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = activate_main_window(&window);
    }
}

fn hide_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let state = app.state::<AppState>();
        persist_window_geometry(&window, &state);
        let _ = window.hide();
    }
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let state = app_handle.state::<AppState>();
        let _ = sync_current_progress(&state).await;
    });
}

fn exit_after_saving(app: &AppHandle) {
    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let state = app_handle.state::<AppState>();
        let _ = sync_current_progress(&state).await;
        persist_all_window_geometries(&app_handle);
        app_handle.exit(0);
    });
}

fn setup_tray(app: &tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示", true, None::<&str>)?;
    let hide = MenuItem::with_id(app, "hide", "隐藏", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &hide, &quit])?;
    let mut tray = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("鱼阅")
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main_window(app),
            "hide" => hide_main_window(app),
            "quit" => exit_after_saving(app),
            _ => {}
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    tray.build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_config,
            write_log,
            save_config,
            show_context_menu,
            open_settings_window,
            open_bookshelf_window,
            open_toc_window,
            start_dragging,
            get_reader_context,
            fetch_bookshelf,
            select_book,
            load_chapter,
            update_progress,
            save_progress,
            hide_window,
            show_window,
            quit_app,
        ])
        .setup(|app| {
            if let Err(error) = initialize_logging() {
                eprintln!("初始化日志失败: {error}");
            }
            std::panic::set_hook(Box::new(|panic_info| {
                let _ = append_log("PANIC", &panic_info.to_string());
            }));
            let config = read_config(app.handle());
            *app.state::<AppState>().config.lock().unwrap_or_else(|poisoned| poisoned.into_inner()) = config.clone();
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_position(tauri::PhysicalPosition::new(config.window_x, config.window_y));
                let _ = window.set_size(tauri::PhysicalSize::new(config.window_width, config.window_height));
                let _ = window.set_always_on_top(config.always_on_top);
                let _ = window.set_skip_taskbar(true);
                window.on_menu_event(|window, event| {
                    let app_handle = window.app_handle().clone();
                    match event.id().as_ref() {
                        "context_bookshelf" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = open_bookshelf_window(app_handle).await;
                            });
                        }
                        "context_toc" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = open_toc_window(app_handle).await;
                            });
                        }
                        "context_settings" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = open_settings_window(app_handle).await;
                            });
                        }
                        "context_hide" => hide_main_window(&app_handle),
                        "context_quit" => exit_after_saving(&app_handle),
                        _ => {}
                    }
                });
            }
            setup_tray(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let state = window.state::<AppState>();
                if let Some(webview_window) = window
                    .app_handle()
                    .get_webview_window(window.label())
                {
                    persist_window_geometry(&webview_window, &state);
                }
                if window.label() != "main" {
                    return;
                }
                api.prevent_close();
                let app = window.app_handle().clone();
                tauri::async_runtime::spawn(async move {
                    let state = app.state::<AppState>();
                    let _ = sync_current_progress(&state).await;
                });
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("启动鱼阅失败");
}
