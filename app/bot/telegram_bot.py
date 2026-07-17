"""Telegram bot skeleton (docs/03-engineering-build-spec.md §6.5).

Commands:
    (plain text/photo/voice) -> saved to inbox/, normalized immediately, replies with what it became
    /track <client> <hours> <desc>   -> events(kind=time_entry)
    /done <habit>                    -> events(kind=habit_tick)  (streak logic is Phase 4's gap engine, not this)
    /lift <exercise> <scheme> <load> -> events(kind=lift)
    /ask <question>                  -> RAG over embeddings, answered with llm()

Run with: python3 -m app.bot.telegram_bot
Needs TELEGRAM_BOT_TOKEN in .env. All money/self-model writes elsewhere in
the system go through a propose->confirm step (docs/03-engineering-build-spec.md
§6.5, §8.3) — this Phase 1 skeleton only has plain logging commands, so
there's nothing to confirm yet; that pattern lands with the gap engine
(Phase 4) and CRM invoicing (Phase 3).
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.common.config import get_env
from app.common.db import DB
from app.llm import get_embedding, llm
from app.normalizer import process_drop

logger = logging.getLogger(__name__)

VAULT_PATH = Path("vault")
HELP_TEXT = (
    "Drop text, a photo, or a voice note and I'll file it.\n\n"
    "/track <client> <hours> <desc> - log billable time\n"
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
        await update.message.reply_text("usage: /track <client> <hours> <description...>")
        return
    client, hours, *desc_words = args
    try:
        hours_val = float(hours)
    except ValueError:
        await update.message.reply_text(f"'{hours}' isn't a number of hours")
        return
    _get_db(context).insert_event(
        "time_entry", value=hours_val, meta={"client": client, "desc": " ".join(desc_words)}, source="coach"
    )
    await update.message.reply_text(f"Logged {hours_val}h on {client}.")


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
