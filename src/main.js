import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { register, unregisterAll } from "@tauri-apps/plugin-global-shortcut";
import "./style.css";

const appState = {
  config: null,
  reader: null,
  loading: false,
  progressTimer: null,
  stateTimer: null,
  lastSavedAt: 0,
};

document.querySelector("#app").innerHTML = `
  <main id="window-shell">
    <article id="reader" aria-live="polite">正在连接网络书架…</article>
    <div id="status" role="status"></div>
  </main>

  <div class="resize-handle resize-n" data-resize-direction="North"></div>
  <div class="resize-handle resize-e" data-resize-direction="East"></div>
  <div class="resize-handle resize-s" data-resize-direction="South"></div>
  <div class="resize-handle resize-w" data-resize-direction="West"></div>
  <div class="resize-handle resize-ne" data-resize-direction="NorthEast"></div>
  <div class="resize-handle resize-se" data-resize-direction="SouthEast"></div>
  <div class="resize-handle resize-sw" data-resize-direction="SouthWest"></div>
  <div class="resize-handle resize-nw" data-resize-direction="NorthWest"></div>

  <div id="toast" class="toast hidden"></div>
`;

const shell = document.querySelector("#window-shell");
const reader = document.querySelector("#reader");
const status = document.querySelector("#status");
const toast = document.querySelector("#toast");
const currentWindow = getCurrentWindow();

document.querySelectorAll("[data-resize-direction]").forEach((handle) => {
  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    currentWindow
      .startResizeDragging(handle.dataset.resizeDirection)
      .catch((error) => showToast(errorMessage(error), true));
  });
});

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function setStatus(message = "") {
  status.textContent = message;
  status.classList.toggle("visible", Boolean(message));
}

let toastTimer;
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  toast.textContent = String(message);
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 2800);
}

function errorMessage(error) {
  return typeof error === "string" ? error : error?.message || String(error);
}

function applyConfig(config) {
  appState.config = config;
  if (!config.ghostMode) {
    shell.classList.remove("ghost-hidden");
  }
  document.documentElement.style.setProperty("--font-family", config.fontFamily);
  document.documentElement.style.setProperty("--font-size", `${config.fontSize}px`);
  document.documentElement.style.setProperty("--line-gap", `${config.lineSpacing}px`);
  document.documentElement.style.setProperty("--text-color", config.textColor);
  document.documentElement.style.setProperty("--background-color", config.bgColor);
  document.documentElement.style.setProperty("--text-opacity", config.textOpacity);
  document.documentElement.style.setProperty("--background-opacity", config.backgroundOpacity);
}

async function registerHotkeys(config) {
  await unregisterAll();
  const hideHotkey = config.hideHotkey?.trim();
  const showHotkey = config.showHotkey?.trim();
  if (hideHotkey && showHotkey && hideHotkey.toLowerCase() === showHotkey.toLowerCase()) {
    throw new Error("显示快捷键和隐藏快捷键不能相同");
  }
  const registrationErrors = [];
  if (hideHotkey) {
    try {
      await register(hideHotkey, async (event) => {
        if (event.state === "Pressed") await hideWindow();
      });
    } catch (error) {
      registrationErrors.push(`隐藏快捷键 ${hideHotkey}: ${errorMessage(error)}`);
    }
  }
  if (showHotkey) {
    try {
      await register(showHotkey, async (event) => {
        if (event.state === "Pressed") {
          shell.classList.remove("ghost-hidden");
          try {
            await invoke("show_window");
          } catch (error) {
            showToast(errorMessage(error), true);
          }
        }
      });
    } catch (error) {
      registrationErrors.push(`显示快捷键 ${showHotkey}: ${errorMessage(error)}`);
    }
  }
  if (registrationErrors.length) {
    throw new Error(registrationErrors.join("；"));
  }
}

