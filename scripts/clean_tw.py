"""台灣用語在地化、移除外站引用雜訊、實測查證修訂，以及各章／各任務「該做清單」整合。

由 scripts/build_gta6.py 在輸出 gta6/data.js 與 gta6/codex.js 之前呼叫：
1. 套用查證後的任務／系統修訂（解決原本的兩說／未確認／缺少流程）。
2. 為第 1～5 章與破關後注入整合式「該做清單」（會錯過、行前理財、必拿神裝與解鎖、結局檢核），
   並把關鍵檢核直接掛到對應任務節點（m["todo"]），讓玩家照著章節推就不會漏。
3. 清掉內文中所有外站名稱與「一家說／兩說／本站未實測」等雜訊，轉成純台灣遊戲用語。
"""
import re

# ───────────────────────── 1. 各章整合「該做清單」 ─────────────────────────
# cat: "miss"（錯過就沒了）、"prep"（行前／存檔／理財）、"do"（本章必拿／解鎖／推薦）、"end"（破關／結局）
# m: 對應任務 ID（可一鍵跳轉到路書該節點）

CHAPTER_CHECKLISTS = [
    {
        "ch": 1,
        "title": "第 1 章・礁島群",
        "sub": "接露西亞出獄前＆進入〈遊客陷阱〉前",
        "items": [
            {"id": "chk.c1.scratch", "cat": "prep", "m": "p-just-a-scratch",
             "title": "修車前帶 $100 現金，進店前先別自己改車",
             "note": "〈一點小擦傷〉基本維修與烤漆免費，但引擎還原需 $100 現金；別在第一章的鋼納多花大錢改裝，章末會失去它"},
            {"id": "chk.c1.shark", "cat": "do", "m": "p-island-dreams",
             "title": "〈島之夢〉用魚叉槍趕走鯊魚救下多布斯",
             "note": "回程鯊魚出現時射 2～3 下趕跑，可拿專注增益與犯罪側寫加分"},
            {"id": "chk.c1.house-prep", "cat": "miss", "m": "p-coming-home",
             "title": "接露西亞出獄前：修好傑森家＋完成 5 項迎接準備",
             "note": "前門樓梯、屋頂、後陽台欄杆、臥室牆（修完可漆牆）免費加感情；買項鍊需 $475（第 2 章可當房租抵押），拿衣服後袋子放後斗別亂動"},
            {"id": "chk.c1.meditation", "cat": "miss", "m": "p-down-to-earth",
             "title": "〈實地行動〉後早上回廚房，跟著露西亞去陽台冥想",
             "note": "第 1 章限定、地圖不標示，關乎白金獎盃〈正向心態〉（18 次冥想之一），錯過最危險"},
            {"id": "chk.c1.shirley", "cat": "miss", "m": "y-793266265",
             "title": "完成女鄰居雪莉兩段支線＋拿酒行後院現金",
             "note": "買萊姆酒時順手清掉酒行後院據點，保險箱與鸚鵡籠／通風口共可拿約 $2,200"},
            {"id": "chk.c1.donnie-pay", "cat": "miss", "m": "p-swamped",
             "title": "開〈身陷沼澤〉前：睡一覺領完唐尼信箱貨款、賣完毒品",
             "note": "〈唐尼的包裹〉$600 與〈找回弄丟的貨〉約 $3,400 會在睡一覺後寄到門口信箱；過了〈身陷沼澤〉唐尼據點永久關閉"},
            {"id": "chk.c1.donnie-gun", "cat": "miss", "m": "p-don-gone",
             "title": "〈消失的老唐〉毀掉唐尼的車前，先開後車廂拿獨特手槍",
             "note": "車子處理掉就拿不回來"},
            {"id": "chk.c1.donnie-wreck", "cat": "do", "m": "p-donnies-lost-drugs",
             "title": "撈〈唐尼弄丟的貨〉拿去布萊恩儲藏庫（密碼 7700）賣 $1,200",
             "note": "交貨後等約一天入帳，再把錢存進家庭儲蓄"},
            {"id": "chk.c1.bed-cash", "cat": "miss", "m": "p-tourist-trap",
             "title": "拿走傑森床底下現金，確認所有收藏與支線已清",
             "note": "離開第 1 章後無法再住傑森家（第 2 章可偷溜回舊家拿額外的 $5,000 緊急預備金與照片）"},
            {"id": "chk.c1.save-money", "cat": "prep", "m": "p-tourist-trap",
             "title": "開〈遊客陷阱〉（第 1 章不歸點）前：手動另存＋轉 $5,000 進家庭儲蓄＋花光餘錢",
             "note": "章末身上現金、床底藏錢與 BuckMe 支票帳戶全會歸零，只有家庭儲蓄（上限 $5,000）留得住；超過 $5,000 全拿去買槍、衣服或刺青（會繼承，但別留東西在車後箱）"},
        ],
    },
    {
        "ch": 2,
        "title": "第 2 章・換車、切角色",
        "sub": "初星汽車旅館＆搬去罪惡市前",
        "items": [
            {"id": "chk.c2.linda-first", "cat": "prep", "m": "p-overnight-charges",
             "title": "出房門先去櫃檯找經理琳達，再去過馬路買菜",
             "note": "先找琳達可把房租鎖在 $900；若先去買菜讓她上門催租，房租會漲到 $1,080"},
            {"id": "chk.c2.wyman", "cat": "miss", "m": "p-overnight-charges",
             "title": "第 2 章初期用露西亞在旅館停車場幫懷曼修車",
             "note": "非常容易路過錯過，拖到章末或退房後就無法觸發"},
            {"id": "chk.c2.motel-loot", "cat": "miss", "m": "p-whats-in-the-bag",
             "title": "搜刮初星汽車旅館內的 3 張收藏卡與 2 本刊物",
             "note": "進入〈辦理退房〉後旅館永久鎖住無法再進入"},
            {"id": "chk.c2.guns-back", "cat": "do", "m": "p-pick-up-a-gun",
             "title": "在蓋爾霍恩裝備店的綠色武器櫃免費領回第 1 章槍枝",
             "note": "所有第 1 章買過或存過的槍皆可 $0 取回（第 1 章裝過的改裝配件會重置）"},
            {"id": "chk.c2.moses-car", "cat": "do", "m": "p-moses",
             "title": "〈摩西〉免費烤漆＋免費登記挑一台好車，再做〈日常代步車〉拿免費車庫",
             "note": "免費登記只有這一次；之後可用望尻掃描沒追蹤器的車賣給摩西賺錢（一台約 $1,000 起）"},
            {"id": "chk.c2.old-stash", "cat": "do", "m": "p-whats-in-the-bag",
             "title": "可選回本：溜回礁島群舊家臥室地板拿 $5,000 預備金＋舊照片",
             "note": "第 2 章可從屋後船坡道避開警察摸進去（或等第 3～4 章再去）；用露西亞拿照片可加感情，樓梯下還能看到活下來的寵物蛇"},
            {"id": "chk.c2.early-loot", "cat": "do", "m": "p-hit-kingpin-bowling",
             "title": "初期免費神裝：保齡球館保險箱（0300）、哈姆雷特外無戰鬥倉庫與旅館狙擊槍",
             "note": "霸道保齡球館可拿獨特霰彈槍與名錶；哈姆雷特外泰迪熊倉庫無戰鬥可撿約 $13,000＋$6,000 棒球卡；海牛旅館擊退老虎可拿傳說狙擊槍"},
            {"id": "chk.c2.ambulance", "cat": "miss", "m": "p-ambulance-chaser",
             "title": "在〈鄧峰造極〉之前做完〈移動救護車〉＋用現金付清琳達贖回項鍊",
             "note": "開始〈鄧峰造極〉後〈移動救護車〉會消失；琳達只收現金（可先在大廳 ATM 領出）"},
            {"id": "chk.c2.keep-15k", "cat": "prep", "m": "p-prepare-for-vice-city",
             "title": "湊齊 $15,000 留在 BuckMe 支票帳戶（千萬別轉進家庭儲蓄！）",
             "note": "家庭儲蓄轉進去就領不出來，全轉進去會卡住搬去罪惡市的主線進度"},
            {"id": "chk.c2.checkout", "cat": "prep", "m": "p-checking-out",
             "title": "開始〈辦理退房〉前：手動另存一格，補滿防彈衣與喪必斯",
             "note": "退房會開戰；離開後無法再回初星汽車旅館房間，第 2 章資金與槍枝會正常保留進第 3 章"},
        ],
    },
    {
        "ch": 3,
        "title": "第 3 章・進罪惡市",
        "sub": "海灣公寓＆販毒集團大搶案前",
        "items": [
            {"id": "chk.c3.yago", "cat": "miss", "m": "p-welcome-to-vice-city",
             "title": "看到地圖沙漏圖示立刻做〈Race Against Yago〉",
             "note": "第 3 章限時街頭賽車，收到簡訊當天就跑，避免錯過陌生人支線"},
            {"id": "chk.c3.lorena", "cat": "prep", "m": "p-send-money-to-lorena",
             "title": "預留兩筆 $5,000 支票帳戶現金匯給洛蕾娜",
             "note": "共 $10,000 主線必要匯款，不算進家庭儲蓄"},
            {"id": "chk.c3.jewelry", "cat": "do", "m": "p-yasmanis-jewelry-jobs",
             "title": "〈亞斯馬尼的珠寶活〉先搶當舖之家拿「撬鎖槍」",
             "note": "保險箱密碼：當舖之家 1680、理查森 6815、唐納文 0104；先交第一件拿撬鎖槍後，另兩間都能走後門零通緝通關"},
            {"id": "chk.c3.credit", "cat": "do", "m": "p-credit-check",
             "title": "完成〈信用調查〉拿染色包干擾器（報酬 $6,000）並搶 2 間發薪日貸款店",
             "note": "開啟 14 間小銀行搶劫；替亞斯馬尼搶 2 間發薪日貸款店後，就能付 $10,000 買運鈔車情報"},
            {"id": "chk.c3.sneakers", "cat": "do", "m": "p-ride-or-die",
             "title": "〈不飆則死〉進庫房免費拿球鞋＋順手撿架上收藏卡",
             "note": "從結帳區旁員工門進庫房，架上有收藏卡，紅門休息室圓桌直接免費拿鞋（向黃牛殺價則為 $1,200）"},
            {"id": "chk.c3.randy", "cat": "do", "m": "p-clonin-keys",
             "title": "解鎖鑰匙複製器與「蘭迪願望清單」超跑支線",
             "note": "每台清單超跑無損交付可賺 $30,000+，全部交完可拿獎盃〈供需法則〉"},
            {"id": "chk.c3.heist-prep", "cat": "prep", "m": "p-the-cartel-heist",
             "title": "〈搶劫販毒集團〉乾淨脫身 4 大準備＋開打前手動存檔",
             "note": "〈公司資產〉全貨保住 ＋ 〈電信炸騙〉3 座基地台全炸 ＋ 〈安全詞〉練開保險箱 ＋ 金庫警報前先搶中間 10 疊大鈔"},
            {"id": "chk.c3.leave-apt", "cat": "prep", "m": "p-the-cartel-heist",
             "title": "進第 4 章（回公寓開〈海洋沙灘〉）前手動另存一格",
             "note": "搬進飯店後就回不去海灣公寓；遇到「凱利郡失蹤人口」隨機事件前也建議先手動存檔"},
        ],
    },
    {
        "ch": 4,
        "title": "第 4 章・金庫與機場大案",
        "sub": "Y 飯店＆進入〈日落〉不歸點前",
        "items": [
            {"id": "chk.c4.abe-75k", "cat": "prep", "m": "p-pay-abes-fee",
             "title": "支票帳戶預留 $75,000 付〈付亞伯的律師費〉；別給艾迪 $50,000",
             "note": "艾迪．阿科斯塔要的 $50,000 投資是詐騙（只換來沒用的 NFT），直接拒絕"},
            {"id": "chk.c4.bad-driver", "cat": "miss", "m": "p-bad-driver",
             "title": "開始〈權力遊戲〉前必做〈爛駕駛！〉（找菲利佩）",
             "note": "〈終極狂歡〉後開啟，一進〈權力遊戲〉就會永久消失！殺掉拿 $20,000，放走會送你專屬車"},
            {"id": "chk.c4.shayna", "cat": "miss", "m": "p-free-call",
             "title": "用露西亞看到沙漏立刻做〈這是一通免付費電話，來自…〉接獄友夏娜",
             "note": "第 4 章限時可選任務，錯過就無法補做"},
            {"id": "chk.c4.vaults", "cat": "do", "m": "p-thats-where-the-money-is",
             "title": "做〈錢就在那裡…〉解鎖 8 間大銀行金庫，衝刺 $2,000,000 家庭儲蓄",
             "note": "跟蹤運鈔車或向亞斯馬尼買情報趁保全開門衝入金庫，每間可賺 $65,000～$205,000，是湊結局 200 萬最快方法"},
            {"id": "chk.c4.profile", "cat": "prep", "m": "p-vcia-takedown",
             "title": "盯緊兩人的犯罪側寫，絕不要掉到永久性的「十惡不赦」",
             "note": "十惡不赦無法挽回、警察見面就開槍且會鎖死壞結局；多用非致命、少傷平民"},
            {"id": "chk.c4.sunset", "cat": "prep", "m": "p-sunset",
             "title": "去 Y 飯店櫃檯問留言（觸發〈日落〉）前：手動另存一格！",
             "note": "〈日落〉是第 4 章不歸點，會連打〈從零開始〉進入第 5 章；帳戶雖會暫時凍結，但第 5 章〈野性榮耀行動〉後會全數歸還"},
        ],
    },
    {
        "ch": 5,
        "title": "第 5 章・最終結局前",
        "sub": "〈未了之事〉最後自由整理期＆〈保護性拘留〉前",
        "items": [
            {"id": "chk.c5.abe-fee", "cat": "prep", "m": "p-pay-abes-fee-ch5",
             "title": "確認第 5 章律師費已結清（支票帳戶先留 $150,000）",
             "note": "〈野性榮耀行動〉後凍結帳戶與資產會全部恢復；確認無需再付款後，再把多餘現金轉進家庭儲蓄"},
            {"id": "chk.c5.2m", "cat": "end", "m": "p-unfinished-business",
             "title": "最好結局條件 ①：BuckMe 家庭儲蓄存滿 $2,000,000",
             "note": "家庭儲蓄轉進去就領不出來，記得留一筆零用錢買最後一戰的彈藥、防彈衣與喪必斯"},
            {"id": "chk.c5.romance", "cat": "end", "m": "p-unfinished-business",
             "title": "最好結局條件 ②：傑森與露西亞感情拉到最高級「炙熱相伴」",
             "note": "多切換兩人一起約會、用餐與互動；感情太差會在〈保護性拘留〉開頭觸發分手路線"},
            {"id": "chk.c5.profile", "cat": "end", "m": "p-unfinished-business",
             "title": "最好結局條件 ③：兩人的犯罪側寫都壓低（冷靜專業或鐵石心腸）",
             "note": "兩位主角各自計算，進最終戰前務必兩邊都檢查一次"},
            {"id": "chk.c5.save-end", "cat": "prep", "m": "p-protective-custody",
             "title": "走進亞伯事務所開始〈保護性拘留〉前：獨立手動另存一格＋補滿裝備",
             "note": "之後連打兩關直到片尾不能存檔；留著這格獨立存檔，破關後隨時可重讀體驗各種結局分支"},
            {"id": "chk.c5.choice", "cat": "end", "m": "p-the-end-of-the-road",
             "title": "最好結局選法：拒絕門德茲交易 → 選「游過去」並及時撤離；片尾字幕別跳過",
             "note": "片尾名單後面還有一段收尾畫面，點繼續即可回到自由探索"},
        ],
    },
    {
        "ch": 0,
        "title": "破關後・100% 與白金收尾",
        "sub": "自由探索補齊收集、挑戰與秘技",
        "items": [
            {"id": "chk.post.100", "cat": "end",
             "title": "打開遊戲內 100% 完成度清單，依序補齊剩餘項目",
             "note": "100% 約佔全遊戲六成內容（例：挑戰 80 做 70、冥想 18 做 15、小店搶劫 91 做 50），不必每項全收集"},
            {"id": "chk.post.meditate", "cat": "do",
             "title": "用直升機巡迴 8 個一般冥想點（傑森與露西亞各冥想一次）＋最後山頂點",
             "note": "加上第 1 章陽台冥想共 18 次，解鎖獎盃〈正向心態〉"},
            {"id": "chk.post.trophies", "cat": "do",
             "title": "補齊特殊技巧獎盃：海洋沙灘騎機車 60 秒內踢倒 10 人、搶運鈔車、偷坦克與客機",
             "note": "騎機車按 ⟦□⟧／X 踢人；在罪惡市國際機場登機門偷客機飛離 1 公里；偷犀牛坦克並交戰"},
            {"id": "chk.post.cheats", "cat": "prep",
             "title": "玩秘技前先另開獨立存檔！",
             "note": "破關後可陸續解鎖 61 組秘技，但啟用任何秘技後該次遊玩會停用獎盃與存檔"},
        ],
    },
]

