import html
import socket
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select


from app.auth import get_current_user
from app.db import (
    AccessRequest,
    AccessStatus,
    Conversation,
    Person,
    PersonaKey,
    Role,
    engine,
    get_session as get_user_session,
    init_db as init_user_db,
)
from app.db.seed import seed as seed_household_defaults
from app.db.session import engine as household_engine
from app.db.session import init_db as init_household_db
from app.integrations.registry import run_action
from app.permissions.gate import check_permission, log_action
from app.routers import actions, household
from app.agents import run_turn
from app.personas import PERSONAS
from app.llm import DEFAULT_MODEL, history_to_display, run_chat
from app.schemas import (
    ChatMessage,
    ChatSession,
    ConversationResponse,
    CreateConversationRequest,
    CreateUserRequest,
    SendMessageRequest,
    SendMessageResponse,
    SessionResponse,
    StartSessionRequest,
    UpdateUserRequest,
    UserCreatedResponse,
    UserResponse,
)
from app.utils import utcnow

load_dotenv()

@asynccontextmanager
async def lifespan(_: FastAPI):
    SQLModel.metadata.create_all(engine)
    init_household_db()
    seed_household_defaults()
    init_user_db()
    yield


app = FastAPI(title="MultiAgent Family Task Organizer API", lifespan=lifespan)

_sessions: dict[UUID, ChatSession] = {}
_person_sessions: dict[str, UUID] = {}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def login_page() -> str:
    return _page(
        "Sign in",
        """
        <section class="card">
          <h1>Family Task Organizer</h1>
          <p>Enter your name to request access.</p>
          <form method="post" action="/login" class="stack">
            <label>Name <input name="name" required autofocus /></label>
            <button type="submit">Continue</button>
          </form>
        </section>
        <script>
          const personId = localStorage.getItem("person_id");
          if (personId) window.location.href = `/chat?person_id=${personId}`;
        </script>
        """,
    )


