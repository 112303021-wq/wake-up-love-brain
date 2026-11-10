"""送進 LLM 之前的安全檢查（簡報 p.9 流程第二格）。

關鍵字規則只是第一道網；接上 Claude 後，模型回傳 break_character=true 也會觸發同一套處理。
寧可誤判跳出，也不要漏掉真的有危機的玩家；但「明顯不是本人危機」的語境
（第三人稱、小說劇情、慣用誇飾）只降級成溫和提醒，不終局（會議紀錄 Q1、Q14）。

介面
- assess(text) -> dict | None   完整判定：category / severity / ends_session / context
- check(text)  -> str | None    向下相容：只有「需要終局」的類別才回傳，其餘回 None
- response(category, model_text="", severity=None) -> dict   給前端的安全畫面資料

severity
- high   第一人稱的自傷、真實暴力、真實詐騙／性勒索：終局並顯示資源
- medium 未成年、玩家要求暫停／退出、現實痛苦、模型跳戲：終局，語氣為建議
- low    同一批關鍵字但語境為第三人稱／虛構／誇飾：不終局，顯示溫和提醒
- info   ai_identity（真誠詢問是不是 AI）：不終局，如實說明
"""
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

RESOURCES = [
    {"name": "安心專線", "number": "1925", "note": "24 小時，心情低落、想傷害自己時"},
    {"name": "165 反詐騙諮詢專線", "number": "165", "note": "懷疑被騙、正被要求匯款或買點數時"},
    {"name": "113 保護專線", "number": "113", "note": "遭受暴力、跟蹤、性侵或脅迫時"},
]

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}
ENDING_SEVERITIES = {"high", "medium"}


# ---------- 正規化 ----------
_SMALL_CAPS = str.maketrans("ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ", "abcdefghijklmnopqrstuvwxyz")


def normalize(text: str) -> str:
    """全半形統一（NFKC）、轉小寫，去掉所有空白、標點、符號、emoji、零寬字元。

    讓「自 殺」「自.殺」「Ｋｉｌｌ　ｍｙｓｅｌｆ」都變成連續字串再比對。
    """
    t = unicodedata.normalize("NFKC", text or "").translate(_SMALL_CAPS).lower()
    return re.sub(r"[\W_]+", "", t)


# ---------- 規則 ----------
_N = r"(?<![不沒別未無勿])"  # 前面不能是否定字

_SELF_HARM = re.compile("|".join([
    r"自殺", r"自盡", r"輕生", r"自殘", r"割腕", r"尋短", r"自s(?![a-z])",
    r"跳樓(?!大拍賣|價|特賣|拍賣|大特賣)",
    r"傷害自己", r"結束(我的|自己的)?(生命|性命)", r"結束自己",
    r"不想(再|繼續)?活(?!在(別人|謊言|過去|期待|這種|這樣|那種|虛假|假象|恐懼|陰影|.{0,6}(關係|感情|愛情|婚姻|家庭|環境|狀態|情況|日子|生活|地方)))(?!得很|得這麼|得像)", r"活不下去", r"活夠了",
    r"活著(好|真|太|很)?(累|痛苦|沒意思|沒意義|沒有意義|沒什麼意義)", r"活得(好|真|太|很)累",
    r"一了百了", r"了結(自己|生命|一切)",
    _N + r"(?<!沒有)(?<!不是)(?<!才不)想死(?!你|妳|您|我了|黨|忠)", r"想去死", r"死了算了", r"死掉算了", r"去死好了",
    r"我去死(?!黨|忠|亡|刑)", r"乾脆死", r"不如死", r"不如消失", r"消失算了",
    r"想(從|在)?(這個|這)?(世界|世上)?消失(?!一個(?:週末|禮拜|星期|月|下午|晚上|週)|兩週|(?:一|二|兩|三|四|五|六|七|幾|\d+)(?:天|週|星期|個月|陣子|下))", r"想永遠消失", _N + r"想消失(?!在人群|在人海|在角落|一個(?:週末|禮拜|星期|月|下午|晚上|週)|兩週|(?:一|二|兩|三|四|五|六|七|幾|\d+)(?:天|週|星期|個月|陣子|下))",
    r"想結束(一切|掉一切|生命|吧$|了$|$)", r"結束一切", r"沒有(活下去|活著)的(理由|意義|動力|必要)",
    r"沒有我(這個|這)?(世界|世上|地球)?(會|還)?(更|比較)好", r"(世界|世上)沒有我(會|還)?(更|比較)?好", r"(死掉|死了|消失)比較好",
    r"是不是(死掉|死了)", r"離開(這個|這)?(世界|世上|人世)", r"(永遠|想要|只想要?)安靜", r"(永遠|睡著)不要醒", r"睡不起",
    r"(好|很)?想(長眠|去世|升天|上路)", r"今晚就(要)?走了?", r"再見了?這是最後一次", r"這是我最後一次(跟你|和你)?(說話|聊天|聊)",
    r"(想|要|準備|打算)(吞|吃)(了)?(很多|一堆|整瓶|大量)?(安眠藥|藥)", r"吃了(一堆|很多|整瓶|一整瓶|大量)(安眠)?藥", r"吞了(一堆|很多|整瓶|一整瓶|大量)(安眠)?藥",
    r"(想|要|準備|打算)跳下去", r"站在(頂樓|天台|屋頂|高樓|橋上|陽台外|窗邊外)", r"拿(刀|美工刀|刀片)(劃|割)自己", r"(劃|割)自己",
    r"就去死(給你看)?", r"zisha", r"自ㄕㄚ", r"ㄗㄕㄚ", r"ㄗ殺", r"想ㄙ", r"想s(?![a-z])", r"kms(?![a-z])",
    r"想解脫", r"求解脫", r"只想解脫", r"不想醒來", r"不想再醒", r"想永遠睡著",
    r"(想|要|打算|準備|好想)(去)?(吞藥|燒炭|上吊|跳河|跳海|跳橋|跳軌|喝農藥)",
    r"killing?myself", r"kill ?myself".replace(" ", ""), r"wan(t|na)(to)?die", r"endmylife",
    r"endingmylife", r"suicid", r"takemyownlife", r"don'?t?wanttolive", r"dontwanttolive",
]))


