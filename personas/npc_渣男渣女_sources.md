# 渣男渣女 NPC：紅旗行為參考來源

對應 `npc_渣男渣女_prompt.md`。每個紅旗代碼／劇情階段，標出支持它的文獻或報導，以及證據強度。

查證日期：2026-10-26。標「待查證」的項目，引用前要回原文確認。

## 一、紅旗代碼 ↔ 文獻對照

| 紅旗代碼／階段 | 支持來源 | 證據強度 |
|---|---|---|
| `no_label`（階段 3） | S1, S2, S3 | 強：有定義研究與質性訪談 |
| `breadcrumb`、`say_do_gap`（階段 2~3） | S4, S5, S6 | 強：量化樣本，有盛行率 |
| `mention_others`（同時多人曖昧） | S5, S7 | 中：S5 為線上交友使用與行為的關聯，S7 為人格特質 |
| `deny_said`、`blame_shift`（階段 4） | S8, S9, S10 | 強：S8 為預先註冊研究，S10 為實驗 |
| `guilt_trip`（階段 5） | S9, S11 | 中：S9 為質性研究；S11 為台灣官方對情緒勒索的定位 |
| `generic_praise`、`late_night_only`（階段 1~2） | S12 | 弱：僅專家焦點團體，沒有直接量化證據 |
| 曖昧對玩家的心理傷害（遊戲教育目標） | S1, S3, S13 | 中~強 |

## 二、文獻清單

### 曖昧／不定義關係

- **S1** Anderson, S., et al. (2026). *All the Feels, None of the Labels: Young Adults' Experiences of Situationships.* **Societies**. 澳洲 14 位 19–25 歲訪談。五大主題：定義混亂、情感投入失衡、科技助長迴避承諾、世代獨立價值觀、心理傷害常被認為「不算數」。
  https://consensus.app/papers/details/f326711d32305457bb0205871d39f156/
- **S2** Langlais, M. R., et al. (2024). *Defining and Describing Situationships: An Exploratory Investigation.* **Sexuality & Culture**. 28 人訪談 + 261 人問卷。situationship ＝沒有明確標籤、低承諾，但有類似伴侶的親密行為與相處時間。這個定義可直接對應階段 3 的行為設計。
  https://consensus.app/papers/details/29ff9b5503f95f33ac49d2966cc71f1e/
- **S3** Şenkal Ertürk, İ., et al. (2025). *Attachment Insecurities and Commitment: The Mediator Role of Relationship Uncertainty.* **Psychological Reports**. N = 276。依附焦慮與迴避都透過「關係不確定感」降低承諾；對焦慮型的影響更大。可解釋為什麼「不給名分」對高依附焦慮玩家殺傷力最強。
  https://consensus.app/papers/details/9aeae219b60c5eb8b52197468c241a18/

### Breadcrumbing（給一點希望就消失）

- **S4** Khattar, V., Huete, N., & Navarro, R. (2023). *Attachment insecurity and breadcrumbing engagement in young adults: a cross-sectional, cross-country study in India and Spain.* **BMC Psychology**, 11, 356. https://doi.org/10.1186/s40359-023-01404-y 
  只測「做出」breadcrumbing 的一方，沒測被害者。焦慮與迴避依附都與之正相關；印度以焦慮為主、西班牙以迴避為主。作者推測焦慮型的動機是尋求肯定，迴避型是保持距離。
  → 提醒：此研究說明「為什麼有人這樣做」，不能說成「迴避型＝渣」。
- **S5** Navarro, R., et al. (2021). *Ghosting and breadcrumbing: prevalence and relations with online dating behaviors among young adults.* **Escritos de Psicología**. 西班牙 18–40 歲。過去 12 個月約 3 成經歷或做過 breadcrumbing、約 2 成經歷或做過 ghosting；使用交友軟體、短期關係較多、線上監看行為，都提高風險。
  https://consensus.app/papers/details/2309382859bd515da3c9c9b1e4461152/
- **S6** Cobzeanu, A., et al. (2025). *Online Fairytales: Breadcrumbing and Ghosting Behavior Among Young Adults.* **Deviant Behavior**. N = 578。breadcrumbing 由道德推諉（moral disengagement）、毒性去抑制、心理困擾預測。→ 對應性格內核「替自己找理由，覺得我又沒騙你」。
  https://consensus.app/papers/details/825198cbb08b597ba5ef0c2222f7b00f/

### 多人曖昧／人格特質