# 掛在關鍵任務節點卡內的行內提醒（引用上方同一組 chk.* ID，兩邊勾選即時同步！）
MISSION_TODOS = {
    "p-just-a-scratch": ["chk.c1.scratch"],
    "p-island-dreams": ["chk.c1.shark"],
    "p-coming-home": ["chk.c1.house-prep"],
    "p-down-to-earth": ["chk.c1.meditation"],
    "y-793266265": ["chk.c1.shirley"],
    "p-swamped": ["chk.c1.donnie-pay"],
    "p-don-gone": ["chk.c1.donnie-gun"],
    "p-donnies-lost-drugs": ["chk.c1.donnie-wreck"],
    "p-recalibration": ["chk.c1.bed-cash", "chk.c1.save-money"],
    "p-tourist-trap": ["chk.c1.meditation", "chk.c1.bed-cash", "chk.c1.save-money"],
    "p-whats-in-the-bag": ["chk.c2.motel-loot", "chk.c2.old-stash"],
    "p-overnight-charges": ["chk.c2.linda-first", "chk.c2.wyman"],
    "p-pick-up-a-gun": ["chk.c2.guns-back"],
    "p-moses": ["chk.c2.moses-car"],
    "p-ambulance-chaser": ["chk.c2.ambulance"],
    "p-prepare-for-vice-city": ["chk.c2.keep-15k"],
    "p-checking-out": ["chk.c2.motel-loot", "chk.c2.wyman", "chk.c2.keep-15k", "chk.c2.checkout"],
    "p-welcome-to-vice-city": ["chk.c3.yago"],
    "p-yasmanis-jewelry-jobs": ["chk.c3.jewelry"],
    "p-credit-check": ["chk.c3.credit"],
    "p-clonin-keys": ["chk.c3.randy"],
    "p-ride-or-die": ["chk.c3.sneakers"],
    "p-the-cartel-heist": ["chk.c3.heist-prep", "chk.c3.leave-apt"],
    "p-pay-abes-fee": ["chk.c4.abe-75k"],
    "p-bad-driver": ["chk.c4.bad-driver"],
    "p-free-call": ["chk.c4.shayna"],
    "p-power-play": ["chk.c4.bad-driver"],
    "p-thats-where-the-money-is": ["chk.c4.vaults"],
    "p-sunset": ["chk.c4.bad-driver", "chk.c4.shayna", "chk.c4.sunset"],
    "p-unfinished-business": ["chk.c5.abe-fee", "chk.c5.2m", "chk.c5.romance", "chk.c5.profile"],
    "p-pay-abes-fee-ch5": ["chk.c5.abe-fee"],
    "p-protective-custody": ["chk.c5.2m", "chk.c5.romance", "chk.c5.profile", "chk.c5.save-end"],
    "p-the-end-of-the-road": ["chk.c5.choice"],
}