# ---- 結構性規則（第 6 輪）：不靠整句詞庫，而是「意圖／狀態」+「死亡／消失／結束」的組合 ----
_INTENT = r"(想要?|欲|(?<![到得])要|打算|準備|決定|考慮|好想|很想|真想|只想|一直想|老是想|常常想|每天都在想|正在考慮|wish|want|wanna|plan|thinking)"
_DEATH = (r"(死(?!你|妳|您|我了|黨|忠|纏|皮|心|都|定|機|亡|刑|命|者|去活來|在|撐)掉?|去世|離世|了斷|了結|自我了斷|輕生|自盡|結束(?:我的|自己的|這)?(?:生命|性命|人生|一切|自己)|"
          r"unalive|disappear|消失(?!(?:一|二|兩|三|四|五|六|七|幾|\d+)(?:天|週|星期|個月|陣子|下)|一個(?:週末|禮拜|星期|月|下午|晚上|週)|兩週)|不在了|離開(?:這個|這)?(?:世界|人世|世上)|長眠|永遠休息|下線人生|登出人生|退出人生|讓自己消失|"
          r"endit|endingit|endingitall|endthis)")
_STRUCT_SELF = [
    # 意圖 + 死亡詞（中間最多 6 字）：我想自我了斷、我欲去死、想讓自己消失、想結束這一切
    _INTENT + r"[去讓自己我掉成要能就馬上現在今晚明天真的快點早點趕好了這一個切再]{0,6}" + _DEATH,
    # 想過／念頭 + 死亡詞：最近老是有想讓自己消失的念頭
    r"(念頭|想法).{0,4}" + _DEATH, _DEATH + r".{0,3}(念頭|想法)", r"(有|冒出|閃過).{0,4}(想|要).{0,3}" + _DEATH,
    # 狀態：活不下去、撐不下去、不想再繼續
    r"活(不|袂)(下去|落去)", r"袂堪得?活", r"不想(再|繼續|要)?(繼續)?(撐|呼吸|醒來?|存在)(了|下去)?", r"不想繼續了", r"早就不想繼續",
    r"撐到今天.{0,6}(極限|放棄)", r"已經(是)?極限了?.{0,6}(放棄|走)", r"我要放棄(這一切|人生|生命)",
    r"存在(就是|只是)?(個)?(錯誤|多餘|累贅|負擔)", r"我是(個)?(累贅|負擔|多餘的)", r"不想再?當別人的?(負擔|累贅)",
    r"(我不在了|我消失|沒有我).{0,8}(輕鬆|比較好|更好|不會有人)", r"(消失|不在).{0,3}不會有人(發現|在意|知道|難過)",
    r"如果我不在了", r"要是我不在", r"明天不用醒", r"不要醒過來", r"不用醒過來", r"睡著.{0,2}不醒", r"永遠(睡著|休息|安息)",
    r"人生(到此|就)?(為止|結束)就好", r"到此為止就好",
    # 準備與手段
    r"遺書", r"囤(了)?(很多|一堆|好多)?(安眠)?藥", r"買了(木炭|炭|繩子|安眠藥|刀片)", r"選好(了)?(地點|地方|時間)", r"查.{0,8}(方式|方法).{0,6}(不痛|死|自殺)",
    r"(託|託付|送|送人).{0,6}(貓|狗|寵物|東西|所有東西)", r"所有東西都送", r"把(貓|狗|寵物).{0,4}託", r"準備好(離開|走|了)", r"做個了斷", r"先走一步",
    r"不會再回來", r"從陽台翻", r"翻出去", r"跳下去", r"劃開", r"(新|又多了|多了).{0,4}(傷口|疤)", r"撞牆.{0,8}(流血|好一點|才覺得)", r"(割|劃|燙|咬)(自己|手|腕)",
    r"選好地點", r"想帶著這個秘密離開", r"帶著.{0,4}離開(這個)?世界",
    # 負擔感、告別、委婉
    r"(只會|會|一直)?(拖累|連累)(大家|別人|家人|所有人|你們)", r"(沒有我|沒我|我走了|我消失|我不在)的?(話)?.{0,8}(更好|比較好|輕鬆)",
    r"(永遠|直接)閉上眼", r"不想再?看到明天", r"(不要|別|不想)再醒", r"死亡是(唯一|最好)的(出口|解脫|辦法)", r"(死|結束)是(唯一|最好)的(出口|解脫|辦法)",
    r"想去(另一個|別的|那個)世界", r"去見上帝", r"想(嘎|掛)(掉|了)", r"想(登出|下線)(人生|世界)", r"(遺言|遺囑)", r"(吞|吃|服)(了)?(一整|一大|整|很多|大量|過量|好多).{0,3}藥",
    r"買好(了)?(繩子|木炭|炭|刀|藥)", r"(這週|今晚|明天|週末).{0,4}(就會|就要)?執行", r"有計(畫|劃)了.{0,8}(執行|做|動手)", r"受夠了.{0,6}(要|想)(結束|離開|走)",
    r"想讓(一切|痛苦|這一切).{0,4}(停止|停下來|結束)", r"極端的方式", r"(存款|財產|東西)(都)?留給", r"想讓一切.{0,4}停下來",
    r"想從.{0,6}(世上|世界上)消失", r"想(要)?消失在?這個世界",
    # 台語、網路梗、英文
    r"欲(去)?死", r"想欲死", r"欲結束.{0,4}(性命|生命)", r"活袂落去",
    r"(do)?n'?t?wanttobealive", r"notworthliving", r"lifeisn'?tworthliving", r"notexist", r"nobodywouldmissme", r"gonetonight", r"feellikeendingmylife",
    r"thinkingaboutsuicide", r"goingtoendit", r"killmyselftonight", r"想欲了斷", r"sewerslide", r"退出人生", r"登出人生", r"下線人生",
    r"wish(ed)?i(was|were)dead", r"betteroff(dead|withoutme)", r"nopointin?(living|going)", r"don'?t?seethepointof(living|going)",
    r"noreasontogoon", r"can'?t?goonlike", r"can'?tdothisanymore", r"nolongerwanttobe(here|alive)", r"disappearforever",
    r"endit(all)?(tonight|now)?", r"endingitall", r"unaliv", r"suicidal", r"hurtmyself", r"harmmyself", r"cutmyself",
]