- **S7** 暗黑三聯徵與出軌／短期擇偶：
  - Jones, D. N., et al. (2013). *Differential infidelity patterns among the Dark Triad.* **Personality and Individual Differences**. 三種暗黑特質皆與出軌相關，精神病態最穩定。
    https://consensus.app/papers/details/1c2bafcbde3755ff91d9db96c7778227/
  - Jonason, P. K., et al. (2009). *The Dark Triad: Facilitating a short-term mating strategy in men.* **European Journal of Personality**, 23, 5–18. doi:10.1002/per.698（作者／年份依我記憶，Consensus 欄位顯示 N/A，**待查證**）
  - **設計提醒**：prompt 把角色定位成「不是邪惡的人，會替自己找理由」，與暗黑三聯徵（精神病態、馬基維利主義）不是同一類。這組文獻只拿來支持「同時多人」的現實性，**不要**把 NPC 寫成病態人格。

### 否認、反咬、情緒勒索（階段 4~5）

- **S8** March, E., et al. (2023). *"It's All in Your Head": Personality Traits and Gaslighting Tactics in Intimate Relationships.* **Journal of Family Violence**. N = 315，預先註冊。gaslighting 手法包含誤導、否認、說謊、反駁，目的是讓對方動搖；男性對這些手法的接受度較高。→ 對應 `deny_said`（「我有說過嗎？」）。
  https://consensus.app/papers/details/33a3394f8b285b8a9850491f44be0894/
- **S9** Klein, W., et al. (2023). *A qualitative analysis of gaslighting in romantic relationships.* **Personal Relationships**. N = 65。gaslighting 常出現在「親密與傷害交錯」的關係中；後果為自我感下降、對他人不信任。
  https://consensus.app/papers/details/bc43064350465743ba753c67125cb036/
- **S10** Harsey, S. J., et al. (2020). *Deny, Attack, and Reverse Victim and Offender (DARVO): What Is the Influence on Perceived Perpetrator and Victim Credibility?* **Journal of Aggression, Maltreatment & Trauma**. 兩個實驗（N = 316、360）：接觸 DARVO 的人覺得被害者較不可信、較該負責；**事先學過 DARVO 的人受影響較小**。→ 這是遊戲「教育價值」最有力的依據：辨識能降低效果。階段 4「反咬」就是 DARVO 的簡化版。
  https://consensus.app/papers/details/40283c3e8caa5488960f772f66bedaa8/

### 台灣脈絡（報導／官方）

- **S11** 衛福部親密關係暴力相關記者會報導（2026-06，經 NOWnews 轉載；**待查證原文**）。報導內容：精神暴力約占親密關係暴力案件 49%；情緒勒索被列為恐怖情人常見特徵之一。
  https://www.nownews.com/news/6847938 （搜尋結果標示為相關報導，連結內文我未逐字確認）
  官方頁面：https://mohw.gov.tw/cp-16-86960-1.html
- **S13** 報導者專題「青少年約會暴力」。引述學者研究：大專生中精神暴力最常見（55.5%）、肢體暴力 18.6%、性暴力 7.6%。**此數字在報導中的原始研究出處我沒追到，引用前待查證**。
  https://www.twreporter.org/topics/dating-violence-among-youth

### 弱證據（不建議當主要依據）

- **S12** Burrell, D. N. (2026). *Digital Trauma as a Health Safety and Security Risk: The Impact of Love Bombing and Breadcrumbing...* **Safety and Security Advances**. 僅為專家焦點團體的質性研究，可輔助說明「過度讚美 → 間歇性關注」的模式，不足以支撐單一紅旗。
  https://consensus.app/papers/details/c7e2842abdc056de9d6f02da6d22d817/

## 三、尚未找到的缺口

1. **台灣本土「曖昧／備胎」實證研究**：中文關鍵字搜尋只找到依附風格與失戀調適，沒有直接研究。要補的話可查華藝（airiti）、臺灣博碩士論文網。
2. **具名新聞案例**：這次沒有找到可驗證的單一案例，我不編造。若要加案例，建議挑 2~3 則主流媒體的約會暴力／情緒勒索報導，逐則查證後再入檔。
3. **love bombing 的同儕審查實證**：目前只找到小型質性研究。

## 四、使用建議

- 遊戲內 NPC **不要引用**文獻（不符合 LINE 口吻）。本檔用於：結算頁「為什麼這是紅旗」說明、期末報告／簡報的設計依據、後台 `red_flags` 代碼說明。
- 若要讓 Claude API 的 NPC 更貼近文獻，把「S2 的 situationship 定義」與「S10 DARVO 三步驟」濃縮成 3~5 行加進 prompt，不要貼整份。
