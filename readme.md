# API de Autenticação — FastAPI, MySQL, JWT, bcrypt, SMTP e Cloudflare Tunnel

API desenvolvida no âmbito da PAP e integrada no projeto da startup Solvex.  
Fornece funcionalidades essenciais de autenticação, gestão de utilizadores e recuperação de password, garantindo segurança, escalabilidade e compatibilidade com aplicações móveis e web.

---

## Tecnologias Utilizadas

- FastAPI — Framework moderna e de alto desempenho para APIs em Python  
- MySQL — Base de dados relacional  
- bcrypt — Hashing seguro de passwords  
- JWT (JSON Web Tokens) — Autenticação baseada em tokens  
- SMTP — Envio de emails de recuperação  
- Cloudflare Tunnel — Acesso externo seguro sem abrir portas no router  
- Pydantic — Validação de dados  
- Python 3.12+

---

## Funcionalidades Principais

- Registo de utilizadores  
- Login com validação de credenciais  
- Geração de tokens JWT  
- Recuperação de password via email  
- Redefinição de password com token temporário  
- Hashing seguro com bcrypt  
- Acesso externo através de Cloudflare Tunnel  
- Estrutura modular e escalável

---

## Estrutura do Projeto

```
📦 api-auth
 ┣ 📂 routers
 ┃ ┗ 📜 auth_routes.py
 ┣ 📂 utils
 ┃ ┣ 📜 jwt_handler.py
 ┃ ┣ 📜 email_recover.py
 ┃ ┗ 📜 database.py
 ┣ 📜 main.py
 ┣ 📜 requirements.txt
 ┣ 📜 .env
 ┗ 📜 README.md
```

---

## Endpoints Principais

### POST /register
Registo de novos utilizadores.

### POST /login
Autenticação e geração de token JWT.

### POST /recover-password
Envio de email com token temporário.

### POST /reset-password
Redefinição de password com token válido.

---

## Instalação e Execução

### 1. Clonar o repositório
```bash
git clone https://github.com/teu-username/api-auth.git
cd api-auth
```

### 2. Criar ambiente virtual
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis no .env
```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=******
DB_NAME=api_auth
SECRET_KEY=******
SMTP_EMAIL=******
SMTP_PASSWORD=******
```

### 5. Iniciar a API
```bash
uvicorn main:app --reload
```

---

## Acesso Externo (Cloudflare Tunnel)

Para expor a API sem abrir portas no router:

```bash
cloudflared tunnel --url http://localhost:8000
```

---

## Licença

Projeto desenvolvido para fins académicos (PAP) e integração na startup Solvex.

---

## Autor

Gabriel Rocha (C) craqu3  
Desenvolvedor Backend • PAP 2025/2026