function getVisibleRawPosition() {
  if (!appState.reader) return 0;
  const textNode = reader.firstChild;
  if (!textNode || textNode.nodeType !== Node.TEXT_NODE) return appState.reader.progressPos || 0;

  const rect = reader.getBoundingClientRect();
  const x = rect.left + 8;
  const y = rect.top + 8;
  let node;
  let offset;

  if (document.caretPositionFromPoint) {
    const caret = document.caretPositionFromPoint(x, y);
    node = caret?.offsetNode;
    offset = caret?.offset;
  } else if (document.caretRangeFromPoint) {
    const range = document.caretRangeFromPoint(x, y);
    node = range?.startContainer;
    offset = range?.startOffset;
  }

  if (node && Number.isInteger(offset)) {
    const range = document.createRange();
    range.setStart(textNode, 0);
    range.setEnd(node, offset);
    const codePointOffset = Array.from(range.toString()).length;
    return clamp(codePointOffset - appState.reader.titlePrefixLen, 0, appState.reader.rawLength);
  }

  const available = Math.max(1, reader.scrollHeight - reader.clientHeight);
  return Math.round((reader.scrollTop / available) * appState.reader.rawLength);
}

function codePointToUtf16Index(text, codePointIndex) {
  return Array.from(text).slice(0, codePointIndex).join("").length;
}

function restoreProgress(payload) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (payload.scrollToBottom) {
      reader.scrollTop = reader.scrollHeight;
      return;
    }
    if (payload.progressPos <= 0 || !reader.firstChild) {
      reader.scrollTop = 0;
      return;
    }
    const codePointIndex = payload.titlePrefixLen + payload.progressPos;
    const utf16Index = codePointToUtf16Index(payload.fullText, codePointIndex);
    const range = document.createRange();
    range.setStart(reader.firstChild, Math.min(utf16Index, reader.firstChild.length));
    range.collapse(true);
    const caretRect = range.getBoundingClientRect();
    const readerRect = reader.getBoundingClientRect();
    reader.scrollTop += caretRect.top - readerRect.top - 8;
  }));
}

function renderReader(payload) {
  appState.reader = payload;
  reader.textContent = payload.fullText;
  reader.classList.remove("empty");
  setStatus(`${payload.book.name} · ${payload.chapterTitle}`);
  restoreProgress(payload);
}

function renderEmpty(message) {
  appState.reader = null;
  reader.textContent = message;
  reader.classList.add("empty");
  setStatus("Ctrl + 右键打开菜单");
}

async function syncProgress(remote = true) {
  if (!appState.reader || appState.loading) return;
  const progressPos = getVisibleRawPosition();
  try {
    await invoke(remote ? "save_progress" : "update_progress", { progressPos });
    if (remote) appState.lastSavedAt = Date.now();
  } catch (error) {
    if (remote) showToast(errorMessage(error), true);
  }
}

function scheduleProgressSave() {
  if (!appState.reader || appState.loading) return;
  clearTimeout(appState.stateTimer);
  appState.stateTimer = setTimeout(() => syncProgress(false), 180);
  clearTimeout(appState.progressTimer);
  appState.progressTimer = setTimeout(() => syncProgress(true), 800);
}

async function hideWindow() {
  clearTimeout(appState.progressTimer);
  clearTimeout(appState.stateTimer);
  try {
    await invoke("hide_window", { progressPos: getVisibleRawPosition() });
    appState.lastSavedAt = Date.now();
  } catch (error) {
    showToast(errorMessage(error), true);
  }
}

async function quitApp() {
  clearTimeout(appState.progressTimer);
  clearTimeout(appState.stateTimer);
  try {
    await invoke("quit_app", { progressPos: getVisibleRawPosition() });
  } catch (error) {
    showToast(errorMessage(error), true);
  }
}

async function loadChapter(index, scrollToBottom = false) {
  if (!appState.reader || appState.loading || index < 0) return;
  appState.loading = true;
  setStatus("正在加载章节…");
  clearTimeout(appState.progressTimer);
  try {
    await invoke("update_progress", { progressPos: getVisibleRawPosition() });
    const payload = await invoke("load_chapter", { index, scrollToBottom });
    renderReader(payload);
  } catch (error) {
    showToast(errorMessage(error), true);
    setStatus(appState.reader ? `${appState.reader.book.name} · ${appState.reader.chapterTitle}` : "");
  } finally {
    appState.loading = false;
  }
}

