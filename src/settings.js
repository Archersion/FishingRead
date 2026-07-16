import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import "./settings.css";

const app = document.querySelector("#app");

function escapeAttribute(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function normalizeColor(color, fallback) {
  return /^#[0-9a-f]{6}$/i.test(color) ? color : fallback;
}

function showMessage(message, isError = false) {
  const element = document.querySelector("#settings-message");
  element.textContent = String(message);
  element.classList.toggle("error", isError);
}

function render(config) {
  app.innerHTML = `
    <main class="settings-shell">
      <header class="settings-header">
        <div><p>PREFERENCES</p><h1>阅读设置</h1></div>
        <button id="settings-close" class="icon-button" type="button" aria-label="关闭">×</button>
      </header>
      <form id="settings-form" class="settings-form">
        <div class="settings-fields">
        <label class="wide"><span>Legado Web 地址</span><input name="ip" value="${escapeAttribute(config.ip)}" placeholder="http://192.168.1.10:1122" /></label>
        <label><span>字体</span><input name="fontFamily" value="${escapeAttribute(config.fontFamily)}" /></label>
        <label><span>字号</span><input name="fontSize" type="number" min="9" max="48" value="${config.fontSize}" /></label>
        <label><span>文字颜色</span><input name="textColor" type="color" value="${normalizeColor(config.textColor, "#c8c8c8")}" /></label>
        <label><span>背景颜色</span><input name="bgColor" type="color" value="${normalizeColor(config.bgColor, "#1e1e1e")}" /></label>
        <label><span>文字透明度 <output id="text-opacity-value">${Math.round(config.textOpacity * 100)}%</output></span><input name="textOpacity" type="range" min="5" max="100" value="${Math.round(config.textOpacity * 100)}" /></label>
        <label><span>背景透明度 <output id="background-opacity-value">${Math.round(config.backgroundOpacity * 100)}%</output></span><input name="backgroundOpacity" type="range" min="1" max="100" value="${Math.round(config.backgroundOpacity * 100)}" /></label>
        <label><span>行间距</span><input name="lineSpacing" type="number" min="0" max="40" value="${config.lineSpacing}" /></label>
        <label><span>隐藏快捷键</span><input name="hideHotkey" value="${escapeAttribute(config.hideHotkey)}" /></label>
        <label><span>显示快捷键</span><input name="showHotkey" value="${escapeAttribute(config.showHotkey)}" /></label>
        <label class="check-row"><input name="ghostMode" type="checkbox" ${config.ghostMode ? "checked" : ""} /><span>鼠标离开阅读区时隐藏文字</span></label>
        <label class="check-row"><input name="contextMenuRequiresCtrl" type="checkbox" ${config.contextMenuRequiresCtrl ? "checked" : ""} /><span>仅允许 Ctrl + 右键打开菜单</span></label>
        <label class="check-row"><input name="alwaysOnTop" type="checkbox" ${config.alwaysOnTop ? "checked" : ""} /><span>窗口始终置顶</span></label>
        </div>
        <footer class="settings-footer">
          <p id="settings-message" class="settings-message"></p>
          <div class="form-actions"><button id="settings-cancel" type="button" class="secondary-button">取消</button><button type="submit" class="primary-button">保存并应用</button></div>
        </footer>
      </form>
    </main>
  `;

  const form = document.querySelector("#settings-form");
  const close = () => getCurrentWindow().close();
  document.querySelector(".settings-header").addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest("button")) return;
    event.preventDefault();
    invoke("start_dragging").catch((error) => showMessage(error, true));
  });
  document.querySelector("#settings-close").addEventListener("click", close);
  document.querySelector("#settings-cancel").addEventListener("click", close);
  form.addEventListener("input", () => {
    document.querySelector("#text-opacity-value").value = `${form.elements.textOpacity.value}%`;
    document.querySelector("#background-opacity-value").value = `${form.elements.backgroundOpacity.value}%`;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const nextConfig = {
      ...config,
      ip: form.elements.ip.value.trim(),
      fontFamily: form.elements.fontFamily.value.trim() || "Microsoft YaHei",
      fontSize: Number(form.elements.fontSize.value),
      lineSpacing: Number(form.elements.lineSpacing.value),
      textColor: form.elements.textColor.value,
      bgColor: form.elements.bgColor.value,
      textOpacity: Number(form.elements.textOpacity.value) / 100,
      backgroundOpacity: Number(form.elements.backgroundOpacity.value) / 100,
      hideHotkey: form.elements.hideHotkey.value.trim(),
      showHotkey: form.elements.showHotkey.value.trim(),
      ghostMode: form.elements.ghostMode.checked,
      contextMenuRequiresCtrl: form.elements.contextMenuRequiresCtrl.checked,
      alwaysOnTop: form.elements.alwaysOnTop.checked,
    };
    if (nextConfig.hideHotkey && nextConfig.showHotkey && nextConfig.hideHotkey.toLowerCase() === nextConfig.showHotkey.toLowerCase()) {
      showMessage("显示快捷键和隐藏快捷键不能相同", true);
      return;
    }
    try {
      await invoke("save_config", { config: nextConfig });
      showMessage("设置已保存并应用");
      setTimeout(close, 350);
    } catch (error) {
      showMessage(typeof error === "string" ? error : error?.message || String(error), true);
    }
  });
}

invoke("get_config")
  .then(render)
  .catch((error) => {
    app.innerHTML = `<main class="settings-load-error"><h1>设置加载失败</h1><p></p></main>`;
    app.querySelector("p").textContent = typeof error === "string" ? error : String(error);
  });
