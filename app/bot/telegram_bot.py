"""Telegram bot (docs/03-engineering-build-spec.md §6.5, §10).

Commands:
    (plain text/photo/voice) -> saved to inbox/, normalized immediately, replies with what it became
    /track <project-slug> <hours> <desc>   -> events(kind=time_entry), replies with budget status
    /done <habit>                          -> events(kind=habit_tick)  (streak logic is Phase 4's gap engine, not this)
    /lift <exercise> <scheme> <load>       -> events(kind=lift)
    /next <exercise>                       -> suggested next load (progressive overload / sleep-based deload, Phase 7)
    /ask <question>                        -> RAG over embeddings, answered with llm()
    /invoice <project-slug> <YYYY-MM>      -> drafts an NL-compliant invoice note + PDF, sends the PDF back to you
    /review                                -> lists pending proposals (from the gap engine, Phase 4) with Confirm/Reject buttons
    /idea <description>                    -> fast verdict (Phase 6 stage 1+2); deep report is the biz-eval Skill, not this bot

Run with: python3 -m app.bot.telegram_bot
Needs TELEGRAM_BOT_TOKEN in .env, plus BUSINESS_* fields for /invoice
(see .env.example). Time is tracked per PROJECT, not client, because
budget_hours/rate live on the project note (app/crm/billing.py).

/invoice and /review are the "propose -> confirm" step required by
docs/03-engineering-build-spec.md §12 ("the brain never silently edits
your identity model or generates an invoice without you approving it"):
/invoice drafts a PDF and sends it here for approval (never auto-sent
elsewhere); /review is how OKR/habit/experiment proposals the gap engine
writes (tagged `proposed`) get confirmed or rejected — see app/bot/confirm.py.

/start records this chat as the one to push proactive messages to (the
morning brief, live nudges — Phase 5) via TELEGRAM_CHAT_ID; the bot has
no other way to know who to message first.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot import confirm
from app.common import frontmatter
from app.common.config import get_env
from app.common.db import DB
from app.crm import billing
from app.crm.invoice_pdf import render_invoice_pdf
from app.evaluator import idea_intake
from app.health import training
from app.llm import get_embedding, llm
from app.normalizer import process_drop

logger = logging.getLogger(__name__)

VAULT_PATH = Path("vault")
HELP_TEXT = (
    "Drop text, a photo, or a voice note and I'll file it.\n\n"
    "/track <project-slug> <hours> <desc> - log billable time\n"
    "/invoice <project-slug> <YYYY-MM> - draft an invoice for that month\n"
    "/review - confirm or reject pending proposals\n"
    "/idea <description> - fast verdict on a business idea\n"
    "/done <habit> - tick a habit\n"
    "/lift <exercise> <scheme> <load> - log a set\n"
    "/next <exercise> - suggested load for next session\n"
    "/ask <question> - ask the vault (RAG)\n"
)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> DB:
    return context.bot_data["db"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"{HELP_TEXT}\nYour chat id is {chat_id} — set TELEGRAM_CHAT_ID={chat_id} "
        f"in .env so the coach (Phase 5) knows where to push the morning "
        f"brief and nudges. Nothing pushes proactively until you do."
    )


async def review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = confirm.list_pending(VAULT_PATH)
    if not pending:
        await update.message.reply_text("Nothing pending review.")
        return

    id_map = context.bot_data.setdefault("pending_map", {})
    for path in pending:
        short_id = uuid.uuid4().hex[:10]
        id_map[short_id] = path
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Confirm", callback_data=f"c:{short_id}"),
                    InlineKeyboardButton("Reject", callback_data=f"r:{short_id}"),
                ]
            ]
        )
        await update.message.reply_text(confirm.describe(path), reply_markup=keyboard)


async def on_review_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, short_id = query.data.split(":", 1)
    path = context.bot_data.get("pending_map", {}).get(short_id)
    if path is None or not path.is_file():
        await query.edit_message_text("That proposal is gone (already handled, or vault changed).")
        return

    if action == "c":
        confirm.confirm(path)
        await query.edit_message_text(f"Confirmed: {confirm.describe(path)}")
    else:
        confirm.reject(path)
        await query.edit_message_text(f"Rejected: {confirm.describe(path)}")
    context.bot_data["pending_map"].pop(short_id, None)


async def capture_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    drop_path = VAULT_PATH / "inbox" / f"telegram-{update.message.message_id}.txt"
    drop_path.parent.mkdir(parents=True, exist_ok=True)
    drop_path.write_text(text, encoding="utf-8")
    await _process_and_reply(update, context, drop_path)


async def capture_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]
    file = await photo.get_file()
    drop_path = VAULT_PATH / "inbox" / f"telegram-{update.message.message_id}.jpg"
    drop_path.parent.mkdir(parents=True, exist_ok=True)
    await file.download_to_drive(str(drop_path))
    await _process_and_reply(update, context, drop_path)


async def capture_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice
    file = await voice.get_file()
    drop_path = VAULT_PATH / "inbox" / f"telegram-{update.message.message_id}.ogg"
    drop_path.parent.mkdir(parents=True, exist_ok=True)
    await file.download_to_drive(str(drop_path))
    await _process_and_reply(update, context, drop_path)


async def _process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, drop_path: Path) -> None:
    try:
        note_path = process_drop(VAULT_PATH, drop_path, db=_get_db(context))
        await update.message.reply_text(f"Filed as {note_path.relative_to(VAULT_PATH)}")
    except Exception as exc:  # noqa: BLE001 - reply with the failure rather than silently drop
        logger.exception("capture failed")
        await update.message.reply_text(f"Couldn't process that: {exc}")


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("usage: /track <project-slug> <hours> <description...>")
        return
    project_slug, hours, *desc_words = args
    try:
        hours_val = float(hours)
    except ValueError:
        await update.message.reply_text(f"'{hours}' isn't a number of hours")
        return

    db = _get_db(context)
    db.insert_event(
        "time_entry", value=hours_val, meta={"project": project_slug, "desc": " ".join(desc_words)}, source="coach"
    )
    try:
        status = billing.budget_status(VAULT_PATH, db, project_slug)
        await update.message.reply_text(
            f"Logged {hours_val}h on {project_slug}. "
            f"{status['logged_hours']:.1f}h / {status['budget_hours']:.1f}h budget "
            f"({status['remaining_hours']:.1f}h remaining)."
        )
    except FileNotFoundError:
        await update.message.reply_text(
            f"Logged {hours_val}h on {project_slug} (no project note found at "
            f"crm/projects/project--{project_slug}.md, so no budget to compare against)."
        )


async def invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) != 2 or "-" not in args[1]:
        await update.message.reply_text("usage: /invoice <project-slug> <YYYY-MM>")
        return
    project_slug, period = args
    try:
        year_str, month_str = period.split("-")
        year, month = int(year_str), int(month_str)
    except ValueError:
        await update.message.reply_text(f"'{period}' isn't YYYY-MM")
        return

    db = _get_db(context)
    try:
        invoice_data = billing.compute_invoice(VAULT_PATH, db, project_slug, year, month)
    except FileNotFoundError as exc:
        await update.message.reply_text(str(exc))
        return

    invoice_path = VAULT_PATH / "crm" / "invoices" / f"invoice--{invoice_data['number']}.md"
    fm, _ = frontmatter.new_note_from_template(
        VAULT_PATH, "invoice", overrides={"visibility": "sensitive", **invoice_data}
    )
    frontmatter.write_note(invoice_path, fm)

    pdf_path = VAULT_PATH / "crm" / "invoices" / f"invoice--{invoice_data['number']}.pdf"
    render_invoice_pdf(invoice_data, pdf_path)

    await update.message.reply_document(
        document=open(pdf_path, "rb"),
        filename=pdf_path.name,
        caption=(
            f"Draft invoice {invoice_data['number']} for {project_slug}, {period}: "
            f"{invoice_data['hours']:.1f}h -> EUR {invoice_data['total']:.2f}. "
            f"Review before sending it anywhere — nothing here emails or sends it for you."
        ),
    )


async def idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("usage: /idea <description>")
        return
    idea_text = " ".join(context.args)
    verdict = idea_intake.fast_verdict(VAULT_PATH, idea_text)

    slug = frontmatter.new_id()  # timestamp-based slug keeps ideas with similar titles distinct
    fm, _ = frontmatter.new_note_from_template(
        VAULT_PATH,
        "idea",
        overrides={
            "verdict": verdict["verdict"],
            "idea_score": verdict["idea_score"],
            "fit_score": verdict["fit_score"],
            "report_status": "none",
        },
    )
    path = VAULT_PATH / "ideas" / f"idea--{slug}.md"
    frontmatter.write_note(path, fm, idea_text)

    await update.message.reply_text(idea_intake.format_verdict_card(verdict))


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("usage: /done <habit>")
        return
    habit = context.args[0]
    _get_db(context).insert_event("habit_tick", meta={"habit": habit}, source="coach")
    await update.message.reply_text(f"Ticked '{habit}'.")


async def lift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.message.reply_text("usage: /lift <exercise> <scheme e.g. 5x5> <load e.g. 80kg>")
        return
    exercise, scheme, load = context.args[0], context.args[1], context.args[2]
    _get_db(context).insert_event(
        "lift", meta={"exercise": exercise, "scheme": scheme, "load": load}, source="coach"
    )
    await update.message.reply_text(f"Logged {exercise} {scheme} @ {load}.")


async def next_lift(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("usage: /next <exercise>")
        return
    exercise = context.args[0]
    result = training.suggest_next_load(_get_db(context), exercise)
    if result["suggestion"] is None:
        await update.message.reply_text(f"{exercise}: {result['reason']}")
    else:
        await update.message.reply_text(f"{exercise}: try {result['suggestion']}kg — {result['reason']}")


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("usage: /ask <question>")
        return
    question = " ".join(context.args)
    db = _get_db(context)
    matches = db.search_embeddings(get_embedding(question), limit=5)

    context_blocks = []
    for match in matches:
        note_path = VAULT_PATH / match["ref"]
        if note_path.is_file():
            context_blocks.append(note_path.read_text(encoding="utf-8"))
    context_text = "\n\n---\n\n".join(context_blocks) or "(no matching notes found)"

    answer = llm(
        f"Answer the question using ONLY the vault excerpts below. If they don't "
        f"contain the answer, say so plainly.\n\nQuestion: {question}\n\n"
        f"Vault excerpts:\n{context_text}",
        tier="default",
        max_tokens=500,
    )
    await update.message.reply_text(answer)


def build_app() -> Application:
    token = get_env("TELEGRAM_BOT_TOKEN", required=True)
    application = Application.builder().token(token).build()
    application.bot_data["db"] = DB()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("track", track))
    application.add_handler(CommandHandler("invoice", invoice))
    application.add_handler(CommandHandler("review", review))
    application.add_handler(CallbackQueryHandler(on_review_button, pattern=r"^[cr]:"))
    application.add_handler(CommandHandler("idea", idea))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("lift", lift))
    application.add_handler(CommandHandler("next", next_lift))
    application.add_handler(CommandHandler("ask", ask))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_text))
    application.add_handler(MessageHandler(filters.PHOTO, capture_photo))
    application.add_handler(MessageHandler(filters.VOICE, capture_voice))
    return application


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    app = build_app()
    logger.info("bot starting, polling for updates...")
    app.run_polling()


if __name__ == "__main__":
    main()
