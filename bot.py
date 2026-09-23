import logging
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "America/Mexico_City"))
DB_PATH = os.getenv("DATABASE_PATH", "student_bot.db")
REMINDER_MINUTES = int(os.getenv("REMINDER_MINUTES", "60"))

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def now():
    return datetime.now(TIMEZONE)


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          subject TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '',
          due_at TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 2,
          duration INTEGER NOT NULL DEFAULT 30, completed INTEGER NOT NULL DEFAULT 0,
          reminded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS study_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          subject TEXT NOT NULL, goal TEXT NOT NULL, days INTEGER NOT NULL,
          plan TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY, first_name TEXT, created_at TEXT NOT NULL
        );
        """)


def priority_text(value):
    return {1: "🔴 alta", 2: "🟡 media", 3: "🟢 baja"}.get(value, "🟡 media")


def parse_date(value):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value, fmt).replace(tzinfo=TIMEZONE)
            return parsed
        except ValueError:
            pass
    raise ValueError("Usa YYYY-MM-DD HH:MM o DD/MM/YYYY HH:MM")


def task_line(task):
    due = datetime.fromisoformat(task["due_at"]).astimezone(TIMEZONE).strftime("%d/%m %H:%M")
    status = "✅" if task["completed"] else "⏳"
    return f"{status} *#{task['id']} {task['subject']}*: {task['title']} — {due} ({priority_text(task['priority'])}, {task['duration']} min)"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (user.id, user.first_name, now().isoformat()))
    await update.message.reply_text(
        f"¡Hola, {user.first_name}! Soy *EstudiaFácil* 📚\n\n"
        "Organizo tus tareas cotidianas y escolares, detecto choques de horario y te ayudo a estudiar con explicaciones, guías y planes personalizados.\n\n"
        "Escribe /ayuda para ver todos los comandos.", parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Comandos principales*\n\n"
        "*Tareas*\n"
        "`/agregar Materia | tarea | fecha y hora | prioridad | minutos`\n"
        "Ejemplo: `/agregar Matemáticas | ejercicios 5-10 | 2026-10-02 18:00 | alta | 45`\n"
        "`/hoy` — tareas de hoy\n`/pendientes` — próximas tareas\n`/simultaneas` — horarios que se cruzan\n"
        "`/completar ID` · `/eliminar ID` · `/resumen`\n\n"
        "*Estudio*\n"
        "`/explicar tema` — explicación sencilla paso a paso\n"
        "`/plan materia | objetivo | días` — plan de estudio\n"
        "`/guia tema` — guía de repaso, preguntas y ejercicios\n"
        "`/tecnica` — técnicas para estudiar mejor\n\n"
        "También puedes escribir una pregunta normal y trataré de ayudarte.", parse_mode=ParseMode.MARKDOWN)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 5:
        await update.message.reply_text("Formato: /agregar Materia | tarea | YYYY-MM-DD HH:MM | alta/media/baja | minutos")
        return
    subject, title, date_text, priority, duration = parts
    try:
        due = parse_date(date_text)
        priority_num = {"alta": 1, "media": 2, "baja": 3}.get(priority.lower(), int(priority) if priority.isdigit() else 2)
        duration_num = max(5, int(duration))
    except (ValueError, TypeError):
        await update.message.reply_text("No pude leer la fecha, prioridad o duración. Revisa el formato.")
        return
    with db() as con:
        cur = con.execute("INSERT INTO tasks(user_id, subject, title, due_at, priority, duration, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (update.effective_user.id, subject, title, due.isoformat(), priority_num, duration_num, now().isoformat()))
        task_id = cur.lastrowid
    await update.message.reply_text(f"Tarea #{task_id} guardada ✅\nUsa /simultaneas para revisar cruces.")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with db() as con:
        rows = con.execute("SELECT * FROM tasks WHERE user_id=? AND completed=0 AND due_at>=? ORDER BY due_at, priority", (user_id, now().isoformat())).fetchall()
    if not rows:
        await update.message.reply_text("No tienes tareas pendientes registradas 🎉")
        return
    today_only = update.message.text.split()[0] == "/hoy"
    if today_only:
        rows = [r for r in rows if datetime.fromisoformat(r["due_at"]).astimezone(TIMEZONE).date() == now().date()]
    await update.message.reply_text("*Tus tareas*\n\n" + ("\n".join(task_line(r) for r in rows[:30]) or "No hay tareas para hoy."), parse_mode=ParseMode.MARKDOWN)


async def clashes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        rows = con.execute("SELECT * FROM tasks WHERE user_id=? AND completed=0 ORDER BY due_at", (update.effective_user.id,)).fetchall()
    found = []
    for i, a in enumerate(rows):
        a_start = datetime.fromisoformat(a["due_at"])
        a_end = a_start + timedelta(minutes=a["duration"])
        for b in rows[i + 1:]:
            b_start = datetime.fromisoformat(b["due_at"])
            b_end = b_start + timedelta(minutes=b["duration"])
            if a_start < b_end and b_start < a_end:
                found.append(f"• #{a['id']} {a['title']} ↔ #{b['id']} {b['title']}")
    await update.message.reply_text("*Cruces detectados*\n\n" + ("\n".join(found) if found else "No hay tareas superpuestas. ¡Buen trabajo!"), parse_mode=ParseMode.MARKDOWN)


async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usa /completar ID")
        return
    with db() as con:
        result = con.execute("UPDATE tasks SET completed=1 WHERE id=? AND user_id=?", (int(context.args[0]), update.effective_user.id))
    await update.message.reply_text("Tarea completada ✅" if result.rowcount else "No encontré esa tarea.")


async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usa /eliminar ID")
        return
    with db() as con:
        result = con.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (int(context.args[0]), update.effective_user.id))
    await update.message.reply_text("Tarea eliminada 🗑️" if result.rowcount else "No encontré esa tarea.")


async def study_response(topic, mode="explain"):
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            prompts = {
                "explain": f"Explica a un estudiante de colegio, en español claro y paso a paso, el tema: {topic}. Incluye ejemplo, errores comunes y 3 preguntas de autoevaluación.",
                "guide": f"Crea una guía de estudio en español sobre {topic}: objetivos, conceptos clave, resumen, método de repaso, 5 preguntas y 2 ejercicios con respuestas breves.",
            }
            result = await client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=[{"role": "system", "content": "Eres un tutor paciente. No haces trampa académica: enseñas el procedimiento."}, {"role": "user", "content": prompts[mode]}], temperature=0.4)
            return result.choices[0].message.content
        except Exception as exc:
            log.warning("IA no disponible: %s", exc)
    return (f"*Plan local para estudiar: {topic}*\n\n1. Define el tema con tus palabras.\n2. Divide el contenido en conceptos pequeños.\n3. Busca un ejemplo y resuélvelo sin mirar.\n4. Explícalo en voz alta usando la técnica Feynman.\n5. Repasa con tarjetas y comprueba tus errores.\n\nSi quieres una explicación específica, añade OPENAI_API_KEY en `.env`." if mode == "explain" else f"*Guía de repaso: {topic}*\n\n• Objetivo: comprender y poder explicarlo.\n• Conceptos clave: definición, partes, ejemplo y aplicación.\n• Repaso: 25 minutos de estudio + 5 de descanso, repetir 3 veces.\n• Autoevaluación: ¿qué sé?, ¿qué no sé?, ¿cómo lo demostraría?\n• Termina creando 5 preguntas y respondiéndolas sin apuntes.")


async def explain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("Usa /explicar seguido del tema. Ejemplo: /explicar fracciones")
        return
    await update.message.reply_text("Estoy preparando una explicación clara… 📖")
    await update.message.reply_text(await study_response(topic), parse_mode=ParseMode.MARKDOWN)


async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("Usa /guia seguido del tema.")
        return
    await update.message.reply_text(await study_response(topic, "guide"), parse_mode=ParseMode.MARKDOWN)


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [p.strip() for p in " ".join(context.args).split("|")]
    if len(parts) != 3 or not parts[2].isdigit():
        await update.message.reply_text("Formato: /plan Materia | objetivo | días\nEjemplo: /plan Historia | preparar examen | 7")
        return
    subject, goal, days = parts[0], parts[1], min(30, int(parts[2]))
    chunks = [f"Día {i}: 25 min de teoría + 10 min de práctica + 5 min de recuerdo" for i in range(1, days + 1)]
    text = f"*Plan de {days} días — {subject}*\nObjetivo: {goal}\n\n" + "\n".join(chunks) + "\n\nConsejo: cada 3 días haz un simulacro sin apuntes."
    with db() as con:
        con.execute("INSERT INTO study_plans(user_id, subject, goal, days, plan, created_at) VALUES (?, ?, ?, ?, ?, ?)", (update.effective_user.id, subject, goal, days, text, now().isoformat()))
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def techniques(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("*Ayudas para estudiar* 📚\n\n• Pomodoro: 25 min concentración + 5 min descanso.\n• Recuperación activa: cierra el libro y recuerda lo aprendido.\n• Repetición espaciada: repasa hoy, mañana, en 3 días y en una semana.\n• Técnica Feynman: explica el tema como si enseñaras a alguien.\n• Intercalado: alterna materias o tipos de ejercicios.\n• Antes de dormir: prepara el material y elige 3 objetivos realistas.", parse_mode=ParseMode.MARKDOWN)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (update.effective_user.id,)).fetchone()[0]
        done = con.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND completed=1", (update.effective_user.id,)).fetchone()[0]
        overdue = con.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND completed=0 AND due_at<?", (update.effective_user.id, now().isoformat())).fetchone()[0]
    await update.message.reply_text(f"*Resumen*\n\nTotal: {total}\nCompletadas: {done}\nPendientes vencidas: {overdue}\n\nUsa /pendientes para organizar el siguiente paso.", parse_mode=ParseMode.MARKDOWN)


async def natural_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(await study_response(update.message.text), parse_mode=ParseMode.MARKDOWN)


async def reminders(context: ContextTypes.DEFAULT_TYPE):
    cutoff = now() + timedelta(minutes=REMINDER_MINUTES)
    with db() as con:
        rows = con.execute("SELECT * FROM tasks WHERE completed=0 AND reminded=0 AND due_at BETWEEN ? AND ?", (now().isoformat(), cutoff.isoformat())).fetchall()
        for row in rows:
            try:
                await context.bot.send_message(row["user_id"], f"⏰ Recordatorio: {task_line(row)}", parse_mode=ParseMode.MARKDOWN)
                con.execute("UPDATE tasks SET reminded=1 WHERE id=?", (row["id"],))
            except Exception as exc:
                log.warning("No se pudo enviar recordatorio: %s", exc)


def main():
    if not TOKEN:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en el archivo .env")
    init_db()
    app = Application.builder().token(TOKEN).build()
    for command, handler in [("start", start), ("ayuda", help_command), ("agregar", add_task), ("hoy", list_tasks), ("pendientes", list_tasks), ("simultaneas", clashes), ("completar", complete_task), ("eliminar", delete_task), ("explicar", explain), ("guia", guide), ("plan", plan), ("tecnica", techniques), ("resumen", summary)]:
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, natural_question))
    app.job_queue.run_repeating(reminders, interval=60, first=10)
    log.info("EstudiaFácil iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
