# Plano — Seed Script + Landing Page

## 1. Seed Script (`scripts/seed_customer.py`)

Script que cria o usuário inicial:

```python
# scripts/seed_customer.py
# Usage: uv run python scripts/seed_customer.py
# 
# Cria:
#   - customer@gmail.com / customer
#   - Organização "Customer Corp"
#   - Membership como owner
#   - Idempotente (pula se já existir)

import asyncio
import sys
sys.path.insert(0, "src")

from shared.infra.config import Settings
from shared.infra.database.session import create_engine
from shared.infra.database.session_manager import SessionManager
from modules.identity.service.dtos import CreateUserInput, CreateOrganizationInput, AddMemberInput
from modules.identity.application.providers import (
    get_create_user_use_case,
    get_create_organization_use_case,
    get_add_member_use_case,
)
from modules.identity.infra.repositories import SQLAlchemyUserRepository

async def seed():
    settings = Settings()
    engine = create_engine(settings)

    async with SessionManager(engine) as manager:
        # Check if user already exists
        user_repo = SQLAlchemyUserRepository(manager.session)
        existing = await user_repo.get_by_email("customer@gmail.com")
        if existing:
            print("User already exists, skipping")
            return

        # Create user
        uc = get_create_user_use_case(manager.session)
        user = await uc.execute(CreateUserInput(email="customer@gmail.com", password="customer"))
        print(f"User created: {user.id} / {user.email}")

        # Create organization
        org_uc = get_create_organization_use_case(manager.session)
        org = await org_uc.execute(CreateOrganizationInput(name="Customer Corp", slug="customer-corp"))
        print(f"Organization created: {org.id} / {org.name}")

        # Add member as owner
        member_uc = get_add_member_use_case(manager.session)
        member = await member_uc.execute(AddMemberInput(
            user_id=user.id,
            organization_id=org.id,
            role="owner",
        ))
        print(f"Member added: {member.id} (role: {member.role})")

    await engine.dispose()
    print("Seed complete!")

if __name__ == "__main__":
    asyncio.run(seed())
```

## 2. Landing Page (`web/src/app/page.tsx`)

Substituir o redirect atual por uma landing page pública com:

### Seções
| Seção | Conteúdo |
|-------|----------|
| **Hero** | Título: "Production Runtime for AI Agents" + subtítulo explicando o produto + CTA "Get Started" → /register |
| **Features** | Grid 3x2 com ícones: AI Models, RAG, Tools, Sessions, Usage Tracking, API Access |
| **How It Works** | 4 passos: Create Agent → Connect Knowledge → Add Tools → Deploy via API |
| **Why ProjectRAI** | Cards comparativos: "Instead of building infra from scratch, just call an API" |
| **CTA Final** | "Ready to build production-ready AI agents?" + botão |

### Design
- Tailwind CSS, responsivo
- Gradiente no hero, cards com sombra, ícones Lucide
- Navbar no topo com logo + Login + Register links
- Footer com links

### Estrutura de arquivos

```
web/src/app/
  page.tsx           → Landing page (pública)
  layout.tsx         → Root layout (sem alteração)
  
web/src/app/
  (auth)/
    login/page.tsx   → Login (inalterado)
    register/page.tsx → Register (inalterado)
    
web/src/app/
  (dashboard)/       → Dashboard layout (inalterado)
```

A landing page substitui o redirect atual. O login e register continuam nos mesmos endpoints. O dashboard permanece em `/dashboard`.

## 3. Atualizar rota raiz

- `/` → Landing page (pública, sem auth)
- `/login` → Login (inalterado)
- `/register` → Register (inalterado)
- `/dashboard` → Dashboard (requer auth, inalterado)

## Arquivos a modificar/criar

| Ação | Arquivo |
|------|---------|
| **Criar** | `scripts/seed_customer.py` |
| **Substituir** | `web/src/app/page.tsx` (landing page) |
| **Manter** | Todos os outros arquivos inalterados |