_SUBJ = r"(他|她|對方|男朋友|女朋友|男友|女友|前任|前男友|前女友|老公|老婆|先生|太太|丈夫|爸爸|媽媽|爸|媽|老闆|主管|同事|室友|網友|有人|那個人)"
_SELF_HARM = re.compile("|".join([_SELF_HARM.pattern] + _STRUCT_SELF))

_VIOLENCE = re.compile("|".join([
    r"家暴", r"我被(打|揍|踹|踢|毆)(了|得|到|傷)", r"被(.{0,4})?(跟蹤|性侵|強暴|侵犯|脅迫|恐嚇|毆打|綁架|軟禁)",
    r"被我?" + _SUBJ + r"(打(?!槍|斷|算|動|敗|擾|臉|賞|開|氣)|踹|踢|揍|掐|勒|毆|摸|碰|強吻|壓)",
    _SUBJ + r".{0,6}(打我|踢我|踹我|揍我|掐我|勒我|摔我|砸我|推我|甩我|扯我|咬我|捅我|摸我|碰我|綁我|關我|鎖我|盯著我|跟蹤我|威脅我|恐嚇我|強迫我|監視我|騷擾我|偷拍我|(?<!自)殺我|砍我|(?<!自)殺了我|打了我)(?!陪|一起|去警|幫|報警)",
    r"(怕|擔心)" + _SUBJ + r"(會)?(殺|打)(了)?我", r"要殺了?我",
    _SUBJ + r".{0,6}(掐|勒|抓|揪|拖|抽|甩|扯|推|按|壓)著?我(的)?(脖子|頭髮|頭|手|手腕|衣服|臉|身體|巴掌|耳光)?",
    _SUBJ + r".{0,8}(皮帶|棍子|刀|拳頭|巴掌).{0,3}(抽|打|砍|揍|砸)", r"(抽|打|砍|揍|砸)我(的)?(臉|頭|背|身體)",
    r"不讓我(出門|離開|走|回家|上學|上班)", r"把我(鎖|關)(在|起來)", r"守在我(家|公司|學校|樓下)", r"在我(家|公司|學校)(樓下|門口).{0,6}(等|守|堵)",
    r"(身上|手上|臉上|脖子上).{0,4}(瘀青|傷痕|淤青)", r"(我|我們)(怕|不敢)(回家|見他|見她|跟他獨處)", r"(對我)?(動手|動粗)", r"(?<!你)(會|又|還|就|常|常常|一直|總是|喝醉就)(打|踹|踢|揍|掐|勒|推|摔)我", r"把我(推|打|摔|拖|壓|按|鎖|關)", r"尾隨", r"(說|要|會|就|威脅).{0,6}(?<!自)殺(了)?我", r"一直霸凌我|霸凌我",
    r"摸我|碰我|強吻我|對我性騷擾|性騷擾我",
]))

