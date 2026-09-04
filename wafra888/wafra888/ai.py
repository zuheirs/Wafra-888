"""كل نداءات الذكاء الاصطناعي تصير من هون فقط — من طرف الخادم (server-side)، عشان
مفتاح الـ API ما ينكشف أبداً بمتصفح أي عضو (كانت هاي الثغرة بالنموذج الأولي).

يستخدم Gemini API (google.dev) — اختيار مجاني بالكامل طلبه زهير صراحة، بعد ما
انوضحله إن الخطة المجانية بتستخدم المحادثات لتحسين موديلات جوجل (خلافاً لـ
Anthropic API المدفوع يلي ما بيعمل هيك افتراضياً). لو حبيتوا تبدّلوا لمزوّد
تاني لاحقاً، هاد الملف هو المكان الوحيد يلي لازم يتعدّل — كل باقي الكود بيتعامل
بس مع _call_ai() بشكل عام."""
from __future__ import annotations

import logging
import re
import threading
import time

import requests
from flask import current_app

from . import repo
from .constitution import FULL_CONSTITUTION_TEXT

logger = logging.getLogger("wafra888.ai")

DCA_REQUEST_RE = re.compile(r"\[DCA_REQUEST\](.*?)\[/DCA_REQUEST\]", re.DOTALL)


class AIError(RuntimeError):
    pass


def _to_gemini_role(role: str) -> str:
    # Gemini بيسمّي رد الموديل "model" مش "assistant" — التخزين بقاعدة البيانات
    # ضل "assistant" بكل مكان تاني بالكود، هاد التحويل بس لحظة نداء الـ API.
    return "model" if role == "assistant" else "user"


