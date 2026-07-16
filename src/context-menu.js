import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import "./context-menu.css";

const app = document.querySelector("#app");
app.innerHTML = `
  <nav class="context-menu" aria-label="阅读菜单">
    <button class="menu-item" type="button" data-action="bookshelf"><span class="menu-icon">▦</span><span class="menu-copy"><strong>网络书架</strong><small>查找并打开书籍</small></span></button>
    <button class="menu-item" type="button" data-action="toc"><span class="menu-icon">☷</span><span class="menu-copy"><strong>章节目录</strong><small>快速切换章节</small></span></button>
    <div class="menu-separator" role="separator"></div>
    <button class="menu-item" type="button" data-action="settings"><span class="menu-icon">⚙</span><span class="menu-copy"><strong>阅读设置</strong><small>字体、外观与快捷键</small></span></button>
    <button class="menu-item" type="button" data-action="hide"><span class="menu-icon">—</span><span class="menu-copy"><strong>隐藏窗口</strong><small id="hide-hotkey">快捷隐藏</small></span></button>
    <div class="menu-separator" role="separator"></div>
    <button class="menu-item danger" type="button" data-action="quit"><span class="menu-icon">⏻</span><span class="menu-copy"><strong>保存并退出</strong><small>保存当前阅读进度</small></span></button>
    <p id="menu-error" class="menu-error" role="alert"></p>
  </nav>
`;

const buttons = [...document.querySelectorAll(".menu-item")];
let running = false;
let closeOnBlur = false;

function errorMessage(error) {
  return typeof error === "string" ? error : error?.message || String(error);
}

async function runAction(button) {
  if (running) return;
  running = true;
  buttons.forEach((item) => { item.disabled = true; });
  try {
    await invoke("execute_context_menu_action", { action: button.dataset.action });
  } catch (error) {
    document.querySelector("#menu-error").textContent = errorMessage(error);
    buttons.forEach((item) => { item.disabled = false; });
    running = false;
  }
}

buttons.forEach((button) => button.addEventListener("click", () => runAction(button)));

window.addEventListener("blur", () => {
  if (running || !closeOnBlur) return;
  setTimeout(() => {
    getCurrentWindow().close().catch((error) => console.error("关闭右键菜单失败", error));
  }, 80);
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Escape") {
    await getCurrentWindow().close();
    return;
  }
  if (!["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) return;
  event.preventDefault();
  const current = Math.max(0, buttons.indexOf(document.activeElement));
  if (event.key === "ArrowDown") buttons[(current + 1) % buttons.length].focus();
  if (event.key === "ArrowUp") buttons[(current - 1 + buttons.length) % buttons.length].focus();
  if (["Enter", " "].includes(event.key)) runAction(buttons[current]);
});

invoke("get_config")
  .then((config) => {
    document.querySelector("#hide-hotkey").textContent = config.hideHotkey || "快捷隐藏";
  })
  .catch((error) => {
    document.querySelector("#menu-error").textContent = errorMessage(error);
  });

requestAnimationFrame(() => buttons[0]?.focus());

invoke("focus_context_menu")
  .then(() => {
    setTimeout(() => { closeOnBlur = true; }, 150);
  })
  .catch((error) => {
    document.querySelector("#menu-error").textContent = errorMessage(error);
  });
