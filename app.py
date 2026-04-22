"""
Servidor de Área de Membros utilizando aiohttp e Jinja2.

Este módulo implementa uma aplicação web assíncrona que fornece uma área de
membros completa. Os administradores podem fazer login, criar e editar
cursos, adicionar módulos com conteúdo, imagens e vídeos do YouTube,
atualizar o logo do site e servir arquivos estáticos. A autenticação é
implementada com um mecanismo de sessão simples baseado em cookies.
"""

import os
import sqlite3
import jinja2
import aiohttp
from aiohttp import web
import urllib.parse
import hashlib
import secrets
from argon2 import PasswordHasher

# Caminhos de diretório
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOADS_DIR = os.path.join(STATIC_DIR, 'uploads')
LOGO_PATH = os.path.join(STATIC_DIR, 'logo.png')
DATABASE = os.path.join(BASE_DIR, 'membership.db')

# Sessões armazenadas em memória: mapeamento de session_id -> user_id
SESSIONS = {}

# Instâncias auxiliares
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES_DIR))
ph = PasswordHasher()


def render_template(template_name, **context):
    """Renderiza um template Jinja2 e retorna HTML como string."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)


def get_db_connection():
    """
    Cria uma conexão com o banco de dados SQLite.

    Retorna:
        sqlite3.Connection: conexão configurada com row_factory.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Inicializa o banco de dados, criando as tabelas necessárias se não existirem.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Usuários: id, username, password
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )
    # Cursos: id, título, descrição, imagem de capa
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            cover_image TEXT
        )
        """
    )
    # Módulos: id, course_id, título, conteúdo, URL do YouTube, imagem
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            youtube_url TEXT,
            image_path TEXT,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def create_admin_user():
    """
    Cria um usuário administrador padrão se não houver usuários no banco.

    O usuário padrão é:
        username: admin
        password: myaccess123 (hash Argon2)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    if count == 0:
        hashed_password = ph.hash('myaccess123')
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ('admin', hashed_password)
        )
        conn.commit()
    conn.close()