_MONEY_WORD = r"(匯款|匯錢|轉帳|轉錢|匯|轉|買點數|買遊戲點數|買禮物卡|買序號|點數|借錢|借|投資|拍|傳|寄|給)"
_REAL_SCAM = re.compile("|".join([
    r"現實(中|裡|生活).{0,12}(匯款|匯錢|轉帳|投資|點數|借錢)",
    r"(真人|網友|現實|有人|別人|交友|那個人|男朋友|女朋友|男友|女友|朋友|同學|客服|他|她|對方).{0,10}(要|叫|逼|要求|請)我(去)?" + _MONEY_WORD,
    r"裸照", r"私密照", r"私密影像", r"私密照片", r"裸聊", r"果聊", r"自拍裸",
    r"被(威脅|勒索)(.{0,6})?(散布|散佈|公開|外流)", r"(散布|散佈|外流)我的(照片|影片|裸)",
    r"我(已經|昨天|前天|剛|剛剛|今天)(匯|轉|買)了?(款|帳|錢|點數|\d|[一二兩三四五六七八九十百千萬]+)(?!.{0,2}給你)",
    _N + r"被騙了?\d", r"我被騙了", r"我上當了", r"我被詐騙", r"被騙(走|光|了好多|了很多)", r"騙(走|光)了?我", r"我的(積蓄|存款|退休金|錢)(都|全|被).{0,4}(騙|沒了|被拿走|被轉走)",
    r"(?<!你)(叫|逼|要求|催|請)我(去|先|趕快)?(買|匯|轉|付|繳|墊|借|傳|拍)(遊戲)?(點數|款|帳|錢|保證金|手續費|裸|照|入金)?", r"(先)?(付|繳|匯|轉|墊).{0,4}(手續費|保證金|稅金|入金)", r"(補|繳)稅金", r"老師叫我.{0,4}入金", r"不讓我(提款|出金|提領)", r"(無法|不能|不給我)(提款|出金|提領)",
    r"被(網友|網路上認識的人|對方|陌生人|假客服).{0,3}騙", r"(網戀|網友|網路認識).{0,14}(借錢|墊|要我先)", r"(私密|不雅)(影片|照片|影像).{0,6}(威脅|外流|散布|公開)", r"(威脅|要).{0,8}(私密|不雅)(影片|照片|影像)",
    r"中獎.{0,10}(手續費|先付|先匯)", r"安全帳戶", r"監管帳戶", r"帳戶(被)?凍結", r"涉嫌?洗錢", r"涉及洗錢", r"解除分期", r"重複扣款", r"帶單(老師)?", r"保證(獲利|賺錢|賺)", r"穩賺不賠", r"保證金才能", r"手續費才能(領|提|出)",
    r"(客服|警察|檢察官|銀行|法院|檢調).{0,10}(叫|要|請|說要|通知)我.{0,10}(轉|匯|操作|ATM|提款|驗證|交出|提供)",
    r"我(已經|剛|剛剛|昨天|前天|今天)?把.{0,8}(錢|存款|積蓄)?(匯|轉|交|給)(給|到)?(他|她|對方|網友|客服|那個人|對方的帳戶|詐騙)",
    r"(按|照)(他|她|對方|客服)(說的|指示).{0,6}(轉|匯|買|操作)",
]))