@app.post("/login", include_in_schema=False)
async def login(request: Request) -> RedirectResponse:
    form = await request.form()
    name = str(form.get("name", "")).strip()
    if not name:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    with Session(engine) as session:
        access_request = AccessRequest(name=name)
        session.add(access_request)
        session.commit()
        session.refresh(access_request)
        return RedirectResponse(
            url=f"/waiting?request_id={access_request.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.get("/waiting", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def waiting_page(request_id: int):
    access_request = _get_access_request(request_id)
    if access_request.person_id is not None:
        return RedirectResponse(
            url=f"/chat?person_id={access_request.person_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return _page(
        "Waiting for admission",
        f"""
        <section class="card">
          <h1>Hi, {_escape(access_request.name)}</h1>
          <p>Your access request is waiting for admin approval.</p>
          <p><a href="/waiting?request_id={access_request.id}">Refresh</a></p>
        </section>
        <script>
          async function checkAdmission() {{
            const response = await fetch("/access-requests/{access_request.id}");
            const data = await response.json();
            if (data.person_id) {{
              localStorage.setItem("person_id", data.person_id);
              window.location.href = `/chat?person_id=${{data.person_id}}`;
            }}
          }}
          setInterval(checkAdmission, 2000);
          checkAdmission();
        </script>
        """,
    )


@app.get("/access-requests/{request_id}", include_in_schema=False)
def access_request_status(request_id: int) -> dict[str, int | str | None]:
    access_request = _get_access_request(request_id)
    return {
        "id": access_request.id,
        "status": access_request.status.value,
        "person_id": access_request.person_id,
    }


@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
def chat_page(person_id: str) -> str:
    person = _find_person(person_id)
    if person is None:
        return _reset_chat_page()
    session = _get_or_create_person_session(person)
    return _chat_page(person, session)


@app.post("/chat/message", response_class=HTMLResponse, response_model=None, include_in_schema=False)
async def chat_message(request: Request):
    form = await request.form()
    person_id = str(form.get("person_id", ""))
    message = str(form.get("message", "")).strip()
    person = _find_person(person_id)
    if person is None:
        return _reset_chat_page()
    if not message:
        return RedirectResponse(url=f"/chat?person_id={person.id}", status_code=status.HTTP_303_SEE_OTHER)

    session = _get_or_create_person_session(person)
    proposed_action = await run_turn(
        _persona_key_for_person(person),
        message,
        [{"role": item.role, "content": item.content} for item in session.messages],
    )
    action_note = _execute_proposed_action(person, proposed_action.action, proposed_action.params)
    user_message = ChatMessage(role="user", content=message)
    assistant_message = ChatMessage(role="assistant", content=proposed_action.reply + action_note)
    session.messages.extend([user_message, assistant_message])
    return _chat_page(person, session)


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page() -> str:
    urls = _join_urls()
    url_items = "".join(f'<li><a href="{url}/">{url}/</a></li>' for url in urls)

    with Session(engine) as session:
        pending = session.exec(select(AccessRequest).where(AccessRequest.status == AccessStatus.pending)).all()
        people = session.exec(select(Person)).all()

    pending_rows = "".join(_pending_request_row(access_request) for access_request in pending) or "<p>No pending people.</p>"
    people_rows = "".join(_person_row(person) for person in people) or "<p>No admitted people yet.</p>"

    return _page(
        "Admin",
        f"""
        <section class="card">
          <p class="status"><span class="dot"></span>API online</p>
          <h1>Family Task Organizer Admin</h1>
          <h2>People waiting</h2>
          <div class="stack">{pending_rows}</div>
          <h2>Admitted people</h2>
          <div class="stack">{people_rows}</div>
          <h2>User login URLs</h2>
          <ul>{url_items}</ul>
          <p class="links"><a href="/docs">API docs</a> · <a href="/health">Health check</a></p>
        </section>
        """,
    )


@app.post("/admin/admit", include_in_schema=False)
async def admit_person(request: Request) -> RedirectResponse:
    form = await request.form()
    request_id = int(str(form.get("request_id", "0")))
    try:
        role = Role(str(form.get("role") or Role.child.value))
    except ValueError:
        role = Role.child

    with Session(engine) as session:
        access_request = session.get(AccessRequest, request_id)
        if access_request is not None and access_request.status == AccessStatus.pending:
            try:
                persona = PersonaKey(str(form.get("persona") or _default_persona_for_role(role).value))
            except ValueError:
                persona = _default_persona_for_role(role)
            person = Person(name=access_request.name, role=role, persona=persona)
            session.add(person)
            session.commit()
            session.refresh(person)

            access_request.person_id = person.id
            access_request.status = AccessStatus.accepted
            session.add(access_request)
            session.commit()

    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/people/delete", include_in_schema=False)
async def delete_person(request: Request) -> RedirectResponse:
    form = await request.form()
    person_id = str(form.get("person_id", ""))

    with Session(engine) as session:
        person = session.get(Person, person_id)
        if person is not None:
            access_requests = session.exec(select(AccessRequest).where(AccessRequest.person_id == person_id)).all()
            for access_request in access_requests:
                session.delete(access_request)
            session.delete(person)
            session.commit()

    session_id = _person_sessions.pop(person_id, None)
    if session_id is not None:
        _sessions.pop(session_id, None)

    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(request: CreateUserRequest, session: Session = Depends(get_user_session)) -> Person:
    role = Role(request.role) if request.role is not None else Role.guest
    persona = request.persona or _default_persona_for_role(role)
    person = Person(name=request.name, role=role, persona=persona, model=request.model)
    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already taken")
    session.refresh(person)
    return person


@app.get("/users", response_model=list[UserResponse])
def list_users(session: Session = Depends(get_user_session)) -> list[Person]:
    return list(session.exec(select(Person)).all())


@app.get("/users/me", response_model=UserResponse)
def get_me(person: Person = Depends(get_current_user)) -> Person:
    return person


@app.patch("/users/me", response_model=UserResponse)
def update_me(
    request: UpdateUserRequest,
    person: Person = Depends(get_current_user),
    session: Session = Depends(get_user_session),
) -> Person:
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(person, key, value)
    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already taken")
    session.refresh(person)
    return person


@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    request: CreateConversationRequest,
    person: Person = Depends(get_current_user),
    session: Session = Depends(get_user_session),
) -> ConversationResponse:
    conversation = Conversation(person_id=person.id, title=request.title)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return _to_conversation_response(conversation)


@app.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    person: Person = Depends(get_current_user),
    session: Session = Depends(get_user_session),
) -> list[ConversationResponse]:
    rows = session.exec(select(Conversation).where(Conversation.person_id == person.id)).all()
    return [_to_conversation_response(conversation) for conversation in rows]


@app.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessage])
def get_messages(
    conversation_id: int,
    person: Person = Depends(get_current_user),
    session: Session = Depends(get_user_session),
) -> list[ChatMessage]:
    conversation = _get_owned_conversation(conversation_id, person, session)
    return history_to_display(conversation.history_json)


