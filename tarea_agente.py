"""Ejecuta una tarea de un agente de código en un sandbox aislado y devuelve un informe auditable."""
import asyncio, base64, json, os, shlex, sys
from datetime import timedelta

from opensandbox import Sandbox
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.sandboxes import (
    Credential, CredentialBinding, CredentialProxyConfig, NetworkPolicy, NetworkRule,
)

ANTHROPIC = "api.anthropic.com"
GIT_HOST = "github.com"


def politica_red() -> NetworkPolicy:
    # Todo lo que no está en la lista queda bloqueado.
    return NetworkPolicy(defaultAction="deny", egress=[
        NetworkRule(action="allow", target=ANTHROPIC),
        NetworkRule(action="allow", target="registry.npmjs.org"),
        NetworkRule(action="allow", target=GIT_HOST),
    ])


def boveda(repo: str, anthropic_key: str, git_user: str, git_token: str):
    basic = base64.b64encode(f"{git_user}:{git_token}".encode()).decode()
    credenciales = [
        Credential(name="anthropic", source={"value": anthropic_key}),
        Credential(name="git", source={"value": basic}),
    ]
    vinculos = [
        CredentialBinding(name="anthropic-api",
                          match={"schemes": ["https"], "hosts": [ANTHROPIC], "paths": ["/v1/*"]},
                          auth={"type": "apiKey", "name": "x-api-key", "credential": "anthropic"}),
        CredentialBinding(name="git-repo",                       # solo este repositorio
                          match={"schemes": ["https"], "hosts": [GIT_HOST], "paths": [f"/{repo}.git*"]},
                          auth={"type": "basic", "credential": "git"}),
    ]
    return credenciales, vinculos


async def ejecutar(sb, cmd: str, minutos: int = 10) -> dict:
    ex = await sb.commands.run(cmd, opts=RunCommandOpts(working_directory="/workspace/repo",
                                                        timeout=timedelta(minutes=minutos)))
    return {"cmd": cmd.split()[0], "exit_code": ex.exit_code,
            "salida": "".join(m.text for m in ex.logs.stdout)[-4000:]}


async def correr_tarea(ticket: str, repo: str, instruccion: str, equipo: str) -> dict:
    sb = await Sandbox.create(
        os.getenv("SANDBOX_IMAGE", "opensandbox/code-interpreter:latest"),
        timeout=timedelta(minutes=30),                      # el sandbox expira solo
        resource={"cpu": "2", "memory": "4Gi"},
        env={"ANTHROPIC_API_KEY": "placeholder", "GIT_TERMINAL_PROMPT": "0"},  # sin secretos reales
        metadata={"equipo": equipo, "ticket": ticket},      # trazabilidad y costos por equipo
        network_policy=politica_red(),
        credential_proxy=CredentialProxyConfig(enabled=True),
    )
    informe = {"ticket": ticket, "sandbox": sb.id, "pasos": []}
    try:
        cred, vinc = boveda(repo, os.environ["ANTHROPIC_API_KEY"],
                            os.environ["GIT_USER"], os.environ["GIT_TOKEN"])
        await sb.credential_vault.create(credentials=cred, bindings=vinc)
        await sb.commands.run(f"git clone https://{GIT_HOST}/{repo}.git /workspace/repo")
        await sb.commands.run("npm install -g @anthropic-ai/claude-code --no-audit --no-fund")
        for cmd in (f"claude -p {shlex.quote(instruccion)} --output-format json",
                    "make test",
                    "git diff --stat"):
            paso = await ejecutar(sb, cmd)
            informe["pasos"].append(paso)
            if paso["exit_code"] not in (0, None):
                break
        informe["resultado"] = "ok" if all(p["exit_code"] in (0, None) for p in informe["pasos"]) else "falló"
        return informe
    finally:
        await sb.kill()                                     # nada queda corriendo


if __name__ == "__main__":
    ticket, repo, instruccion = sys.argv[1:4]
    print(json.dumps(asyncio.run(correr_tarea(ticket, repo, instruccion, os.getenv("EQUIPO", "plataforma"))),
                     ensure_ascii=False, indent=2))