_MINOR = re.compile("|".join([
    r"我(才|今年|只有|現在|剛)?(1[0-7]|十[一二三四五六七]?)歲(?!以上|的時候|時|前|之前|那年|就)",
    r"我(才|今年|只有|現在)?([89]|九)歲(?!以上|的時候|時|前|之前|那年|就)(?=$)", r"剛滿(1[0-7]|十[一二三四五六七])(歲)?", r"我.{0,4}升(高[一二]|國[一二三]|國中|國小)", r"我(今年|現在|剛|才|目前|還)?(是|在|上|讀|念)?(剛)?(上)?(國|高)[一二三](?![直向度內外家際語文同學])", r"我?(是|還在)?小學(生|[一二三四五六]年級)", r"國小(剛)?畢業沒多久",
    r"(?<![a-z])i'?m(1[0-7])(?!\d)(?=$|years)",
    r"我(今年)?1[0-7](?!\d)(?=$)",
    r"我今年(1[0-7]|十[一二三四五六七])(?![\d號号日月點樓分秒年元塊])",
    r"我(是|現在|今年|剛|才|目前|還在讀|還在念|還是)?(國[一二三]|國中|國小[一二三四五六]?|小[一二三四五六])(生|年級|$|了|喔|啊|欸|耶|而已)",
    r"我(是|讀|念|還在讀|目前)?高[一二]生?(?![中等])", r"我(是|讀|念|還在讀)?高三生",
    r"我還?未成年", r"我還沒成年", r"未滿(18|十八)", r"(還)?沒滿(18|十八)", r"不到(18|十八)歲", r"我(今年)?(才|剛)(國|高)[一二三]", r"我(是|讀|念)?(國|高)[一二三](?=快|要|的|生|$|了|而已)",
    r"我(還)?在(念|讀|上)(國中|國小|高中)", r"我是(個)?(國|高)(中|小)生", r"我是高中生", r"我(才|今年才|現在才)(1[0-7]|十[一二三四五六七])(?!\d)", r"我媽不讓我.{0,8}因為我才(1[0-7])", r"我是(未成年|青少年|學生妹|學生弟)",
    r"iam(1[0-7])yearsold", r"i'?m(1[0-7])yearsold", r"imunder18",
]))

_PAUSE = re.compile("|".join([
    r"暫停(一下)?(遊戲|吧)", r"我(要|想|先|需要)暫停(?!.{0,6}(訂閱|會員|服務|營業|合作|付款|聯絡|見面|手機))", r"先暫停", r"(我)?不玩了", r"不想玩了", r"不要玩了",
    r"別玩了", r"退出遊戲", r"^退出$", r"(中斷|中止)(遊戲|一下)", r"(讓我|幫我|麻煩讓我)停一下", r"我現在不想玩", r"我(要|想)退出", r"停止遊戲", r"結束遊戲", r"離開遊戲",
    r"不想繼續玩", r"我(要|想)停止", r"先停一下", r"我要登出(遊戲|$)", r"quitgame", r"stopthegame",
    r"我(要|想)(關掉|關閉)(遊戲|了$|$)", r"請(幫我)?(暫停|停止)", r"(幫我|讓我)(暫停|停下來)", r"我(想|要|需要)(先)?(停下來|離開遊戲)", r"不想繼續玩",
]))
# 「停止聯絡」「暫停聯絡」「退出群組」等劇情用語不算
_PAUSE_FALSE = re.compile(r"(暫停|停止|退出|不想)(聯絡|聯繫|見面|來往|交往|群組|社團|這段|關係)|退出群")

_TOO_PAINFUL = re.compile(r"撐不(下去|住)|(現實|真的).{0,6}(好痛苦|撐不下去|受不了了)|太痛苦.{0,4}(玩不下去|沒辦法繼續)")

_AI_IDENTITY = re.compile("|".join([
    r"你(是不是|是否|到底是|其實是|真的是|是)(一個)?(真人|機器人|ai|人工智慧|人工智能|chatgpt|gpt|機器|程式|bot|電腦|人類)",
    r"你是人還是(ai|機器|程式|人工)", r"(對面|螢幕那頭|螢幕另一端|你)是真人嗎",
    r"你有沒有真人", r"你是真的人嗎", r"你是(在)?用(機器人|ai|chatgpt|gpt|程式|自動).{0,4}(回|寫|生成)", r"你是不是用(chatgpt|gpt|ai|機器人).{0,4}(寫|回|生成)",
    r"(我|是)在跟(ai|機器人|真人|程式|人工智慧).{0,3}(講話|說話|聊天|對話)", r"你背後是(真人|ai|機器人)", r"(是|由)(ai|機器人)在(回|跟我)", r"對面是真人嗎",
    r"你是真人還是(程式|機器|ai)", r"你是機器人還是", r"你是(gpt|gemini|claude|chatgpt)嗎", r"是不是在跟(ai|機器人)", r"自動回覆", r"你是程式嗎",
    r"areyou(a|an|really)?(real|human|ai|bot|robot|person|chatgpt|machine)",
    r"isthisan?(ai|bot|robot)", r"areyouaperson",
]))

