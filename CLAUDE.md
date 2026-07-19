# 本仓自治规则（内容层：自停 · 自愈 · 英文泄漏自查）

TOPICS.md 是本仓选题的**唯一真相源**。以下三条每次运行都适用；trigger 的启用/停用由外部 `verify-routine-caps` 守卫按 N_pub vs N_top 统一管，**你不要去改 trigger**。

## 1. 自停（写完 TOPICS 就不再生成）
运行开头先算：
- `N_pub` = 已发布页最高编号：`ls *-day*.html` 去 `.en.html`、去前导零取最大。
- `N_top` = TOPICS.md 最大编号：`grep '^[-*#]* *Day *[0-9]+'` 取最大。

**若 N_pub ≥ N_top（TOPICS 已全部写完）**：本次**不生成任何页面、不修改 TOPICS.md、绝不自己发明新主题**；直接结束（至多发一条『world-religions 已写完 TOPICS 路线图，补充新主题后自动续写』的通知，且仅在你判断这是刚写完的当次时发，不要每次都发）。**这条优先级高于 routine prompt 里任何"超表就自造新主题"的措辞。** 新主题只由 BigCat 手动或 deep-research 反哺加进 TOPICS.md；加了之后守卫会自动重开、routine 自然续写。

## 2. 自愈（保持 TOPICS ⊇ 已发布）
**只在越界时动手**：若本期 Day 按 TOPICS 计划写、TOPICS 里本就有这行 → 不动。只有当你发布的编号是 **TOPICS.md 里没有的**（用户手动指定主题、或 deep-research 反哺内容，当时漏记进 TOPICS）时：
1. 用本期页面标题/副标题，在 TOPICS.md **末尾 append** 一行 `- Day N: <传统名> — <四维要点简列>`。
2. 与本期内容改动**一并 commit / push 到 main**。
3. **只 append，绝不修改已有行。** 否则越界页占了 `dayN`、TOPICS 缺行，日后往 TOPICS 补的 Day N 新主题会撞车永远写不出。

## 3. 英文页中文泄漏自查
生成 `*.en.html` 后、publish 前，对它 grep 这些指纹（命中=模板槽把中文漏进了英文页）：
`class="en">[一-鿿]` / `class="name-en">[一-鿿]` / `class="name-zh">[一-鿿]` / `class="cn">[一-鿿]` / `class="lang-tag">ZH`
命中就修掉（删中文节点或译成英文）再 publish。**正常情况不算泄漏**：经文/圣典原文+英译（希伯来/阿拉伯/梵/巴利+英译）、term(中文) 括注、语言切换标签『中文』、主题本身是中文的页（如涉华民间信仰的专名）。


## index 维护：roadmap-first（写时把非链接灰色占位转成链接 + 每次对齐）

本仓 `index.html` / `index.en.html` 是「路线图先出」：TOPICS.md 里**还没写**的条目已作为**非链接**灰色占位行 `<div class="entry">…</div>`（无 href）预先列出，靠 CSS 里 `a.entry` 比 `.entry` 亮自动显灰。

**写编号 N 时**：在**两个** index 里找到该 N 的非链接 `<div class="entry">` 占位行，**原地改成** `<a class="entry" href="{本期文件名}">…</a>`（照本仓已写条目的样式，如有 `live`/上线徽章就一并加上），内部结构不变。`index.html` 用中文页文件名、`index.en.html` 用 `.en.html`。**绝不要**在末尾另 append 一行——否则和占位行重复。

**每次运行先「对齐」**：运行开头先扫 `TOPICS.md`，凡是**没写**（无对应页）**且** index 里**没有对应行**的编号，按编号顺序补一条非链接 `<div class="entry">` 占位（`index.en.html` 翻成 house-style 英文、**勿泄漏中文**；`index.html` 用 TOPICS 中文裁成本仓 zh 风格）。**两个 index 都补。** 这样 BigCat / deep-research 往 TOPICS 加的新主题，下次运行会自动作为灰色条目出现；等真正写它时再原地转成链接。

## 新页面必带共享脚本（免触发 inject-comments 机器人提交）

生成任何 `*.html`（含 `.en.html`）时，在 `</body>` 前直接写入这 4 行，勿遗漏：

```html
<script src="https://hub.cissychen.com/comments.js" defer></script>
<script src="https://hub.cissychen.com/search.js" defer></script>
<script src="https://hub.cissychen.com/index-button.js" defer></script>
<script src="https://hub.cissychen.com/i18n-tts.js" defer></script>
```

这样 CI 的 inject-comments 不会再对新页面追加自动提交。
