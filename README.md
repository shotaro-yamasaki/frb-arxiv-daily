# FRB arXiv Daily

arXiv に毎日告知される新着論文のうち、FRB(fast radio burst)に関するものだけを拾い、サブ分野ごとにまとめて表示する自分用サイト。

- **取得**: arXiv の RSS(astro-ph 全体 + gr-qc + hep-ph + physics.plasm-ph)から `new` と `cross` だけを取得する。差し替え版(replace)は除外。
- **FRB判定**: タイトル・アブストに "fast radio burst" / "FRB" / "FRB 2024…" などが含まれるもの。
- **分類**: `config.json` のキーワード重み(タイトル一致は2倍)で11のサブ分野+その他に振り分ける。
  `ANTHROPIC_API_KEY` を設定すると、Claude が分類を見直し、英語と日本語の一行要約も付ける(任意)。表示言語に合わせて切り替わる。
- **更新**: GitHub Actions が平日の毎朝 10:17(台湾時間)に実行し、`docs/data/papers.json` を更新してコミットし、そのままサイトを公開し直す。main に push したときも実行される。
- **表示**: GitHub Pages(公開元は GitHub Actions)で `docs/` を公開する。サイトは英語が基本で、右上のボタンで日本語に切り替えられる(初回はブラウザの言語設定に合わせる)。★・既読・言語の状態はブラウザに保存される(端末ごと)。

## セットアップ

1. GitHub で新しいリポジトリ(例: `frb-arxiv-daily`)を作り、このフォルダの中身を push する。
2. **Settings → Pages**: Build and deployment の Source を "GitHub Actions" にする。
   → `https://shotaro-yamasaki.github.io/frb-arxiv-daily/` で見られる。
3. **Settings → Actions → General → Workflow permissions** を "Read and write permissions" にする。
4. 過去分を入れる: **Actions → Update FRB papers → Run workflow** で `backfill_days` に `60` などを入れて実行する。
5. (任意)日本語要約と高精度分類を使う場合: **Settings → Secrets and variables → Actions** で
   Secret `ANTHROPIC_API_KEY` を追加する。モデルを変えたいときは Variable `ANTHROPIC_MODEL` を設定する(既定は `claude-haiku-5-5`)。

## 調整

- サブ分野やキーワードは `config.json` の `subfields` を編集する(`name` が英語名、`name_ja` が日本語名)。色は `docs/index.html` の `COLORS` で変えられる。編集後は Run workflow で `reclassify` にチェックを入れると、保存済みの論文も分類し直される(LLMで分類したものは除く)。
- `watchlist` に入れた語(CHIME、BURSTT、20240114A など)を含む論文は、左端に色の帯が付き、該当語がハイライトされる。

## ローカルで試す

```bash
python scripts/fetch.py --rss-file tests/sample_rss.xml   # テスト用フィードで動作確認
python scripts/fetch.py                                   # 実際の arXiv から取得
cd docs && python -m http.server 8000                     # http://localhost:8000 で表示
```

外部ライブラリは不要(Python 3.9 以上の標準ライブラリのみ)。

## 隠し機能:Citation Radar(自分の論文の被引用)

`docs/me.html` は、自分の論文を引用した論文を毎朝まとめる自分用ページ。トップページからはリンクしていない。
トップページで(検索欄の外で)キーボードの `c` `i` `t` `e` を続けて押すと開く。直接 `…/frb-arxiv-daily/me.html` を開いてもよい。

- **新しい被引用**: NASA ADS で自分の論文を引用している論文を毎日すべて取り、前日との差分を「新規引用」として表示する。arXiv 版で引用していた論文がジャーナルに出版されたときは「ジャーナルに掲載」として表示する。自己引用には印が付く(初期設定では隠す)。
- **引用漏れ候補**: 公開から3〜30日の FRB 論文(このサイトが集めたもの)について、ADS が解析した参考文献リストを調べる。自分の論文を引用していないのに、アブストラクトの類似度が高い、または参考文献が多く重なる(書誌結合)ものを候補として出す。`ANTHROPIC_API_KEY` があれば Claude が候補ごとに「引用すべきか」を判定し、明らかに無関係なものは除く。
- **自分の論文**: 被引用数と直近30日の増加。

### 設定

1. ADS のアカウントを作り、API トークンを取得する: https://ui.adsabs.harvard.edu/user/settings/token
2. リポジトリの Settings → Secrets and variables → Actions → New repository secret で、Name `ADS_TOKEN`、Secret にトークンを入れる。
3. Actions から Run workflow を1回実行する。初回に見つかった引用は「追跡開始前」として扱い、2回目以降の差分だけを「新規」とする。
4. 「自分の論文」タブで、自分の論文が過不足なく入っているか確認する。他人の論文が混ざっていたら `config.json` の `me.exclude_bibcodes` に bibcode を、抜けている論文は `me.include_bibcodes` に足す。論文の選び方は `me.papers_query`(ORCID と著者名)で決まる。

### 注意

- GitHub Pages は公開サイトなので、`me.html` と `data/citations.json` も URL を知っていれば誰でも見られる。中身は ADS で誰でも調べられる公開情報だけ。ADS のトークンは Secret に入れるので外には出ない。
- ADS が新しい arXiv 論文の参考文献を解析するまで数日かかるため、引用の検出は arXiv 公開から少し遅れることがある。

### テスト

```bash
python tests/test_citations.py   # 偽の ADS 応答でロジックを確認(ネット不要)
```

## Transient phase space(突発天体の位相空間マップ)

`docs/phase.html`。電波の位相空間(L_ν と ν·W)と、光度と継続時間の図の2枚。拡大・ホバー・種類の切り替え・自分のモデルの重ね描き・スライド用PNGの保存ができる。

- データは `docs/data/phase.json`。FRB は CHIME/FRB Catalog 2(`data/chimefrbcat2.csv`。入手元は `data/chimefrbcat2.source`。最初は GitHub 上の写しを使い、ワークフローが公式 API(`scripts/get_chime_cat2.py`)から取得できた時点で公式ファイルに置き換えて図を作り直す)。塗りつぶしの印は母銀河の分光赤方偏移、白抜きは DM から推定した赤方偏移。
- `scripts/phase_manual.json` や `scripts/build_phase.py` を変えると、毎日のワークフローが自動で作り直す。手元では `python scripts/build_phase.py <Transient_Phase_Space> <FRBs/FRB> --cat2 data/chimefrbcat2.csv`。
- 長周期電波トランジェントと高エネルギー・光学の各種類の値は `scripts/phase_manual.json` に手で入れてある(出典つき)。新しい天体はここに足す。
- FRBs/Transient_Phase_Space のデータは GPL-3.0(E. Keane)。ページの下に出典を表示している。
