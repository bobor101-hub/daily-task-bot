# EstudiaFácil — bot escolar y cotidiano

Bot de Telegram en español para organizar tareas diarias y escolares, detectar tareas simultáneas y apoyar el estudio con explicaciones, guías y planes.

## Funciones

- Tareas por materia, fecha/hora, prioridad y duración.
- Listas de tareas del día y pendientes.
- Detección de solapamientos entre tareas.
- Completar y eliminar tareas.
- Recordatorios automáticos hasta 60 minutos antes.
- Explicaciones paso a paso, ejemplos y autoevaluación.
- Guías de repaso con preguntas y ejercicios.
- Planes de estudio de 1 a 30 días.
- Técnicas: Pomodoro, Feynman, recuperación activa y repetición espaciada.
- SQLite local; cada estudiante solo ve sus propias tareas.
- Tutor IA opcional mediante OpenAI. Sin clave, funciona un modo local de estudio.

## Puesta en marcha

1. Crea un bot con [@BotFather](https://t.me/BotFather) en Telegram y copia su token.
2. Instala Python 3.11 o superior.
3. Crea un entorno e instala dependencias:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

4. Copia `.env.example` como `.env` y configura `TELEGRAM_BOT_TOKEN`.
5. Opcionalmente agrega `OPENAI_API_KEY` para respuestas más completas.
6. Ejecuta:

```bash
python bot.py
```

El bot usa *polling*, por lo que queda activo mientras el proceso esté ejecutándose. Para mantenerlo 24/7 puedes desplegarlo en un servidor o servicio de hosting que ejecute Python.

## Comandos

- `/agregar Materia | tarea | 2026-10-02 18:00 | alta | 45`
- `/hoy`, `/pendientes`, `/simultaneas`
- `/completar ID`, `/eliminar ID`, `/resumen`
- `/explicar fracciones`
- `/guia revolución francesa`
- `/plan Matemáticas | preparar examen | 7`
- `/tecnica`, `/ayuda`

El bot enseña y orienta: no sustituye al profesor y no debe usarse para copiar en exámenes.
