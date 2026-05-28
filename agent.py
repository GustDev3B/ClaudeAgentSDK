"""
Agente básico usando Claude Code CLI directamente.
No requiere API key — usa la autenticación de Claude Code.
"""

import asyncio
import json
import sys


async def run_agent(prompt: str) -> None:
    print(f"\n>>> Prompt: {prompt}")
    print("-" * 50)

    process = await asyncio.create_subprocess_exec(
        "claude",
        "--output-format", "stream-json",
        "--verbose",
        "--print",
        "--",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    buffer = ""
    async for raw_line in process.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue

        buffer += line
        try:
            data = json.loads(buffer)
            buffer = ""
        except json.JSONDecodeError:
            continue

        msg_type = data.get("type", "")

        if msg_type == "assistant":
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    print(block["text"])

        # "result" es el resumen final — ya imprimimos el contenido arriba

        elif msg_type == "rate_limit_event":
            retry_ms = data.get("retry_after_ms", 0)
            retry_s = (retry_ms / 1000) if retry_ms else 5
            print(f"[Rate limit] Esperando {retry_s:.0f}s...")
            await asyncio.sleep(retry_s)

    await process.wait()


async def main():
    print("=== Agente Claude Code SDK ===")
    await run_agent("Cual es la capital de Bolivia y cual es su altitud aproximada?")


if __name__ == "__main__":
    asyncio.run(main())