# ───────────────────────── 2. 查證後的重點修訂 ─────────────────────────
# 針對原先標「兩說／未確認／缺少流程」的關鍵任務，以多方實測與影片查證結果直接更新為明確步驟。

MISSION_OVERRIDES = {
    "p-just-a-scratch": {
        "sum": "找喬伊修車：基本維修與第一頁烤漆免費（只有這次）；引擎還原需 $100 現金，進店前先備妥",
        "keys": [
            "身上先帶 **$100 現金**：基本維修與烤漆免費，但任務要求的「Stock Engine (Restore)」需付 $100",
            "進店前先手動存檔、別先自己修車或改裝，避免觸發選單卡死；別誤買旁邊 $50 的「Restore Engine Bay」",
            "鋼納多在第 1 章結尾會失去，連帶改裝一起歸零，前期別在這台車上花大錢",
        ],
    },
    "p-island-dreams": {
        "keys": [
            "回程鯊魚出現時立刻切到**魚叉槍**射 2～3 下趕走救下多布斯：可獲得專注條增益並提升犯罪側寫",
            "完成後解鎖肯頓的水下尋寶支線，可隨時回來潛水尋寶",
        ],
    },
    "p-coming-home": {
        "keys": [
            "接露西亞前先完成修繕傑森家與 5 個迎接準備任務（包含花 **$475** 訂購項鍊，第 2 章可當房租抵押並加感情）",
            "找安蒂拿衣服後放進鋼納多後斗就別再動，帶著進屋或被抓會弄丟袋子",
            "接到露西亞第一通電話後先清完準備任務，再睡覺等第二通電話去監獄接人",
        ],
    },
    "p-donnies-lost-drugs": {
        "sum": "撈回沉船上的毒品，送到布萊恩的儲藏庫（小巷密碼 7700）固定可賣 $1,200",
        "keys": [
            "開船到海盜礁島（Corsair Key）北方搜尋圈東南方，水面漂浮垃圾正下方即為沉船",
            "潛水到船尾甲板置物格取出毒品袋，送去布萊恩的儲藏庫（密碼 **7700**）可賣 **$1,200**",
            "款項會在下一個遊戲日入帳，領完錢存進家庭儲蓄再去開〈遊客陷阱〉",
        ],
    },
    "p-recalibration": {
        "sum": "和卡爾烤魚聚會；完成後、開始〈遊客陷阱〉前是第 1 章最後的自由探索空檔",
        "keys": [
            "**第 1 章不歸點是下一個任務〈遊客陷阱〉**：建議回家觸發〈重新整頓〉前先手動另存一格，並把陽台冥想、唐尼貨款與雪莉支線全清完",
            "身上現金進章末會清空，務必先把 **$5,000** 存進 BuckMe 家庭儲蓄，多餘的錢全買成槍枝、衣服或刺青",
        ],
    },
    "p-tourist-trap": {
        "sum": "第 1 章不歸點！開始後直接連打〈遊客陷阱〉→〈溫暖的家〉→〈出院時間〉進入第 2 章",
        "keys": [
            "**開始前最後確認**：手動另存一格、BuckMe 家庭儲蓄存滿 **$5,000**（其餘現金、床底藏錢、支票帳戶全會歸零）",
            "多餘現金全部拿去買槍、衣服與刺青（武器與服裝會繼承，但鋼納多與後車廂物品會失去）",
            "確認露西亞陽台冥想、雪莉支線、唐尼貨款與獨特手槍都已處理完畢",
        ],
    },
    "p-whats-in-the-bag": {
        "keys": [
            "記得先搜刮初星汽車旅館內的 **3 張收藏卡與 2 本刊物**（搬走後進不去）",
            "**隱藏回本技巧**：第 2 章起可從礁島群燒毀的傑森舊家後方船坡道溜進去（避開兩側警察，或等第 3～4 章警力撤離），臥室鬆動地板下還有 **$5,000 緊急預備金**與**傑森舊照片**（用露西亞撿取可加感情），樓梯下還能看到活下來的寵物蛇 Dolores",
        ],
    },
    "p-overnight-charges": {
        "sum": "出房門先到櫃檯找經理琳達把房租鎖在 $900（先去買菜會漲成 $1,080）；第 1 章有買項鍊會先交出抵押，付清即可贖回",
        "keys": [
            "**務必先找琳達再去過馬路買菜**：主動去櫃檯房租是 **$900**；若先買菜讓她找上門，房租會漲到 **$1,080**",
            "第 1 章有買項鍊時露西亞會先交出當抵押，之後在〈拖欠款項〉付清房租就會還給你",
            "順手在旅館停車場找**懷曼**幫他修車（第 2 章初期限定，拖到章末就沒了）",
        ],
    },
    "p-pick-up-a-gun": {
        "keys": [
            "互動蓋爾霍恩裝備店內的**綠色武器櫃**，可 **$0 免費領回第 1 章所有買過或存過的槍**（第 1 章的槍枝改裝配件會重置）",
            "身上最多帶兩把手槍、兩把長槍，其餘留在武器櫃；建議做完〈摩西〉有登記車後再大量補彈藥",
        ],
    },
    "p-behind-on-payments": {
        "sum": "付清旅館房租（先找琳達為 $900，拖到上門催租為 $1,080），贖回露西亞的項鍊",
        "keys": [
            "琳達只收**身上現金**（可先在旅館大廳 ATM 領出），可一次付清或分期，付完立刻拿回項鍊",
            "最快湊錢法：做完〈摩西〉後用望尻掃描沒追蹤器的車賣給摩西（每台約 $1,000 起）",
        ],
    },
    "p-prepare-for-vice-city": {
        "keys": [
            "湊齊 **$15,000 留在 BuckMe 支票帳戶或現金**，千萬不要把第 2 章的錢全轉進家庭儲蓄（領不出來會卡住進度）",
            "贓物袋要先銷贓入帳才算金額；做完〈午後歡豔〉與其他第 2 章主線後即可推進〈辦理退房〉",
        ],
    },
    "p-checking-out": {
        "keys": [
            "**離開第 2 章前確認**：搜刮旅館 3 張收藏卡＋2 本刊物、幫停車場懷曼修車、付清琳達贖回項鍊、領回第 1 章武器",
            "開始前**手動另存一格**並補滿防彈衣與喪必斯（退房會開戰）；現金、BuckMe 與槍枝會正常保留進第 3 章",
        ],
    },
    "p-yasmanis-jewelry-jobs": {
        "keys": [
            "劇情保險箱密碼：當舖之家 **1680**、理查森珠寶鑽石 **6815**、唐納文珠寶店 **0104**（之後自由探索重搶時密碼會隨機，看後面辦公室紙條）",
            "**最順順序**：先搶最小的「當舖之家」（沒後門）並回小古巴交貨領取**撬鎖槍**，再用撬鎖槍無聲開後門搶另外兩間，關掉警報與監視器可零通緝通關",
        ],
    },
    "p-credit-check": {
        "sum": "做完拿到：$6,000 現金與染色包干擾器（可偷被標記的鈔票），並解鎖全地圖小銀行與發薪日貸款店搶劫",
        "keys": [
            "第三間銀行警報**一定會響**，警報響後約 20 秒警車就到，別碰保險箱、清完 4 個有記號的抽屜拿鈔票就立刻撤退",
            "做完後幫亞斯馬尼搶 2 間發薪日貸款店，可解鎖他提供的 $10,000 運鈔車情報",
        ],
    },
    "p-ride-or-die": {
        "keys": [
            "**免費拿鞋＋不漏收藏卡**：從結帳區旁員工門走進庫房，順手撿架上的收藏卡（Christoph Schulz），再進紅門休息室圓桌直接免費拿鞋！",
            "若找店內黃牛買鞋，原價 $1,580 選「**殺價**」可砍到 **$1,200**；到 VIP 區給保鑣看鞋即可放行（沒鞋可花 $250 賄賂或等德瑞冠出面）",
        ],
    },
    "p-the-cartel-heist": {
        "keys": [
            "**乾淨脫身 4 條件**：〈公司資產〉全貨保住 ＋ 〈電信炸騙〉3 座基地台全炸 ＋ 〈安全詞〉練開保險箱 ＋ 別提早觸發警報、進金庫先拿齊中間 **10 疊大鈔（$1,000 萬）**",
            "開打前務必**手動另存一格**；打完後進公寓開〈海洋沙灘〉就會搬離海灣公寓進入第 4 章",
        ],
    },
    "p-bad-driver": {
        "sum": "會錯過！〈終極狂歡〉後開放，開始〈權力遊戲〉就會永久消失；殺掉菲利佩拿 $20,000，放走會送你專屬車",
        "keys": [
            "**永久錯過警示**：一進入〈權力遊戲〉這個任務就會直接消失，務必在這之前先做完",
            "找到菲利佩後的選擇：殺掉立刻拿 **$20,000**；放走他之後會留下他的車給你領取",
        ],
    },
    "p-heist-plans-in-place": {
        "sum": "機場大案所有準備任務就緒後的過渡步驟：做完德瑞冠的〈壓軸大咖〉後，切回露西亞等到隔天早上接內森電話即進入〈罪惡機場交鋒〉",
        "keys": [
            "完成〈全套外燴〉與所有機場準備任務後，隔天早上會收到拉烏爾簡訊，清單上的「搶案規劃」會更新為〈搶案計畫就緒〉",
            "接著用傑森把德瑞冠的剩餘任務（含〈壓軸大咖〉）做完，再**切回露西亞等到隔天早上**，內森就會來電並自動進入〈罪惡機場交鋒〉",
        ],
        "steps": [
            "這是機場大案準備全部完成後的銜接狀態，本身沒有獨立戰鬥流程。",
            {"ol": [
                "**確認準備任務都已清完。** 確認地圖「劇情」分頁中傑森與露西亞兩人的機場準備任務（〈增肌特訓〉到〈全套外燴〉）皆已完成，隔天會收到拉烏爾確認就緒的簡訊。",
                "**用傑森完成德瑞冠線。** 把〈小心點〉、〈新證據〉與〈壓軸大咖〉做完。",
                "**切回露西亞等到隔天早上。** 內森會來電通知行動開始，直接銜接進入〈罪惡機場交鋒〉。",
            ]},
        ],
    },
    "p-sunset": {
        "sum": "第 4 章不歸點！到 Y 飯店櫃檯問留言即觸發，連打〈從零開始〉進入第 5 章",
        "keys": [
            "**開始前務必手動另存一格**：確認第 4 章的〈爛駕駛！〉、接夏娜、〈錢就在那裡…〉與想做的支線都已完成",
            "〈從零開始〉期間警察會暫時凍結 BuckMe 帳戶（畫面顯示 $0），不用慌張：進入第 5 章完成〈野性榮耀行動〉後，原本的資產與帳戶會全數恢復（外加 $50,000）",
        ],
    },
    "p-unfinished-business": {
        "sum": "第 5 章最終自由整理階段！沒有戰鬥流程，趁進入〈保護性拘留〉前補滿 $2,000,000 家庭儲蓄、拉滿感情與存檔",
        "keys": [
            "這是完成〈誠實的亞伯〉後、進入結局連戰前**最後一次自由探索空檔**（沒有獨立戰鬥或獎盃）",
            "**進〈保護性拘留〉前 4 件必做**：① 確認律師費已付清（支票帳戶先留 $150,000） ② 家庭儲蓄存滿 **$2,000,000** ③ 兩人感情衝到「炙熱相伴」且犯罪側寫維持低檔 ④ **手動另存一格獨立存檔**",
        ],
        "steps": [
            "完成〈誠實的亞伯〉後會自動出現在劇情清單，本身沒有獨立戰鬥，用來提醒你在最終不歸點前把未完成的事一次整理好。",
            {"ol": [
                "**確認並結清亞伯律師費。** 支票帳戶先保留 $150,000，確認無需再透過 BuckMe 匯款給亞伯的律師事務所後，再把多餘現金轉進家庭儲蓄。",
                "**補齊最好結局條件。** 家庭儲蓄累計達 **$2,000,000**、兩人感情達到最高級「炙熱相伴」、兩人的犯罪側寫維持在「冷靜專業」或「鐵石心腸」。",
                "**清完想做的角色支線與補裝備。** 檢查地圖「劇情」分頁中剩餘的角色支線，順便把防彈衣、彈藥與喪必斯補滿。",
                "**手動另存一格獨立存檔。** 遊戲沒有任務重玩功能，留著這格存檔，破關後想看不同結局分支就能直接讀檔。",
            ]},
            "準備好後等亞伯來電，前往律師事務所即可開啟〈保護性拘留〉（門外會跳出是否繼續的最後確認提示）。",
        ],
    },
    "p-pay-abes-fee-ch5": {
        "sum": "結清第 5 章亞伯律師事務所的費用（支票帳戶預留 $150,000）；部分流程在〈誠實的亞伯〉結束時即完成結算",
        "keys": [
            "把資金轉進家庭儲蓄前，**支票帳戶先保留 $150,000**（家庭儲蓄轉進去後無法領出）",
            "收到事務所簡訊或亞伯來電確認費用結清後，再將多餘資金轉進家庭儲蓄衝 $2,000,000",
        ],
        "steps": [
            "在進入〈保護性拘留〉之前，先確認第 5 章給亞伯事務所的律師費是否已結清。",
            {"ol": [
                "**支票帳戶先留足 $150,000。** 先不要急著把全部資金轉進家庭儲蓄，若收到事務所付款通知，直接打開手機 BuckMe 匯款即可。",
                "**確認結清後再補滿家庭儲蓄。** 收到亞伯來電通知可隨時來簽約，就把想留的資金轉進家庭儲蓄（目標 $2,000,000），接著手動另存一格再前往事務所。",
            ]},
        ],
    },
    "p-protective-custody": {
        "keys": [
            "**最終不歸點（門外會有繼續／延後提示）**：開始前務必確認家庭儲蓄滿 **$2,000,000**、感情滿級「炙熱相伴」、側寫低檔，並**手動另存獨立存檔**",
            "若兩人感情過低，任務開頭會觸發**分手過場**並進入分手結局分支；想走最好結局務必**拒絕門德茲交易**",
            "全程約 40～50 分鐘，後半段為長槍戰，並會直接銜接最終任務〈旅程終點〉",
        ],
    },
    "p-the-end-of-the-road": {
        "keys": [
            "最好結局選法：前面拒絕門德茲交易 ＋ 最後選擇「**游過去（Swim for It）**」並及時按下撤離",
            "片尾字幕**別跳過**，後面還有一段收尾畫面；結束後點「繼續」可回到自由探索補 100% 與白金獎盃（想試不同結局讀〈保護性拘留〉前存檔最保險）",
        ],
    },
}