@app.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_conversation_message(
    conversation_id: int,
    request: SendMessageRequest,
    person: Person = Depends(get_current_user),
    session: Session = Depends(get_user_session),
) -> SendMessageResponse:
    conversation = _get_owned_conversation(conversation_id, person, session)
    reply_text, updated_history = await run_chat(
        user_id=0,
        user_name=person.name,
        persona_prompt=PERSONAS[person.persona.value].system_prompt,
        model_name=person.model,
        message=request.message,
        history_json=conversation.history_json,
    )
    messages = history_to_display(updated_history)
    conversation.history_json = updated_history
    conversation.message_count = len(messages)
    conversation.updated_at = utcnow()
    session.add(conversation)
    session.commit()
    return SendMessageResponse(
        conversation_id=conversation_id,
        reply=ChatMessage(role="assistant", content=reply_text),
        messages=messages,
    )


@app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(request: StartSessionRequest) -> SessionResponse:
    session = ChatSession(
        id=uuid4(),
        model=request.model or DEFAULT_MODEL,
        system_prompt=request.system_prompt,
    )
    _sessions[session.id] = session
    return _to_session_response(session)


@app.get("/sessions/{session_id}", response_model=ChatSession)
def get_session(session_id: UUID) -> ChatSession:
    return _get_session(session_id)


@app.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: UUID, request: SendMessageRequest) -> SendMessageResponse:
    session = _get_session(session_id)
    proposed_action = await run_turn(
        "guest",
        request.message,
        [{"role": item.role, "content": item.content} for item in session.messages],
    )

    user_message = ChatMessage(role="user", content=request.message)
    assistant_message = ChatMessage(role="assistant", content=proposed_action.reply)

    session.messages.extend([user_message, assistant_message])
    return SendMessageResponse(
        session_id=session.id,
        reply=assistant_message,
        messages=session.messages,
    )


def _get_owned_conversation(conversation_id: int, person: Person, session: Session) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None or conversation.person_id != person.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _to_conversation_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=conversation.message_count,
    )


def _chat_page(person: Person, session: ChatSession) -> str:
    messages = "".join(
        f'<div class="message {message.role}"><strong>{_escape(message.role)}:</strong> {_escape(message.content)}</div>'
        for message in session.messages
    ) or "<p>No messages yet.</p>"
    return _page(
        "Chat",
        f"""
        <section class="card chat">
          <h1>Hi, {_escape(person.name)}</h1>
          <p>Role: {_escape(person.role.value)} · Persona: {_escape(person.persona.value)}</p>
          <div class="messages">{messages}</div>
          <form method="post" action="/chat/message" class="stack">
            <input type="hidden" name="person_id" value="{person.id}" />
            <label>Message <textarea name="message" rows="3" required autofocus></textarea></label>
            <button type="submit">Send</button>
          </form>
        </section>
        <script>localStorage.setItem("person_id", "{person.id}");</script>
        """,
    )


def _execute_proposed_action(person: Person, action_type: str, params: dict) -> str:
    if action_type == "none":
        return ""

    permission_scope = _permission_scope_for_role(person.role)
    with Session(household_engine) as session:
        decision = check_permission(permission_scope, action_type, session)
        result = run_action(action_type, params) if decision == "allow" else None
        log_action(session, person.id, action_type, params, decision)

    if decision == "allow":
        return f"\n\nAction executed: {action_type} → {result}"
    return f"\n\nAction {decision}: {action_type}"


def _permission_scope_for_role(role: Role) -> str:
    if role == Role.parent:
        return "parent"
    if role == Role.child:
        return "kid"
    return "guest"


def _default_persona_for_role(role: Role) -> PersonaKey:
    if role == Role.parent:
        return PersonaKey.julie
    if role == Role.child:
        return PersonaKey.spencer
    return PersonaKey.guest


def _persona_key_for_person(person: Person) -> str:
    return person.persona.value


def _get_or_create_person_session(person: Person) -> ChatSession:
    session_id = _person_sessions.get(person.id)
    if session_id is not None and session_id in _sessions:
        return _sessions[session_id]

    chat_session = ChatSession(
        id=uuid4(),
        model=DEFAULT_MODEL,
        system_prompt=f"You are helping {person.name}, whose household role is {person.role.value}.",
    )
    _sessions[chat_session.id] = chat_session
    _person_sessions[person.id] = chat_session.id
    return chat_session