# 語境判斷
_THIRD_MARKERS = re.compile(
    r"朋友|同學|室友|同事|家人|姊姊|姐姐|哥哥|弟弟|妹妹|媽媽|爸爸|兒子|女兒|學生|病人|客人|"
    r"弟|哥|姐|姊|妹|媽|爸|角色|主角|男主|女主|他|她|牠|別人|有人|網友|某人|對方")
_FICTION = re.compile(r"小說|劇情|故事|電影|電視劇|影集|劇本|漫畫|動畫|戲裡|遊戲裡|遊戲中|情節|寫到|如果是|假設|演戲|角色扮演")
_REAL = re.compile(r"現實|真的|認真|說真的|其實我|不是遊戲|不是劇情|不是小說|不是開玩笑|沒在開玩笑|我自己")
_SELF_AFTER = re.compile(r"我也(是|想|一樣|有|好想|很想|不想|覺得|是這樣)|我跟(他|她|牠)一樣|我自己也|我同樣")
_HYPERBOLE = re.compile(r"[累煩熱冷餓睏氣忙痛窮臉尬糗羞爛]到(都)?$")

_CONTEXT_CATS = {"self_harm", "real_violence", "real_scam"}

_PATTERNS = [  # (category, pattern, base severity)，順序即同嚴重度時的優先序
    ("self_harm", _SELF_HARM, "high"),
    ("real_violence", _VIOLENCE, "high"),
    ("real_scam", _REAL_SCAM, "high"),
    ("minor", _MINOR, "medium"),
    ("too_painful", _TOO_PAINFUL, "medium"),
    ("pause", _PAUSE, "medium"),
    ("ai_identity", _AI_IDENTITY, "info"),
    ("self_harm", re.compile(r"kys(?![a-z])"), "low"),
]


_HYPER_CUES = re.compile(r"露營|旅行|放假|度假|山上|出國|點名|當眾|被老師|被罵|被笑|蒸發|挖洞|社死|社恐|尷尬|丟臉|聚會|冬眠|上班|打槍|臉紅|考爛|考試|要我命|哈哈|xd|lol|作業|報告|加班|期末|被老闆|好煩|氣死|人群|社交")
_WORK_CUES = re.compile(r"戒酒|戒菸|喝酒|抽菸|減肥|健身|運動|復健|跑步|工作|壓力|報告|考試|作業|加班|期末|主管|老闆|專題|論文|開會")
_NEG_PREFIX = re.compile(r"(沒有|不是|並沒有|並不是|沒|不會|不要|不|別|絕對不|才不)(是|要|會)?(想|打算)?$")
_REFUSE_SCAM = re.compile(r"我拒絕(?!不)|不可能|瘋了|才不會|不會傳|不傳|不給|不要傳|不要匯")
_ASKED_BY_NPC = re.compile(r"你(剛才|剛剛|是不是|現在|又)?(要|叫|逼|請|想)我")
_TOPIC = re.compile(r"理論|討論|分析|社會學|心理學|考試|題目|評估|諮商|課|論文|主題|研究|防治|宣導|議題|文獻|課程|報導|新聞|演講|報告")
_FIRST_INTENT = re.compile(r"我(也)?(好)?(想|要|決定|打算)(?!知道|研究|寫|問|看|討論)")
_CHALLENGE = re.compile(r"視訊|證明|證據|拍照|露臉|影片給我|打電話")
_THIRD_NAMES = ("弟|哥|姐|姊|妹|媽|爸|朋友|同學|室友|同事|家人|姊姊|姐姐|哥哥|弟弟|妹妹|媽媽|爸爸|兒子|女兒|學生|病人|客人|角色|主角")


def _context(norm: str, m: "re.Match", cat: str = "") -> str:
    """回傳 first_person / third_person / fiction / hyperbole。

    自傷（Q30）：句中只要有第一人稱意圖（我想自殺、我也是…），遊戲／電影／小說字眼不得降級；
    降級只限明確第三人稱角色，或整句根本沒有第一人稱主詞的虛構敘述。
    """
    fic = bool(_FICTION.search(norm)) and not _REAL.search(norm)
    prefix = norm[max(0, m.start() - 10):m.start()]
    if cat != "self_harm":
        if fic:
            return "fiction"
        if "我" not in m.group(0):
            if _HYPERBOLE.search(prefix):
                return "hyperbole"
            cleaned = re.sub(r"我的?(?=" + _THIRD_NAMES + ")", "", prefix)
            marks = list(_THIRD_MARKERS.finditer(cleaned))
            if marks and "我" not in cleaned[marks[-1].end():]:
                if _SELF_AFTER.match(norm[m.end():m.end() + 8]) or _SELF_AFTER.search(norm[m.end():m.end() + 6]):
                    return "first_person"
                return "third_person"
        return "first_person"
    # ---- self_harm ----
    if _TOPIC.search(norm) and not _REAL.search(norm) and not _FIRST_INTENT.search(norm):
        return "fiction"  # 討論／研究自殺防治議題，不是本人意圖
    if _SELF_AFTER.search(norm[m.end():m.end() + 6]):
        return "first_person"
    if re.search("死|消失", m.group(0)) and not _REAL.search(norm) and (
            _HYPERBOLE.search(prefix) or _HYPER_CUES.search(norm)):
        return "hyperbole"
    cleaned = re.sub(r"我的?(?=" + _THIRD_NAMES + ")", "", prefix)
    marks = list(_THIRD_MARKERS.finditer(cleaned))
    third = bool(marks) and "我" not in cleaned[marks[-1].end():]
    if third:
        return "fiction" if fic else "third_person"
    if fic and "我" not in cleaned:
        return "fiction"
    return "first_person"


