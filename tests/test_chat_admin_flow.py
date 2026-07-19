from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import app.main as main


@pytest.fixture()
def client(tmp_path) -> Iterator[TestClient]:
    original_engine = main.engine
    test_engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    main.engine = test_engine
    main._sessions.clear()
    main._person_sessions.clear()
    SQLModel.metadata.create_all(test_engine)

    with TestClient(main.app) as test_client:
        yield test_client

    main.engine = original_engine
    main._sessions.clear()
    main._person_sessions.clear()


def test_login_creates_pending_access_request(client: TestClient) -> None:
    response = client.post("/login", data={"name": "Alice"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/waiting?request_id=1"

    status_response = client.get("/access-requests/1")
    assert status_response.json() == {
        "id": 1,
        "status": "Pending",
        "person_id": None,
    }


def test_admin_admit_creates_ulid_person_with_role(client: TestClient) -> None:
    login_response = client.post("/login", data={"name": "Alice"}, follow_redirects=False)
    request_id = login_response.headers["location"].split("=")[1]

    admit_response = client.post(
        "/admin/admit",
        data={"request_id": request_id, "role": "Guest", "persona": "guest"},
        follow_redirects=False,
    )

    assert admit_response.status_code == 303
    assert admit_response.headers["location"] == "/admin"

    request_status = client.get(f"/access-requests/{request_id}").json()
    person_id = request_status["person_id"]
    assert request_status["status"] == "Accepted"
    assert isinstance(person_id, str)
    assert len(person_id) == 26

    with Session(main.engine) as session:
        person = session.get(main.Person, person_id)
        assert person is not None
        assert person.name == "Alice"
        assert person.role == main.Role.guest
        assert person.persona == main.PersonaKey.guest


def test_admin_admit_corrects_a_persona_for_another_role(client: TestClient) -> None:
    login_response = client.post("/login", data={"name": "Alice"}, follow_redirects=False)
    request_id = login_response.headers["location"].split("=")[1]

    client.post(
        "/admin/admit",
        data={"request_id": request_id, "role": "Parent", "persona": "marta"},
    )

    person_id = client.get(f"/access-requests/{request_id}").json()["person_id"]
    with Session(main.engine) as session:
        person = session.get(main.Person, person_id)
        assert person is not None
        assert person.role == main.Role.parent
        assert person.persona == main.PersonaKey.julie


def test_admin_admission_form_filters_personas_by_role(client: TestClient) -> None:
    client.post("/login", data={"name": "Alice"}, follow_redirects=False)

    page = client.get("/admin").text

    assert 'Parent: ["chris", "julie"]' in page
    assert 'Child: ["spencer", "marta"]' in page
    assert 'Guest: ["guest"]' in page


def test_deleted_person_resets_chat(client: TestClient) -> None:
    login_response = client.post("/login", data={"name": "Alice"}, follow_redirects=False)
    request_id = login_response.headers["location"].split("=")[1]
    client.post("/admin/admit", data={"request_id": request_id, "role": "Parent"})
    person_id = client.get(f"/access-requests/{request_id}").json()["person_id"]

    assert "Hi, Alice" in client.get(f"/chat?person_id={person_id}").text

    delete_response = client.post(
        "/admin/people/delete",
        data={"person_id": person_id},
        follow_redirects=False,
    )

    assert delete_response.status_code == 303
    assert delete_response.headers["location"] == "/admin"
    assert "localStorage.removeItem" in client.get(f"/chat?person_id={person_id}").text

    with Session(main.engine) as session:
        assert session.get(main.Person, person_id) is None
        accepted_requests = session.exec(select(main.AccessRequest)).all()
        assert accepted_requests == []