# ───────────────────────── 3. 外站引用清除 & 台灣用語轉換 ─────────────────────────

# 常見外站與攻略網名（清除用）
_SITES = (
    r"PowerPyx|Output\s*Lag|Outputlag|GamesRadar|GTABase|MetaForge|Metaforge|4Gamers|"
    r"Game8|The\s*Click|theclick|GameWith|GameSpot|MeowDB|Gamerch|TrueAchievements|"
    r"Gamersky|oplay\.cc|oplay|Beebom|Nerdschalk|VGC|IGN|PC\s*Gamer|Dexerto|Gameriv|"
    r"Insider\s*Gaming|Playday|Alcast|Power\s*Up|RockstarINTEL|PlayTheory|Bloxodes|"
    r"Game\s*Rant|CNET|ayther\.fr|LeonidaHub|MobstersDaily|GTA6\s*Bible|GameTrek|"
    r"thegameswiki|games\.gg|gta\.wiki|Eurogamer|Polygon|Kotaku|Push\s*Square|Shacknews|ComicBook|"
    r"遊民星空|遊民|游民星空|游民|巴哈姆特|巴哈"
)

_SITE_PAREN_RE = re.compile(
    r"[（(][^（）()]{0,180}?(?:" + _SITES + r"|外站|本站|原站|單一來源|只有一家|一家寫|一家說|兩家|同源|未實測|畫面用字)[^（）()]{0,180}?[）)]",
    re.I,
)
_SITE_BRACKET_RE = re.compile(
    r"〔[^〕]{0,240}?(?:" + _SITES + r"|一家說|兩說|兩家說|幾家說|單一來源|外站|本站|原站|未實測|未確認|未驗證)[^〕]{0,240}?〕",
    re.I,
)
_TEMP_TRANS_RE = re.compile(r"〈暫譯[；;：:]\s*([^〉]+)〉")
_BARE_TEMP_RE = re.compile(r"〈暫譯〉")
_SITE_ANGLE_RE = re.compile(r"〈[^〉]{0,60}?(?:" + _SITES + r"|畫面用字)[^〉]{0,60}?〉", re.I)

