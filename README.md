# Área de Membros – Guia de Uso

Esta aplicação fornece uma área de membros completa onde você pode gerenciar cursos e módulos. A interface permite criar e editar cursos, adicionar módulos com conteúdo escrito, vídeos do YouTube e imagens, além de atualizar o logo do site. Tudo é responsivo, funcionando bem tanto em computadores quanto em dispositivos móveis.

## Funcionalidades principais

- **Autenticação**: login com usuário e senha. Um usuário administrador é criado automaticamente na primeira execução com as credenciais:
  - Usuário: `admin`
  - Senha: `myaccess123`
- **Gerenciamento de Cursos**: crie, edite e visualize cursos. É possível adicionar uma descrição e uma imagem de capa para cada curso.
- **Gerenciamento de Módulos**: para cada curso, adicione quantos módulos desejar. Cada módulo pode conter:
  - Título
  - Conteúdo em texto (copy)
  - Link de vídeo do YouTube (o site extrai automaticamente o ID do vídeo para embed)
  - Imagem (upload de arquivo)
- **Personalização do Logo**: envie uma nova imagem para substituir o logo existente. O logo é exibido no topo da página.
- **Responsividade**: as páginas utilizam Bootstrap 5 para garantir boa visualização em dispositivos móveis e desktops.

## Requisitos

- Python 3.9 ou superior
- Pacotes Python listados em `requirements.txt` (instalados via `pip`). Estes incluem `aiohttp` (servidor web assíncrono), `jinja2` (templates), `argon2-cffi` (hash de senhas) e `Pillow` (para gerar um logo padrão).

## Instalação e execução local

1. Navegue até a pasta do projeto:

   ```bash
   cd membership_app
   ```

2. (Opcional) Crie e ative um ambiente virtual:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate    # Windows
   ```

3. Instale as dependências necessárias (use `pip` ou `pip3`):

   ```bash
   pip install -r requirements.txt
   ```

4. Execute a aplicação:

   ```bash
   python app.py
   ```

5. Acesse `http://localhost:5000` no navegador. Faça login com o usuário e senha padrão indicados acima. Depois de logado, você poderá criar cursos, adicionar módulos, enviar imagens e alterar o logo.

## Estrutura de arquivos

```
membership_app/
├── app.py              # Código principal da aplicação Flask
├── membership.db       # Banco de dados SQLite (criado automaticamente)
├── static/
│   ├── logo.png        # Logo do site (pode ser substituída via interface)
│   ├── css/
│   │   └── style.css   # Estilos personalizados e ajustes de responsividade
│   └── uploads/        # Diretório para imagens enviadas (capas e módulos)
└── templates/
    ├── layout.html     # Layout base com navbar e estrutura da página
    ├── login.html      # Tela de login
    ├── dashboard.html  # Painel de listagem de cursos
    ├── course_edit.html # Formulário de criação/edição de cursos
    ├── modules.html    # Listagem dos módulos de um curso
    ├── module_edit.html # Formulário de criação/edição de módulos
    └── update_logo.html # Tela para atualização do logo
```

## Personalização

Se desejar personalizar ainda mais a área de membros, você pode editar os arquivos de template em `templates/` ou adicionar estilos adicionais em `static/css/style.css`. Os templates utilizam a linguagem de marcação do Jinja2, permitindo incluir lógica simples como condicionais e loops.

## Observações de Segurança

- A senha padrão (`myaccess123`) deve ser alterada assim que possível em um ambiente de produção. Para alterar a senha, modifique o banco de dados ou implemente uma função de alteração de senha.
- O `SECRET_KEY` no `app.py` é fixo para fins de demonstração. Em produção, troque por uma string aleatória secreta para proteger sessões e cookies.
- Este exemplo utiliza o SQLite para simplificar a configuração. Em ambientes de produção, considere utilizar um banco de dados mais robusto (PostgreSQL, MySQL etc.) e implemente controle de acesso adequado caso existam múltiplos usuários.