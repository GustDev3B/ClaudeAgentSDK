"""
Agente Claude conectado al Data Agent de Microsoft Fabric via MCP.
Autentica con Azure AD y pasa el token al servidor MCP de Fabric.
"""

import asyncio
import json
import shutil
from pathlib import Path
from azure.identity import InteractiveBrowserCredential


def find_claude() -> str:
    """Encuentra el ejecutable de claude en el sistema."""
    # 1. Buscar en el PATH normal
    if cmd := shutil.which("claude"):
        return cmd
    # 2. Buscar en ubicaciones comunes de Volta y npm en Windows
    candidates = [
        Path.home() / "AppData/Local/Volta/bin/claude.cmd",
        Path.home() / "AppData/Local/Volta/bin/claude",
        Path.home() / "AppData/Roaming/npm/claude.cmd",
        Path.home() / "AppData/Roaming/npm/claude",
        Path.home() / "AppData/Local/npm/claude.cmd",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError(
        "No se encontro el ejecutable 'claude'.\n"
        "Asegurate de tener Claude Code instalado y ejecuta desde PowerShell."
    )

FABRIC_MCP_URL = (
    "https://api.fabric.microsoft.com/v1/mcp/workspaces/"
    "be2ea36c-3935-42e9-9a26-45e22db69941/dataagents/"
    "89444cc8-c862-448b-9541-7390574a151b/agent"
)
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


def get_token() -> str:
    print("[Auth] Iniciando autenticacion con Microsoft...")
    credential = InteractiveBrowserCredential()
    token = credential.get_token(FABRIC_SCOPE).token
    print("[Auth] Token OK\n")
    return token


def build_mcp_config(token: str) -> str:
    config = {
        "mcpServers": {
            "fabric-gold": {
                "type": "http",
                "url": FABRIC_MCP_URL,
                "headers": {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            }
        }
    }
    return json.dumps(config)


async def ask_fabric(question: str, token: str) -> None:
    print(f">>> {question}")
    print("-" * 60)

    mcp_config = build_mcp_config(token)

    claude_bin = find_claude()
    process = await asyncio.create_subprocess_exec(
        claude_bin,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--mcp-config", mcp_config,
        "--print",
        "--",
        question,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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

        if msg_type == "user":
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    print(f"\n[MCP Tool result RAW]\n{json.dumps(block.get('content', ''), ensure_ascii=False)[:800]}")

        elif msg_type == "assistant":
            for block in data.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    print(block["text"])
                elif block.get("type") == "tool_use":
                    print(f"\n[MCP Tool call] {block.get('name')} → {json.dumps(block.get('input', {}))[:200]}")
                elif block.get("type") == "tool_result":
                    print(f"\n[MCP Tool result] {str(block.get('content', ''))[:400]}")

        elif msg_type == "rate_limit_event":
            retry_ms = data.get("retry_after_ms", 0)
            retry_s = (retry_ms / 1000) if retry_ms else 5
            print(f"[Rate limit] Esperando {retry_s:.0f}s...")
            await asyncio.sleep(retry_s)

    stderr_output = await process.stderr.read()
    await process.wait()

    if stderr_output:
        stderr_text = stderr_output.decode("utf-8", errors="replace").strip()
        if stderr_text:
            print(f"\n[DEBUG stderr]\n{stderr_text[:1000]}")


async def main():
    print("=== Agente Claude + Fabric MCP (RetailGoldAgent) ===")
    print("Tablas disponibles: gold_fact_ventas, gold_fact_facturas, gold_fact_stock_tienda")
    print("Escribe 'salir' para terminar.\n")

    token = get_token()

    while True:
        try:
            pregunta = input("Tu pregunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break

        if not pregunta:
            continue
        if pregunta.lower() in ("salir", "exit", "quit"):
            print("Hasta luego.")
            break

        await ask_fabric(pregunta, token)
        print()


if __name__ == "__main__":
    asyncio.run(main())