window.addEventListener("contextmenu", (event) => {
  event.preventDefault();
  event.stopPropagation();
  if (appState.config?.contextMenuRequiresCtrl && !event.ctrlKey) return;
  // 菜单交互不等待进度落盘，避免本地状态锁或保存链路延迟导致右键无响应。
  void syncProgress(false);
  invoke("show_context_menu").catch((error) => showToast(errorMessage(error), true));
}, true);
reader.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  // 内容隐藏时优先保留双击事件，避免原生拖动吞掉第二次点击。
  if (shell.classList.contains("ghost-hidden")) return;
  event.preventDefault();
  invoke("start_dragging").catch((error) => showToast(errorMessage(error), true));
});

shell.addEventListener("mouseleave", () => {
  if (appState.config?.ghostMode) {
    shell.classList.add("ghost-hidden");
  }
});
shell.addEventListener("dblclick", () => {
  if (appState.config?.ghostMode && shell.classList.contains("ghost-hidden")) {
    shell.classList.remove("ghost-hidden");
  }
});

reader.addEventListener("scroll", scheduleProgressSave, { passive: true });
reader.addEventListener("wheel", (event) => {
  if (!appState.reader || appState.loading) return;
  if (event.deltaY > 0 && reader.scrollTop + reader.clientHeight >= reader.scrollHeight - 2) {
    setTimeout(() => loadChapter(appState.reader.chapterIndex + 1, false), 80);
  } else if (event.deltaY < 0 && reader.scrollTop <= 0 && appState.reader.chapterIndex > 0) {
    setTimeout(() => loadChapter(appState.reader.chapterIndex - 1, true), 80);
  }
}, { passive: true });

document.addEventListener("keydown", (event) => {
  if (["ArrowRight", "ArrowDown", "PageDown", " "].includes(event.key)) {
    event.preventDefault();
    const previous = reader.scrollTop;
    reader.scrollBy({ top: reader.clientHeight - 32, behavior: "smooth" });
    if (previous + reader.clientHeight >= reader.scrollHeight - 4 && appState.reader) {
      loadChapter(appState.reader.chapterIndex + 1, false);
    }
  }
  if (["ArrowLeft", "ArrowUp", "PageUp"].includes(event.key)) {
    event.preventDefault();
    if (reader.scrollTop <= 2 && appState.reader?.chapterIndex > 0) {
      loadChapter(appState.reader.chapterIndex - 1, true);
    } else {
      reader.scrollBy({ top: -(reader.clientHeight - 32), behavior: "smooth" });
    }
  }
});

setInterval(() => {
  if (appState.reader && !appState.loading && Date.now() - appState.lastSavedAt >= 30_000) {
    syncProgress(true);
  }
}, 15_000);

async function bootstrap() {
  try {
    const config = await invoke("get_config");
    applyConfig(config);
    try {
      await registerHotkeys(config);
    } catch (error) {
      showToast(errorMessage(error), true);
    }
    await listen("config-updated", async ({ payload: nextConfig }) => {
      applyConfig(nextConfig);
      try {
        await registerHotkeys(nextConfig);
      } catch (error) {
        showToast(errorMessage(error), true);
      }
    });
    await listen("show-reader-content", () => {
      shell.classList.remove("ghost-hidden");
    });
    await listen("reader-loaded", ({ payload }) => {
      appState.loading = false;
      // 选书或从独立目录切章完成后只恢复内容，不调整主窗口几何信息。
      shell.classList.remove("ghost-hidden");
      renderReader(payload);
    });
    renderEmpty("从网络书架选择一本书开始阅读");
  } catch (error) {
    renderEmpty("初始化失败，请打开设置检查配置");
    showToast(errorMessage(error), true);
  }
}

bootstrap();
