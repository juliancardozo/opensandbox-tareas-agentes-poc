# Tareas de agentes de código en OpenSandbox con permisos mínimos

Prueba de concepto que acompaña el artículo **[OpenSandbox: dónde corren los agentes de IA y por qué es una decisión de Engineering Management](https://juliancardozo.github.io/blog/opensandbox-agentes-ia-engineering-management/)**.

## Motivación técnica

Cuando un agente de código corre en la laptop de un desarrollador o en un runner compartido, hereda sus permisos, sus credenciales y su acceso a la red. La propuesta del artículo es tratar el sandbox como **la unidad de delegación**: cada tarea corre en un entorno aislado y efímero, con red denegada por defecto y credenciales que nunca llegan al proceso del agente. Esta POC implementa esa idea con [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox): ejecuta una tarea de Claude Code asociada a un ticket y devuelve un informe auditable.

## Qué hace `tarea_agente.py`

1. Crea un sandbox con timeout, recursos explícitos y metadata de equipo y ticket.
2. Aplica una política de red que deniega todo salvo la API del modelo, el registro de npm y GitHub.
3. Guarda la clave del modelo y el token de Git en el **Credential Vault**. El token se vincula a la ruta de un único repositorio; dentro del sandbox solo hay valores de relleno.
4. Clona el repositorio, ejecuta Claude Code en modo no interactivo, corre `make test` y resume el diff.
5. Destruye el sandbox siempre, incluso si algo falla.

## Cómo ejecutarla

Requiere un servidor de OpenSandbox con el egress en modo `dns+nft`, necesario para el Credential Vault (ver la [guía oficial](https://github.com/opensandbox-group/OpenSandbox/blob/main/docs/guides/credential-vault.md)).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # pruebas con un sandbox simulado

export SANDBOX_DOMAIN=localhost:8080 ANTHROPIC_API_KEY=... GIT_USER=... GIT_TOKEN=...
python tarea_agente.py ENG-42 org/repo "Agregar pruebas para el módulo de facturación"
```

## Estado de verificación

Usa el SDK de Python de OpenSandbox 1.2.1. Las políticas y credenciales se construyen con los modelos del SDK, que validan sus campos. Tres pruebas verifican, con un sandbox simulado, que ningún secreto llega al entorno ni a los comandos, que el informe registra el resultado y que el sandbox se destruye ante una falla. **No se ejecutó contra un servidor real.**

## Riesgo residual

Los destinos permitidos siguen siendo canales posibles. Conviene que el token tenga solo los permisos de la tarea y que la entrega del resultado, como abrir un pull request, la haga el pipeline fuera del sandbox.

## Licencia

MIT. OpenSandbox se distribuye bajo Apache 2.0.