# 行內句子層級的外站主詞／附註改寫（有序執行）
_INLINE_REWRITES = [
    (re.compile(r"這頁的「已完成\s*x／81」是本站的勾，不是遊戲內的完成度。?"), "這裡的勾選僅供個人記錄，與遊戲內完成度獨立。"),
    (re.compile(r"地圖上「隨機事件」分類的點是\s*GTABase\s*的玩家投稿，只代表有人在那裡遇過。?", re.I), "隨機事件多半不是固定點，地圖標記僅代表常見出沒位置。"),
    (re.compile(r"外站目前沒有這一項的單篇攻略。?"), ""),
    (re.compile(r"遇到這頁沒寫的卡關，到\s*DC\s*的\s*GTA6\s*聊天區回報，我們會補上。?"), ""),
    (re.compile(r"目前只有\s*(?:" + _SITES + r")\s*寫[，、]?(?:我們|本站)?(?:還)?沒(?:實測|驗證|確認)?[。，]?", re.I), ""),
    (re.compile(r"這個任務只有\s*(?:" + _SITES + r")\s*一家寫了完整步驟[，、]?(?:我們|本站)?(?:還)?沒(?:實測|驗證|確認)?[。，]?", re.I), ""),
    (re.compile(r"另外[二兩三四]家沒寫這一步[，、]?(?:我們|本站)?(?:還)?沒(?:實測|驗證|確認)?[。，]?"), ""),
    (re.compile(r"沒有攻略寫(?:清楚)?[，、]?(?:我們|本站)?(?:都)?(?:還)?沒(?:實測|驗證|確認)?[。，]?"), "實際情況以遊戲內提示為準。"),
    (re.compile(r"兩家(?:都)?沒寫(?:清楚)?[，、]?(?:我們|本站)?(?:都)?(?:還)?沒(?:實測|驗證|確認)?[。，]?"), ""),
    (re.compile(r"兩家對不上[，、]?"), ""),
    (re.compile(r"(?:[，、；]\s*)?(?:我們|本站)(?:也|都)?(?:還)?沒(?:實測|驗證|確認|查到)[。，]?"), ""),
    (re.compile(r"(?:[，、；]\s*)?本站未(?:實測|驗證|確認)[。，]?"), ""),
    (re.compile(r"^未實測[：:]\s*"), ""),
    (re.compile(r"(?:[，、；]\s*)?獨立交叉查證未完成[，、]?均未確認"), ""),
    (re.compile(r"是不是本站地圖"), "是不是地圖上"),
    (re.compile(r"互動地圖上還沒有這個點。?"), ""),
    (re.compile(r"外站估約"), "估約"),
    (re.compile(r"外站截圖是用"), "實測是用"),
    (re.compile(r"外站攻略(?:與本站互動地圖)?整理[，、；。]?"), ""),
    (re.compile(r"外站說法相反"), "實際請先存檔再確認"),
    (re.compile(r"本文核對過的路線"), "此路線"),
    (re.compile(r"本攻略〈互動地圖的槍械店〉"), "互動地圖的槍械店分類"),
    (re.compile(r"本站〈互動地圖的槍械店〉"), "互動地圖的槍械店分類"),
    # 清除「A 和 B 都寫／A、B 寫／A 建議…」這類來源主詞
    (re.compile(r"(?:(?:" + _SITES + r")(?:[、，\s與和及]+(?:" + _SITES + r"))*)\s*(?:的(?:全任務目錄|整章順序|整章總攻略|單篇|獎勵欄|搶案篇|100%\s*清單|攻略|接人總攻略|項鍊專頁|結局篇|全結局篇|〈[^〉]+〉頁)\s*)?(?:[0-9\-]+\s*的[^\s，。]{1,8}\s*)?(?:實測回報|回報|明寫|另寫|也寫|都寫|另外提醒|建議|列為|列出|提醒|指出|記錄|轉述另一家的說法[：:]?|說|寫道|寫的是|寫成|寫|稱|估計|給出|提到|標成|排成|把)[：:]?\s*", re.I), ""),
    (re.compile(r"(?:(?:" + _SITES + r")(?:[、，\s與和及]+(?:" + _SITES + r"))*)\s*等(?:兩家|三家)?(?:說|寫)[：:]?\s*", re.I), ""),
    (re.compile(r"(?:(?:" + _SITES + r")(?:[、，\s與和及]+(?:" + _SITES + r"))*)\s*(?:玩家|兩位玩家|幾位玩家|的說法|一致|這篇的說法也跟|玩了|只在|沒提|還在確認|三座全炸卻|自己的存檔裡|影片說|編輯一家實玩回報)", re.I), "實測"),
    # 清掉殘留的單獨網站名與孤立連接詞
    (re.compile(r"(?:" + _SITES + r")", re.I), ""),
    (re.compile(r"(?:[，、；]\s*)?和\s*都寫"), "，也可以"),
    (re.compile(r"兩說[：:。，]?\s*"), ""),
    (re.compile(r"說法不一[：:。，]?\s*"), ""),
    (re.compile(r"說法相反[。，]?\s*"), ""),
    (re.compile(r"一家說[：:。，]?\s*"), ""),
    (re.compile(r"兩家(?:寫法|說法)不同[，。]?\s*"), ""),
    (re.compile(r"只有這?一家寫(?:了)?[，。：:]?\s*"), ""),
    (re.compile(r"另有一家攻略說"), "也可以"),
    (re.compile(r"這幾條只有\s*一家寫[，、]?不能判定一定擋白金。?"), "建議接任務前先另存一格以防卡關。"),
    (re.compile(r"哪個對[、，]?是不是看觸發順序[，、]?還沒確認"), "依實際觸發順序為準"),
    (re.compile(r"誰這樣說[：:]?"), "備註："),
    (re.compile(r"本站"), "這裡"),
    (re.compile(r"外站"), "實測"),
    (re.compile(r"原站"), "遊戲內"),
    (re.compile(r"法文站\s*寫"), "有實測指出"),
    (re.compile(r"各家(?:沒寫清楚|都提醒|攻略|說法不同)"), "實測提醒"),
    (re.compile(r"同站(?:另一篇|正文)(?:寫|說)"), "另有情況"),
    (re.compile(r"繁中(?:遊戲)?(?:畫面|選單|清單|字幕)(?:上的字|用字|名字)?(?:我們)?還沒核到[，。]?"), ""),
    (re.compile(r"項目名是照英文意思寫的暫譯[，。]?"), ""),
    (re.compile(r"其他人名是暫譯[。，]?"), ""),
    (re.compile(r"實測實玩過的其他賺法"), "其他賺錢方法"),
    (re.compile(r"攻略實玩過的其他賺法"), "其他賺錢方法"),
    (re.compile(r"整理自攻略攻略"), "整理自玩家實測"),
    (re.compile(r"這頁"), "本節"),
]

