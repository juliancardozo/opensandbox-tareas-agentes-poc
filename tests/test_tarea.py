import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import asyncio, types
import pytest
import tarea_agente as t


def test_politica_y_boveda_validan_con_el_sdk():
    p = t.politica_red()
    assert p.default_action == "deny" and {r.target for r in p.egress} == {"api.anthropic.com", "registry.npmjs.org", "github.com"}
    cred, vinc = t.boveda("acme/pagos", "sk-real", "bot", "ghp_x")
    assert vinc[1].match.paths == ["/acme/pagos.git*"] and vinc[0].auth.type == "apiKey"


class FakeSandbox:
    def __init__(self, fallar_en=None):
        self.id, self.matado, self.cmds, self.fallar_en = "sb-1", False, [], fallar_en
        self.vault = None
        self.credential_vault = types.SimpleNamespace(create=self._vault)
        self.commands = types.SimpleNamespace(run=self._run)
    async def _vault(self, credentials, bindings): self.vault = (credentials, bindings)
    async def _run(self, cmd, opts=None):
        self.cmds.append(cmd)
        code = 1 if self.fallar_en and cmd.startswith(self.fallar_en) else 0
        return types.SimpleNamespace(exit_code=code, logs=types.SimpleNamespace(stdout=[types.SimpleNamespace(text="ok")]))
    async def kill(self): self.matado = True


@pytest.fixture
def entorno(monkeypatch):
    for k, v in {"ANTHROPIC_API_KEY": "sk-real", "GIT_USER": "bot", "GIT_TOKEN": "ghp_x"}.items():
        monkeypatch.setenv(k, v)


def _crear(monkeypatch, fake, capturado):
    async def create(image, **kw):
        capturado.update(kw); return fake
    monkeypatch.setattr(t.Sandbox, "create", create)


def test_flujo_completo_sin_secretos_en_el_sandbox(monkeypatch, entorno):
    fake, kw = FakeSandbox(), {}
    _crear(monkeypatch, fake, kw)
    inf = asyncio.run(t.correr_tarea("ENG-42", "acme/pagos", "Agregar validación de moneda", "pagos"))
    assert inf["resultado"] == "ok" and fake.matado
    assert "sk-real" not in str(kw["env"]) and kw["metadata"]["ticket"] == "ENG-42"
    assert kw["credential_proxy"].enabled and fake.vault is not None
    assert not any("sk-real" in c or "ghp_x" in c for c in fake.cmds)


def test_corta_si_fallan_las_pruebas_y_destruye_el_sandbox(monkeypatch, entorno):
    fake, kw = FakeSandbox(fallar_en="make test"), {}
    _crear(monkeypatch, fake, kw)
    inf = asyncio.run(t.correr_tarea("ENG-43", "acme/pagos", "x", "pagos"))
    assert inf["resultado"] == "falló" and fake.matado
    assert not any(c.startswith("git diff") for c in fake.cmds)