# ---------- 可插拔第二道分類器（預設關閉）----------
_CLASSIFIER = None
VALID_CATEGORIES = {c for c, _, _ in _PATTERNS}


def set_classifier(fn) -> None:
    """安裝第二道分類器；傳 None 關閉（預設關閉）。

    fn(text) -> None 或 dict(category=..., severity="high|medium|low|info")。
    只在規則層「完全沒觸發」或只觸發 low 時才會被呼叫；fn 拋例外、回傳格式不對都當作沒事，
    不會讓遊戲壞掉。分類器可以是 LLM、embedding 或下面的 heuristic_classifier。
    """
    global _CLASSIFIER
    _CLASSIFIER = fn


def get_classifier():
    return _CLASSIFIER


def _from_classifier(text: str) -> Optional[dict]:
    if _CLASSIFIER is None:
        return None
    try:
        out = _CLASSIFIER(text)
        if not out:
            return None
        cat, sev = out.get("category"), out.get("severity")
        if cat not in VALID_CATEGORIES or sev not in SEVERITY_RANK:
            return None
        return {"category": cat, "severity": sev, "ends_session": sev in ENDING_SEVERITIES,
                "context": "classifier"}
    except Exception:
        return None


_DESPAIR = re.compile(r"絕望|沒有希望|沒希望|沒意義|沒有意義|崩潰|撐不|痛苦|好累|太累|受夠|解脫|放棄|沒有人(?:在乎|需要|懂)|孤單|負擔|累贅|不想面對|活著")
_FIRST = re.compile(r"我|自己|myself|\bi\b")


def heuristic_classifier(text: str) -> Optional[dict]:
    """本機可跑的粗略第二道網：第一人稱 + 多個絕望線索 → self_harm / low（只提醒，不終局）。

    這只是示範與保底，不是完整的風險偵測器；召回與精確度都沒有嚴格評估。
    """
    t = unicodedata.normalize("NFKC", text or "").lower()
    if _FIRST.search(t) and len(set(_DESPAIR.findall(t))) >= 2:
        return {"category": "self_harm", "severity": "low"}
    return None


def assess(text: str) -> Optional[dict]:
    """完整判定。沒事回 None，否則回 {category, severity, ends_session, context}。

    先跑規則；規則沒觸發（或只有 low）且已用 set_classifier() 安裝第二道分類器時，再問分類器。
    """
    result = _assess_rules(text)
    if _CLASSIFIER is not None and (result is None or result["severity"] == "low"):
        extra = _from_classifier(text)
        if extra and (result is None or SEVERITY_RANK[extra["severity"]] > SEVERITY_RANK[result["severity"]]):
            return extra
    return result


def _assess_rules(text: str) -> Optional[dict]:
    norm = normalize(text)
    if not norm:
        return None
    best = None  # (rank, -order, dict)
    for order, (cat, pattern, base) in enumerate(_PATTERNS):
        for m in pattern.finditer(norm):
            prefix = norm[max(0, m.start() - 4):m.start()]
            if cat == "pause" and (_PAUSE_FALSE.search(norm) or "你" in norm[max(0, m.start() - 2):m.start()]
                                   or re.search(r"騙我|你在騙|知道你|詐騙", norm)):
                continue  # 「你別玩了，我知道你在騙我」是在質疑對方，不是要退出
            if cat == "ai_identity" and (_CHALLENGE.search(norm) or re.match(r"(你就|就|的話|那就)", norm[m.end():m.end() + 2])):
                continue  # 「你是真人你就視訊」是質疑，不是問 AI 身分
            if cat == "real_scam" and m.group(0).startswith("我") and "你" in norm[m.start():m.end() + 14] \
                    and not re.search("騙|詐", norm[m.start():m.end() + 14]):
                continue  # 「我剛剛匯了五萬到你的帳戶」：玩家在遊戲內對 NPC 說話，是入戲不是現實詐騙
            if cat == "real_scam" and re.search(r"我[^叫要逼]{0,8}(幫你|替你|給你|到你)", norm) \
                    and not re.search("騙|詐|被|叫我|要我|逼我", norm):
                continue  # 入戲：「我剛刷卡幫你付了保證金」
            if cat == "real_scam" and (_REFUSE_SCAM.search(norm) or _ASKED_BY_NPC.search(prefix + m.group(0))):
                continue  # 玩家正在拒絕或轉述 NPC 的要求
            if cat == "self_harm" and _NEG_PREFIX.search(prefix):
                continue  # 我沒有想死、我不是想自殺
            ctx = "first_person"
            sev = base
            if cat == "too_painful" and _WORK_CUES.search(norm) and "現實" not in norm:
                sev, ctx = "low", "hyperbole"  # 工作壓力大到快撐不住了
            if cat in _CONTEXT_CATS:
                ctx = _context(norm, m, cat)
                if ctx != "first_person":
                    sev = "low"
            cand = (SEVERITY_RANK[sev], -order, {
                "category": cat, "severity": sev,
                "ends_session": sev in ENDING_SEVERITIES, "context": ctx})
            if best is None or cand[:2] > best[:2]:
                best = cand
    return best[2] if best else None