def allowed_file(filename):
    """
    Verifica se o arquivo possui extensão permitida.

    Args:
        filename (str): nome do arquivo enviado.

    Retorna:
        bool: True se a extensão for permitida, False caso contrário.
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


def secure_filename(filename):
    """
    Sanitiza o nome do arquivo, removendo diretórios e caracteres perigosos.

    Args:
        filename (str): nome original do arquivo.

    Retorna:
        str: nome seguro para armazenamento.
    """
    keepcharacters = ('.', '_', '-')
    filename = os.path.basename(filename)
    return ''.join(c for c in filename if c.isalnum() or c in keepcharacters).rstrip()


def youtube_embed_id(url):
    """
    Extrai o ID de um vídeo do YouTube a partir de uma URL.

    Retorna None se não for possível extrair o ID.
    """
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname in {'www.youtube.com', 'youtube.com'}:
        query = urllib.parse.parse_qs(parsed.query)
        return query.get('v', [None])[0]
    if parsed.hostname == 'youtu.be':
        return parsed.path.lstrip('/')
    return None


async def get_current_user(request):
    """
    Recupera o ID do usuário logado a partir do cookie de sessão.
    """
    session_id = request.cookies.get('SESSION_ID')
    if session_id and session_id in SESSIONS:
        return SESSIONS[session_id]
    return None


def create_app() -> web.Application:
    """
    Cria e configura a aplicação aiohttp.

    Retorna:
        aiohttp.web.Application: aplicação configurada com rotas e handlers.
    """
    # Assegurar diretórios
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Criar logo padrão se não existir
    if not os.path.exists(LOGO_PATH):
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (300, 100), color=(200, 200, 200))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        d.text((10, 40), "Your Logo", fill=(0, 0, 0), font=font)
        img.save(LOGO_PATH)

    # Inicializar DB e admin
    init_db()
    create_admin_user()

    app = web.Application()

    # Registrar rotas estáticas (static e uploads)
    app.router.add_static('/static/', STATIC_DIR, name='static')

    # Adicionar filtros Jinja2 ao ambiente
    jinja_env.filters['youtube_embed'] = youtube_embed_id

    # Define rotas
    app.add_routes([
        web.get('/', index),
        web.get('/login', login_get),
        web.post('/login', login_post),
        web.get('/logout', logout),
        web.get('/dashboard', dashboard),
        web.get('/courses/create', course_create_get),
        web.post('/courses/create', course_create_post),
        web.get('/courses/edit/{course_id}', course_edit_get),
        web.post('/courses/edit/{course_id}', course_edit_post),
        web.get('/courses/{course_id}', view_course),
        web.get('/modules/create/{course_id}', module_create_get),
        web.post('/modules/create/{course_id}', module_create_post),
        web.get('/modules/edit/{module_id}', module_edit_get),
        web.post('/modules/edit/{module_id}', module_edit_post),
        web.get('/logo', logo_get),
        web.post('/logo', logo_post),
    ])

    return app


async def index(request: web.Request) -> web.Response:
    """
    Redireciona para dashboard se logado, senão para tela de login.
    """
    user_id = await get_current_user(request)
    if user_id:
        raise web.HTTPFound('/dashboard')
    raise web.HTTPFound('/login')


async def login_get(request: web.Request) -> web.Response:
    """Exibe a página de login."""
    # Passar contexto com sessão vazia
    html = render_template('login.html', error=None, session={})
    return web.Response(text=html, content_type='text/html')


async def login_post(request: web.Request) -> web.Response:
    """Processa o formulário de login."""
    data = await request.post()
    username = data.get('username')
    password = data.get('password')
    error = None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    conn.close()
    if user:
        try:
            ph.verify(user['password'], password)
            # Logar usuário: gerar session_id e gravar cookie
            session_id = secrets.token_hex(16)
            SESSIONS[session_id] = user['id']
            response = web.HTTPFound('/dashboard')
            response.set_cookie('SESSION_ID', session_id, httponly=True, max_age=3600 * 24)
            return response
        except Exception:
            error = 'Usuário ou senha incorretos.'
    else:
        error = 'Usuário ou senha incorretos.'
    # Renderizar login com mensagem de erro
    html = render_template('login.html', error=error, session={})
    return web.Response(text=html, content_type='text/html')


async def logout(request: web.Request) -> web.Response:
    """Realiza logout removendo o session_id do dicionário e cookie."""
    session_id = request.cookies.get('SESSION_ID')
    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]
    response = web.HTTPFound('/login')
    response.del_cookie('SESSION_ID')
    return response


async def ensure_logged(request: web.Request) -> int:
    """
    Garante que o usuário esteja autenticado.

    Retorna o ID do usuário ou redireciona para login se não autenticado.
    """
    user_id = await get_current_user(request)
    if not user_id:
        raise web.HTTPFound('/login')
    return user_id


async def dashboard(request: web.Request) -> web.Response:
    """Mostra a lista de cursos."""
    await ensure_logged(request)
    conn = get_db_connection()
    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    html = render_template('dashboard.html', courses=courses, session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def course_create_get(request: web.Request) -> web.Response:
    """Exibe o formulário para criar um curso."""
    await ensure_logged(request)
    html = render_template('course_edit.html', course=None, session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def course_create_post(request: web.Request) -> web.Response:
    """Processa a criação de um novo curso."""
    await ensure_logged(request)
    data = await request.post()
    title = data.get('title')
    description = data.get('description')
    file_field = data.get('cover_image')
    image_path = None
    if isinstance(file_field, aiohttp.web.FileField) and file_field.filename:
        if allowed_file(file_field.filename):
            filename = secure_filename(file_field.filename)
            save_path = os.path.join(UPLOADS_DIR, filename)
            # Gravar arquivo
            with open(save_path, 'wb') as f:
                f.write(file_field.file.read())
            image_path = os.path.join('uploads', filename)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO courses (title, description, cover_image) VALUES (?, ?, ?)",
        (title, description, image_path)
    )
    conn.commit()
    conn.close()
    raise web.HTTPFound('/dashboard')


async def course_edit_get(request: web.Request) -> web.Response:
    """Exibe o formulário para editar um curso existente."""
    await ensure_logged(request)
    course_id = int(request.match_info['course_id'])
    conn = get_db_connection()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    if not course:
        raise web.HTTPNotFound()
    html = render_template('course_edit.html', course=course, session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def course_edit_post(request: web.Request) -> web.Response:
    """Processa a edição de um curso."""
    await ensure_logged(request)
    course_id = int(request.match_info['course_id'])
    data = await request.post()
    title = data.get('title')
    description = data.get('description')
    file_field = data.get('cover_image')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT cover_image FROM courses WHERE id = ?", (course_id,))
    course = cur.fetchone()
    current_image = course['cover_image'] if course else None
    image_path = current_image
    if isinstance(file_field, aiohttp.web.FileField) and file_field.filename:
        if allowed_file(file_field.filename):
            filename = secure_filename(file_field.filename)
            save_path = os.path.join(UPLOADS_DIR, filename)
            with open(save_path, 'wb') as f:
                f.write(file_field.file.read())
            image_path = os.path.join('uploads', filename)
    cur.execute(
        "UPDATE courses SET title = ?, description = ?, cover_image = ? WHERE id = ?",
        (title, description, image_path, course_id)
    )
    conn.commit()
    conn.close()
    raise web.HTTPFound('/dashboard')


async def view_course(request: web.Request) -> web.Response:
    """Mostra os módulos de um curso."""
    await ensure_logged(request)
    course_id = int(request.match_info['course_id'])
    conn = get_db_connection()
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    modules = conn.execute(
        "SELECT * FROM modules WHERE course_id = ?",
        (course_id,)
    ).fetchall()
    conn.close()
    if not course:
        raise web.HTTPNotFound()
    html = render_template('modules.html', course=course, modules=modules, session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def module_create_get(request: web.Request) -> web.Response:
    """Exibe o formulário para criar um módulo."""
    await ensure_logged(request)
    course_id = int(request.match_info['course_id'])
    html = render_template('module_edit.html', module=None, course_id=course_id, session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def module_create_post(request: web.Request) -> web.Response:
    """Processa a criação de um módulo."""
    await ensure_logged(request)
    course_id = int(request.match_info['course_id'])
    data = await request.post()
    title = data.get('title')
    content = data.get('content')
    youtube_url = data.get('youtube_url')
    file_field = data.get('image')
    image_path = None
    if isinstance(file_field, aiohttp.web.FileField) and file_field.filename:
        if allowed_file(file_field.filename):
            filename = secure_filename(file_field.filename)
            save_path = os.path.join(UPLOADS_DIR, filename)
            with open(save_path, 'wb') as f:
                f.write(file_field.file.read())
            image_path = os.path.join('uploads', filename)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO modules (course_id, title, content, youtube_url, image_path) VALUES (?, ?, ?, ?, ?)",
        (course_id, title, content, youtube_url, image_path)
    )
    conn.commit()
    conn.close()
    raise web.HTTPFound(f'/courses/{course_id}')


async def module_edit_get(request: web.Request) -> web.Response:
    """Exibe o formulário para editar um módulo."""
    await ensure_logged(request)
    module_id = int(request.match_info['module_id'])
    conn = get_db_connection()
    module = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
    conn.close()
    if not module:
        raise web.HTTPNotFound()
    html = render_template('module_edit.html', module=module, course_id=module['course_id'], session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def module_edit_post(request: web.Request) -> web.Response:
    """Processa a edição de um módulo."""
    await ensure_logged(request)
    module_id = int(request.match_info['module_id'])
    data = await request.post()
    title = data.get('title')
    content = data.get('content')
    youtube_url = data.get('youtube_url')
    file_field = data.get('image')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT image_path, course_id FROM modules WHERE id = ?", (module_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise web.HTTPNotFound()
    current_image = row['image_path']
    course_id = row['course_id']
    image_path = current_image
    if isinstance(file_field, aiohttp.web.FileField) and file_field.filename:
        if allowed_file(file_field.filename):
            filename = secure_filename(file_field.filename)
            save_path = os.path.join(UPLOADS_DIR, filename)
            with open(save_path, 'wb') as f:
                f.write(file_field.file.read())
            image_path = os.path.join('uploads', filename)
    cur.execute(
        "UPDATE modules SET title = ?, content = ?, youtube_url = ?, image_path = ? WHERE id = ?",
        (title, content, youtube_url, image_path, module_id)
    )
    conn.commit()
    conn.close()
    raise web.HTTPFound(f'/courses/{course_id}')


async def logo_get(request: web.Request) -> web.Response:
    """Exibe a página para atualizar o logo."""
    await ensure_logged(request)
    html = render_template('update_logo.html', logo='/static/logo.png', session={'user_id': True})
    return web.Response(text=html, content_type='text/html')


async def logo_post(request: web.Request) -> web.Response:
    """Processa o envio de um novo logo."""
    await ensure_logged(request)
    data = await request.post()
    file_field = data.get('logo')
    if isinstance(file_field, aiohttp.web.FileField) and file_field.filename:
        if allowed_file(file_field.filename):
            # Salvar logo diretamente no caminho do logo padrão
            with open(LOGO_PATH, 'wb') as f:
                f.write(file_field.file.read())
    raise web.HTTPFound('/dashboard')


def main():
    app = create_app()
    import os
    port = int(os.environ.get("PORT", 5000))
    web.run_app(app, host='0.0.0.0', port=port)


if __name__ == '__main__':
    main()