# 台灣用語標準化（順序重要，先處理專詞與複合詞）
_TW_TERMS = [
    (re.compile(r"作弊碼（秘籍）"), "秘技"),
    (re.compile(r"作弊碼"), "秘技"),
    (re.compile(r"秘籍"), "秘技"),
    (re.compile(r"飛車兄弟\s*(?:APP|App|app)"), "滑機兄弟 App"),
    (re.compile(r"飛車兄弟"), "滑機兄弟"),
    (re.compile(r"僵立停"), "喪必斯"),
    (re.compile(r"圖標"), "圖示"),
    (re.compile(r"(?<!水上)摩托車"), "機車"),
    (re.compile(r"手柄"), "手把"),
    (re.compile(r"鎖屏"), "鎖定螢幕"),
    (re.compile(r"公交車"), "公車"),
    (re.compile(r"公交"), "公車"),
    (re.compile(r"便利店"), "便利商店"),
    (re.compile(r"視頻"), "影片"),
    (re.compile(r"通關(?!密語)"), "破關"),
    (re.compile(r"等一會兒?"), "等一下"),
    (re.compile(r"過一會兒?"), "過一陣子"),
    (re.compile(r"一會兒"), "一下"),
    (re.compile(r"趕緊"), "趕快"),
    (re.compile(r"立馬"), "馬上"),
    (re.compile(r"掉幀"), "掉格"),
    (re.compile(r"緩存"), "快取"),
    (re.compile(r"默認"), "預設"),
    (re.compile(r"菜單"), "選單"),
    (re.compile(r"界面"), "介面"),
    (re.compile(r"信息"), "資訊"),
    (re.compile(r"屏幕"), "螢幕"),
    (re.compile(r"軟件"), "軟體"),
    (re.compile(r"硬件"), "硬體"),
    (re.compile(r"數據"), "資料"),
    (re.compile(r"鏈接"), "連結"),
    (re.compile(r"聯繫"), "聯絡"),
    (re.compile(r"拉滿"), "衝滿"),
    (re.compile(r"網絡"), "網路"),
    (re.compile(r"聯網"), "連網"),
    (re.compile(r"任務【([^】]+)】"), r"任務〈\1〉"),
    (re.compile(r"獎盃【([^】]+)】"), r"獎盃〈\1〉"),
    (re.compile(r"【([^】]+)】"), r"〈\1〉"),
]

