"use strict";

// Keep this feature separate from the dialogue UI so teammates can work independently.
(() => {
  const content = $("quiz-content");
  let pending = false;
  let requestVersion = 0;
  const action = (label, fn, primary = true) => {
    const b = el("button", "btn" + (primary ? " primary" : ""), label);
    b.type = "button";
    b.onclick = fn;
    return b;
  };
  const focusContent = () => {
    const heading = content.querySelector("h3");
    if (heading && !$("quiz-modal").classList.contains("hidden")) {
      heading.tabIndex = -1;
      heading.focus();
    }
  };
  async function request(path, extra = {}, feedback = false) {
    if (pending) return;
    pending = true;
    content.setAttribute("aria-busy", "true");
    const controls = [...content.querySelectorAll("button, input, select")];
    const disabled = controls.map(x => x.disabled);
    controls.forEach(x => { x.disabled = true; });
    const version = ++requestVersion;
    const player = S.player;
    try {
      const data = await api("/api/quiz/" + path, { player, ...extra });
      if (version === requestVersion && player === S.player) {
        render(data, feedback);
        focusContent();
      }
    } catch (e) {
      controls.forEach((x, i) => { x.disabled = disabled[i]; });
      if (path === "state") {
        content.replaceChildren(el("p", "", "暫時無法載入測驗，請再試一次。"), action("重新載入", () => request("state")));
      }
      handleErr(e, "小測驗：");
    } finally {
      pending = false;
      content.removeAttribute("aria-busy");
    }
  }
  function resultCard(q, answer, number) {
    const card = el("section", "quiz-review " + (answer.correct ? "quiz-correct" : "quiz-wrong"));
    card.append(el("h4", "", `${number}. ${answer.correct ? "答對" : "再留意一下"}`), el("p", "", q.prompt),
      el("p", "", "你的答案：" + q.options[answer.choice]),
      el("p", "", "參考答案：" + q.options[answer.correct_choice]), el("p", "", answer.explanation));
    if (!answer.correct && answer.confidence === 3) card.append(el("p", "quiz-insight", "這題原本很有把握，值得再讀一次解析。"));
    return card;
  }
  function render(data, feedback = false) {
    content.replaceChildren();
    const a = data.active;
    const summary = el("p", "fine", `已完成 ${data.completed_count} 次 · 最高 ${data.best_score} / 6 分`);
    content.append(summary);
    if (feedback && a && a.answers.length) {
      const index = a.answers.length - 1;
      content.append(el("h3", "", "這題的判斷"), resultCard(a.questions[index], a.answers[index], index + 1),
        action(a.completed ? "查看本次結果" : "下一題", () => { render(data); focusContent(); }));
      return;
    }
    if (!a) {
      content.append(el("h3", "", "看懂話術，也辨認正常互動"),
        el("p", "", "每次 6 題，約 3 分鐘。選擇答案與把握程度，確認後就會看到解析。每題確認後自動儲存，可隨時關閉休息。"),
        action("開始 6 題練習", () => request("start")));
      return;
    }
    if (a.completed) {
      content.append(el("h3", "quiz-score", `本次答對 ${a.score} / ${a.questions.length} 題`),
        el("p", "", "分數只反映這次情境練習，不代表你的依附類型或受騙機率。"));
      a.answers.forEach((answer, i) => content.append(resultCard(a.questions[i], answer, i + 1)));
      content.append(action("再練 6 題", () => request("start")));
      if (data.history.length) {
        const details = el("details", "quiz-review");
        details.append(el("summary", "", "最近的測驗紀錄"));
        const list = el("ul");
        [...data.history].reverse().forEach(h => list.append(el("li", "", `${new Date(h.completed_at * 1000).toLocaleString("zh-TW")}：${h.score} / ${h.total}`)));
        details.append(list); content.append(details);
      }
      return;
    }
    const index = a.answers.length, q = a.questions[index];
    content.append(el("h3", "", `第 ${index + 1} / ${a.questions.length} 題`));
    const progress = el("progress", "quiz-progress");
    progress.max = a.questions.length; progress.value = index;
    progress.setAttribute("aria-label", `已完成 ${index} 題`);
    content.append(progress, el("p", "quiz-situation", q.prompt));
    const form = el("form", "quiz-form"), options = el("fieldset", "quiz-options");
    options.append(el("legend", "", "這段互動最值得留意的是？"));
    q.options.forEach((option, i) => {
      const label = el("label", "quiz-option"), input = el("input");
      input.type = "radio"; input.name = "choice"; input.value = i; input.required = true;
      label.append(input, el("span", "", option)); options.append(label);
    });
    const confidenceLabel = el("label", "quiz-confidence", "這題你有多大把握？ ");
    const confidence = el("select"); confidence.name = "confidence"; confidence.required = true;
    [["", "請選擇"], [1, "不太確定"], [2, "有點把握"], [3, "很有把握"]].forEach(([value, title]) => {
      const option = el("option", "", title); option.value = value; confidence.append(option);
    });
    confidenceLabel.append(confidence);
    const submit = el("button", "btn primary", "確認答案"); submit.type = "submit";
    form.append(options, confidenceLabel, submit);
    form.onsubmit = e => {
      e.preventDefault();
      if (!form.reportValidity()) return;
      request("answer", { attempt_id: a.id, question_id: q.id,
        choice: Number(new FormData(form).get("choice")), confidence: Number(confidence.value) }, true);
    };
    content.append(form, el("p", "fine", "確認後不能修改；關閉後可從下一道未作答題繼續。"));
  }
  document.querySelectorAll("[data-quiz]").forEach(b => {
    b.onclick = () => {
      if (S.legacy) { legacyPrompt(); return; }
      if (!S.consentOk) {
        show("home");
        toast("請先閱讀並同意首頁的資料說明，再按「開始」進入。");
        $("consent-ok").focus();
        return;
      }
      if (!$("quiz-modal").classList.contains("hidden")) return;
      content.replaceChildren(el("p", "", "載入測驗中…"));
      openModal("quiz-modal");
      request("state");
    };
  });
})();