def _person_row(person: Person) -> str:
    return f"""
    <form method="post" action="/admin/people/delete" class="person-row">
      <input type="hidden" name="person_id" value="{person.id}" />
      <span><strong>{_escape(person.name)}</strong><br /><small>{_escape(person.id)}</small></span>
      <span>{_escape(person.role.value)} · {_escape(person.persona.value)}</span>
      <button type="submit" class="danger">Delete</button>
    </form>
    """


def _pending_request_row(access_request: AccessRequest) -> str:
    role_options = "".join(f'<option value="{role.value}">{role.value}</option>' for role in Role)
    persona_options = "".join(f'<option value="{persona.value}">{persona.value}</option>' for persona in PersonaKey)
    return f"""
    <form method="post" action="/admin/admit" class="person-row">
      <input type="hidden" name="request_id" value="{access_request.id}" />
      <strong>{_escape(access_request.name)}</strong>
      <select name="role">{role_options}</select>
      <select name="persona">{persona_options}</select>
      <button type="submit">Admit</button>
    </form>
    """


def _find_person(person_id: str) -> Person | None:
    with Session(engine) as session:
        return session.get(Person, person_id)


def _get_access_request(request_id: int) -> AccessRequest:
    with Session(engine) as session:
        access_request = session.get(AccessRequest, request_id)
        if access_request is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
        return access_request


def _reset_chat_page() -> str:
    return _page(
        "Chat reset",
        """
        <section class="card">
          <h1>Chat reset</h1>
          <p>Your user was removed by the admin. Please enter your name again to request access.</p>
          <p><a href="/">Return to login</a></p>
        </section>
        <script>localStorage.removeItem("person_id");</script>
        """,
    )



def _join_urls() -> list[str]:
    urls = ["http://localhost:8000"]
    hostname = socket.gethostname().removesuffix(".local")
    if hostname:
        urls.append(f"http://{hostname}.local:8000")

    ips: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ips.add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass

    urls.extend(f"http://{ip}:8000" for ip in sorted(ips))
    return list(dict.fromkeys(urls))


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <title>{_escape(title)} - Family Task Organizer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {{ color-scheme: light dark; }}
          body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            line-height: 1.5;
            background: #f6f7f9;
            color: #18202a;
          }}
          main {{ max-width: 48rem; margin: 0 auto; padding: 2rem; }}
          .card {{
            background: white;
            border: 1px solid #dde2e8;
            border-radius: 1rem;
            box-shadow: 0 1rem 2.5rem rgb(15 23 42 / 8%);
            padding: 1.5rem;
          }}
          .stack {{ display: grid; gap: 0.75rem; }}
          label {{ display: grid; gap: 0.35rem; font-weight: 700; }}
          input, textarea, select, button {{ font: inherit; border-radius: 0.5rem; padding: 0.65rem; }}
          input, textarea, select {{ border: 1px solid #cbd5e1; }}
          button {{ border: 0; background: #2563eb; color: white; font-weight: 700; cursor: pointer; }}
          button.danger {{ background: #dc2626; }}
          h1 {{ margin-top: 0; }}
          .status {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            border-radius: 999px;
            background: #e8f7ee;
            color: #166534;
            font-weight: 700;
            padding: 0.35rem 0.75rem;
          }}
          .dot {{ width: 0.6rem; height: 0.6rem; border-radius: 50%; background: currentColor; }}
          .links {{ margin-top: 1.5rem; }}
          .person-row {{ display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 0.5rem; align-items: center; }}
          .messages {{ display: grid; gap: 0.5rem; margin: 1rem 0; }}
          .message {{ border-radius: 0.75rem; padding: 0.75rem; background: #f1f5f9; }}
          .message.assistant {{ background: #e0f2fe; }}
          a {{ color: #2563eb; }}
          @media (prefers-color-scheme: dark) {{
            body {{ background: #0f172a; color: #e5e7eb; }}
            .card {{ background: #111827; border-color: #263244; }}
            input, textarea, select {{ background: #0f172a; border-color: #334155; color: #e5e7eb; }}
            .status {{ background: #052e16; color: #86efac; }}
            .message {{ background: #1e293b; }}
            .message.assistant {{ background: #172554; }}
            a {{ color: #93c5fd; }}
          }}
        </style>
      </head>
      <body><main>{body}</main></body>
    </html>
    """


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _get_session(session_id: UUID) -> ChatSession:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _to_session_response(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        model=session.model,
        system_prompt=session.system_prompt,
        created_at=session.created_at,
        message_count=len(session.messages),
    )


app.include_router(household.router)
app.include_router(actions.router)