def check(text: str) -> Optional[str]:
    """向下相容：回傳「需要終局」的類別，沒事（或只是溫和提醒／AI 身分）回 None。

    要拿到溫和提醒與 ai_identity，請改用 assess()。
    """
    hit = assess(text)
    return hit["category"] if hit and hit["ends_session"] else None


# ---------- 回覆文案 ----------
_MESSAGES = {
    "self_harm": "聽起來你現在真的很不好受，謝謝你願意說出來。你不用一個人撐著，現在就可以打 1925 找人聊聊。",
    "real_violence": "你描述的事情很嚴重，你的安全比任何遊戲都重要。如果有立即危險請打 113 或 110。",
    "real_scam": "如果現實中真的有人要你匯款、買點數或傳私密照，請先停下來，不要照做，也不是你的錯。可以先打 165 問問。",
    "minor": "這款遊戲的情境比較成人，建議你先暫停，有困擾可以找信任的大人聊聊。",
    "too_painful": "如果這些對話勾起了真實的痛苦，先停下來照顧自己，完全沒關係。",
    "pause": "好的，我們先暫停。隨時想回來都可以，你的進度會保留。",
    "model": "我們先暫停一下遊戲。",
    "ai_identity": ("我是 AI 驅動的模擬角色，不是真人。這是一款防詐騙的練習遊戲，"
                    "對話都是模擬的；現實中如果有網友讓你懷疑，可以打 165 查證。想繼續的話，我們可以回到遊戲。"),
}
_SOFT_MESSAGES = {
    "self_harm": ("我注意到你提到了和傷害自己有關的字眼。如果這是在說朋友、故事，或只是一時的氣話，我們可以繼續；"
                  "但如果其實是你自己的感受，請先停下來，撥 1925 找人聊聊，隨時都有人在。"),
    "real_violence": "我注意到你提到了暴力或跟蹤的情境。如果是你認識的人遇到，可以陪他打 113；如果是你自己，請先確認安全。",
    "real_scam": "我注意到你提到了詐騙或私密照的情境。如果是別人或故事就沒關係；如果是你自己遇到，請先停下來，打 165 問問。",
}
_DEFAULT_SEVERITY = {}
for _c, _p, _b in _PATTERNS:
    _DEFAULT_SEVERITY.setdefault(_c, _b)
_DEFAULT_SEVERITY["model"] = "medium"
_NOTE = "（這不是遊戲裡的角色在說話，這是安全提示。）"


def response(category: str, model_text: str = "", severity: Optional[str] = None) -> dict:
    """安全畫面資料。舊欄位 category/message/model_text/resources/disclaimer 保持不變，
    新增 severity、ends_session。severity 省略時用該類別的預設值。"""
    sev = severity or _DEFAULT_SEVERITY.get(category, "medium")
    if sev == "low" and category in _SOFT_MESSAGES:
        lead = _SOFT_MESSAGES[category]
    else:
        lead = _MESSAGES.get(category, _MESSAGES["model"])
    note = "" if category == "ai_identity" else "\n\n" + _NOTE
    return {
        "category": category,
        "severity": sev,
        "ends_session": sev in ENDING_SEVERITIES,
        "message": lead + note,
        "model_text": model_text,
        "resources": [] if category == "ai_identity" else RESOURCES,
        "disclaimer": "本遊戲不是心理治療，也不提供診斷或投資理財建議。",
    }


def respond(text: str) -> Optional[dict]:
    """便利函式：assess + response。沒事回 None。"""
    hit = assess(text)
    return response(hit["category"], severity=hit["severity"]) if hit else None
