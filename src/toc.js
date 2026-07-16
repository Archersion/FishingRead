import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import "./panel.css";

const app = document.querySelector("#app");

app.addEventListener("pointerdown", (event) => {
  if (!event.target.closest(".panel-header") || event.button !== 0 || event.target.closest("button")) return;
  event.preventDefault();
  invoke("start_dragging").catch((error) => {
    const message = app.querySelector(".panel-message");
    if (message) message.textContent = errorMessage(error);
  });
});

function errorMessage(error) {
  return typeof error === "string" ? error : error?.message || String(error);
}

function render(context) {
  app.innerHTML = `
    <main class="panel-shell">
      <header class="panel-header">
        <div><p>TABLE OF CONTENTS</p><h1></h1></div>
        <button id="panel-close" class="icon-button" type="button" aria-label="关闭">×</button>
      </header>
      <section class="panel-body"><div id="chapter-list" class="item-list toc-list"></div></section>
    </main>
  `;
  app.querySelector("h1").textContent = `章节目录 · ${context.book.name}`;
  document.querySelector("#panel-close").addEventListener("click", () => getCurrentWindow().close());
  const list = document.querySelector("#chapter-list");
  context.chapters.forEach((chapter, position) => {
    const index = Number.isInteger(chapter.index) ? chapter.index : position;
    const button = document.createElement("button");
    button.className = `list-item compact ${index === context.chapterIndex ? "active" : ""}`;
    button.innerHTML = `<span class="chapter-number"></span><strong></strong>`;
    button.querySelector(".chapter-number").textContent = String(index + 1).padStart(3, "0");
    button.querySelector("strong").textContent = chapter.title || `第 ${index + 1} 章`;
    button.addEventListener("click", async () => {
      button.querySelector("strong").textContent = "正在加载…";
      try {
        await invoke("load_chapter", { index, scrollToBottom: false });
        await getCurrentWindow().close();
      } catch (error) {
        button.querySelector("strong").textContent = errorMessage(error);
      }
    });
    list.append(button);
  });
  requestAnimationFrame(() => list.querySelector(".active")?.scrollIntoView({ block: "center" }));
}

invoke("get_reader_context")
  .then(render)
  .catch((error) => {
    app.innerHTML = `<main class="panel-shell"><header class="panel-header"><div><p>TABLE OF CONTENTS</p><h1>章节目录</h1></div><button id="panel-close" class="icon-button">×</button></header><p class="panel-message error"></p></main>`;
    app.querySelector(".panel-message").textContent = errorMessage(error);
    app.querySelector("#panel-close").addEventListener("click", () => getCurrentWindow().close());
  });
