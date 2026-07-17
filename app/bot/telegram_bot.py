"""Telegram bot (docs/03-engineering-build-spec.md §6.5, §10).

Commands:
    (plain text/photo/voice) -> saved to inbox/, normalized immediately, replies with what it became
    /track <project-slug> <hours> <desc>   -> events(kind=time_entry), replies with budget status
    /done <habit>                          -> events(kind=habit_tick)  (streak logic is Phase 4's gap engine, not this)
    /lift <exercise> <scheme> <load>       -> events(kind=lift)
    /ask <question>                        -> RAG over embeddings, answered with llm()
    /invoice <project-slug> <YYYY-MM>      -> drafts an NL-compliant invoice note + PDF, sends the PDF back to you

Run with: python3 -m app.bot.telegram_bot
Needs TELEGRAM_BOT_TOKEN in .env, plus BUSINESS_* fields for /invoice
(see .env.example). Time is tracked per PROJECT, not client, because
budget_hours/rate live on the project note (app/crm/billing.py).

/invoice is the "propose -> confirm" step for money
(docs/03-engineering-build-spec.md §6.5, §10): it drafts the invoice note
+ PDF and sends the PDF to you in this chat for approval. It never emails
or sends it anywhere else — that stays a manual step, on purpose.
"""
from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.common import frontmatter
from app.common.config import get_env
from app.common.db import DB
from app.crm import billing
from app.crm.invoice_pdf import render_invoice_pdf
from app.llm import get_embedding, llm
from app.normalizer import process_drop

logger = logging.getLogger(__name__)

VAULT_PATH = Path("vault")
HELP_TEXT = (
    "Drop text, a photo, or a voice note and I'll file it.\n\n"
    "/track <project-slug> <hours> <desc> - log billable time\n"
    "/invoice <project-slug> <YYYY-MM> - draft an invoice for that month\n"
    "/done <habit> - tick a habit\n"
    "/lift <exercise> <scheme> <load> - log a set\n"
    "/ask <question> - ask the vault (RAG)\n"
)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> DB:
    return context.bot_data["db"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


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
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("lift", lift))
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