def _call_ai(messages: list[dict], system: str, max_tokens: int) -> str:
    api_key = current_app.config["GEMINI_API_KEY"]
    if not api_key:
        raise AIError(
            "ما في مفتاح Gemini API مضبوط بالخادم (GEMINI_API_KEY). "
            "كلّم القيادة التقنية لضبطه."
        )
    model = current_app.config["GEMINI_MODEL"]
    url = current_app.config["GEMINI_API_URL_TEMPLATE"].format(model=model)

    payload = {
        "contents": [
            {"role": _to_gemini_role(m["role"]), "parts": [{"text": m["content"]}]}
            for m in messages
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            # موديلات Gemini 3 (زي gemini-flash-latest) بتستخدم "تفكير داخلي" قبل
            # الرد، وهاد التفكير بياكل من نفس حصة maxOutputTokens — لو خليناه
            # افتراضي كان عم ياكل معظم الحصة ويطلع رد مبتور بالنص. "low" أخفض
            # مستوى مدعوم فعلياً بالموديل الحالي (gemini-3.7-flash ما بيدعم
            # "minimal" وبيرجع خطأ 400 عليها) عشان يفضل أكبر قدر ممكن من
            # الحصة للرد الفعلي يلي بيشوفه العضو.
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    headers = {"x-goog-api-key": api_key, "content-type": "application/json"}

    # موديلات Gemini المجانية بترجع أحياناً 503 (UNAVAILABLE) وقت الضغط العالي —
    # Google نفسها بتقول بالرسالة إنه مؤقت وينصح بإعادة المحاولة. منجرب لحتى 3
    # مرات بفواصل قصيرة قبل ما نطلع خطأ للعضو، عشان أغلب حالات "high demand"
    # بتنحل خلال ثواني.
    max_attempts = 3
    resp = None
    for attempt in range(1, max_attempts + 1):
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            break
        is_retryable = resp.status_code in (503, 429)
        if is_retryable and attempt < max_attempts:
            logger.warning(
                "Gemini API %s (محاولة %d/%d) — بعيد المحاولة...",
                resp.status_code, attempt, max_attempts,
            )
            time.sleep(2 * attempt)  # 2s ثم 4s
            continue
        break

    if resp.status_code != 200:
        logger.error("Gemini API error %s: %s", resp.status_code, resp.text[:500])
        if resp.status_code in (503, 429):
            raise AIError(
                "الكيان مزحوم شوي هلق (خدمة Gemini تحت ضغط عالي). جرب بعد دقيقة."
            )
        raise AIError(f"صار خطأ من Gemini API (كود {resp.status_code})")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        # ممكن يصير لو الرد انحجب بفلتر أمان جوجل (finishReason=SAFETY) وما رجع نص
        reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
        raise AIError(f"Gemini ما رجّع رد (سبب: {reason})")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "\n".join(p.get("text", "") for p in parts if "text" in p).strip()


def _member_system_prompt(account: dict, profile: dict | None) -> str:
    profile = profile or {}
    return f"""أنت "كيان الماستر مايند" الخاص بمجموعة وفرة 888. تتكلم مع {account['name']} بخصوصية تامة —
لا القيادة ولا أي عضو تاني بيشوف هاد الحكي.

{FULL_CONSTITUTION_TEXT}

معلومات العضو الحالية:
- DCA: {profile.get('dca') or 'غير محدد بعد'}
- هدف 4 أشهر: {profile.get('goal4m') or 'غير محدد بعد'}
- العائق: {profile.get('fear') or 'غير محدد بعد'}
- أنماطه (بكلماته): {profile.get('patterns') or 'غير محدد بعد'}

كل كلامك ونصائحك لازم تنبع من هالدستور (الـ WHY والقيم)، بالإضافة لمبادئ نابليون هيل
(الهدف المحدد، الإيمان، المثابرة، تحالف العقول) ومفاهيم د. جو ديسبنزا (تنظيم الجهاز
العصبي وتغيير الحالة الداخلية) — بصياغتك الخاصة تماماً، بدون اقتباس حرفي من أي كتاب
أو مصدر.

إذا طلب العضو تغيير الـ DCA تبعه: ناقشه أولاً بعمق (هل هاد نمو حقيقي أم نمط هروب
متكرر؟)، وإذا أصرّ وحدد القيمة الجديدة بوضوح، أخبره إن هذا يحتاج موافقة القيادة،
وأنهِ ردك بسطر منفصل تماماً بالشكل: [DCA_REQUEST]القيمة الجديدة[/DCA_REQUEST]
(هاد السطر رح ينحذف من الرد يلي بيشوفه العضو وينبعث كطلب رسمي للقيادة).

كن مباشر ودافئ وعملي، وما تطوّل أكتر من اللازم."""


def chat_with_member(account: dict, user_text: str) -> dict:
    """يرسل رسالة العضو للكيان، يخزّن الرد، يكتشف طلبات تغيير DCA، ويشغّل استخراج
    النمط بالخلفية (بدون ما يوقف الرد عن العضو)."""
    profile = repo.get_profile(account["id"])
    repo.append_chat_message(account["id"], "user", user_text)

    history = repo.get_chat_history(account["id"], limit=current_app.config["CHAT_HISTORY_WINDOW"])
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    system = _member_system_prompt(account, profile)
    reply = _call_ai(api_messages, system, max_tokens=1500)

    match = DCA_REQUEST_RE.search(reply)
    dca_request_created = False
    if match:
        new_dca = match.group(1).strip()
        reply = DCA_REQUEST_RE.sub("", reply).strip()
        if new_dca:
            repo.create_dca_request(account["id"], (profile or {}).get("dca") or "", new_dca)
            dca_request_created = True

    repo.append_chat_message(account["id"], "assistant", reply)

    # استخراج النمط بالخلفية — ما بيوقف رد العضو، وما بيشوفه العضو أبداً
    app_obj = current_app._get_current_object()
    thread = threading.Thread(
        target=_extract_pattern_background, args=(app_obj, account["id"]), daemon=True
    )
    thread.start()

    return {"reply": reply, "dca_request_created": dca_request_created}


PATTERN_PROMPT = """أنت محلل أنماط سلوكية لصالح قيادة ماسترمايند وفرة 888. من المحادثة
التالية بين عضو وكيان الماسترمايند، استخرج نمط سلوكي عام واحد فقط ينفع القيادة.

قواعد صارمة وإلزامية:
- ممنوع نقل أي جملة حرفية من كلام العضو
- ممنوع ذكر أي تفصيل شخصي محدد (اسم شخص، حدث، مكان، موضوع خاص تحدث عنه)
- اكتب النمط بشكل مجرد فقط، سطر واحد أقل من 15 كلمة، مثل: "ميل لتبرير التأجيل" أو
  "تقدم ثابت بالتنفيذ" أو "يعيد طرح نفس التساؤل بدل الحسم"
- إذا ما في نمط واضح أو جديد، اكتب بالضبط: لا يوجد نمط جديد ملحوظ

رد بالسطر فقط بدون أي مقدمة أو شرح.

المحادثة:
{recent}"""


def _extract_pattern_background(app_obj, account_id: int) -> None:
    with app_obj.app_context():
        try:
            history = repo.get_chat_history(account_id, limit=6)
            recent = "\n".join(
                ("العضو: " if m["role"] == "user" else "الكيان: ") + m["content"] for m in history[-6:]
            )
            prompt = PATTERN_PROMPT.format(recent=recent)
            note = _call_ai([{"role": "user", "content": prompt}], system="", max_tokens=300)
            note = note.strip()
            if note and note != "لا يوجد نمط جديد ملحوظ":
                repo.add_pattern_note(account_id, note)
        except Exception:  # pragma: no cover - background best-effort
            logger.exception("pattern extraction failed for account %s", account_id)


def leadership_report(records: list[dict]) -> str:
    # قصداً ما منمرر غير DCA وهدف الـ4 أشهر — العائق/شو بيعطي/شو بدو إجابات خاصة
    # بالعضو وما لازم توصل حرفياً لا للقيادة ولا للذكاء الاصطناعي بهالسياق.
    data_text = "\n---\n".join(
        f"الاسم: {r['name']}\nDCA: {r.get('dca','')}\nهدف 4 أشهر: {r.get('goal4m','')}"
        for r in records
    )
    prompt = f"""أنت مساعد ماسترمايند "وفرة 888" القائم على مبادئ نابليون هيل ومفاهيم د. جو
ديسبنزا. لكل عضو اكتب: 1) ملخص قصير بناءً على الـ DCA والهدف، 2) نصيحة عملية مختصرة
بصياغتك الخاصة بدون اقتباس حرفي. اكتب بالعربية منظم بعنوان لكل عضو.

{data_text}"""
    return _call_ai([{"role": "user", "content": prompt}], system="", max_tokens=2500)


def leadership_chat(leader_account: dict, user_text: str, aggregate_data: list[dict]) -> str:
    repo.append_leader_chat_message(leader_account["id"], "user", user_text)
    data_text = "\n".join(
        f"{r['name']}: DCA={r.get('dca','')} | هدف4أشهر={r.get('goal4m','')}"
        for r in aggregate_data
    )
    system = f"""أنت مساعد قيادة ماسترمايند "وفرة 888". عندك بيانات الأعضاء العامة التالية
(وليس أي محتوى من المحادثات الخاصة للأعضاء، هذه سرية تماماً):
{data_text}

{FULL_CONSTITUTION_TEXT}

جاوب أسئلة القيادة بشكل مباشر ومختصر، وركّز عند الطلب على وين المجموعة ككل بطريق
تحقيق الرؤية، مش بس التزام كل فرد لحاله."""
    history = repo.get_leader_chat_history(leader_account["id"], limit=current_app.config["CHAT_HISTORY_WINDOW"])
    api_messages = [{"role": m["role"], "content": m["content"]} for m in history]
    reply = _call_ai(api_messages, system, max_tokens=1500)
    repo.append_leader_chat_message(leader_account["id"], "assistant", reply)
    return reply
