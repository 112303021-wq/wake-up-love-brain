"use strict";

(() => {
  const content = $("achievements-content");
  let filter = "all", generation = 0;
  function render(data, guest) {
    content.replaceChildren();
    const intro = el("div", "achievement-overview");
    const emblem = el("div", "achievement-emblem"); emblem.append(ico("medal"));
    const summary = el("div");
    summary.append(el("h3", "", `已解鎖 ${data.unlocked_count} / ${data.total}`),
      el("p", "fine", guest ? "開始練習後，成就會自動儲存在你的玩家紀錄。" : "每一枚徽章，都來自你實際完成的練習。"));
    intro.append(emblem, summary);
    const total = el("progress", "achievement-progress");
    total.max = data.total; total.value = data.unlocked_count;
    total.setAttribute("aria-label", `成就進度：${data.unlocked_count} / ${data.total}`);
    content.append(intro, total);
    const tabs = el("div", "achievement-filters");
    tabs.setAttribute("role", "group"); tabs.setAttribute("aria-label", "篩選成就");
    for (const [key, text] of [["all", "全部"], ["unlocked", "已解鎖"], ["locked", "未解鎖"]]) {
      const button = el("button", "btn", text); button.type = "button";
      button.setAttribute("aria-pressed", String(filter === key));
      button.onclick = () => {
        filter = key; render(data, guest);
        [...content.querySelectorAll(".achievement-filters button")].find(b => b.textContent === text).focus();
      };
      tabs.append(button);
    }
    content.append(tabs);
    const visible = data.badges.filter(b => filter === "all" || b.unlocked === (filter === "unlocked"));
    if (!visible.length) content.append(el("p", "achievement-empty", filter === "unlocked"
      ? "還沒有解鎖徽章。完成一次小測驗，或實際互動後看一次覆盤，就能留下第一步。"
      : "目前所有徽章都已解鎖，可以照自己的步調繼續練習。"));
    for (const group of [...new Set(visible.map(b => b.group))]) {
      content.append(el("h3", "achievement-group", group));
      const grid = el("div", "achievement-grid");
      for (const badge of visible.filter(b => b.group === group)) {
        const card = el("article", "achievement-card" + (badge.unlocked ? " is-unlocked" : ""));
        const icon = el("div", "achievement-icon"); icon.append(ico(badge.icon));
        const status = el("span", "achievement-status", badge.unlocked ? "已解鎖" : "未解鎖");
        card.append(icon, status, el("h4", "", badge.title), el("p", "", badge.description));
        if (badge.unlocked) {
          card.append(el("p", "fine", "記錄日期：" + new Date(badge.unlocked_at * 1000).toLocaleDateString("zh-TW")));
        } else if (badge.target > 1) {
          const progress = el("progress", "achievement-progress");
          progress.max = badge.target; progress.value = badge.progress;
          progress.setAttribute("aria-label", `${badge.title}：${badge.progress} / ${badge.target}`);
          card.append(el("p", "fine", `已完成 ${badge.progress} / ${badge.target} 種角色`), progress);
        }
        grid.append(card);
      }
      content.append(grid);
    }
    content.append(el("p", "fine", "徽章會在覆盤或測驗完成時判定，重新開始一局不會清除已解鎖成就；刪除我的資料會一併清除。"));
    const refresh = el("button", "btn", "更新成就"); refresh.onclick = load;
    content.append(refresh);
  }
  async function load() {
    const id = ++generation, player = S.player;
    const guest = !S.consentOk;
    content.setAttribute("aria-busy", "true");
    content.replaceChildren(el("p", "", "載入成就中…"));
    try {
      const data = guest ? await api("/api/achievements/catalog") : await api("/api/achievements", { player });
      if (id === generation && player === S.player) render(data, guest);
    } catch (e) {
      if (id !== generation) return;
      const retry = el("button", "btn", "重新載入"); retry.onclick = load;
      content.replaceChildren(el("p", "", "成就暫時無法載入，請再試一次。"), retry);
      handleErr(e, "成就：");
    } finally {
      if (id === generation) content.removeAttribute("aria-busy");
    }
  }
  document.querySelectorAll("[data-achievements]").forEach(button => {
    button.onclick = () => {
      if (S.legacy) { legacyPrompt(); return; }
      filter = "all";
      openModal("achievements-modal");
      load();
    };
  });
})();
