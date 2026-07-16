import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import "./panel.css";

const app = document.querySelector("#app");
app.innerHTML = `
  <main class="panel-shell">
    <header class="panel-header">
      <div><p>NETWORK BOOKSHELF</p><h1>网络书架</h1></div>
      <button id="panel-close" class="icon-button" type="button" aria-label="关闭">×</button>
    </header>
    <section class="panel-body">
      <div class="toolbar"><input id="book-search" type="search" placeholder="搜索书名或作者" autocomplete="off" /><button id="book-refresh" class="secondary-button">刷新</button></div>
      <div id="book-list" class="item-list"><p class="panel-message">正在同步 Legado 书架…</p></div>
    </section>
  </main>
`;

const search = document.querySelector("#book-search");
const list = document.querySelector("#book-list");
let books = [];
let loading = false;

document.querySelector(".panel-header").addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.target.closest("button")) return;
  event.preventDefault();
  invoke("start_dragging").catch((error) => {
    list.innerHTML = `<p class="panel-message error"></p>`;
    list.firstChild.textContent = errorMessage(error);
  });
});
document.querySelector("#panel-close").addEventListener("click", () => getCurrentWindow().close());

function errorMessage(error) {
  return typeof error === "string" ? error : error?.message || String(error);
}

function renderBooks() {
  const keyword = search.value.trim().toLowerCase();
  const matches = books.filter((book) => `${book.name} ${book.author}`.toLowerCase().includes(keyword));
  list.replaceChildren();
  if (!matches.length) {
    list.innerHTML = `<p class="panel-message">没有匹配的网络书籍</p>`;
    return;
  }
  matches.forEach((book) => {
    const button = document.createElement("button");
    button.className = "list-item";
    button.innerHTML = `<strong></strong><span></span>`;
    button.querySelector("strong").textContent = book.name || "未命名书籍";
    button.querySelector("span").textContent = `${book.author || "未知作者"} · 第 ${(Number(book.durChapterIndex) || 0) + 1} 章`;
    button.addEventListener("click", async () => {
      if (loading) return;
      loading = true;
      button.querySelector("span").textContent = "正在打开…";
      try {
        await invoke("select_book", { book });
        await getCurrentWindow().close();
      } catch (error) {
        button.querySelector("span").textContent = errorMessage(error);
        loading = false;
      }
    });
    list.append(button);
  });
}

async function refresh() {
  list.innerHTML = `<p class="panel-message">正在同步 Legado 书架…</p>`;
  try {
    books = await invoke("fetch_bookshelf");
    renderBooks();
  } catch (error) {
    list.innerHTML = `<p class="panel-message error"></p>`;
    list.firstChild.textContent = errorMessage(error);
  }
}

search.addEventListener("input", renderBooks);
document.querySelector("#book-refresh").addEventListener("click", refresh);
refresh();