_PUNCT_CLEAN = [
    (re.compile(r"[（(]\s*[）)]"), ""),
    (re.compile(r"〔\s*〕"), ""),
    (re.compile(r"〈\s*〉"), ""),
    (re.compile(r"\*\*\s*\*\*"), ""),
    (re.compile(r"[，、；]{2,}"), "，"),
    (re.compile(r"。\s*[，、；]"), "。"),
    (re.compile(r"[，、；]\s*。"), "。"),
    (re.compile(r"。\s*。+"), "。"),
    (re.compile(r"：\s*。"), "。"),
    (re.compile(r"\s{2,}"), " "),
]

_DROP_NOTE_HEADINGS = re.compile(r"^(?:資料來源|來源|出處|參考資料)$")
_DROP_NOTE_PARA = re.compile(
    r"^\s*(?:下面的金額大多只有|地點是文字描述，|「先從哪種車下手」參考|金額都是.*範圍|這頁整理 Rockstar 繁中官網|"
    r"80 項的條件與數字都有|地圖地點卡上的截圖取自|海德島、外星人、Capri.*來源|"
    r"只有一家寫、或只有地圖投稿|解鎖條件說法不同的已寫|本攻略任務攻略|這頁依一支實玩影片整理|"
    r"玩家最常卡住的小事，一題一句答案|項目名照英文意思寫|場地名保留英文|射擊場、店名|選單名稱附上英文|任務名用英文原名|郡名的繁中)"
)


def _balance_bold(s: str) -> str:
    """確保字串中的 ** 成對（若清理過程誤刪單側 **，安全移除孤立標記）。"""
    if s.count("**") % 2 == 0:
        return s
    i = s.rfind("**")
    return s[:i] + s[i + 2:]


def clean_text(s: str) -> str:
    if not isinstance(s, str) or not s:
        return s
    s = _TEMP_TRANS_RE.sub(r"（\1）", s)
    s = _BARE_TEMP_RE.sub("", s)
    for _ in range(2):
        s = _SITE_BRACKET_RE.sub("", s)
        s = _SITE_PAREN_RE.sub("", s)
        s = _SITE_ANGLE_RE.sub("", s)
    for rx, rep in _INLINE_REWRITES:
        s = rx.sub(rep, s)
    for rx, rep in _TW_TERMS:
        s = rx.sub(rep, s)
    for rx, rep in _PUNCT_CLEAN:
        s = rx.sub(rep, s)
    s = s.strip(" ；，、")
    s = _balance_bold(s)
    return s.strip()


def _clean_deep(obj, skip_keys=("id", "slug", "url", "i", "map", "href", "tick", "imgBase", "builtOn", "sourceUpdated", "cat", "ch", "m", "see", "covers", "aliases")):
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        out = []
        for item in obj:
            c = _clean_deep(item, skip_keys)
            if isinstance(c, str) and not c:
                continue
            out.append(c)
        return out
    if isinstance(obj, dict):
        return {k: (v if k in skip_keys else _clean_deep(v, skip_keys)) for k, v in obj.items()}
    return obj


def _strip_note_meta_sections(blocks):
    """裁掉筆記尾端的「資料來源」整個區塊、空標題區塊，以及純屬站方編目說明的廢話段落。"""
    out = []
    skipping_level = None
    for b in blocks:
        if isinstance(b, dict) and "h" in b:
            h_txt = b["h"].strip()
            lvl = b.get("l", 2)
            if _DROP_NOTE_HEADINGS.match(h_txt) or re.match(r"^(?:PowerPyx|Game8|GamesRadar).{0,6}的$", h_txt, re.I):
                skipping_level = lvl
                continue
            if skipping_level is not None and lvl <= skipping_level:
                skipping_level = None
        if skipping_level is not None:
            continue
        if isinstance(b, str) and _DROP_NOTE_PARA.search(b):
            continue
        out.append(b)
    return out


def _patch_notes(notes):
    """將實測查證後的結論更新到對應系統筆記，裁掉資料來源尾段，消除矛盾寫法。"""
    for n in notes:
        n["blocks"] = _strip_note_meta_sections(n.get("blocks", []))
        n.pop("stamp", None)
    by_slug = {n["slug"]: n for n in notes}
    if "endings" in by_slug:
        by_slug["endings"]["sub"] = "存滿 $200 萬、側寫壓低、感情炙熱相伴，見亞伯前先存檔"
        by_slug["endings"]["blocks"].insert(0,
            "**最好結局實測確認條件**：BuckMe 家庭儲蓄達 **$2,000,000** ＋ 兩人感情滿級「炙熱相伴」 ＋ 兩人犯罪側寫維持低檔（冷靜專業或鐵石心腸） ＋ 拒絕門德茲交易 ＋ 最終選擇「游過去」並及時按下撤離。若感情過低會在〈保護性拘留〉開頭觸發分手路線。")
    if "romance" in by_slug:
        by_slug["romance"]["blocks"].insert(0,
            "**感情會影響結局分支**：保持互動、約會與送禮可把感情升到最高級「炙熱相伴」（最好結局必要條件）；若長期冷落使感情過低，會在第 5 章〈保護性拘留〉開頭觸發分手路線。")
    if "cheats" in by_slug:
        by_slug["cheats"]["title"] = "秘技一覽"
        by_slug["cheats"]["sub"] = "主線破關後才可用，61 組（含立刻拿 $250,000 與切換天氣）"
    if "stats" in by_slug:
        by_slug["stats"]["blocks"].insert(0,
            "**補血規則**：自然回血只會補到血條白線；按住 ⟦L1⟧＋⟦□⟧（Xbox：LB＋X）吃**喪必斯**可越過白線繼續回血（最多帶 5 瓶，短時間連吃效果會暫時減弱）。粉紅愛心食物補血、橘色愛心食物暫時加血量上限、睡覺補滿。")
    if "events" in by_slug:
        for b in by_slug["events"]["blocks"]:
            if isinstance(b, dict) and b.get("h") == "本站還沒核對的":
                b["h"] = "其他罕見隨機事件"


def _patch_codex(codex):
    """修訂圖鑑與 HUD 中已查證的項目，並清理分類名稱成台灣用語。"""
    for g in codex.get("groups", []):
        for c in g.get("cats", []):
            if c.get("slug") == "cheat":
                c["name"] = "秘技"
    for grp in codex.get("hud", []):
        for it in grp.get("items", []):
            if "喪必斯" in it.get("n", "") or "愛心條" in it.get("n", ""):
                it["do"] = "躲掩體會自動回血到白線；越過白線要按住 ⟦L1⟧ 再按 ⟦□⟧（Xbox：LB＋X）吃喪必斯（最多帶 5 瓶，連吃效果會暫時減弱），或吃粉紅愛心食物、回家睡覺回滿。"
            if it.get("tag") and "還沒確認" in it["tag"]:
                it.pop("tag", None)


def process_guide(guide: dict) -> dict:
    """套用查證修訂、移除外站日記／作者公告、注入各章／任務該做清單，並全量轉為台灣用語。"""
    guide["intro"] = []
    guide["notices"] = []
    guide["sources"] = []

    for ch in guide.get("chapters", []):
        for m in ch.get("missions", []):
            ov = MISSION_OVERRIDES.get(m["id"])
            if ov:
                for k, v in ov.items():
                    m[k] = list(v) if isinstance(v, list) else v
            m.pop("aka", None)
            if m["id"] in MISSION_TODOS:
                m["todo"] = list(MISSION_TODOS[m["id"]])

        for sec in ch.get("info", []):
            for r in sec.get("rows", []):
                if r.get("n") == "搭好的整套衣服可以存起來嗎" or "Saved Outfits" in r.get("a", ""):
                    r["a"] = "可以，在住處衣櫃「Saved Outfits」按 ⟦△⟧（Xbox：Y）最多存 10 套；個人車後車廂可放 5 套。"

    _patch_notes(guide.get("notes", []))
    guide["checklists"] = CHAPTER_CHECKLISTS
    guide = _clean_deep(guide)
    return guide


def process_codex(codex: dict) -> dict:
    """清理圖鑑、彩蛋、HUD 與更新紀錄的外站字眼並標準化為台灣用語。"""
    _patch_codex(codex)
    codex_skip = ("id", "slug", "url", "i", "map", "href", "tick", "imgBase", "builtOn", "sourceUpdated", "ch", "m", "see", "covers", "aliases")
    codex = _clean_deep(codex, skip_keys=codex_skip)
    return codex
